import fastf1
import pandas as pd
import numpy as np
from utils.db import get_supabase_client
from utils.logger import get_logger
import os

# Enable cache
if not os.path.exists('cache'):
    os.makedirs('cache')
fastf1.Cache.enable_cache('cache')

supabase = get_supabase_client()
logger = get_logger("DataIngestion")

def resolve_id(table, column, value, data_if_missing=None):
    """
    Checks if a record exists by a unique column. 
    If yes, returns ID. 
    If no, inserts data_if_missing and returns new ID.
    """
    try:
        res = supabase.table(table).select("id").eq(column, value).execute()
        if res.data:
            return res.data[0]['id']
        
        if data_if_missing:
            logger.info(f"Inserting new {table}: {value}")
            res = supabase.table(table).insert(data_if_missing).execute()
            if res.data:
                return res.data[0]['id']
            
        return None
    except Exception as e:
        logger.error(f"Error resolving ID for {table} {value}: {e}")
        return None

def ingest_race_data(year, race_round):
    logger.info(f"Starting ingestion for {year} Round {race_round}")
    
    try:
        session = fastf1.get_session(year, race_round, 'R')
        session.load()
    except Exception as e:
        logger.error(f"Failed to load FastF1 session: {e}")
        return

    # 1. Season
    # Check/Insert Season
    try:
        res = supabase.table('seasons').select('year').eq('year', year).execute()
        if not res.data:
            supabase.table('seasons').insert({'year': year}).execute()
    except Exception as e:
        logger.error(f"Error processing season: {e}")

    # 2. Circuit
    circuit_name = session.event.EventName # Fallback if CircuitName not available directly in event
    # FastF1 event object has 'Location', 'Country', 'EventName'
    # We need a unique ID. Let's use a slugified name or just the name for now as 'ergast_circuit_id'
    circuit_ref = session.event.EventName.replace(" ", "_").lower()
    
    circuit_data = {
        'ergast_circuit_id': circuit_ref,
        'name': session.event.EventName,
        'location': session.event.Location,
        'country': session.event.Country,
        'lat': 0, # FastF1 doesn't provide this easily
        'lng': 0
    }
    circuit_id = resolve_id('circuits', 'ergast_circuit_id', circuit_ref, circuit_data)

    # 3. Race
    race_ref = f"{year}_{race_round}_{circuit_ref}"
    race_data = {
        'ergast_race_id': race_ref,
        'season_year': year,
        'round': race_round,
        'name': session.event.EventName,
        'circuit_id': circuit_id,
        'date': session.date.strftime('%Y-%m-%d'),
        'time': session.date.strftime('%H:%M:%S')
    }
    race_id = resolve_id('races', 'ergast_race_id', race_ref, race_data)
    
    if not race_id:
        logger.error("Could not resolve Race ID. Aborting.")
        return

    # 4. Drivers & Constructors
    driver_map = {} # Map Abbreviation -> UUID
    
    for drv in session.drivers:
        drv_info = session.get_driver(drv)
        if drv_info is None or pd.isna(drv_info['Abbreviation']):
            continue
            
        # Driver
        d_ref = drv_info['Abbreviation'].lower()
        d_data = {
            'ergast_driver_id': d_ref,
            'code': drv_info['Abbreviation'],
            'permanent_number': int(drv_info['DriverNumber']) if drv_info['DriverNumber'] and drv_info['DriverNumber'].isdigit() else None,
            'given_name': drv_info['FirstName'],
            'family_name': drv_info['LastName'],
            'nationality': drv_info['CountryCode'], # Approximate
            'date_of_birth': None # Not in FastF1
        }
        d_id = resolve_id('drivers', 'ergast_driver_id', d_ref, d_data)
        driver_map[drv_info['Abbreviation']] = d_id
        
        # Constructor
        team_name = drv_info['TeamName']
        if team_name:
            c_ref = team_name.replace(" ", "_").lower()
            c_data = {
                'ergast_constructor_id': c_ref,
                'name': team_name,
                'nationality': None
            }
            c_id = resolve_id('constructors', 'ergast_constructor_id', c_ref, c_data)
            
            # Race Results (Basic)
            # We can populate 'race_results' table here if needed, but let's focus on LAPS first as requested
            
    # 5. Laps
    logger.info("Processing Laps...")
    laps = session.laps
    laps_batch = []
    
    for i, lap in laps.iterrows():
        d_abbrev = lap['Driver']
        if d_abbrev not in driver_map:
            continue
            
        d_id = driver_map[d_abbrev]
        
        # Helper for intervals
        def get_interval(td):
            return str(td) if pd.notnull(td) else None

        laps_batch.append({
            'race_id': race_id,
            'driver_id': d_id,
            'lap_number': int(lap['LapNumber']),
            'lap_time': get_interval(lap['LapTime']),
            'sector_1_time': get_interval(lap['Sector1Time']),
            'sector_2_time': get_interval(lap['Sector2Time']),
            'sector_3_time': get_interval(lap['Sector3Time']),
            'compound': lap['Compound'],
            'tyre_life': int(lap['TyreLife']) if pd.notnull(lap['TyreLife']) else None,
            'fresh_tyre': bool(lap['FreshTyre']) if pd.notnull(lap['FreshTyre']) else None,
            'track_status': lap['TrackStatus'],
            'is_accurate': bool(lap['IsAccurate']) if pd.notnull(lap['IsAccurate']) else None
        })
        
        if len(laps_batch) >= 100:
            try:
                supabase.table('laps').upsert(laps_batch, on_conflict='race_id, driver_id, lap_number').execute()
                laps_batch = []
            except Exception as e:
                logger.error(f"Error inserting laps batch: {e}")
                laps_batch = [] # Drop bad batch or handle better
                
    if laps_batch:
        supabase.table('laps').upsert(laps_batch, on_conflict='race_id, driver_id, lap_number').execute()

    # 6. Weather
    logger.info("Processing Weather...")
    weather = session.weather_data
    weather_batch = []
    
    for i, row in weather.iterrows():
        # Time in weather is a Timedelta from session start. 
        # We need absolute timestamp.
        # session.date is the start time (datetime)
        # row['Time'] is timedelta
        
        w_time = session.date + row['Time']
        
        weather_batch.append({
            'race_id': race_id,
            'timestamp': w_time.isoformat(),
            'air_temp': row['AirTemp'],
            'track_temp': row['TrackTemp'],
            'humidity': row['Humidity'],
            'pressure': row['Pressure'],
            'rainfall': bool(row['Rainfall']),
            'wind_speed': row['WindSpeed'],
            'wind_direction': int(row['WindDirection'])
        })
        
        if len(weather_batch) >= 100:
            supabase.table('weather').insert(weather_batch).execute()
            weather_batch = []
            
    if weather_batch:
        supabase.table('weather').insert(weather_batch).execute()

    logger.info(f"Ingestion complete for {year} Round {race_round}")

if __name__ == "__main__":
    # Test with a recent race
    ingest_race_data(2024, 1)
