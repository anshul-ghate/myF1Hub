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
logger = get_logger("DataIngestionEnhanced")

# Configure Retries for FastF1/Requests
from utils.api_config import configure_fastf1_retries
configure_fastf1_retries()


# Global In-Memory Cache to reduce DB reads
# Structure: { 'table_name': { 'column_value': 'uuid' } }
ID_CACHE = {
    'drivers': {},
    'circuits': {},
    'races': {},
    'seasons': {}
}

def resolve_id(table, column, value, data_if_missing=None):
    # 1. Check Cache
    if table in ID_CACHE and value in ID_CACHE[table]:
        return ID_CACHE[table][value]

    try:
        # 2. Try to find in DB
        res = supabase.table(table).select("id").eq(column, value).execute()
        if res.data:
            uid = res.data[0]['id']
            if table in ID_CACHE: ID_CACHE[table][value] = uid
            return uid
            
        # 3. If not found, try to insert
        if data_if_missing:
            try:
                logger.info(f"Inserting new {table}: {value}")
                res = supabase.table(table).insert(data_if_missing).execute()
                if res.data:
                    uid = res.data[0]['id']
                    if table in ID_CACHE: ID_CACHE[table][value] = uid
                    return uid
            except Exception:
                # 4. If insert fails (likely race condition), try to find again
                res = supabase.table(table).select("id").eq(column, value).execute()
                if res.data:
                    uid = res.data[0]['id']
                    if table in ID_CACHE: ID_CACHE[table][value] = uid
                    return uid
        return None
    except Exception as e:
        logger.error(f"Error resolving ID for {table} {value}: {e}")
        return None

def ingest_enhanced_race_data(year, race_round):
    logger.info(f"Starting ENHANCED ingestion for {year} Round {race_round}")
    
    try:
        session = fastf1.get_session(year, race_round, 'R')
        session.load()
    except Exception as e:
        logger.error(f"Failed to load FastF1 session: {e}")
        return

    # --- Basic Info Setup ---
    # 1. Season
    try:
        if year not in ID_CACHE['seasons']:
            res = supabase.table('seasons').select('year').eq('year', year).execute()
            if not res.data:
                supabase.table('seasons').insert({'year': year}).execute()
            ID_CACHE['seasons'][year] = True # Just mark as present
    except Exception:
        pass

    # 2. Circuit
    circuit_ref = session.event.EventName.replace(" ", "_").lower()
    circuit_data = {
        'ergast_circuit_id': circuit_ref,
        'name': session.event.EventName,
        'location': session.event.Location,
        'country': session.event.Country,
        'lat': 0, 'lng': 0
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

    # 4. Drivers
    driver_map = {} 
    for drv in session.drivers:
        drv_info = session.get_driver(drv)
        if drv_info is None or pd.isna(drv_info['Abbreviation']):
            continue
        d_ref = drv_info['Abbreviation'].lower()
        d_data = {
            'ergast_driver_id': d_ref,
            'code': drv_info['Abbreviation'],
            'given_name': drv_info['FirstName'],
            'family_name': drv_info['LastName'],
            'nationality': drv_info['CountryCode']
        }
        d_id = resolve_id('drivers', 'ergast_driver_id', d_ref, d_data)
        driver_map[drv_info['Abbreviation']] = d_id

    # --- ENHANCED DATA PROCESSING ---

    # --- ENHANCED DATA PROCESSING (VECTORIZED) ---

    # 5. Laps with Fuel & Gap
    logger.info("Processing Laps (Vectorized)...")
    laps = session.laps
    
    # Ensure numeric
    laps['LapNumber'] = pd.to_numeric(laps['LapNumber'])
    total_laps_in_race = laps['LapNumber'].max()
    
    # A. Calculate Gaps (Vectorized)
    # Get leader time per lap
    leader_times = laps[laps['Position'] == 1][['LapNumber', 'Time']].set_index('LapNumber')['Time']
    # Map leader time to all laps
    laps['LeaderTime'] = laps['LapNumber'].map(leader_times)
    # Calculate gap
    laps['GapToLeader'] = (laps['Time'] - laps['LeaderTime']).dt.total_seconds().fillna(0)
    
    # B. Calculate Fuel (Vectorized)
    # Linear burn: 110kg -> 0kg
    if total_laps_in_race > 0:
        laps['FuelLoad'] = 110.0 * (1.0 - (laps['LapNumber'] / total_laps_in_race))
    else:
        laps['FuelLoad'] = 0.0

    # Prepare Laps Batch
    laps_to_upload = []
    
    # We need to map Driver Abbreviation to ID efficiently
    # driver_map is { 'HAM': 'uuid', ... }
    
    # Iterate by Driver to handle Telemetry efficiently too
    telemetry_to_upload = []
    
    for drv in session.drivers:
        if drv not in session.results['Abbreviation'].values: continue
        d_abbrev = session.get_driver(drv)['Abbreviation']
        d_id = driver_map.get(d_abbrev)
        if not d_id: continue

        # Get laps for this driver
        d_laps = laps[laps['Driver'] == d_abbrev].copy()
        if d_laps.empty: continue

        # --- Process Laps ---
        for _, lap in d_laps.iterrows():
            # Helper for intervals
            def get_interval(td):
                return str(td) if pd.notnull(td) else None

            laps_to_upload.append({
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
                'is_accurate': bool(lap['IsAccurate']) if pd.notnull(lap['IsAccurate']) else None,
                'position': int(lap['Position']) if pd.notnull(lap['Position']) else None,
                'gap_to_leader': float(lap['GapToLeader']),
                'fuel_load': float(lap['FuelLoad'])
            })

        # --- Process Telemetry (Batch by Driver) ---
        # Instead of get_telemetry() per lap, we get car data for the whole session
        # and slice it by lap times.
        try:
            # Load car data for driver
            car_data = session.car_data[drv] # This is a DataFrame
            if car_data is None or car_data.empty: continue
            
            # We need to assign a LapNumber to each telemetry sample
            # We define bins based on Lap Start Times
            # Lap N starts at Lap N-1 End Time (or Session Start)
            
            # Create bins
            # We use 'Time' (SessionTime)
            # We need a list of (LapNumber, StartTime, EndTime)
            # d_laps has 'LapStartTime' and 'Time' (which is LapEndTime)
            # Note: FastF1 v3.1+ has 'LapStartTime'
            
            # Filter for accurate laps only for telemetry stats
            accurate_laps = d_laps[d_laps['IsAccurate'] == True]
            
            for _, lap in accurate_laps.iterrows():
                # Slice telemetry for this lap
                # This is still a loop, but it's a loop over ~50 laps doing simple slicing
                # faster than get_telemetry() which does internal overhead
                t_start = lap['LapStartTime']
                t_end = lap['Time'] # Lap End Time
                
                if pd.isnull(t_start) or pd.isnull(t_end): continue
                
                # Slice
                mask = (car_data['Time'] >= t_start) & (car_data['Time'] <= t_end)
                lap_tel = car_data.loc[mask]
                
                if lap_tel.empty: continue
                
                # Aggregate
                t_stats = {
                    'race_id': race_id,
                    'driver_id': d_id,
                    'lap_number': int(lap['LapNumber']),
                    'speed_max': float(lap_tel['Speed'].max()) if 'Speed' in lap_tel else 0,
                    'speed_avg': float(lap_tel['Speed'].mean()) if 'Speed' in lap_tel else 0,
                    'throttle_avg': float(lap_tel['Throttle'].mean()) if 'Throttle' in lap_tel else 0,
                    'brake_avg': float(lap_tel['Brake'].mean()) if 'Brake' in lap_tel else 0,
                    'gear_shifts': int(lap_tel['nGear'].diff().abs().sum() / 2) if 'nGear' in lap_tel else 0
                }
                telemetry_to_upload.append(t_stats)
                
        except Exception as e:
            # logger.warning(f"Telemetry error for {d_abbrev}: {e}")
            pass

    # Bulk Upsert
    # Laps
    if laps_to_upload:
        # Chunking to avoid payload limits (Supabase has 1MB limit sometimes, or row limits)
        chunk_size = 2000
        for i in range(0, len(laps_to_upload), chunk_size):
            chunk = laps_to_upload[i:i+chunk_size]
            try:
                supabase.table('laps').upsert(chunk, on_conflict='race_id, driver_id, lap_number').execute()
            except Exception as e:
                logger.error(f"Error upserting laps chunk: {e}")

    # Telemetry
    if telemetry_to_upload:
        chunk_size = 2000
        for i in range(0, len(telemetry_to_upload), chunk_size):
            chunk = telemetry_to_upload[i:i+chunk_size]
            try:
                supabase.table('telemetry_stats').upsert(chunk, on_conflict='race_id, driver_id, lap_number').execute()
            except Exception as e:
                logger.error(f"Error upserting telemetry chunk: {e}")

    # 6. Pit Stops
    logger.info("Processing Pit Stops...")
    pit_stops_batch = []
    pit_laps = session.laps.dropna(subset=['PitInTime', 'PitOutTime'], how='all') 
    
    for i, lap in pit_laps.iterrows():
        d_abbrev = lap['Driver']
        d_id = driver_map.get(d_abbrev)
        if not d_id: continue
        
        # Calculate duration manually if PitDuration is missing
        if 'PitDuration' in lap:
            duration = lap['PitDuration']
        else:
            if pd.notnull(lap['PitOutTime']) and pd.notnull(lap['PitInTime']):
                duration = lap['PitOutTime'] - lap['PitInTime']
            else:
                duration = None
                
        if pd.notnull(duration):
            if isinstance(duration, pd.Timedelta):
                duration_s = duration.total_seconds()
            else:
                duration_s = duration
                
            pit_stops_batch.append({
                'race_id': race_id,
                'driver_id': d_id,
                'lap_number': int(lap['LapNumber']),
                'duration': duration_s,
                'local_timestamp': None
            })
            
    if pit_stops_batch:
        supabase.table('pit_stops').insert(pit_stops_batch).execute()

    # 8. Results (Positions, Grid, Points)
    logger.info("Processing Results...")
    print(f"   Processing results for {len(session.drivers)} drivers...")
    results_batch = []
    for drv in session.drivers:
        if drv not in session.results['Abbreviation'].values: 
            print(f"   Skipping {drv} (not in results)")
            continue
            
        d_info = session.get_driver(drv)
        d_id = driver_map.get(d_info['Abbreviation'])
        if not d_id: 
            print(f"   Skipping {drv} (no ID)")
            continue
        
        # Safe extraction of fields
        position = d_info.get('Position')
        grid = d_info.get('GridPosition')
        points = d_info.get('Points')
        status = d_info.get('Status')
        
        # Handle NaN/None
        position = int(position) if pd.notnull(position) else None
        grid = int(grid) if pd.notnull(grid) else None
        points = float(points) if pd.notnull(points) else 0.0
        status = str(status) if pd.notnull(status) else 'Finished'
        
        results_batch.append({
            'race_id': race_id,
            'driver_id': d_id,
            'position': position,
            'grid': grid,
            'points': points,
            'status': status,
            # 'team': d_info.get('TeamName', 'Unknown'), # Column missing in DB
            'laps': int(d_info['ClassifiedPosition']) if str(d_info['ClassifiedPosition']).isdigit() else None
        })
        
    if results_batch:
        try:
            print(f"   Upserting {len(results_batch)} results...")
            data = supabase.table('race_results').upsert(results_batch, on_conflict='race_id, driver_id').execute()
            print(f"   ✅ Upsert success! Data: {len(data.data) if data.data else 'No data returned'}")
        except Exception as e:
            logger.error(f"Error upserting results: {e}")
            print(f"   ❌ Error upserting results: {e}")
    else:
        print("   ⚠️ No results to upsert.")

    # 7. Mark Ingestion as Complete
    supabase.table('races').update({'ingestion_complete': True}).eq('id', race_id).execute()
    logger.info(f"Enhanced Ingestion complete for {year} Round {race_round}")

def ingest_qualifying_results(year, race_round):
    """
    Ingest ONLY qualifying results to populate the grid for upcoming races.
    """
    logger.info(f"Starting QUALIFYING ingestion for {year} Round {race_round}")
    
    try:
        session = fastf1.get_session(year, race_round, 'Q')
        session.load()
    except Exception as e:
        logger.error(f"Failed to load FastF1 Qualifying session: {e}")
        return

    # Resolve Race ID (Must exist)
    circuit_ref = session.event.EventName.replace(" ", "_").lower()
    race_ref = f"{year}_{race_round}_{circuit_ref}"
    
    # Try to find race_id
    res = supabase.table('races').select('id').eq('ergast_race_id', race_ref).execute()
    if not res.data:
        # Try by name/year/round if ergast_id missing
        res = supabase.table('races').select('id').eq('season_year', year).eq('round', race_round).execute()
        
    if not res.data:
        logger.error("Race not found in DB. Run schedule population first.")
        return
        
    race_id = res.data[0]['id']
    
    # Process Qualifying Results
    results_batch = []
    
    # Ensure drivers exist
    for drv in session.drivers:
        if drv not in session.results['Abbreviation'].values: continue
        d_info = session.get_driver(drv)
        
        # Resolve Driver ID
        d_ref = d_info['Abbreviation'].lower()
        d_data = {
            'ergast_driver_id': d_ref,
            'code': d_info['Abbreviation'],
            'given_name': d_info['FirstName'],
            'family_name': d_info['LastName'],
            'nationality': d_info['CountryCode']
        }
        d_id = resolve_id('drivers', 'ergast_driver_id', d_ref, d_data)
        
        if not d_id: continue
        
        # Extract Position (which is Grid for the race)
        position = d_info.get('Position')
        
        if pd.notnull(position):
            results_batch.append({
                'race_id': race_id,
                'driver_id': d_id,
                'grid': int(position),
                'status': 'Qualified' # Marker
            })
            
    if results_batch:
        try:
            # Upsert - Update grid if exists, insert if not
            # Note: This might overwrite race results if run AFTER race, so use carefully.
            # But for upcoming race, it's fine.
            supabase.table('race_results').upsert(results_batch, on_conflict='race_id, driver_id').execute()
            logger.info(f"✅ Qualifying results ingested for {len(results_batch)} drivers.")
        except Exception as e:
            logger.error(f"Error upserting qualifying results: {e}")

if __name__ == "__main__":
    ingest_enhanced_race_data(2024, 1)
