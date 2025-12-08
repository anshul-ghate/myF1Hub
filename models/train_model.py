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
    
    print(f"Training on {len(train_races)} races, Testing on {len(test_races)} races.")
    
    # Hyperparameter Tuning with RandomizedSearchCV
    from sklearn.model_selection import RandomizedSearchCV
    
    # Define parameter grid
    param_grid = {
        'n_estimators': [100, 200, 300, 500],
        'learning_rate': [0.01, 0.05, 0.1, 0.2],
        'max_depth': [3, 5, 7, 9],
        'subsample': [0.6, 0.8, 1.0],
        'colsample_bytree': [0.6, 0.8, 1.0],
        'min_child_weight': [1, 3, 5]
    }
    
    xgb_model = xgb.XGBRegressor(objective='reg:squarederror', random_state=42)
    
    # Randomized Search
    print("Starting hyperparameter tuning...")
    random_search = RandomizedSearchCV(
        estimator=xgb_model,
        param_distributions=param_grid,
        n_iter=20, # Number of parameter settings that are sampled
        scoring='neg_mean_absolute_error',
        cv=3,
        verbose=1,
        random_state=42,
        n_jobs=-1
    )
    
    random_search.fit(X_train, y_train)
    
    print(f"Best parameters found: {random_search.best_params_}")
    print(f"Best CV MAE: {-random_search.best_score_:.3f} s")
    
    # Train best model on full training set (RandomizedSearchCV refits automatically, but good to be explicit/verify)
    best_model = random_search.best_estimator_
    
    # Evaluate
    preds = best_model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    
    print(f"Model Tuned & Trained. Test MAE: {mae:.3f} s, RMSE: {rmse:.3f} s")
    
    # Save Model
    if not os.path.exists('models/saved'):
        os.makedirs('models/saved')
    joblib.dump(best_model, 'models/saved/lap_time_model.pkl')
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
