import fastf1
import datetime
import pandas as pd
from data.ingest_data_enhanced import ingest_enhanced_race_data, ingest_qualifying_results
from models.train_model import train_model
from utils.db import get_supabase_client
from utils.logger import get_logger
from utils.api_config import configure_fastf1_retries
from utils.race_utils import get_latest_completed_session

configure_fastf1_retries()

logger = get_logger("AutoUpdate")
supabase = get_supabase_client()

def check_and_update():
    logger.info("Checking for new race data...")
    
    # 1. Get Latest Completed Session in Real World
    latest_session = get_latest_completed_session()
    
    if not latest_session:
        logger.info("No completed sessions found for current year yet.")
        return

    year = latest_session['Year']
    round_num = latest_session['Round']
    session_type = latest_session['SessionType']
    event_name = latest_session['EventName']
    
    logger.info(f"Latest Real-World Session: {year} Round {round_num} ({event_name}) - {latest_session['Session']}")

    # 2. Check DB State for this Race
    # We check if we have results for this race and what kind
    # If it's a Race session, we check if 'ingestion_complete' is True in 'races'
    # If it's Qualifying, we check if we have grid data in 'race_results'
    
    # First, find the race_id
    race_res = supabase.table('races').select('*').eq('season_year', year).eq('round', round_num).execute()
    
    if not race_res.data:
        logger.info(f"Race not found in DB for {year} R{round_num}. Attempting to insert schedule...")
        # If race doesn't exist, we might need to run full schedule ingest or just insert it
        # ideally ingest_enhanced_race_data handles creation, but let's be safe.
        pass # The ingest functions usually handle it

    race_data = race_res.data[0] if race_res.data else None
    race_id = race_data['id'] if race_data else None
    
    update_needed = False
    action = None # 'RACE', 'QUALI', 'NONE'
    
    if session_type == 'R':
        # Check if Race is already ingested
        if race_data and race_data.get('ingestion_complete'):
            logger.info(f"Race {year} R{round_num} already fully ingested.")
        else:
            logger.info(f"Race {year} R{round_num} COMPLETED but not fully ingested. Triggering Update.")
            update_needed = True
            action = 'RACE'
            
    elif session_type == 'Q':
        # Check if Qualifying is ingested
        # Heuristic: Check if we have any results for this race with status='Qualified' or grid data
        if race_id:
            # Check for existing grid data
            # We look for rows for this race_id in race_results
            res = supabase.table('race_results').select('driver_id', count='exact').eq('race_id', race_id).execute()
            count = res.count if res.count is not None else len(res.data)
            
            if count > 10: # Arbitrary threshold, valid grid has 20
                 logger.info(f"Qualifying {year} R{round_num} likely already ingested ({count} entries).")
            else:
                 logger.info(f"Qualifying {year} R{round_num} COMPLETED but grid missing/incomplete. Triggering Update.")
                 update_needed = True
                 action = 'QUALI'
        else:
             # Race doesn't exist yet, so we definitely need to ingest
             update_needed = True
             action = 'QUALI'
             
    # 3. Perform Updates
    if update_needed:
        try:
            if action == 'RACE':
                logger.info(f"🚀 Starting Full Race Ingestion for {year} Round {round_num}...")
                ingest_enhanced_race_data(year, round_num)
                
                # Check directly if it was successful (heuristic)
                # Then train
                logger.info("Triggering Model Retraining...")
                
                # Get all race IDs for training
                all_races = supabase.table('races').select('id').eq('ingestion_complete', True).execute()
                race_ids = [r['id'] for r in all_races.data]
                train_model(race_ids)
                
            elif action == 'QUALI':
                logger.info(f"⏱️ Starting Qualifying Ingestion for {year} Round {round_num}...")
                ingest_qualifying_results(year, round_num)
                logger.info("Qualifying data updated. No full retraining needed yet.")
                
            logger.info("✅ Update Sequence Complete.")
            
        except Exception as e:
            logger.error(f"❌ Update failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        logger.info("System is up to date with latest completed session.")

if __name__ == "__main__":
    check_and_update()
