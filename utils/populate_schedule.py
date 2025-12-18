import fastf1
import pandas as pd
from utils.db import get_supabase_client
from datetime import datetime

def populate_schedule(year=2025):
    supabase = get_supabase_client()
    print(f"Fetching schedule for {year}...")
    
    schedule = fastf1.get_event_schedule(year)
    
    # Filter out testing
    races = schedule[schedule['EventFormat'] != 'testing']
    
    print(f"Found {len(races)} races.")
    
    # Get a fallback circuit ID
    try:
        circuit_res = supabase.table('circuits').select('id').limit(1).execute()
        fallback_circuit_id = circuit_res.data[0]['id'] if circuit_res.data else None
    except:
        fallback_circuit_id = None

    for i, row in races.iterrows():
        round_num = row['RoundNumber']
        event_name = row['EventName']
        event_date = row['EventDate']
        circuit_name = row['Location'] 
        
        # Check if exists
        res = supabase.table('races').select('id').eq('season_year', year).eq('round', round_num).execute()
        
        if not res.data:
            print(f"Inserting Round {round_num}: {event_name}")
            data = {
                'season_year': int(year),
                'round': int(round_num),
                'name': event_name,
                'ergast_race_id': f"{year}_{round_num}_{event_name.replace(' ', '_').lower()}",
                'circuit_id': fallback_circuit_id, # Required FK
                'race_date': event_date.strftime('%Y-%m-%d'),
                'ingestion_status': 'PENDING'
            }
            try:
                supabase.table('races').insert(data).execute()
            except Exception as e:
                print(f"Failed to insert {event_name}: {e}")
        else:
            # Update date if needed?
            pass
            
    print("Schedule population complete.")

if __name__ == "__main__":
    populate_schedule()
