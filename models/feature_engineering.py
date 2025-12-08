import pandas as pd
import numpy as np
import time
import logging
from utils.db import get_supabase_client

logger = logging.getLogger(__name__)

def fetch_race_data(race_id, max_retries=3, base_delay=2.0):
    """
    Fetch race data from Supabase with retry logic for transient network errors.
    
    Args:
        race_id: The race ID to fetch data for
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 2.0)
    
    Returns:
        Tuple of (laps_df, weather_df) DataFrames
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            supabase = get_supabase_client()
            
            # Fetch Laps
            laps_res = supabase.table('laps').select('*').eq('race_id', race_id).execute()
            laps_df = pd.DataFrame(laps_res.data)
            
            # Fetch Weather
            weather_res = supabase.table('weather').select('*').eq('race_id', race_id).execute()
            weather_df = pd.DataFrame(weather_res.data)
            
            return laps_df, weather_df
            
        except Exception as e:
            last_exception = e
            error_msg = str(e).lower()
            
            # Check if it's a retryable network error
            retryable = any(msg in error_msg for msg in [
                'connection', 'timeout', '10054', 'reset', 'closed',
                'network', 'eof', 'broken pipe', 'readerror'
            ])
            
            if retryable and attempt < max_retries:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Network error fetching race {race_id} (attempt {attempt + 1}/{max_retries + 1}): {e}")
                logger.info(f"Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
            else:
                # Not retryable or max retries exceeded
                break
    
    # If we get here, all retries failed
    logger.error(f"Failed to fetch race data for race {race_id} after {max_retries + 1} attempts: {last_exception}")
    raise last_exception

def preprocess_features(laps_df, weather_df):
    if laps_df.empty:
        return pd.DataFrame(), pd.Series()  # Return empty DataFrame and Series for X and y
        
    # Convert timestamps
    # weather 'timestamp' is iso string
    if not weather_df.empty:
        weather_df['timestamp'] = pd.to_datetime(weather_df['timestamp'])
        weather_df = weather_df.sort_values('timestamp')
    
    # We don't have exact timestamps for every lap in the 'laps' table currently (only lap time).
    # In a real scenario, we would have 'time_of_day' for each lap start/end.
    # For this MVP, we might have to approximate or use race-level averages if lap timestamps are missing.
    # BUT, FastF1 data usually has 'Time' (session time) or 'LapStartTime'. 
    # Our schema has 'lap_time' (interval). 
    # Let's assume for now we use static weather or average for the race, 
    # OR we improve ingestion to include 'lap_start_time' to merge with weather.
    
    # Let's stick to lap-based features for now:
    # - Tyre Life
    # - Compound (One-Hot)
    # - Track Status
    # - Previous Lap Time (for autoregression)
    
    # Filter out non-racing laps (SC, VSC, In/Out laps)
    # TrackStatus '1' is Green.
    df = laps_df[laps_df['track_status'] == '1'].copy()
    df = df[df['is_accurate'] == True].copy() # Only accurate laps
    
    # Convert Interval strings to seconds
    # Postgres interval format might be "00:01:35.123" or similar. 
    # Pandas might read it as string.
    def parse_interval(x):
        if x is None: return None
        # Simple parser if it comes as string "HH:MM:SS.ssss"
        try:
            return pd.to_timedelta(x).total_seconds()
        except:
            return None

    df['lap_time_s'] = df['lap_time'].apply(parse_interval)
    df = df.dropna(subset=['lap_time_s'])
    
    # One-Hot Encode Compound
    # Compounds: SOFT, MEDIUM, HARD, INTERMEDIATE, WET
    compounds = pd.get_dummies(df['compound'], prefix='tyre').astype(int)
    df = pd.concat([df, compounds], axis=1)

    # One-Hot Encode Driver and Team
    driver_dummies = pd.DataFrame()
    if 'driver' in df.columns:
        driver_dummies = pd.get_dummies(df['driver'], prefix='driver').astype(int)
        df = pd.concat([df, driver_dummies], axis=1)
    
    team_dummies = pd.DataFrame()
    if 'team' in df.columns:
        team_dummies = pd.get_dummies(df['team'], prefix='team').astype(int)
        df = pd.concat([df, team_dummies], axis=1)
        
    # Autoregression: Add Previous Lap Time
    # We need to sort by driver and lap number to ensure correct shifting
    if 'driver' in df.columns:
        df = df.sort_values(['driver', 'lap_number'])
        df['prev_lap_time'] = df.groupby('driver')['lap_time_s'].shift(1)
    else:
        # Fallback if no driver column (shouldn't happen with correct data)
        df = df.sort_values(['lap_number'])
        df['prev_lap_time'] = df['lap_time_s'].shift(1)
        
    # Drop the first lap of each group (where prev_lap_time is NaN)
    df = df.dropna(subset=['prev_lap_time'])
    
    # Select features and target
    # Now including enhanced features: fuel_load, gap_to_leader, position, driver_*, team_*, prev_lap_time
    base_features = ['lap_number', 'tyre_life', 'fuel_load', 'gap_to_leader', 'position', 'prev_lap_time']
    
    # Ensure base features are numeric
    for col in base_features:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    features = base_features + list(compounds.columns) + list(driver_dummies.columns) + list(team_dummies.columns)
    
    # Fill NaNs for new features if any (e.g. first lap gap might be 0 or NaN)
    # (Already handled by to_numeric fillna above for base features)
    
    X = df[features]
    y = df['lap_time_s']
    
    return X, y

if __name__ == "__main__":
    # Test fetching (requires data in DB)
    pass
