
import sys
import os
import time
import datetime
import traceback

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import fastf1
from data.ingest_data_enhanced import ingest_enhanced_race_data, _process_telemetry_cache
from utils.db import get_supabase_client
from utils.logger import get_logger
from utils.api_config import configure_fastf1_retries

# Configure Logging
# Configure Logging
logger = get_logger("BackfillTelemetry")
supabase = get_supabase_client()

# Enable Cache & Retries GLOBALLY for this script
if not os.path.exists('f1_cache'):
    os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')
configure_fastf1_retries()

def backfill_telemetry(start_year=2018, end_year=2025):
    """
    Intelligent backfill for telemetry cache.
    Checks if telemetry exists in Supabase. If not, processes it.
    Also ensures basic race data exists.
    """
    current_year = datetime.datetime.now().year
    
    # We want to go from 2025 backwards to 2018 (or user spec)
    # Actually user said "starts from where the script was stopped". 
    # Going backwards is usually better for "latest data first".
    # But user asked 2018 to 2025. Let's do 2018 -> 2025 (Forward) or Reverse?
    # "data will be from 2018 to all teh way uptill 2025"
    # Let's do reverse (2025 -> 2018) so latest races get cached first for immediate use.
    
    years = list(range(start_year, end_year + 1))
    years.reverse()
    
    logger.info(f"Starting Backfill for years: {years}")
    
    for year in years:
        try:
            schedule = fastf1.get_event_schedule(year)
            # Filter for completed races only
            now = datetime.datetime.now()
            completed_races = schedule[schedule['EventDate'] < now]
            
            # Reverse rounds too
            completed_races = completed_races.iloc[::-1]
            
            total_races = len(completed_races)
            
            for idx, row in completed_races.iterrows():
                round_num = row['RoundNumber']
                event_name = row['EventName']
                
                if round_num == 0: continue # Skip Testing
                
                logger.info(f"Processing Year {year} Round {round_num} ({event_name})...")
                process_race_with_timeout(year, round_num, event_name)
                
        except Exception as e:
            logger.error(f"Error processing schedule for {year}: {e}")

def process_race_with_timeout(year, round_num, event_name, timeout_seconds=300):
    """Wrapper to run process_race with a timeout."""
    import threading
    
    # Define a thread target that captures exceptions
    def target():
        try:
            process_race(year, round_num, event_name)
        except Exception as e:
            logger.error(f"Error in thread for {year} R{round_num}: {e}")

    t = threading.Thread(target=target)
    t.start()
    t.join(timeout=timeout_seconds)
    
    if t.is_alive():
        logger.error(f"TIMEOUT: Processing {year} Round {round_num} took longer than {timeout_seconds}s. Skipping.")
        # We can't easily kill the thread in Python without using multiprocessing or ctypes hacks.
        # But we can at least move on. The thread will eventually die or hang in background on OS exit.
        return

def process_race(year, round_num, event_name):
    """Process a single race."""
    race_ref = f"{year} Round {round_num} ({event_name})"
    
    # 1. Check if Telemetry Cache exists
    try:
        # We need race_id to check cache efficiently, but we can query by year/round
        # The schema plan added season_year and round to race_telemetry_cache for this reason!
        
        # Let's find race_id first to be safe
        res = supabase.table('races').select('id, ingestion_status').eq('season_year', year).eq('round', round_num).execute()
        
        race_id = None
        needs_ingestion = True
        
        if res.data:
            race_id = res.data[0]['id']
            status = res.data[0].get('ingestion_status')
            if status == 'COMPLETE':
                needs_ingestion = False
        
        # If race doesn't exist or incomplete, we MUST run ingestion
        if needs_ingestion:
            logger.info(f"[MISSING DATA] {race_ref} - Ingesting base data...")
            try:
                ingest_enhanced_race_data(year, round_num)
                # Fetch race_id again
                res = supabase.table('races').select('id').eq('season_year', year).eq('round', round_num).execute()
                if res.data:
                    race_id = res.data[0]['id']
            except Exception as e:
                logger.error(f"Failed to ingest base data for {race_ref}: {e}")
                return

        if not race_id:
            logger.error(f"Could not resolve race_id for {race_ref}")
            return

        # 2. Check Cache with race_id
        res_cache = supabase.table('race_telemetry_cache').select('id').eq('race_id', race_id).execute()
        
        if res_cache.data:
            logger.info(f"[SKIP] {race_ref} - Telemetry already cached.")
            return
            
        # 3. Process Telemetry Cache
        logger.info(f"[PROCESSING] {race_ref} - Generating Telemetry Cache...")
        start_time = time.time()
        
        try:
            session = fastf1.get_session(year, round_num, 'R')
            session.load(telemetry=True, laps=True, weather=False, messages=False)
            
            _process_telemetry_cache(session, race_id, year, round_num)
            
            elapsed = time.time() - start_time
            logger.info(f"[SUCCESS] {race_ref} - Cached in {elapsed:.1f}s")
            
        except Exception as e:
            logger.error(f"Failed to cache telemetry for {race_ref}: {e}")
            traceback.print_exc()

    except Exception as e:
        logger.error(f"Error checking status for {race_ref}: {e}")
        
    # Rate Limiting Pause
    delay = random.uniform(3, 7)
    logger.info(f"Sleeping for {delay:.1f}s to respect API rate limits...")
    time.sleep(delay)

if __name__ == "__main__":
    backfill_telemetry()
