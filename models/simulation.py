import numpy as np
import pandas as pd
import joblib
import logging
from utils.db import get_supabase_client
import streamlit as st

logger = logging.getLogger(__name__)

class RaceSimulator:
    def __init__(self, model_path='models/saved/lap_time_model.pkl'):
        try:
            self.model = joblib.load(model_path)
        except FileNotFoundError:
            self.model = None
            print(f"Model not found at {model_path}")
            
        self.supabase = get_supabase_client()
        
    def get_race_drivers(self, race_id):
        # Fetch drivers participating in a race
        print(f"Fetching drivers for race {race_id}...")
        res = self.supabase.table('laps').select('driver_id').eq('race_id', race_id).execute()
        driver_ids = list(set([r['driver_id'] for r in res.data]))
        print(f"Found {len(driver_ids)} drivers in laps table.")
        
        # Fallback for future races: Use drivers from the last completed race of the same season
        if not driver_ids:
            print("Using fallback logic for drivers...")
            # Get season of the requested race
            race_info = self.supabase.table('races').select('season_year, race_date').eq('id', race_id).single().execute()
            if race_info.data:
                season = race_info.data['season_year']
                date = race_info.data['race_date']
                print(f"Race season: {season}, date: {date}")
                
                # Find last race with data
                last_race = self.supabase.table('races')\
                    .select('id, name')\
                    .eq('season_year', season)\
                    .lt('race_date', date)\
                    .eq('ingestion_status', 'COMPLETE')\
                    .order('race_date', desc=True)\
                    .limit(1)\
                    .execute()
                
                if last_race.data:
                    last_race_id = last_race.data[0]['id']
                    print(f"Found last race: {last_race.data[0]['name']} ({last_race_id})")
                    res = self.supabase.table('laps').select('driver_id').eq('race_id', last_race_id).execute()
                    driver_ids = list(set([r['driver_id'] for r in res.data]))
                    print(f"Found {len(driver_ids)} drivers in fallback race.")
                else:
                    print("No previous race found in season.")

        # Final Fallback: Just get all drivers from the drivers table (Demo Mode)
        if not driver_ids:
            print("⚠️ No drivers found in race data. Fetching ALL drivers for demo.")
            res = self.supabase.table('drivers').select('id').limit(20).execute()
            driver_ids = [r['id'] for r in res.data]

        if not driver_ids:
            print("No drivers found even in drivers table.")
            return pd.DataFrame()
            
        drivers_res = self.supabase.table('drivers').select('*').in_('id', driver_ids).execute()
        return pd.DataFrame(drivers_res.data)
        
    def get_recent_form(self, driver_ids, current_race_id):
        """
        Calculate driver form based on recent race results.
        Returns a dictionary of driver_id -> form_score (0.0 to 1.0, higher is better).
        """
        form_scores = {}
        try:
            # Fetch last 5 races results for these drivers
            # We can't easily join in one query with this client, so we iterate or fetch bulk
            # Optimization: Fetch all results for these drivers in the current season
            
            # Get current season
            race_info = self.supabase.table('races').select('season_year, date').eq('id', current_race_id).single().execute()
            if not race_info.data:
                return {d: 0.5 for d in driver_ids}
            
            season = race_info.data['season_year']
            date = race_info.data['date']
            
            # Fetch results for this season prior to current race
            # This might be heavy if many races, but it's robust
            res = self.supabase.table('race_results')\
                .select('driver_id, position')\
                .lt('race_id', current_race_id)\
                .in_('driver_id', driver_ids)\
                .execute()
                
            # Group by driver
            driver_results = {d: [] for d in driver_ids}
            for r in res.data:
                if r['position']:
                    driver_results[r['driver_id']].append(r['position'])
            
            for d_id, positions in driver_results.items():
                if positions:
                    # Average position (lower is better)
                    avg_pos = sum(positions) / len(positions)
                    # Normalize to 0-1 score (1 = avg pos 1, 0 = avg pos 20)
                    score = max(0, (21 - avg_pos) / 20)
                    form_scores[d_id] = score
                else:
                    form_scores[d_id] = 0.5 # Default average form
                    
        except Exception as e:
            print(f"Error calculating form: {e}")
            return {d: 0.5 for d in driver_ids}
            
        return form_scores

    def get_qualifying_positions(self, race_id):
        """Fetch qualifying results for the race."""
        try:
            res = self.supabase.table('race_results').select('driver_id, grid').eq('race_id', race_id).execute()
            if res.data:
                return {r['driver_id']: r['grid'] for r in res.data if r['grid'] is not None}
            return {}
        except Exception:
            return {}

    def predict_qualifying(self, race_id, driver_ids):
        """Predict qualifying positions (grid) for drivers based on recent form."""
        predicted_grid = {}
        try:
            # Get current race date
            race_info = self.supabase.table('races').select('race_date, season_year').eq('id', race_id).single().execute()
            if not race_info.data:
                return {d: 10 for d in driver_ids}
                
            for d_id in driver_ids:
                # Fetch last 5 races for this driver
                res = self.supabase.table('race_results')\
                    .select('grid')\
                    .eq('driver_id', d_id)\
                    .lt('race_id', race_id)\
                    .neq('grid', None)\
                    .order('race_id', desc=True)\
                    .limit(5)\
                    .execute()
                
                grids = [r['grid'] for r in res.data if r['grid'] > 0]
                
                if grids:
                    weights = np.linspace(0.5, 1.0, len(grids))
                    avg_grid = np.average(grids, weights=weights)
                    predicted_grid[d_id] = int(round(avg_grid))
                else:
                    predicted_grid[d_id] = 10
                    
        except Exception as e:
            print(f"Error predicting qualifying: {e}")
            return {d: 10 for d in driver_ids}
            
        sorted_drivers = sorted(predicted_grid.items(), key=lambda x: x[1])
        final_grid = {}
        for i, (d_id, _) in enumerate(sorted_drivers, 1):
            final_grid[d_id] = i
            
        return final_grid

    def simulate_race(self, race_id, total_laps=57, n_simulations=100):
        if not self.model:
            logger.warning(f"No model loaded, cannot simulate race {race_id}")
            return None, None

        drivers_df = self.get_race_drivers(race_id)
        if drivers_df.empty:
            logger.warning(f"No drivers found for race {race_id}")
            return None, None
            
        drivers_df = drivers_df.drop_duplicates(subset=['id'])
        driver_ids = drivers_df['id'].tolist()
        driver_codes = drivers_df.set_index('id')['code'].to_dict()
        
        # --- 1. Calculate Performance Weights (Dynamic) ---
        form_scores = self.get_recent_form(driver_ids, race_id)
        
        driver_weights = {}
        for d_id in driver_ids:
            form = form_scores.get(d_id, 0.5)
            weight = 1.01 - (form * 0.02) 
            driver_weights[d_id] = weight

        # --- 2. Qualifying / Grid Position ---
        grid_positions = self.get_qualifying_positions(race_id)
        if not grid_positions:
            print("ℹ️ Qualifying results unavailable. Predicting grid positions...")
            grid_positions = self.predict_qualifying(race_id, driver_ids)
            
        for d_id in driver_ids:
            if d_id not in grid_positions:
                grid_positions[d_id] = 20
        
        # --- 3. Run Simulation (Vectorized) ---
        model_features = self.model.feature_names_in_
        n_drivers = len(driver_ids)
        
        driver_weights_arr = np.array([driver_weights.get(d, 1.0) for d in driver_ids])
        
        consistencies = []
        for d_id in driver_ids:
            form = form_scores.get(d_id, 0.5)
            consistencies.append(0.5 - (form * 0.3))
        consistencies_arr = np.array(consistencies)
        
        grid_penalties = np.array([(grid_positions.get(d, 10) - 1) * 0.5 for d in driver_ids])
        
        accumulated_times = np.zeros((n_simulations, n_drivers)) + grid_penalties
        
        strategies = np.random.choice([0, 1, 2], size=(n_simulations, n_drivers), p=[0.6, 0.3, 0.1])
        
        progress_bar = None
        if 'streamlit' in str(type(st)):
             progress_bar = st.progress(0)

        for lap in range(1, total_laps + 1):
            if progress_bar and lap % 5 == 0:
                progress_bar.progress(lap / total_laps)
            
            fuel = 110.0 * (1.0 - (lap / total_laps))
            
            input_data = []
            for d in driver_ids:
                row = {
                    'lap_number': lap,
                    'tyre_life': 10,
                    'fuel_load': fuel,
                    'gap_to_leader': 0, 
                    'position': grid_positions.get(d, 10),
                    'tyre_HARD': 0, 'tyre_INTERMEDIATE': 0, 'tyre_MEDIUM': 0, 'tyre_SOFT': 1, 'tyre_WET': 0
                }
                input_data.append(row)
            
            input_df = pd.DataFrame(input_data)
            for col in model_features:
                if col not in input_df.columns: input_df[col] = 0
            input_df = input_df[model_features]
            
            base_times = self.model.predict(input_df)
            
            step_times = np.tile(base_times, (n_simulations, 1))
            
            mask_s0 = (strategies == 0)
            step_times[mask_s0 & (lap < 25)] += 0.4
            step_times[mask_s0 & (lap == 25)] += 22.0
            step_times[mask_s0 & (lap > 25)] += 0.8
            
            mask_s1 = (strategies == 1)
            step_times[mask_s1 & (lap == 15)] += 22.0
            step_times[mask_s1 & (lap > 15) & (lap < 40)] += 0.4
            step_times[mask_s1 & (lap == 40)] += 22.0
            step_times[mask_s1 & (lap > 40)] += 0.4
            
            mask_s2 = (strategies == 2)
            step_times[mask_s2 & (lap < 20)] += 0.4
            step_times[mask_s2 & (lap == 20)] += 22.0
            step_times[mask_s2 & (lap > 20) & (lap < 45)] += 0.8
            step_times[mask_s2 & (lap == 45)] += 22.0
            step_times[mask_s2 & (lap > 45)] += 0.4

            step_times *= driver_weights_arr
            
            noise = np.random.normal(0, consistencies_arr, size=(n_simulations, n_drivers))
            
            traffic_prob = 0.1
            traffic_mask = np.random.random((n_simulations, n_drivers)) < traffic_prob
            step_times[traffic_mask] += 0.5
            
            accumulated_times += step_times + noise
            
            dnf_prob = 0.0005
            dnf_mask = np.random.random((n_simulations, n_drivers)) < dnf_prob
            accumulated_times[dnf_mask] = np.inf
            
        positions = np.argsort(np.argsort(accumulated_times, axis=1), axis=1) + 1
        
        results = []
        for sim_idx in range(n_simulations):
            sim_res = {}
            for driver_idx, d_id in enumerate(driver_ids):
                sim_res[d_id] = positions[sim_idx, driver_idx]
            results.append(sim_res)
            
        return results, driver_codes

    def aggregate_results(self, results, driver_codes):
        if not results:
            return pd.DataFrame()
            
        df = pd.DataFrame(results)
        
        stats = []
        for d_id in df.columns:
            positions = df[d_id]
            # Filter out DNFs (infinity) for avg pos, but count them for completion
            valid_positions = positions[positions < 1000] # Assuming < 1000 is valid
            
            wins = (positions == 1).sum()
            podiums = (positions <= 3).sum()
            top10 = (positions <= 10).sum()
            dnfs = (positions > 1000).sum()
            
            avg_pos = valid_positions.mean() if not valid_positions.empty else 20
            
            stats.append({
                'Driver': driver_codes.get(d_id, d_id),
                'Win %': (wins / len(results)) * 100,
                'Podium %': (podiums / len(results)) * 100,
                'Top 10 %': (top10 / len(results)) * 100,
                'DNF %': (dnfs / len(results)) * 100,
                'Avg Pos': avg_pos
            })
            
        return pd.DataFrame(stats).sort_values('Win %', ascending=False)
