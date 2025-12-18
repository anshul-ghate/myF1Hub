"""
Hybrid F1 Race Prediction Engine
Combines multiple ML models with Monte Carlo simulation for maximum accuracy.
"""

import numpy as np
import pandas as pd
import joblib
import os
import warnings
from datetime import datetime
import logging

# Lazy imports for heavy modules
_lgb = None
_xgb = None
_ff1 = None
_mlflow = None
_shap = None
_ModelRegistry = None

def _ensure_lightgbm():
    global _lgb
    if _lgb is None:
        import lightgbm
        _lgb = lightgbm
    return _lgb

def _ensure_xgboost():
    global _xgb
    if _xgb is None:
        import xgboost
        _xgb = xgboost
    return _xgb

def _ensure_fastf1():
    global _ff1
    if _ff1 is None:
        import fastf1
        _ff1 = fastf1
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        _ff1.Cache.enable_cache(CACHE_DIR)
    return _ff1

def _ensure_mlflow():
    global _mlflow
    if _mlflow is None:
        import mlflow
        import mlflow.lightgbm
        import mlflow.xgboost
        _mlflow = mlflow
    return _mlflow

def _ensure_shap():
    global _shap
    if _shap is None:
        try:
            import shap
            _shap = shap
        except ImportError:
            _shap = False  # Marker for unavailable
    return _shap if _shap is not False else None

def _ensure_registry():
    global _ModelRegistry
    if _ModelRegistry is None:
        from models.registry import ModelRegistry
        _ModelRegistry = ModelRegistry
    return _ModelRegistry

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# Lazy import of heavy local modules (deferred to __init__)
# from models.enhanced_features import F1FeatureEngineer
# from models.dynasty_engine import DynastyEngine, EloTracker, get_track_dna
from utils.db import get_supabase_client

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# Paths
MODEL_DIR = 'models/saved/hybrid'
CACHE_DIR = 'f1_cache_dynasty'

if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)


class HybridPredictor:
    """
    Advanced hybrid prediction engine combining:
    1. LightGBM Ranker (from Dynasty Engine)
    2. XGBoost Regressor (position prediction)
    3. Enhanced feature engineering
    4. Monte Carlo simulation with comprehensive uncertainty modeling
    """
    
    def __init__(self):
        self.supabase = get_supabase_client()
        
        # Lazy load heavy modules only when predictor is instantiated
        from models.enhanced_features import F1FeatureEngineer
        from models.dynasty_engine import DynastyEngine, EloTracker, get_track_dna
        
        self.feature_engineer = F1FeatureEngineer()
        self.dynasty_engine = DynastyEngine()
        
        try:
            self.registry = _ensure_registry()()
        except Exception as e:
            print(f"⚠️ ModelRegistry unavailable: {e}")
            self.registry = None
        
        # Models
        self.ranker_model = None
        self.position_model = None
        self.scaler = StandardScaler()
        
        # Metadata
        self.feature_names = []
        self.feature_importances = {}
        self.last_trained = None
        
        # Load existing models
        self.load_models()

        # MLflow Setup
        try:
            mlflow = _ensure_mlflow()
            mlflow.set_tracking_uri("file:./mlruns")
            mlflow.set_experiment("F1_Hybrid_Predictor")
        except Exception as e:
            print(f"⚠️ MLflow setup failed: {e}")
    
    def load_models(self):
        """Load saved models if they exist."""
        try:
            ranker_path = os.path.join(MODEL_DIR, 'ranker_model.pkl')
            position_path = os.path.join(MODEL_DIR, 'position_model.pkl')
            scaler_path = os.path.join(MODEL_DIR, 'scaler.pkl')
            meta_path = os.path.join(MODEL_DIR, 'metadata.pkl')
            
            if os.path.exists(ranker_path):
                self.ranker_model = joblib.load(ranker_path)
                print("✅ Loaded ranker model")
            
            if os.path.exists(position_path):
                self.position_model = joblib.load(position_path)
                print("✅ Loaded position model")
            
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
                print("✅ Loaded scaler")
            
            if os.path.exists(meta_path):
                metadata = joblib.load(meta_path)
                self.feature_names = metadata.get('feature_names', [])
                self.feature_importances = metadata.get('feature_importances', {})
                self.last_trained = metadata.get('last_trained')
                print(f"✅ Loaded metadata (last trained: {self.last_trained})")
                
        except Exception as e:
            print(f"⚠️ Could not load models: {e}")
    
    def save_models(self):
        """Save trained models."""
        try:
            joblib.dump(self.ranker_model, os.path.join(MODEL_DIR, 'ranker_model.pkl'))
            joblib.dump(self.position_model, os.path.join(MODEL_DIR, 'position_model.pkl'))
            joblib.dump(self.scaler, os.path.join(MODEL_DIR, 'scaler.pkl'))
            
            metadata = {
                'feature_names': self.feature_names,
                'feature_importances': self.feature_importances,
                'last_trained': datetime.now().isoformat()
            }
            joblib.dump(metadata, os.path.join(MODEL_DIR, 'metadata.pkl'))
            
            print("✅ Models saved successfully")
        except Exception as e:
            print(f"❌ Error saving models: {e}")
    
    def check_for_updates(self):
        """Check if new race data is available and retrain if needed."""
        if not self.last_trained:
            print("🔄 No training history found. Training required.")
            return True
        
        try:
            # Get latest race in database
            latest_race = self.supabase.table('races')\
                .select('season_year, round, race_date')\
                .eq('ingestion_status', 'COMPLETE')\
                .order('race_date', desc=True)\
                .limit(1)\
                .execute()
            
            if not latest_race.data:
                return False
            
            latest_date = pd.to_datetime(latest_race.data[0]['race_date'])
            last_trained_date = pd.to_datetime(self.last_trained)
            
            if latest_date > last_trained_date:
                print(f"🔄 New race data found. Retraining required.")
                return True
            
            print("✅ Models are up to date.")
            return False
            
        except Exception as e:
            print(f"⚠️ Error checking for updates: {e}")
            return False
    
    def train(self, min_year=2021):
        """
        Train all models on historical data.
        
        Args:
            min_year: Earliest year to include in training data
        """
        print(f"⚙️ Training Hybrid Predictor (data from {min_year} onwards)...")
        
        # 1. Train Dynasty Engine (for Elo ratings and ranker)
        print("\n[1/3] Training Dynasty Engine...")
        self.dynasty_engine.train()
        
        # 2. Get training data from database
        print("\n[2/3] Building comprehensive feature dataset...")
        
        try:
            # Get all completed races since min_year
            races_res = self.supabase.table('races')\
                .select('id, season_year')\
                .gte('season_year', min_year)\
                .eq('ingestion_status', 'COMPLETE')\
                .execute()
            
            if not races_res.data:
                print("❌ No training data available")
                return False
            
            race_ids = [r['id'] for r in races_res.data]
            print(f"   Found {len(race_ids)} races for training")
            
            # Build features using enhanced feature engineer
            X, y, metadata = self.feature_engineer.build_training_dataset(race_ids, include_target=True)
            
            if X.empty or y is None:
                print("❌ Failed to build training dataset (Empty)")
                print("⚠️ Proceeding with Dynasty Engine (Elo) only.")
                return True
            
            print(f"   Built dataset: {len(X)} samples, {len(X.columns)} features")
            self.feature_names = X.columns.tolist()
            
            # Split by race to prevent data leakage
            unique_races = metadata['race_id'].unique()
            train_races = unique_races[:int(len(unique_races) * 0.8)]
            
            train_mask = metadata['race_id'].isin(train_races)
            X_train, X_val = X[train_mask], X[~train_mask]
            y_train, y_val = y[train_mask], y[~train_mask]
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_val_scaled = self.scaler.transform(X_val)
            
            print(f"   Train: {len(X_train)} samples, Val: {len(X_val)} samples")
            
        except Exception as e:
            print(f"❌ Error building dataset: {e}")
            print("⚠️ Proceeding with Dynasty Engine (Elo) only.")
            return True
        
        # 3. Train models
        print("\n[3/3] Training prediction models...")


        
        # Model A: LightGBM Ranker
        print("   Training LightGBM Ranker...")
        try:
            # Create groups for ranker (one group per race)
            train_groups = metadata[train_mask].groupby('race_id').size().values
            
            # Convert positions to relevance scores (higher is better)
            y_train_relevance = 21 - y_train
            
            lgb = _ensure_lightgbm()
            
            self.ranker_model = lgb.LGBMRanker(
                objective='lambdarank',
                metric='ndcg',
                n_estimators=500,
                learning_rate=0.03,
                num_leaves=31,
                random_state=42
            )
            
            self.ranker_model.fit(
                X_train_scaled, 
                y_train_relevance,
                group=train_groups,
                eval_set=[(X_val_scaled, 21 - y_val)],
                eval_group=[metadata[~train_mask].groupby('race_id').size().values],
                callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)]
            )
            
            print("   ✅ Ranker trained")
            
        except Exception as e:
            print(f"   ⚠️ Ranker training failed: {e}")
        
        # Model B: XGBoost Position Predictor
        print("   Training XGBoost Position Predictor...")
        try:
            xgb = _ensure_xgboost()
            
            self.position_model = xgb.XGBRegressor(
                objective='reg:squarederror',
                n_estimators=400,
                learning_rate=0.05,
                max_depth=6,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42
            )
            
            self.position_model.fit(
                X_train_scaled,
                y_train,
                eval_set=[(X_val_scaled, y_val)],
                early_stopping_rounds=50,
                verbose=100
            )
            
            print("   ✅ Position model trained")
            
        except Exception as e:
            print(f"   ⚠️ Position model training failed: {e}")
        
        # Calculate feature importances
        if self.position_model:
            importances = self.position_model.feature_importances_
            self.feature_importances = dict(zip(self.feature_names, importances))
            
            # Print top 10 features
            sorted_features = sorted(self.feature_importances.items(), 
                                   key=lambda x: x[1], reverse=True)
            print("\n   📊 Top 10 Most Important Features:")
            for feat, imp in sorted_features[:10]:
                print(f"      {feat}: {imp:.4f}")
            
            # Save models locally first
            self.last_trained = datetime.now().isoformat()
            self.save_models()
            self.feature_importances = getattr(self, 'feature_importances', {})

            # Log Ranker to Registry
            if self.ranker_model:
                self.registry.log_model(
                    model=self.ranker_model,
                    model_name="HybridRanker",
                    model_type="lightgbm",
                    metrics={}, # Could add val metrics here if captured
                    params={
                        "n_estimators": 500,
                        "learning_rate": 0.03,
                        "num_leaves": 31
                    },
                    artifacts={
                        "scaler": os.path.join(MODEL_DIR, 'scaler.pkl'),
                        "metadata": os.path.join(MODEL_DIR, 'metadata.pkl')
                    }
                )

            # Log Position Model to Registry
            if self.position_model:
                self.registry.log_model(
                    model=self.position_model,
                    model_name="HybridPositionModel",
                    model_type="xgboost",
                    metrics={}, 
                    params={
                        "n_estimators": 400,
                        "max_depth": 6,
                        "learning_rate": 0.05
                    },
                    artifacts={
                        "scaler": os.path.join(MODEL_DIR, 'scaler.pkl'),
                        "metadata": os.path.join(MODEL_DIR, 'metadata.pkl')
                    }
                )
            
            print("\n✅ Hybrid Predictor training complete and logged to Registry!")
        return True

    
    def predict_race(self, year, race_name, weather_forecast='Dry', n_sims=5000):
        """
        Predict race outcome using hybrid approach.
        
        Args:
            year: Race year
            race_name: Race name (e.g., "Monaco")
            weather_forecast: 'Dry' or 'Wet'
            n_sims: Number of Monte Carlo simulations
        
        Returns:
            DataFrame with predictions and probabilities
        """
        # Check if models are trained
        if self.ranker_model is None and self.position_model is None:
            print("⚠️ No models found. Training...")
            if not self.train():
                return None
        
        print(f"\n🔮 Predicting {year} {race_name}")
        print(f"   Weather: {weather_forecast}, Simulations: {n_sims:,}")
        
        # Get track DNA (import here to avoid circular imports)
        from models.dynasty_engine import get_track_dna
        dna = get_track_dna(race_name)
        print(f"   Track Type: {dna['Type']}, Overtaking: {dna['Overtaking']}/10")
        
        # Get grid (from qualifying or predict it)
        try:
            ff1 = _ensure_fastf1()
            
            session = ff1.get_session(year, race_name, 'Q')
            session.load(laps=False, telemetry=False, weather=False, messages=False)
            
            if not session.results.empty:
                grid_df = session.results[['Abbreviation', 'TeamName', 'GridPosition']].copy()
                print(f"   ✅ Loaded qualifying results ({len(grid_df)} drivers)")
            else:
                raise ValueError("No qualifying results")
                
        except Exception as e:
            print(f"   ⚠️ Qualifying unavailable: {e}")
            print("   Using projected grid from recent form...")
            
            # Use Dynasty Engine projection
            latest_year = self.dynasty_engine.train_df['Year'].max()
            active_drivers = self.dynasty_engine.train_df[
                self.dynasty_engine.train_df['Year'] == latest_year
            ].drop_duplicates('Driver')
            
            active_drivers['Proj_Score'] = (
                active_drivers['Driver_Elo'] * 0.6 + 
                active_drivers['Team_Elo'] * 0.4
            )
            
            grid_df = active_drivers.sort_values('Proj_Score', ascending=False)[
                ['Driver', 'Team', 'Proj_Score']
            ].head(20).copy()
            
            grid_df.columns = ['Abbreviation', 'TeamName', 'Proj_Score']
            grid_df['GridPosition'] = range(1, len(grid_df) + 1)
        
        n_drivers = len(grid_df)
        
        # Build features for each driver (simplified for prediction)
        # In full implementation, would get race_id and properly query features
        driver_scores = []
        
        for idx, row in grid_df.iterrows():
            driver_abbr = row['Abbreviation']
            team = row['TeamName']
            grid = row['GridPosition']
            
            # Fallback for NaN grid positions
            if pd.isna(grid):
                grid = len(driver_scores) + 1  # Assign next available position
            grid = int(grid)
            
            # Get Elo ratings from Dynasty Engine
            driver_elo = self.dynasty_engine.tracker.get_rating(driver_abbr)
            team_elo = self.dynasty_engine.tracker.get_rating(team, is_team=True)
            
            # Simple feature dict (would use full feature engineering in production)
            features = {
                'grid_position': grid,
                'driver_elo': driver_elo,
                'team_elo': team_elo,
                'is_wet': 1.0 if weather_forecast == 'Wet' else 0.0
            }
            
            # For missing features, use defaults
            for feat in self.feature_names:
                if feat not in features:
                    features[feat] = 0.0
            
            driver_scores.append((driver_abbr, team, grid, features, driver_elo, team_elo))
        
        # Create feature matrix
        try:
            X_pred = pd.DataFrame([d[3] for d in driver_scores])[self.feature_names]
            if self.scaler:
                 X_pred_scaled = self.scaler.transform(X_pred)
                 # Cache for SHAP (restore column names for interpretability)
                 self.last_X_df = pd.DataFrame(X_pred_scaled, columns=X_pred.columns)
                 self.last_driver_names = [d[0] for d in driver_scores]
            else:
                 X_pred_scaled = None
                 self.last_X_df = None
                 self.last_driver_names = []
        except Exception as e:
            logger.warning(f"Feature matrix creation failed: {e}")
            X_pred_scaled = None

        
        # Get predictions from both models
        ranker_scores = None
        position_preds = None
        
        if self.ranker_model and X_pred_scaled is not None:
            ranker_scores = self.ranker_model.predict(X_pred_scaled)
            
        if self.position_model and X_pred_scaled is not None:
            position_preds = self.position_model.predict(X_pred_scaled)
        
        # Ensemble predictions
        if ranker_scores is not None and position_preds is not None:
            # Combine: 60% ranker, 40% position model
            combined_scores = ranker_scores * 0.6 - (position_preds * 0.4)
        elif ranker_scores is not None:
            combined_scores = ranker_scores
        elif position_preds is not None:
            combined_scores = -position_preds
        else:
            # Fallback to Heuristic (Elo + Grid)
            print("⚠️ Using Heuristic Prediction (Elo + Grid)")
            # Score = 40% Driver Elo + 30% Team Elo - 30% Grid (lower grid is better)
            combined_scores = []
            for d in driver_scores:
                # d = (abbr, team, grid, features)
                features = d[3]
                score = (features['driver_elo'] * 0.5) + (features['team_elo'] * 0.3) - (features['grid_position'] * 50)
                combined_scores.append(score)
            combined_scores = np.array(combined_scores)
        
        # Sort by combined score
        sorted_indices = np.argsort(-combined_scores)
        base_positions = np.arange(1, n_drivers + 1)[sorted_indices]
        
        # Monte Carlo Simulation
        print(f"\n   Running {n_sims:,} Monte Carlo simulations...")
        
        results_matrix = np.zeros((n_drivers, n_drivers))
        
        # Get driver characteristics for simulation
        reliabilities = []
        for abbr, team, grid, features, _, _ in driver_scores:
            rel = self.feature_engineer.get_team_reliability(team)
            reliabilities.append(rel)
        reliabilities = np.array(reliabilities)
        
        # Simulation parameters
        chaos_factor = (0.5 + dna['Overtaking'] / 10.0) * (1.5 if weather_forecast == 'Wet' else 1.0)
        dnf_base_prob = 1.0 - reliabilities
        if weather_forecast == 'Wet':
            dnf_base_prob *= 1.5
        
        # Run simulations
        for sim in range(n_sims):
            # Add randomness to base positions
            noise = np.random.normal(0, chaos_factor * 2, n_drivers)
            sim_positions = base_positions + noise
            
            # Apply DNFs
            dnf_mask = np.random.random(n_drivers) < dnf_base_prob
            sim_positions[dnf_mask] = 999
            
            # Rank
            final_positions = np.argsort(sim_positions)
            
            # Record results
            for rank, driver_idx in enumerate(final_positions):
                if sim_positions[driver_idx] < 900:  # Not DNF
                    results_matrix[driver_idx, rank] += 1
        
        # Calculate probabilities
        probabilities = (results_matrix / n_sims) * 100
        
        # Build output DataFrame with explainability
        output = []
        for i, (driver_abbr, team, grid, _, driver_elo, team_elo) in enumerate(driver_scores):
            probs = probabilities[i]
            
            # Generate explanation
            explanation_parts = []
            if driver_elo >= 1600:
                explanation_parts.append(f"Elite Elo ({driver_elo:.0f})")
            elif driver_elo >= 1550:
                explanation_parts.append(f"Strong Elo ({driver_elo:.0f})")
            else:
                explanation_parts.append(f"Elo {driver_elo:.0f}")
            
            if grid <= 3:
                explanation_parts.append(f"Front Row (P{grid})")
            elif grid <= 10:
                explanation_parts.append(f"Grid P{grid}")
            else:
                explanation_parts.append(f"Back Grid (P{grid})")
            
            if team_elo >= 1580:
                explanation_parts.append("Top Team")
            
            explanation = " | ".join(explanation_parts)
            
            output.append({
                'Driver': driver_abbr,
                'Team': team,
                'Grid': grid,
                'Win %': probs[0],
                'Podium %': probs[:3].sum(),
                'Points %': probs[:10].sum(),
                'Top 5 %': probs[:5].sum(),
                'Avg Pos': np.sum(probs * np.arange(1, n_drivers + 1)) / 100,
                'DNF %': 100 - probs.sum(),
                'Explanation': explanation
            })
        
        results_df = pd.DataFrame(output).sort_values('Win %', ascending=False).reset_index(drop=True)
        results_df.index = results_df.index + 1  # 1-based index
        
        print("   ✅ Prediction complete!\n")
        
        return results_df
    
    def get_feature_importances(self, top_n=15):
        """Return top N most important features."""
        # Try HybridPredictor's feature importances first
        if self.feature_importances:
            sorted_features = sorted(
                self.feature_importances.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return pd.DataFrame(sorted_features[:top_n], columns=['Feature', 'Importance'])
        
        # Fallback to Dynasty Engine's LightGBM model
        if self.dynasty_engine.model is not None:
            try:
                feature_names = ['Grid', 'Driver_Elo', 'Team_Elo', 'Form', 'Consistency', 
                                'Type_Affinity', 'Overtaking_Fac', 'Reliability', 
                                'Driver_ID', 'Team_ID', 'Type_ID']
                importances = self.dynasty_engine.model.feature_importances_
                sorted_features = sorted(
                    zip(feature_names, importances),
                    key=lambda x: x[1],
                    reverse=True
                )
                return pd.DataFrame(sorted_features[:top_n], columns=['Feature', 'Importance'])
            except Exception as e:
                print(f"Error getting Dynasty Engine importances: {e}")
        
        return None

    def explain_predictions(self, X_df):
        """Generate SHAP values for the given feature set."""
        shap = _ensure_shap()
        if not shap:
            logger.warning("SHAP not installed.")
            return None
            
        if not self.ranker_model:
            return None
            
        try:
            # SHAP TreeExplainer works well with LightGBM
            explainer = shap.TreeExplainer(self.ranker_model)
            shap_values = explainer(X_df)
            return shap_values
        except Exception as e:
            logger.error(f"SHAP explanation failed: {e}")
            return None


if __name__ == "__main__":
    # Test
    predictor = HybridPredictor()
    
    # Check for updates
    if predictor.check_for_updates():
        predictor.train()
