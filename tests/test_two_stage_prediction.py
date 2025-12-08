import sys
import os
import pandas as pd
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.simulation import RaceSimulator

def test_two_stage_prediction():
    print("🧪 Testing Two-Stage Prediction Logic...")
    
    # Initialize Simulator
    sim = RaceSimulator()
    
    # Mock Data
    race_id = "test_race_id"
    driver_ids = ["d1", "d2", "d3"]
    
    # Mock get_race_drivers to return a DataFrame
    sim.get_race_drivers = MagicMock(return_value=pd.DataFrame({
        'id': driver_ids,
        'code': ['VER', 'NOR', 'HAM']
    }))
    
    # Mock model (so we don't need actual model file)
    sim.model = MagicMock()
    sim.model.feature_names_in_ = ['grid', 'recent_form', 'constructor_strength'] # Example features
    sim.model.predict.return_value = [80.0, 81.0, 82.0] # Dummy lap times
    
    # --- TEST CASE 1: Qualifying Unavailable (Predict Grid) ---
    print("\n📋 Test Case 1: Qualifying Unavailable (Should Predict Grid)")
    
    # Mock get_qualifying_positions to return empty dict
    sim.get_qualifying_positions = MagicMock(return_value={})
    
    # Mock predict_qualifying to return specific values
    sim.predict_qualifying = MagicMock(return_value={'d1': 1, 'd2': 2, 'd3': 3})
    
    # Run Simulation
    # We mock the actual simulation loop part or just check if predict_qualifying was called
    # Since simulate_race is complex, let's just run it and catch the print output or check mocks
    
    # We need to mock Supabase calls inside simulate_race if any (e.g. for weights)
    sim.supabase = MagicMock()
    sim.supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {'date': '2025-01-01', 'season_year': 2025}
    
    try:
        sim.simulate_race(race_id)
    except Exception as e:
        # It might fail later in the loop due to missing features/model, but we check the flow before that
        pass
        
    # Verify predict_qualifying was called
    if sim.predict_qualifying.called:
        print("✅ SUCCESS: predict_qualifying() was called when grid was empty.")
    else:
        print("❌ FAILURE: predict_qualifying() was NOT called.")

    # --- TEST CASE 2: Qualifying Available (Use Actual Grid) ---
    print("\n📋 Test Case 2: Qualifying Available (Should Use Actual Grid)")
    
    # Reset mocks
    sim.predict_qualifying.reset_mock()
    
    # Mock get_qualifying_positions to return actual grid
    sim.get_qualifying_positions = MagicMock(return_value={'d1': 10, 'd2': 11, 'd3': 12})
    
    try:
        sim.simulate_race(race_id)
    except Exception:
        pass
        
    # Verify predict_qualifying was NOT called
    if not sim.predict_qualifying.called:
        print("✅ SUCCESS: predict_qualifying() was NOT called when grid existed.")
    else:
        print("❌ FAILURE: predict_qualifying() WAS called despite grid existing.")

if __name__ == "__main__":
    test_two_stage_prediction()
