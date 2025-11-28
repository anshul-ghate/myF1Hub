import fastf1
import pandas as pd
import numpy as np
from utils.db import get_supabase_client
import os

# Enable cache
if not os.path.exists('cache'):
    os.makedirs('cache')
fastf1.Cache.enable_cache('cache')

supabase = get_supabase_client()

def ingest_race_data(year, race_round):
    print(f"Loading data for {year} Round {race_round}...")
    session = fastf1.get_session(year, race_round, 'R')
    session.load()
    
    # 1. Ingest Race Info
    race_info = {
        'year': year,
        'round': race_round,
        'circuit_id': session.event.EventName, # Using EventName as ID for now
        'name': session.event.EventName,
        'date': session.date.isoformat(),
        'location': session.event.Location
    }
    
    print("Upserting Race Info...")
    # Check if race exists to get ID, or insert
    # For simplicity in this script, we'll try to insert and ignore duplicates or handle via upsert if possible
    # Supabase upsert requires a primary key or unique constraint match. 
    # We have unique(year, round).
    
    res = supabase.table('races').upsert(race_info, on_conflict='year, round').execute()
    race_id = res.data[0]['race_id']
    
    # 2. Ingest Drivers
    print("Ingesting Drivers...")
    drivers_data = []
    for drv in session.drivers:
        drv_info = session.get_driver(drv)
        drivers_data.append({
            'driver_id': drv_info['Abbreviation'],
            'driver_number': int(drv_info['DriverNumber']) if drv_info['DriverNumber'] else None,
            'full_name': drv_info['FullName'],
            'team_name': drv_info['TeamName'],
            'country': drv_info['CountryCode']
        })
    
    if drivers_data:
        supabase.table('drivers').upsert(drivers_data).execute()
        
    # 3. Ingest Laps
    print("Ingesting Laps...")
    laps = session.laps
    laps_data = []
    
    # Pre-fetch driver mapping to ensure we have correct IDs
    # (Assuming Abbreviation is the ID)
    
    for i, lap in laps.iterrows():
        # Handle NaNs/Nats
        lap_time = lap['LapTime'].total_seconds() if pd.notnull(lap['LapTime']) else None
        s1 = lap['Sector1Time'].total_seconds() if pd.notnull(lap['Sector1Time']) else None
        s2 = lap['Sector2Time'].total_seconds() if pd.notnull(lap['Sector2Time']) else None
        s3 = lap['Sector3Time'].total_seconds() if pd.notnull(lap['Sector3Time']) else None
        
        laps_data.append({
            'race_id': race_id,
            'driver_id': lap['Driver'],
            'lap_number': int(lap['LapNumber']),
            'lap_time': lap_time,
            'sector1_time': s1,
            'sector2_time': s2,
            'sector3_time': s3,
            'compound': lap['Compound'],
            'tyre_life': int(lap['TyreLife']) if pd.notnull(lap['TyreLife']) else None,
            'fresh_tyre': bool(lap['FreshTyre']) if pd.notnull(lap['FreshTyre']) else None,
            'track_status': lap['TrackStatus'],
            'is_accurate': bool(lap['IsAccurate']) if pd.notnull(lap['IsAccurate']) else None
        })
        
    # Batch insert laps to avoid payload limits
    batch_size = 100
    for i in range(0, len(laps_data), batch_size):
        batch = laps_data[i:i+batch_size]
        supabase.table('laps').insert(batch).execute()

    # 4. Ingest Weather (Sampled)
    print("Ingesting Weather...")
    weather = session.weather_data
    weather_data = []
    
    for i, row in weather.iterrows():
        weather_data.append({
            'race_id': race_id,
            'time': row['Time'].isoformat() if pd.notnull(row['Time']) else None, # This is timedelta relative to session start, might need adjustment to absolute time
            'air_temp': row['AirTemp'],
            'track_temp': row['TrackTemp'],
            'humidity': row['Humidity'],
            'pressure': row['Pressure'],
            'rainfall': bool(row['Rainfall']),
            'wind_speed': row['WindSpeed'],
            'wind_direction': int(row['WindDirection'])
        })
        
    # Adjust weather time to be absolute timestamp? 
    # FastF1 weather 'Time' is session time. We can add it to session.date (start time).
    # Actually session.weather_data index is usually the time, or 'Time' column.
    # Let's stick to the raw values or convert if needed. 
    # For now, let's just store it.
    
    if weather_data:
        # Batch insert
        for i in range(0, len(weather_data), batch_size):
            batch = weather_data[i:i+batch_size]
            supabase.table('weather').insert(batch).execute()
            
    print(f"Completed ingestion for {year} Round {race_round}")

if __name__ == "__main__":
    # Example: Ingest 2023 Bahrain GP (Round 1)
    ingest_race_data(2023, 1)
