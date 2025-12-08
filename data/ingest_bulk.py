import fastf1
import pandas as pd
import datetime
import concurrent.futures
import time
import random
from tqdm import tqdm
from data.ingest_data_enhanced import ingest_enhanced_race_data
from models.train_model import train_model
from utils.db import get_supabase_client
from utils.logger import get_logger
from utils.reports import generate_race_report

logger = get_logger("BulkIngestion")
supabase = get_supabase_client()

def process_race_with_retry(args):
    year, round_num, event_name = args
    max_retries = 3
    base_delay = 5
    
    for attempt in range(max_retries):
        try:
            # logger.info(f"Ingesting {year} Round {round_num}: {event_name}")
            ingest_enhanced_race_data(year, round_num)
            
            # Generate Report
            try:
                # We need the race_id. Since ingest doesn't return it easily, we fetch it.
                res = supabase.table('races').select('id').eq('season_year', year).eq('round', round_num).execute()
                if res.data:
                    race_id = res.data[0]['id']
                    report_path = generate_race_report(race_id, year, round_num, event_name)
                    if report_path:
                        logger.info(f"Generated Report: {report_path}")
            except Exception as e:
                logger.warning(f"Report generation failed: {e}")
                
            return True
        except Exception as e:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            logger.warning(f"Error processing {year} Round {round_num} (Attempt {attempt+1}/{max_retries}): {e}. Retrying in {delay:.1f}s...")
            time.sleep(delay)
    
    logger.error(f"Failed to process {year} Round {round_num} after {max_retries} attempts.")
    return False

def ingest_bulk_history(start_year=2018):
    current_year = datetime.datetime.now().year
    
    logger.info(f"Starting Intelligent Bulk Ingestion from {current_year} down to {start_year}")
    
    races_to_process = []
    
    # 1. Collect all races first (Reverse Order)
    # We iterate backwards from current year to start_year
    for year in range(current_year, start_year - 1, -1):
        try:
            schedule = fastf1.get_event_schedule(year)
            completed_races = schedule[schedule['EventDate'] < datetime.datetime.now()]
            
            # Reverse the rounds too, so we get the absolutely latest race first
            completed_races = completed_races.iloc[::-1]
            
            for i, row in completed_races.iterrows():
                round_num = row['RoundNumber']
                event_name = row['EventName']
                
                if round_num == 0:
                    continue

                # STRICT FUTURE FILTER (Restored)
                event_date = row['EventDate']
                if event_date > datetime.datetime.now():
                    continue
                
                # Check if race already exists AND is complete
                try:
                    res = supabase.table('races').select('id, ingestion_complete').eq('season_year', year).eq('round', round_num).execute()
                    if res.data:
                        # If it exists and is marked complete, skip it
                        if res.data[0].get('ingestion_complete', False):
                            # logger.info(f"Skipping {year} Round {round_num}: Already complete in DB.")
                            continue
                        else:
                            logger.info(f"Resuming {year} Round {round_num}: Incomplete ingestion found.")
                except Exception:
                    pass
                
                races_to_process.append((year, round_num, event_name))
                
        except Exception as e:
            logger.error(f"Error fetching schedule for {year}: {e}")

    total_races = len(races_to_process)
    logger.info(f"Found {total_races} races to ingest. Starting parallel execution...")

    # 2. Process sequentially (or low parallelism) to prevent Rate Limiting/Network Errors
    # Reduced to 1 worker for maximum reliability as per user request
    if total_races > 0:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # Use tqdm for progress bar
            results = list(tqdm(executor.map(process_race_with_retry, races_to_process), total=total_races, unit="race"))
    else:
        logger.info("All races are already up to date!")

    logger.info("Bulk Ingestion Complete. Triggering Model Training...")
    
    # Fetch all race IDs to train on
    res = supabase.table('races').select('id').execute()
    all_race_ids = [r['id'] for r in res.data]
    
    if all_race_ids:
        train_model(all_race_ids)
        logger.info("Model Retraining Complete.")
    else:
        logger.warning("No races found to train on.")

if __name__ == "__main__":
    ingest_bulk_history()
