import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fastf1
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List

from utils.db import get_supabase_client
from utils.logger import get_logger, log_operation
from utils.exceptions import (
    IngestionError, 
    DatabaseError, 
    DataValidationError,
    RateLimitError
)
from utils.schemas import (
    DriverCreate, 
    RaceCreate, 
    LapCreate, 
    RaceResultCreate,
    LapData,
    TelemetryStats,
    validate_race_results
)
from utils.api_config import configure_fastf1_retries

# Enable cache
if not os.path.exists('f1_cache'):
    os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

# Configure Retries
configure_fastf1_retries()

# Lazy supabase client - initialized on first use
_supabase_client = None

def _get_db():
    """Get supabase client (lazy initialization)."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = get_supabase_client()
    return _supabase_client

logger = get_logger("DataIngestionEnhanced")

# Global In-Memory Cache to reduce DB reads
ID_CACHE = {
    'drivers': {},
    'circuits': {},
    'races': {},
    'seasons': {}
}

def resolve_id(table: str, column: str, value: Any, data_if_missing: Optional[Dict] = None) -> Optional[str]:
    """
    Resolve a database ID for a given entity, inserting it if missing.
    Uses in-memory cache to minimize DB lookups.
    """
    # 1. Check Cache
    if table in ID_CACHE and value in ID_CACHE[table]:
        return ID_CACHE[table][value]

    try:
        # 2. Try to find in DB
        res = _get_db().table(table).select("id").eq(column, value).execute()
        if res.data:
            uid = res.data[0]['id']
            if table in ID_CACHE: ID_CACHE[table][value] = uid
            return uid
            
        # 3. If not found, try to insert
        if data_if_missing:
            try:
                logger.info(f"Inserting new {table}: {value}", extra={"table": table, "value": value})
                res = _get_db().table(table).insert(data_if_missing).execute()
                if res.data:
                    uid = res.data[0]['id']
                    if table in ID_CACHE: ID_CACHE[table][value] = uid
                    return uid
            except Exception as e:
                # 4. If insert fails (likely race condition), try to find again
                logger.warning(f"Insert failed for {table} {value}, retrying fetch: {e}")
                res = _get_db().table(table).select("id").eq(column, value).execute()
                if res.data:
                    uid = res.data[0]['id']
                    if table in ID_CACHE: ID_CACHE[table][value] = uid
                    return uid
        return None
        
    except Exception as e:
        logger.error(f"Error resolving ID for {table} {value}", exc_info=True)
        raise DatabaseError(f"Failed to resolve ID for {table}: {value}", details={"error": str(e)})

def ingest_enhanced_race_data(year: int, race_round: int):
    """
    Ingest full race data including laps, telemetry, and results.
    Validates data against schemas before insertion.
    """
    logger.info(f"Starting ENHANCED ingestion for {year} Round {race_round}")
    
    with log_operation(logger, "ingest_race", year=year, round=race_round):
        # 1. Load FastF1 Session
        try:
            session = fastf1.get_session(year, race_round, 'R')
            session.load()
        except Exception as e:
            raise IngestionError(
                f"Failed to load FastF1 session for {year} Round {race_round}", 
                source="FastF1",
                details={"error": str(e)}
            )

        # 2. Setup Basic Info (Season, Circuit, Race)
        _ingest_basic_info(session, year, race_round)
        
        # Get Race ID
        circuit_ref = session.event.EventName.replace(" ", "_").lower()
        race_ref = f"{year}_{race_round}_{circuit_ref}"
        
        # We need to reconstruct the race_data for resolve_id just in case, or just fetch ID
        # Assuming _ingest_basic_info handled creation, we just fetch ID
        try:
            res = _get_db().table('races').select('id').eq('ergast_race_id', race_ref).execute()
            if not res.data:
                 raise IngestionError(f"Race {race_ref} not found after basic ingestion")
            race_id = res.data[0]['id']
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve race ID for {race_ref}", details={"error": str(e)})

        # 3. Process Drivers and Map IDs
        driver_map = _ingest_drivers(session)
        
        # 4. Process Laps (Vectorized)
        _process_laps(session, race_id, driver_map)
        
        # 5. Process Telemetry
        _process_telemetry(session, race_id, driver_map)
        
        # 6. Process Pit Stops
        _process_pit_stops(session, race_id, driver_map)
        
        # 7. Process Results
        _process_results(session, race_id, driver_map)
        
        # 8. Process Telemetry Cache (Instant Load)
        if session.f1_api_support: # Only for sessions with F1 API support
            try:
                _process_telemetry_cache(session, race_id, year, race_round)
            except Exception as e:
                logger.error(f"Failed to process telemetry cache: {e}")

        # 9. Mark Complete
        try:
            _get_db().table('races').update({'ingestion_status': 'COMPLETE', 'updated_at': 'now()'}).eq('id', race_id).execute()
            logger.info(f"Enhanced Ingestion complete for {year} Round {race_round}")
        except Exception as e:
            logger.error("Failed to mark ingestion complete", exc_info=True)


def _ingest_basic_info(session, year, race_round):
    """Ingest Season, Circuit, and Race metadata."""
    try:
        # Season
        if year not in ID_CACHE['seasons']:
            res = _get_db().table('seasons').select('year').eq('year', year).execute()
            if not res.data:
                _get_db().table('seasons').insert({'year': year}).execute()
            ID_CACHE['seasons'][year] = True

        # Circuit
        circuit_ref = session.event.EventName.replace(" ", "_").lower()
        circuit_data = {
            'ergast_circuit_id': circuit_ref,
            'name': session.event.EventName,
            'location': session.event.Location,
            'country': session.event.Country,
            'lat': 0, 'lng': 0
        }
        circuit_id = resolve_id('circuits', 'ergast_circuit_id', circuit_ref, circuit_data)

        # Race
        race_ref = f"{year}_{race_round}_{circuit_ref}"
        race_db_data = {
            'season_year': year,
            'round': race_round,
            'name': session.event.EventName,
            'race_date': session.date.strftime('%Y-%m-%d'),
            'race_time': session.date.strftime('%H:%M:%S'),
            'circuit_id': circuit_id,
            'ergast_race_id': race_ref,
            'ingestion_status': 'PENDING'
        }
        
        resolve_id('races', 'ergast_race_id', race_ref, race_db_data)
        
    except Exception as e:
        raise IngestionError("Failed to ingest basic race info", details={"error": str(e)})


def _ingest_drivers(session) -> Dict[str, str]:
    """Ingest drivers and return map of Abbreviation -> UUID."""
    driver_map = {} 
    for drv in session.drivers:
        try:
            drv_info = session.get_driver(drv)
            if drv_info is None or pd.isna(drv_info['Abbreviation']):
                continue
                
            d_ref = drv_info['Abbreviation'].lower()
            
            # Validate with Schema
            driver_data = DriverCreate(
                code=drv_info['Abbreviation'],
                given_name=drv_info['FirstName'],
                family_name=drv_info['LastName'],
                nationality=drv_info['CountryCode'],
                ergast_driver_id=d_ref
            )
            
            d_id = resolve_id('drivers', 'ergast_driver_id', d_ref, driver_data.model_dump())
            if d_id:
                driver_map[drv_info['Abbreviation']] = d_id
                
        except Exception as e:
            logger.warning(f"Failed to process driver {drv}: {e}")
            continue
            
    return driver_map


def _process_laps(session, race_id, driver_map):
    """Process and upsert laps."""
    logger.info("Processing Laps (Vectorized)...")
    laps = session.laps
    
    if laps.empty:
        logger.warning("No laps data in session")
        return
        
    laps['LapNumber'] = pd.to_numeric(laps['LapNumber'])
    total_laps_in_race = laps['LapNumber'].max()
    
    # Vectorized Gap & Fuel
    leader_times = laps[laps['Position'] == 1][['LapNumber', 'Time']].set_index('LapNumber')['Time']
    laps['LeaderTime'] = laps['LapNumber'].map(leader_times)
    laps['GapToLeader'] = (laps['Time'] - laps['LeaderTime']).dt.total_seconds().fillna(0)
    
    if total_laps_in_race > 0:
        laps['FuelLoad'] = 110.0 * (1.0 - (laps['LapNumber'] / total_laps_in_race))
    else:
        laps['FuelLoad'] = 0.0

    laps_to_upload = []
    errors_count = 0

    # Get unique drivers from lap data
    unique_drivers = laps['Driver'].unique()
    logger.info(f"Found {len(unique_drivers)} drivers with lap data")

    for d_abbrev in unique_drivers:
        d_id = driver_map.get(d_abbrev)
        if not d_id:
            logger.debug(f"Driver {d_abbrev} not in driver_map, skipping")
            continue

        d_laps = laps[laps['Driver'] == d_abbrev].copy()
        
        for _, lap in d_laps.iterrows():
            try:
                def to_ms(td):
                    """Convert timedelta to milliseconds."""
                    if pd.notnull(td):
                        return int(td.total_seconds() * 1000)
                    return None

                # Create lap dict with milliseconds for times
                lap_dict = {
                    'race_id': race_id,
                    'driver_id': d_id,
                    'lap_number': int(lap['LapNumber']),
                    'lap_time_ms': to_ms(lap['LapTime']),
                    'sector_1_ms': to_ms(lap['Sector1Time']),
                    'sector_2_ms': to_ms(lap['Sector2Time']),
                    'sector_3_ms': to_ms(lap['Sector3Time']),
                    'compound': str(lap['Compound']) if pd.notnull(lap['Compound']) else None,
                    'tyre_life': int(lap['TyreLife']) if pd.notnull(lap['TyreLife']) else None,
                    'fresh_tyre': bool(lap['FreshTyre']) if pd.notnull(lap['FreshTyre']) else None,
                    'track_status': str(lap['TrackStatus']) if pd.notnull(lap['TrackStatus']) else None,
                    'is_accurate': bool(lap['IsAccurate']) if pd.notnull(lap['IsAccurate']) else None,
                    'position': int(lap['Position']) if pd.notnull(lap['Position']) else None,
                    'gap_to_leader_ms': int(lap['GapToLeader'] * 1000) if pd.notnull(lap['GapToLeader']) else None,
                    'fuel_load': float(lap['FuelLoad']) if pd.notnull(lap['FuelLoad']) else None
                }
                
                laps_to_upload.append(lap_dict)

            except Exception as e:
                errors_count += 1
                if errors_count <= 5:  # Only log first 5 errors
                    logger.warning(f"Error processing lap {lap.get('LapNumber', '?')} for {d_abbrev}: {e}")

    logger.info(f"Collected {len(laps_to_upload)} laps (errors: {errors_count})")
    
    if laps_to_upload:
        _bulk_upsert('laps', laps_to_upload, 'race_id,driver_id,lap_number')


def _process_telemetry(session, race_id, driver_map):
    """Process and upsert telemetry stats."""
    logger.info("Processing Telemetry...")
    telemetry_to_upload = []
    
    for drv in session.drivers:
        if drv not in session.results['Abbreviation'].values: continue
        d_id = driver_map.get(session.get_driver(drv)['Abbreviation'])
        if not d_id: continue

        try:
            d_laps = session.laps.pick_driver(drv).pick_accurate()
            car_data = session.car_data[drv]
            if car_data is None or car_data.empty: continue

            for _, lap in d_laps.iterrows():
                t_start = lap['LapStartTime']
                t_end = lap['Time']
                if pd.isnull(t_start) or pd.isnull(t_end): continue

                mask = (car_data['Time'] >= t_start) & (car_data['Time'] <= t_end)
                lap_tel = car_data.loc[mask]
                
                if lap_tel.empty: continue
                
                stats = TelemetryStats(
                    race_id=race_id,
                    driver_id=d_id,
                    lap_number=int(lap['LapNumber']),
                    speed_max=float(lap_tel['Speed'].max()),
                    speed_avg=float(lap_tel['Speed'].mean()),
                    throttle_avg=float(lap_tel['Throttle'].mean()),
                    brake_avg=float(lap_tel['Brake'].mean()),
                    gear_shifts=int(lap_tel['nGear'].diff().abs().sum() / 2)
                )
                telemetry_to_upload.append(stats.model_dump())
                
        except Exception as e:
            logger.debug(f"Telemetry skipped for {drv}: {e}")

    if telemetry_to_upload:
        _bulk_upsert('telemetry_stats', telemetry_to_upload, 'race_id, driver_id, lap_number')


def _process_results(session, race_id, driver_map):
    """Process and upsert race results with validation."""
    logger.info("Processing Results...")
    results_batch = []
    
    # Iterate directly over session.results DataFrame
    for _, row in session.results.iterrows():
        d_abbrev = row.get('Abbreviation')
        if pd.isna(d_abbrev):
            continue
        
        d_id = driver_map.get(d_abbrev)
        if not d_id:
            logger.debug(f"Driver {d_abbrev} not in driver_map")
            continue
        
        try:
            result = RaceResultCreate(
                race_id=race_id,
                driver_id=d_id,
                position=int(row['Position']) if pd.notnull(row.get('Position')) else None,
                grid=int(row['GridPosition']) if pd.notnull(row.get('GridPosition')) else None,
                points=float(row['Points']) if pd.notnull(row.get('Points')) else 0.0,
                status=str(row['Status']) if pd.notnull(row.get('Status')) else 'Finished',
                laps_completed=int(row['LapsCompleted']) if pd.notnull(row.get('LapsCompleted')) else None
            )
            results_batch.append(result.model_dump(exclude_unset=True))
        except Exception as e:
            logger.warning(f"Invalid result for {d_abbrev}: {e}")

    logger.info(f"Collected {len(results_batch)} race results")
    
    if results_batch:
        _bulk_upsert('race_results', results_batch, 'race_id,driver_id')


def _process_pit_stops(session, race_id, driver_map):
    """Process pit stops."""
    logger.info("Processing Pit Stops...")
    stops = []
    pit_laps = session.laps.dropna(subset=['PitInTime', 'PitOutTime'], how='all')
    
    for _, lap in pit_laps.iterrows():
        d_id = driver_map.get(lap['Driver'])
        if not d_id: continue
        
        duration = lap.get('PitDuration')
        if pd.isnull(duration) and pd.notnull(lap['PitOutTime']) and pd.notnull(lap['PitInTime']):
            duration = lap['PitOutTime'] - lap['PitInTime']

        if pd.notnull(duration):
            duration_ms = int(duration.total_seconds() * 1000) if hasattr(duration, 'total_seconds') else int(duration * 1000)
            stops.append({
                'race_id': race_id,
                'driver_id': d_id,
                'lap_number': int(lap['LapNumber']),
                'duration_ms': duration_ms
            })
            
    if stops:
        try:
            _get_db().table('pit_stops').insert(stops).execute()
        except Exception as e:
            logger.error(f"Error inserting pit stops: {e}")


def _process_telemetry_cache(session, race_id, year, round_num):
    """
    Pre-compute visualization frames and store in DB for instant loading.
    Uses zlib compression to minimize storage.
    """
    logger.info("Processing Telemetry Cache (Supabase)...")
    from utils.race_visualization import build_race_frames, get_driver_colors, get_circuit_rotation, _get_track_statuses, _build_frames_fast_mode
    import zlib
    import json
    
    drivers = session.drivers
    laps = session.laps
    
    if laps.empty: return

    # Get driver codes
    driver_codes = {}
    for num in drivers:
        try:
            driver_codes[num] = session.get_driver(num)["Abbreviation"]
        except:
            driver_codes[num] = f"#{num}"
            
    max_lap = int(laps['LapNumber'].max())
    
    # Build frames (FULL MODE)
    # Note: We force FULL mode computation here
    try:
        frames = build_race_frames(session, drivers, driver_codes, max_lap)
    except Exception as e:
        logger.warning(f"Full telemetry build failed, falling back to fast mode: {e}")
        frames = _build_frames_fast_mode(session, drivers, driver_codes, laps, max_lap)
    
    if not frames:
        logger.warning("No frames generated")
        return

    # Prepare data object
    result = {
        "frames": frames,
        "driver_colors": get_driver_colors(session),
        "track_statuses": _get_track_statuses(session), # Track status list
        "total_laps": max_lap,
        "circuit_rotation": get_circuit_rotation(session),
        "event_name": session.event['EventName']
    }
    
    # Get track coordinates (same logic as visualization)
    try:
        fastest = laps.pick_fastest()
        if fastest is not None:
             tel = fastest.get_telemetry()
             if tel is not None and not tel.empty and 'X' in tel.columns:
                 result["track_coords"] = {
                     "x": tel['X'].iloc[::5].tolist(),
                     "y": tel['Y'].iloc[::5].tolist()
                 }
             else:
                 result["track_coords"] = {"x": [], "y": []}
    except:
        result["track_coords"] = {"x": [], "y": []}

    # Compress frames_data (the large part)
    # We strip frames out of result to compress separately if needed, 
    # but the schema expects `frames_data` as bytea.
    # Actually, let's look at the schema plan: "frames_data BYTEA"
    # So we compress the LIST of frames.
    
    frames_json = json.dumps(frames)
    frames_compressed = zlib.compress(frames_json.encode('utf-8'), level=9)
    
    # Upsert to DB
    data = {
        'race_id': race_id,
        'session_type': 'R', # Assuming Race for now
        'total_laps': max_lap,
        'total_frames': len(frames),
        'driver_colors': result['driver_colors'],
        'track_coords': result['track_coords'],
        'circuit_rotation': float(result['circuit_rotation']),
        'event_name': result['event_name'],
        'track_statuses': result['track_statuses'], # Added field
        'season_year': year, # Add year/round for easier querying
        'round': round_num,
        'frames_data': frames_compressed.hex() # Send as hex string for bytea compatibility via PostgREST
    }
    
    # Use simple Insert (Upsert needs conflict handling)
    # Use simple Insert (Upsert needs conflict handling)
    # Conflict on (race_id, session_type)
    
    # Retry logic for Supabase 5xx errors
    import time
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            _get_db().table('race_telemetry_cache').upsert(data, on_conflict='race_id, session_type').execute()
            logger.info(f"Telemetry cache stored for {year} R{round_num} ({len(frames)} frames)")
            break
        except Exception as e:
            error_str = str(e)
            if attempt < max_retries - 1 and ('520' in error_str or '521' in error_str or '500' in error_str or 'JSON' in error_str):
                delay = 5 * (attempt + 1)
                logger.warning(f"Supabase upsert failed (Attempt {attempt+1}/{max_retries}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed to upsert telemetry cache after {max_retries} attempts: {e}")
                raise e


def _bulk_upsert(table, data, conflict_columns):
    """Helper for chunked upserts. Uses insert with ignore_duplicates for reliability."""
    chunk_size = 500  # Reduced chunk size for more reliable inserts
    total = len(data)
    inserted = 0
    
    logger.info(f"Bulk inserting {total} rows into {table}...")
    
    for i in range(0, total, chunk_size):
        chunk = data[i:i+chunk_size]
        try:
            # Use upsert with ignore_duplicates=False to update on conflict
            # The on_conflict param should match the UNIQUE constraint columns
            result = _get_db().table(table).upsert(
                chunk, 
                on_conflict=conflict_columns,
                ignore_duplicates=False
            ).execute()
            inserted += len(result.data) if result.data else 0
        except Exception as e:
            # On upsert failure, fallback to individual inserts with ignore
            logger.warning(f"Bulk upsert failed for {table}, trying individual inserts: {e}")
            for row in chunk:
                try:
                    _get_db().table(table).upsert(row, on_conflict=conflict_columns).execute()
                    inserted += 1
                except Exception as row_e:
                    logger.debug(f"Row insert failed: {row_e}")
    
    logger.info(f"Inserted {inserted}/{total} rows into {table}")


def ingest_qualifying_results(year: int, race_round: int):
    """Ingest qualifying results to populate the grid."""
    logger.info(f"Starting QUALIFYING ingestion for {year} Round {race_round}")
    
    try:
        session = fastf1.get_session(year, race_round, 'Q')
        session.load()
    except Exception as e:
        logger.error(f"Failed to load qualifying: {e}")
        return

    # Find Race ID
    circuit_ref = session.event.EventName.replace(" ", "_").lower()
    race_ref = f"{year}_{race_round}_{circuit_ref}"
    race_id = resolving_race_id_helper(race_ref, year, race_round)
    
    if not race_id:
        logger.error("Race not found for qualifying ingestion.")
        return

    # Process
    driver_map = _ingest_drivers(session)
    results_batch = []

    for drv in session.drivers:
        if drv not in session.results['Abbreviation'].values: continue
        d_id = driver_map.get(session.get_driver(drv)['Abbreviation'])
        if not d_id: continue
        
        d_info = session.get_driver(drv)
        if pd.notnull(d_info.get('Position')):
            results_batch.append({
                'race_id': race_id,
                'driver_id': d_id,
                'grid': int(d_info['Position']),
                'status': 'Qualified'
            })
            
    if results_batch:
        _bulk_upsert('race_results', results_batch, 'race_id, driver_id')
        logger.info(f"Ingested {len(results_batch)} qualifying results")


def resolving_race_id_helper(race_ref, year, round_num):
    try:
        res = _get_db().table('races').select('id').eq('ergast_race_id', race_ref).execute()
        if res.data: return res.data[0]['id']
        
        res = _get_db().table('races').select('id').eq('season_year', year).eq('round', round_num).execute()
        if res.data: return res.data[0]['id']
    except:
        pass
    return None

if __name__ == "__main__":
    # Test run
    try:
        ingest_enhanced_race_data(2024, 1)
    except Exception as e:
        logger.error(f"Ingestion script failed: {e}")
