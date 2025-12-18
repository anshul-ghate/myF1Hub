"""
Comprehensive Feature Engineering for F1 Race Predictions
Combines all available data sources for maximum prediction accuracy.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.db import get_supabase_client
import warnings
warnings.filterwarnings('ignore')


class F1FeatureEngineer:
    """
    Advanced feature engineering pipeline that extracts and computes
    features from all available data sources.
    """
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.feature_cache = {}
        
    # ========== DRIVER FEATURES ==========
    
    def get_driver_recent_form(self, driver_id, current_race_id, lookback_races=5):
        """
        Calculate driver's recent performance metrics.
        Returns: avg_position, consistency, podium_rate, dnf_rate
        """
        try:
            # Get recent races before current race
            res = self.supabase.table('race_results')\
                .select('position, status')\
                .eq('driver_id', driver_id)\
                .lt('race_id', current_race_id)\
                .order('race_id', desc=True)\
                .limit(lookback_races)\
                .execute()
            
            if not res.data:
                return 15.0, 5.0, 0.0, 0.1  # Default values
            
            positions = []
            podiums = 0
            dnfs = 0
            
            for r in res.data:
                if r['position'] and r['position'] > 0:
                    positions.append(r['position'])
                    if r['position'] <= 3:
                        podiums += 1
                
                if r['status'] and 'DNF' in str(r['status']).upper():
                    dnfs += 1
            
            avg_pos = np.mean(positions) if positions else 15.0
            consistency = np.std(positions) if len(positions) > 1 else 5.0
            podium_rate = podiums / len(res.data) if res.data else 0.0
            dnf_rate = dnfs / len(res.data) if res.data else 0.1
            
            return avg_pos, consistency, podium_rate, dnf_rate
            
        except Exception as e:
            print(f"Error getting driver form: {e}")
            return 15.0, 5.0, 0.0, 0.1
    
    def get_driver_circuit_history(self, driver_id, circuit_id, lookback_years=5):
        """
        Get driver's historical performance at this specific circuit.
        """
        try:
            # Get races at this circuit
            circuit_races = self.supabase.table('races')\
                .select('id')\
                .eq('circuit_id', circuit_id)\
                .order('season_year', desc=True)\
                .limit(lookback_years)\
                .execute()
            
            if not circuit_races.data:
                return 15.0, 0
            
            race_ids = [r['id'] for r in circuit_races.data]
            
            # Get results at this circuit
            res = self.supabase.table('race_results')\
                .select('position')\
                .eq('driver_id', driver_id)\
                .in_('race_id', race_ids)\
                .execute()
            
            if not res.data:
                return 15.0, 0
            
            positions = [r['position'] for r in res.data if r['position'] and r['position'] > 0]
            avg_circuit_pos = np.mean(positions) if positions else 15.0
            circuit_experience = len(positions)
            
            return avg_circuit_pos, circuit_experience
            
        except Exception as e:
            print(f"Error getting circuit history: {e}")
            return 15.0, 0
    
    def get_driver_qualifying_vs_race_delta(self, driver_id, lookback_races=10):
        """
        How well does the driver perform vs their grid position?
        Positive = gains positions, Negative = loses positions
        """
        try:
            res = self.supabase.table('race_results')\
                .select('grid, position')\
                .eq('driver_id', driver_id)\
                .not_.is_('grid', 'null')\
                .not_.is_('position', 'null')\
                .order('race_id', desc=True)\
                .limit(lookback_races)\
                .execute()
            
            if not res.data:
                return 0.0
            
            deltas = []
            for r in res.data:
                if r['grid'] > 0 and r['position'] > 0:
                    deltas.append(r['grid'] - r['position'])  # Positive = gained positions
            
            return np.mean(deltas) if deltas else 0.0
            
        except Exception as e:
            # print(f"Error getting qualifying delta: {e}")
            return 0.0
    
    # ========== TEAM FEATURES ==========
    
    def get_team_reliability(self, team_name, lookback_races=20):
        """
        Calculate team's reliability score (% of races finished).
        """
        try:
            # NOTE: race_results table currently lacks 'team' column in schema v3
            # Returning default reliability for now to avoid errors
            return 0.85
            
            # For simplicity, we'll query by team name in results
            # In production, you'd join through drivers table
            # res = self.supabase.table('race_results')\
            #     .select('status')\
            #     .eq('team', team_name)\
            #     .order('race_id', desc=True)\
            #     .limit(lookback_races)\
            #     .execute()
            
            # if not res.data:
            #     return 0.85  # Default 85% reliability
            
            # finished = 0
            # for r in res.data:
            #     status = str(r.get('status', '')).upper()
            #     if 'FINISHED' in status or '+' in status or 'LAP' in status:
            #         finished += 1
            
            # return finished / len(res.data) if res.data else 0.85
            
        except Exception as e:
            # print(f"Error getting team reliability: {e}")
            return 0.85
    
    def get_team_pitstop_efficiency(self, team_name, lookback_races=10):
        """
        Average pit stop duration for the team.
        """
        try:
            # Get recent races
            recent_races = self.supabase.table('races')\
                .select('id')\
                .order('race_date', desc=True)\
                .limit(lookback_races)\
                .execute()
            
            if not recent_races.data:
                return 22.0  # Default pit stop time
            
            race_ids = [r['id'] for r in recent_races.data]
            
            # Get pit stops - need to join with drivers to filter by team
            # For now, simplified approach
            pit_stops = self.supabase.table('pit_stops')\
                .select('duration_ms')\
                .in_('race_id', race_ids)\
                .execute()
            
            if not pit_stops.data:
                return 22.0
            
            # Convert ms to seconds
            durations = [p['duration_ms'] / 1000.0 for p in pit_stops.data if p.get('duration_ms') and p['duration_ms'] > 0]
            return np.mean(durations) if durations else 22.0
            
        except Exception as e:
            print(f"Error getting pit stop efficiency: {e}")
            return 22.0
    
    # ========== CIRCUIT FEATURES ==========
    
    def get_circuit_characteristics(self, circuit_id):
        """
        Get circuit-specific metadata.
        """
        try:
            res = self.supabase.table('circuits')\
                .select('*')\
                .eq('id', circuit_id)\
                .single()\
                .execute()
            
            if res.data:
                return {
                    'length': res.data.get('length', 5.0),
                    'type': res.data.get('type', 'balanced'),
                    'elevation': res.data.get('elevation_change', 0),
                }
            
            return {'length': 5.0, 'type': 'balanced', 'elevation': 0}
            
        except Exception as e:
            print(f"Error getting circuit characteristics: {e}")
            return {'length': 5.0, 'type': 'balanced', 'elevation': 0}
    
    def get_circuit_safety_car_probability(self, circuit_id, lookback_years=5):
        """
        Historical likelihood of safety car at this circuit.
        """
        try:
            # Get historical races at this circuit
            races = self.supabase.table('races')\
                .select('id')\
                .eq('circuit_id', circuit_id)\
                .order('season_year', desc=True)\
                .limit(lookback_years)\
                .execute()
            
            if not races.data:
                return 0.3  # Default 30% chance
            
            # Check for safety car indicators in lap data
            # Track status '4' or '6' indicates SC/VSC
            sc_races = 0
            for race in races.data:
                laps = self.supabase.table('laps')\
                    .select('track_status')\
                    .eq('race_id', race['id'])\
                    .in_('track_status', ['4', '6'])\
                    .limit(1)\
                    .execute()
                
                if laps.data:
                    sc_races += 1
            
            return sc_races / len(races.data) if races.data else 0.3
            
        except Exception as e:
            print(f"Error getting SC probability: {e}")
            return 0.3
    
    # ========== WEATHER FEATURES ==========
    
    def get_race_weather_forecast(self, race_id):
        """
        Get weather conditions for the race (or forecast).
        """
        try:
            weather = self.supabase.table('weather')\
                .select('*')\
                .eq('race_id', race_id)\
                .execute()
            
            if not weather.data:
                # Default conditions
                return {
                    'air_temp': 25.0,
                    'track_temp': 35.0,
                    'humidity': 50.0,
                    'rainfall': False,
                    'wind_speed': 5.0
                }
            
            # Average the weather data
            df = pd.DataFrame(weather.data)
            return {
                'air_temp': df['air_temp'].mean() if 'air_temp' in df else 25.0,
                'track_temp': df['track_temp'].mean() if 'track_temp' in df else 35.0,
                'humidity': df['humidity'].mean() if 'humidity' in df else 50.0,
                'rainfall': df['rainfall'].any() if 'rainfall' in df else False,
                'wind_speed': df['wind_speed'].mean() if 'wind_speed' in df else 5.0
            }
            
        except Exception as e:
            print(f"Error getting weather: {e}")
            return {
                'air_temp': 25.0,
                'track_temp': 35.0,
                'humidity': 50.0,
                'rainfall': False,
                'wind_speed': 5.0
            }
    
    # ========== MASTER FEATURE BUILDER ==========
    
    def build_race_features(self, race_id, driver_id, grid_position, 
                           driver_elo, team_elo, team_name, circuit_id):
        """
        Build comprehensive feature set for a single driver in a race.
        
        Returns: Dictionary of all features
        """
        features = {}
        
        # Basic inputs
        features['grid_position'] = grid_position
        features['driver_elo'] = driver_elo
        features['team_elo'] = team_elo
        
        # Driver features
        avg_pos, consistency, podium_rate, dnf_rate = self.get_driver_recent_form(driver_id, race_id)
        features['driver_avg_position_last_5'] = avg_pos
        features['driver_consistency'] = consistency
        features['driver_podium_rate'] = podium_rate
        features['driver_dnf_rate'] = dnf_rate
        
        circuit_avg_pos, circuit_exp = self.get_driver_circuit_history(driver_id, circuit_id)
        features['driver_circuit_avg_position'] = circuit_avg_pos
        features['driver_circuit_experience'] = circuit_exp
        
        features['driver_grid_vs_race_delta'] = self.get_driver_qualifying_vs_race_delta(driver_id)
        
        # Team features
        features['team_reliability'] = self.get_team_reliability(team_name)
        features['team_pitstop_avg'] = self.get_team_pitstop_efficiency(team_name)
        
        # Circuit features
        circuit_chars = self.get_circuit_characteristics(circuit_id)
        features['circuit_length'] = circuit_chars['length']
        features['circuit_type_encoded'] = hash(circuit_chars['type']) % 10  # Simple encoding
        features['circuit_elevation'] = circuit_chars['elevation']
        features['circuit_sc_probability'] = self.get_circuit_safety_car_probability(circuit_id)
        
        # Weather features
        weather = self.get_race_weather_forecast(race_id)
        features['air_temp'] = weather['air_temp']
        features['track_temp'] = weather['track_temp']
        features['humidity'] = weather['humidity']
        features['is_wet'] = 1.0 if weather['rainfall'] else 0.0
        features['wind_speed'] = weather['wind_speed']
        
        return features
    
    def build_training_dataset(self, race_ids, include_target=True):
        """
        Build complete training dataset from historical races.
        
        Args:
            race_ids: List of race IDs to include
            include_target: Whether to include actual race positions as target
        
        Returns:
            X: Feature DataFrame
            y: Target Series (if include_target=True)
            metadata: DataFrame with driver/race info
        """
        all_features = []
        all_targets = []
        all_metadata = []
        
        for race_id in race_ids:
            try:
                # Get race results
                # We select * to be safe, or specific columns if we know them. 
                # Since 'team' might be missing, we'll fetch everything and check in python.
                results = self.supabase.table('race_results')\
                    .select('*')\
                    .eq('race_id', race_id)\
                    .execute()
                
                if not results.data:
                    print(f"⚠️ No results found for race {race_id}")
                    continue
                
                print(f"✅ Found {len(results.data)} results for race {race_id}")
                
                # Get race info
                race_info = self.supabase.table('races')\
                    .select('circuit_id, season_year')\
                    .eq('id', race_id)\
                    .single()\
                    .execute()
                
                if not race_info.data:
                    continue
                
                circuit_id = race_info.data['circuit_id']
                
                # Build features for each driver
                for result in results.data:
                    driver_id = result['driver_id']
                    team_name = result.get('team', 'Unknown')
                    grid = result.get('grid', 20)
                    position = result.get('position')
                    
                    # Get Elo ratings (simplified - would integrate with Dynasty Engine)
                    driver_elo = 1500.0  # Placeholder
                    team_elo = 1500.0    # Placeholder
                    
                    features = self.build_race_features(
                        race_id, driver_id, grid, driver_elo, team_elo, team_name, circuit_id
                    )
                    
                    all_features.append(features)
                    
                    if include_target and position:
                        all_targets.append(position)
                    
                    all_metadata.append({
                        'race_id': race_id,
                        'driver_id': driver_id,
                        'team': team_name
                    })
                    
            except Exception as e:
                print(f"❌ Error processing race {race_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        X = pd.DataFrame(all_features)
        y = pd.Series(all_targets) if include_target else None
        metadata = pd.DataFrame(all_metadata)
        
        return X, y, metadata


if __name__ == "__main__":
    # Test feature engineering
    engineer = F1FeatureEngineer()
    print("Feature Engineer initialized successfully!")
