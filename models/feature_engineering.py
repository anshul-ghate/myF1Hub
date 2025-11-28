import pandas as pd
import numpy as np
from utils.db import get_supabase_client

def fetch_race_data(race_id):
    supabase = get_supabase_client()
    
    # Fetch Laps
    # We need to join with weather if possible, or fetch separately and merge on timestamp
    # For simplicity, let's fetch laps and weather separately
    
    laps_res = supabase.table('laps').select('*').eq('race_id', race_id).execute()
    laps_df = pd.DataFrame(laps_res.data)
    
    # Fetch Weather
    weather_res = supabase.table('weather').select('*').eq('race_id', race_id).execute()
    weather_df = pd.DataFrame(weather_res.data)
    
    return laps_df, weather_df

def preprocess_features(laps_df, weather_df):
    if laps_df.empty:
        return pd.DataFrame()
        
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
import pandas as pd
import numpy as np
from utils.db import get_supabase_client

def fetch_race_data(race_id):
    supabase = get_supabase_client()
    
    # Fetch Laps
    # We need to join with weather if possible, or fetch separately and merge on timestamp
    # For simplicity, let's fetch laps and weather separately
    
    laps_res = supabase.table('laps').select('*').eq('race_id', race_id).execute()
    laps_df = pd.DataFrame(laps_res.data)
    
    # Fetch Weather
    weather_res = supabase.table('weather').select('*').eq('race_id', race_id).execute()
    weather_df = pd.DataFrame(weather_res.data)
    
    return laps_df, weather_df

def preprocess_features(laps_df, weather_df):
    if laps_df.empty:
        return pd.DataFrame(), pd.Series() # Return empty DataFrame and Series for X and y
        
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
    
    # Select features and target
    # Now including enhanced features: fuel_load, gap_to_leader, position
    features = ['lap_number', 'tyre_life', 'fuel_load', 'gap_to_leader', 'position'] + \
               [c for c in df.columns if c.startswith('tyre_') and c != 'tyre_life']
    
    # Fill NaNs for new features if any (e.g. first lap gap might be 0 or NaN)
    df['fuel_load'] = df['fuel_load'].fillna(0)
    df['gap_to_leader'] = df['gap_to_leader'].fillna(0)
    df['position'] = df['position'].fillna(20) # Default to back if unknown
    
    X = df[features]
    y = df['lap_time_s']
    
    return X, y

if __name__ == "__main__":
    # Test fetching (requires data in DB)
    pass
