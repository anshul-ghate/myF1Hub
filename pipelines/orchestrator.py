"""
F1 PitWall AI - Data & Training Pipeline Orchestrator

This module orchestrates the end-to-end flow:
1. Check for new race data (Real World vs Database).
2. Ingest new data (Ingestion Layer).
3. Materialize features (Feature Store).
4. Retrain models (Model Registry).
"""

import sys
import os
import traceback
from datetime import datetime

# Adjust path to include project root
sys.path.append(os.getcwd())

from data.ingest_data_enhanced import ingest_enhanced_race_data, ingest_qualifying_results
from models.hybrid_predictor import HybridPredictor
from models.materialize_features import materialize_driver_stats
from utils.db import get_supabase_client
from utils.logger import get_logger
from utils.api_config import configure_fastf1_retries
from utils.race_utils import get_latest_completed_session

logger = get_logger("PipelineOrchestrator")
configure_fastf1_retries()
supabase = get_supabase_client()

def run_pipeline():
    logger.info("🚀 Starting Pipeline Execution...")
    
    try:
        # --- STEP 1: CHECK FOR UPDATES ---
        logger.info("[Step 1/4] Checking for new sessions...")
        latest_session = get_latest_completed_session()
        
        if not latest_session:
            logger.info("No completed sessions found.")
            return

        year = latest_session['Year']
        round_num = latest_session['Round']
        session_type = latest_session['SessionType']
        event_name = latest_session['EventName']
        
        logger.info(f"Latest Real-World Session: {year} R{round_num} ({event_name}) - {latest_session['Session']}")
        
        # Check DB State
        race_res = supabase.table('races').select('*').eq('season_year', year).eq('round', round_num).execute()
        race_data = race_res.data[0] if race_res.data else None
        race_id = race_data['id'] if race_data else None
        
        action = 'NONE'
        
        if session_type == 'R':
            if race_data and race_data.get('ingestion_status') == 'COMPLETE':
                logger.info("Race already fully ingested.")
            else:
                logger.info("Race completed but not ingested. Triggering RACE action.")
                action = 'RACE'
        elif session_type == 'Q':
            # Check for grid sufficiency
            grid_count = 0
            if race_id:
                res = supabase.table('race_results').select('driver_id', count='exact').eq('race_id', race_id).execute()
                grid_count = res.count if res.count is not None else len(res.data)
            
            if grid_count > 10:
                logger.info(f"Qualifying likely ingested ({grid_count} entries).")
            else:
                logger.info("Qualifying completed but grid data missing. Triggering QUALI action.")
                action = 'QUALI'
        
        if action == 'NONE':
            logger.info("System up to date. Exiting.")
            return

        # --- STEP 2: INGESTION ---
        logger.info("[Step 2/4] Running Ingestion...")
        if action == 'RACE':
            ingest_enhanced_race_data(year, round_num)
        elif action == 'QUALI':
            ingest_qualifying_results(year, round_num)
            
        logger.info("Ingestion complete.")

        # --- STEP 3: FEATURE MATERIALIZATION ---
        if action == 'RACE':
            logger.info("[Step 3/4] Materializing Features...")
            materialize_driver_stats()
            # If we had more feature views, we'd materialize them here
            logger.info("Features materialized to Offline Store.")
        else:
             logger.info("[Step 3/4] Skipping Feature Materialization (only Quali update).")

        # --- STEP 4: MODEL RETRAINING ---
        if action == 'RACE':
            logger.info("[Step 4/4] Retraining Models...")
            predictor = HybridPredictor()
            success = predictor.train()
            if success:
                logger.info("Models retrained and registered successfully.")
            else:
                logger.error("Model training failed.")
        else:
             logger.info("[Step 4/4] Skipping Model Retraining (only Quali update).")

        logger.info("✅ Pipeline Execution Complete via Orchestrator.")

    except Exception as e:
        logger.error(f"Pipeline Failed: {e}")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    run_pipeline()
