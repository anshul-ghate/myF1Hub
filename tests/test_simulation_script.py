import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
from models.simulation import RaceSimulator
from utils.db import get_supabase_client

# Mock Supabase for testing if needed, or rely on real DB if available
# For this test, we'll try to run it against the real DB if configured, 
# otherwise we might need to mock. Assuming DB is accessible as per user context.

def test_simulation():
    print("Initializing RaceSimulator...")
    sim = RaceSimulator()
    
    if not sim.model:
        print("⚠️ Model not loaded. Skipping simulation test.")
        return

    # Fetch a recent race ID to test with
    supabase = get_supabase_client()
    # Get the last race of 2023 or 2024
    res = supabase.table('races').select('id, name, season_year').eq('season_year', 2023).limit(1).execute()
    
    if not res.data:
        print("No race found for testing.")
        return
        
    race_id = res.data[0]['id']
    race_name = res.data[0]['name']
    print(f"Testing simulation for: {race_name} (ID: {race_id})")
    
    print("Running simulate_race...")
    try:
        results, driver_codes = sim.simulate_race(race_id, n_simulations=10)
        
        if results:
            print("Simulation successful!")
            print(f"Generated {len(results)} simulation results.")
            
            agg_df = sim.aggregate_results(results, driver_codes)
            print("\nAggregated Results (Top 5):")
            print(agg_df.head())
            
            # Basic Validation
            if 'DNF %' in agg_df.columns:
                print("[OK] DNF column present.")
            else:
                print("[FAIL] DNF column missing.")
                
            if agg_df['Win %'].sum() > 99.0: # Should be approx 100
                print("[OK] Win probabilities sum to ~100%.")
            else:
                print(f"[FAIL] Win probabilities sum to {agg_df['Win %'].sum()}%.")
                
        else:
            print("[FAIL] Simulation returned no results.")
            
    except Exception as e:
        print(f"[FAIL] Simulation failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simulation()
