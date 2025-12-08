import pandas as pd
from models.simulation import RaceSimulator
from utils.db import get_supabase_client

def validate_race_prediction(race_name_pattern, year=2024):
    supabase = get_supabase_client()
    
    # 1. Find the race
    res = supabase.table('races').select('id, name, season_year, round').eq('season_year', year).ilike('name', f'%{race_name_pattern}%').execute()
    
    if not res.data:
        print(f"Race not found: {race_name_pattern} {year}")
        return
        
    race = res.data[0]
    race_id = race['id']
    print(f"Validating Prediction for: {race['season_year']} {race['name']}")
    
    # 2. Get Actual Results (from FastF1 since 'results' table might be missing)
    import fastf1
    try:
        session = fastf1.get_session(year, race['round'], 'R')
        session.load()
        actual_results = session.results
        actual_results['Driver'] = actual_results['Abbreviation']
        print("\nActual Top 5:")
        print(actual_results[['Driver', 'Position']].head(5))
    except Exception as e:
        print(f"Error loading FastF1 data: {e}")
        return

    # 3. Run Simulation
    print("\nRunning Simulation...")
    simulator = RaceSimulator()
    
    # Get lap count
    laps_res = supabase.table('laps').select('lap_number').eq('race_id', race_id).order('lap_number', desc=True).limit(1).execute()
    total_laps = laps_res.data[0]['lap_number'] if laps_res.data else 57
    
    results, driver_codes = simulator.simulate_race(race_id, total_laps=total_laps, n_simulations=100)
    
    if not results:
        print("Simulation failed.")
        return
        
    agg_df = simulator.aggregate_results(results, driver_codes)
    
    print("\nPredicted Top 5 (Most Likely Winner):")
    print(agg_df[['Driver', 'Win %', 'Avg Pos']].head(5))
    
    # 4. Compare
    print("\n--- Accuracy Analysis ---")
    correct_top_10 = 0
    top_10_drivers = actual_results.head(10)['Driver'].tolist()
    predicted_top_10 = agg_df.head(10)['Driver'].tolist()
    
    for d in predicted_top_10:
        if d in top_10_drivers:
            correct_top_10 += 1
            
    print(f"Top 10 Overlap: {correct_top_10}/10")
    
    # Check Winner
    actual_winner = actual_results.iloc[0]['Driver']
    predicted_winner = agg_df.iloc[0]['Driver']
    print(f"Winner Correct? {'✅' if actual_winner == predicted_winner else '❌'} (Actual: {actual_winner}, Predicted: {predicted_winner})")

if __name__ == "__main__":
    # Validate Sao Paulo 2025
    validate_race_prediction("São Paulo", 2025)
