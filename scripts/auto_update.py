import fastf1
import datetime
import pandas as pd
from data.ingest_data_enhanced import ingest_enhanced_race_data
from models.train_lap_model import train_model
from utils.db import get_supabase_client
from utils.logger import get_logger

logger = get_logger("AutoUpdate")
supabase = get_supabase_client()

def check_and_update():
    logger.info("Checking for new races...")
    
    # 1. Get latest race in DB
    res = supabase.table('races').select('season_year, round').order('season_year', desc=True).order('round', desc=True).limit(1).execute()
    
    if not res.data:
        logger.info("No data in DB. Please run bulk ingestion first.")
        return

    last_db_race = res.data[0]
    last_year = last_db_race['season_year']
    last_round = last_db_race['round']
    
    logger.info(f"Last DB Race: {last_year} Round {last_round}")
    
    # 2. Check FastF1 Schedule for newer races
    current_year = datetime.datetime.now().year
    new_data_found = False
    
    # Check current year (and next year if we are at year boundary)
    # For simplicity, check current year schedule
    try:
        schedule = fastf1.get_event_schedule(current_year)
        completed_races = schedule[schedule['EventDate'] < datetime.datetime.now()]
        
        for i, row in completed_races.iterrows():
            r_year = int(row['EventYear'])
            r_round = int(row['RoundNumber'])
            
            if r_round == 0: continue
            
            # Logic to check if this race is newer than DB
            is_newer = False
            if r_year > last_year:
                is_newer = True
            elif r_year == last_year and r_round > last_round:
                is_newer = True
                
            if is_newer:
                logger.info(f"New race found: {r_year} Round {r_round} - {row['EventName']}")
                ingest_enhanced_race_data(r_year, r_round)
                new_data_found = True
                
    except Exception as e:
        logger.error(f"Error checking schedule: {e}")
        
    # 3. Retrain if needed
    if new_data_found:
        logger.info("New data ingested. Retraining model...")
        res = supabase.table('races').select('id').execute()
        all_race_ids = [r['id'] for r in res.data]
        train_model(all_race_ids)
        logger.info("Update Complete.")
    else:
        logger.info("System is up to date.")

if __name__ == "__main__":
    check_and_update()
