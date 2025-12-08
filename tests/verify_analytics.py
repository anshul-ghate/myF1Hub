import pandas as pd
import numpy as np
import joblib
import os
import sys
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_supabase_client
from models.feature_engineering import fetch_race_data, preprocess_features

def verify_model_performance(race_year=2023, race_round=1):
    print(f"🔍 Verifying Analytics for {race_year} Round {race_round}...")
    
    # 1. Load Model
    model_path = 'models/saved/lap_time_model.pkl'
    if not os.path.exists(model_path):
        print("❌ Model not found. Please train the model first.")
        return
    
    model = joblib.load(model_path)
    print("✅ Model loaded.")
    
    # 2. Fetch Data
    supabase = get_supabase_client()
    # Find race_id
    res = supabase.table('races').select('id').eq('season_year', race_year).eq('round', race_round).execute()
    if not res.data:
        print("❌ Race not found in database.")
        return
        
    race_id = res.data[0]['id']
    
    laps, weather = fetch_race_data(race_id)
    if laps.empty:
        print("❌ No lap data found for this race.")
        return
        
    print(f"✅ Fetched {len(laps)} laps.")
    
    # 3. Preprocess
    X, y_true = preprocess_features(laps, weather)
    
    if X.empty:
        print("❌ No valid features extracted.")
        return
        
    # 4. Predict
    # Align columns with model
    model_features = model.get_booster().feature_names
    
    # Add missing columns with 0
    for col in model_features:
        if col not in X.columns:
            X[col] = 0
            
    # Reorder columns to match model
    X = X[model_features]
    
    try:
        y_pred = model.predict(X)
    except Exception as e:
        print(f"❌ Prediction failed: {e}")
        return
        
    # 5. Evaluate
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    
    print("\n📊 Performance Report:")
    print(f"   - Mean Absolute Error (MAE): {mae:.3f} s")
    print(f"   - Root Mean Squared Error (RMSE): {rmse:.3f} s")
    
    if mae < 2.0: # Arbitrary threshold for "good enough" for MVP
        print("\n✅ Analytics Verification PASSED. Model is providing reasonable estimates.")
    else:
        print("\n⚠️ Analytics Verification WARNING. Model error is high.")

if __name__ == "__main__":
    # Test on Spanish Grand Prix 2018 (Available in DB)
    verify_model_performance(2018, 5)
