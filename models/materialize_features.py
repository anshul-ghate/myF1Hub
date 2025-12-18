"""
Feature Materialization Script

This script computes features from the raw data/models and saves them to 
Parquet files for the Feast Offline Store to consume.
"""

import pandas as pd
import os
from datetime import datetime
from models.dynasty_engine import DynastyEngine
from utils.logger import get_logger

logger = get_logger("FeatureMaterialization")

DATA_DIR = "data"
PARQUET_PATH = os.path.join(DATA_DIR, "driver_stats.parquet")

def materialize_driver_stats():
    """
    Load Dynasty Engine state, extract driver ratings and stats,
    and save to Parquet with appropriate timestamps.
    """
    try:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            
        logger.info("Initializing Dynasty Engine...")
        engine = DynastyEngine()
        
        # If engine not trained, cannot materialize
        if engine.tracker is None:
            logger.warning("Dynasty Engine not trained. Cannot materialize features.")
            return

        logger.info("Extracting driver stats...")
        driver_ratings = engine.tracker.driver_ratings
        
        # Create DataFrame
        # Feast requires: entity_key, feature_values, event_timestamp, created_timestamp
        
        rows = []
        now = datetime.now()
        
        for driver, elo in driver_ratings.items():
            # In a real scenario, we'd pull more stats (consistency, etc) from engine.train_df
            # For now, simplistic extraction
            rows.append({
                "driver_id": driver,
                "driver_elo": float(elo),
                "driver_consistency": 3.0, # Placeholder or fetch from engine df
                "driver_aggression": 5.0, # Placeholder
                "races_finished_ratio": 0.9, # Placeholder
                "event_timestamp": now,
                "created_timestamp": now
            })
            
        if not rows:
            logger.warning("No driver ratings found.")
            return

        df = pd.DataFrame(rows)
        
        # Save to Parquet
        df.to_parquet(PARQUET_PATH, index=False)
        logger.info(f"Materialized {len(df)} driver records to {PARQUET_PATH}")
        
    except Exception as e:
        logger.error(f"Failed to materialize features: {e}")
        raise

if __name__ == "__main__":
    materialize_driver_stats()
