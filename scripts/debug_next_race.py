import sys
import os
import pandas as pd
from utils.race_utils import get_next_upcoming_race
from models.hybrid_predictor import HybridPredictor
import traceback

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)

def debug_next_race():
    print("🔍 Debugging Next Race Prediction...")
    
    # 1. Check Next Race Logic
    try:
        next_race = get_next_upcoming_race()
        if not next_race:
            print("❌ get_next_upcoming_race() returned None.")
            return
        
        print(f"✅ Found Next Race: {next_race.get('name')} ({next_race.get('season_year')})")
        print(f"   ID: {next_race.get('id')}")
        print(f"   Date: {next_race.get('date')}")
        
    except Exception as e:
        print(f"❌ Error getting next race: {e}")
        traceback.print_exc()
        return

    # 2. Initialize Predictor
    try:
        print("\nInitializing HybridPredictor...")
        predictor = HybridPredictor()
    except Exception as e:
        print(f"❌ Error initializing predictor: {e}")
        traceback.print_exc()
        return

    # 3. Run Prediction
    try:
        print(f"\nRunning prediction for {next_race['name']}...")
        results = predictor.predict_race(
            year=next_race['season_year'],
            race_name=next_race['name'],
            weather_forecast='Dry',
            n_sims=100 # Low number for quick debug
        )
        
        if results is not None and not results.empty:
            print("\n✅ Prediction Successful!")
            print(results.head())
        else:
            print("\n❌ Prediction returned None or empty.")
            
    except Exception as e:
        print(f"\n❌ Prediction crashed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    with open('debug_log.txt', 'w', encoding='utf-8') as f:
        sys.stdout = f
        sys.stderr = f
        debug_next_race()
