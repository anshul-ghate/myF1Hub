import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import os
from models.feature_engineering import fetch_race_data, preprocess_features
from utils.db import get_supabase_client

def train_model(race_ids):
    all_X = []
    all_y = []
    
    for rid in race_ids:
        laps, weather = fetch_race_data(rid)
        if laps.empty:
            continue
            
        X, y = preprocess_features(laps, weather)
        if not X.empty:
            X['race_id'] = rid # Add race_id for splitting
            all_X.append(X)
            all_y.append(y)
            
    if not all_X:
        print("No data found for training.")
        return
        
    X_full = pd.concat(all_X)
    y_full = pd.concat(all_y)
    
    # Train/Test Split by Race ID to prevent leakage
    # We want to test on unseen races, not random laps from seen races
    unique_races = X_full['race_id'].unique()
    train_races, test_races = train_test_split(unique_races, test_size=0.2, random_state=42)
    
    # Create masks
    train_mask = X_full['race_id'].isin(train_races)
    test_mask = X_full['race_id'].isin(test_races)
    
    X_train = X_full[train_mask].drop(columns=['race_id'])
    y_train = y_full[train_mask]
    X_test = X_full[test_mask].drop(columns=['race_id'])
    y_test = y_full[test_mask]
    
    print(f"Training on {len(train_races)} races, Testing on {len(test_races)} races.")
    
    # XGBoost Regressor
    model = xgb.XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, objective='reg:squarederror')
    model.fit(X_train, y_train)
    
    # Evaluate
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    
    print(f"Model Trained. MAE: {mae:.3f} s, RMSE: {rmse:.3f} s")
    
    # Save Model
    if not os.path.exists('models/saved'):
        os.makedirs('models/saved')
    joblib.dump(model, 'models/saved/lap_time_model.pkl')
    print("Model saved to models/saved/lap_time_model.pkl")

if __name__ == "__main__":
    # Fetch all race IDs from DB
    supabase = get_supabase_client()
    res = supabase.table('races').select('id').execute()
    rids = [r['id'] for r in res.data]
    
    if rids:
        print(f"Training on {len(rids)} races...")
        train_model(rids)
    else:
        print("No races found in DB.")
