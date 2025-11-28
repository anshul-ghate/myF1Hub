import os
import sys
import logging
from datetime import datetime
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import get_supabase_client
from utils.populate_schedule import populate_schedule
from data.ingest_bulk import ingest_bulk_history
from models.train_lap_model import train_model

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_pipeline():
    logger.info("🚀 Starting F1 ML Pipeline...")
    
    supabase = get_supabase_client()
    current_year = datetime.now().year
    
    # 1. Update Schedule
    logger.info(f"📅 Updating Schedule for {current_year}...")
    try:
        populate_schedule(current_year)
        logger.info("✅ Schedule updated.")
    except Exception as e:
        logger.error(f"❌ Failed to update schedule: {e}")
        return

    # 2. Check for New Data to Ingest
    logger.info("🔍 Checking for completed races needing ingestion...")
    
    # Get all completed races from DB that are NOT ingested
    # We define "completed" as date < now
    now = datetime.now().isoformat()
    
    # Fetch races that are in the past but ingestion_complete is False
    res = supabase.table('races')\
        .select('*')\
        .lt('date', now)\
        .eq('ingestion_complete', False)\
        .execute()
        
    races_to_ingest = res.data
    
    if races_to_ingest:
        logger.info(f"📥 Found {len(races_to_ingest)} races to ingest: {[r['name'] for r in races_to_ingest]}")
        
        # Run Bulk Ingestion (it handles logic to skip already ingested, but we explicitly found ones that need it)
        # ingest_bulk_history checks for 'completed_races' locally via FastF1, 
        # so calling it for the current year should trigger ingestion for any missing ones.
        try:
            ingest_bulk_history(start_year=current_year, end_year=current_year)
            logger.info("✅ Data ingestion complete.")
            
            # Trigger Retraining since we have new data
            should_retrain = True
        except Exception as e:
            logger.error(f"❌ Ingestion failed: {e}")
            should_retrain = False
    else:
        logger.info("✅ No new races to ingest.")
        should_retrain = False

    # 3. Model Retraining
    # We can also force retrain if a flag is passed, but for now rely on new data
    if should_retrain:
        logger.info("🧠 New data detected. Starting Model Retraining...")
        try:
            # Fetch all race IDs for training
            res = supabase.table('races').select('id').eq('ingestion_complete', True).execute()
            rids = [r['id'] for r in res.data]
            
            if rids:
                train_model(rids)
                logger.info("✅ Model retrained and saved.")
            else:
                logger.warning("⚠️ No ingested races found for training.")
        except Exception as e:
            logger.error(f"❌ Model training failed: {e}")
    else:
        logger.info("⏩ Skipping model training (no new data).")

    logger.info("🏁 Pipeline Finished.")

if __name__ == "__main__":
    run_pipeline()
