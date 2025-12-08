import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import os
from models.feature_engineering import fetch_race_data, preprocess_features
from utils.db import get_supabase_client

def evaluate():
    # Load Model
    if not os.path.exists('models/saved/lap_time_model.pkl'):
        print("Model not found.")
        return

    model = joblib.load('models/saved/lap_time_model.pkl')
    
    # Fetch Data (Same logic as train)
    supabase = get_supabase_client()
    res = supabase.table('races').select('id').execute()
    rids = [r['id'] for r in res.data]
    
    all_X = []
    all_y = []
    
    for rid in rids:
        laps, weather = fetch_race_data(rid)
        if laps.empty:
            continue
            
        X, y = preprocess_features(laps, weather)
        if not X.empty:
            X['race_id'] = rid
            all_X.append(X)
            all_y.append(y)
            
    if not all_X:
        print("No data found.")
        return
        
    X_full = pd.concat(all_X)
    y_full = pd.concat(all_y)
    
    unique_races = X_full['race_id'].unique()
    train_races, test_races = train_test_split(unique_races, test_size=0.2, random_state=42)
    
    test_mask = X_full['race_id'].isin(test_races)
    X_test = X_full[test_mask].drop(columns=['race_id'])
    y_test = y_full[test_mask]
    
    # Evaluate
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    
    print(f"Evaluation Results:")
    print(f"MAE: {mae:.3f} s")
    print(f"RMSE: {rmse:.3f} s")

if __name__ == "__main__":
    evaluate()
