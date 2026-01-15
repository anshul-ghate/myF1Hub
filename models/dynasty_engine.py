import pandas as pd
import numpy as np
import os
import logging
import warnings
from datetime import datetime
import joblib
from typing import Dict, List, Optional, Tuple, Any

# Lazy imports to optimize startup time
ff1 = None
lgb = None
mlflow = None
ModelRegistry = None

# Configure logging
logger = logging.getLogger(__name__)

# --- CONSTANTS & CONFIG ---
CACHE_DIR = 'f1_cache_dynasty'
MODEL_PATH = 'models/saved/dynasty_model.pkl'
TRACKER_PATH = 'models/saved/dynasty_tracker.pkl'
ENCODERS_PATH = 'models/saved/dynasty_encoders.pkl'

TRACK_DNA = {
    'Bahrain': {'Type': 'Balanced', 'Overtaking': 8},
    'Saudi': {'Type': 'Street_Fast', 'Overtaking': 7},
    'Australia': {'Type': 'Street_Fast', 'Overtaking': 6},
    'Japan': {'Type': 'Technical', 'Overtaking': 4},
    'China': {'Type': 'Balanced', 'Overtaking': 7},
    'Miami': {'Type': 'Street_Fast', 'Overtaking': 6},
    'Emilia': {'Type': 'Technical', 'Overtaking': 3},
    'Monaco': {'Type': 'Street_Slow', 'Overtaking': 1},
    'Canada': {'Type': 'Street_Fast', 'Overtaking': 7},
    'Spain': {'Type': 'Technical', 'Overtaking': 5},
    'Austria': {'Type': 'Power', 'Overtaking': 8},
    'Britain': {'Type': 'High_Speed', 'Overtaking': 7},
    'Hungary': {'Type': 'Technical', 'Overtaking': 3},
    'Belgium': {'Type': 'High_Speed', 'Overtaking': 9},
    'Netherlands': {'Type': 'Technical', 'Overtaking': 4},
    'Italy': {'Type': 'Power', 'Overtaking': 8},
    'Azerbaijan': {'Type': 'Street_Fast', 'Overtaking': 8},
    'Singapore': {'Type': 'Street_Slow', 'Overtaking': 2},
    'Austin': {'Type': 'Balanced', 'Overtaking': 7},
    'Mexico': {'Type': 'High_Altitude', 'Overtaking': 6},
    'Brazil': {'Type': 'Balanced', 'Overtaking': 9},
    'Las Vegas': {'Type': 'Street_Fast', 'Overtaking': 8},
    'Qatar': {'Type': 'High_Speed', 'Overtaking': 6},
    'Abu Dhabi': {'Type': 'Balanced', 'Overtaking': 5},
}

def _ensure_fastf1() -> Any:
    """Lazy loads and configures FastF1 with caching."""
    global ff1
    if ff1 is None:
        import fastf1 as _ff1
        ff1 = _ff1
        from utils.api_config import configure_fastf1_retries
        configure_fastf1_retries()
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        ff1.Cache.enable_cache(CACHE_DIR)
        
        # Suppress FastF1 info logs
        logging.getLogger('fastf1').setLevel(logging.ERROR)
    return ff1

def _ensure_lightgbm() -> Any:
    """Lazy loads LightGBM."""
    global lgb
    if lgb is None:
        import lightgbm as _lgb
        lgb = _lgb
    return lgb

def _ensure_registry() -> Any:
    """Lazy loads ModelRegistry."""
    global ModelRegistry
    if ModelRegistry is None:
        try:
            from models.registry import ModelRegistry as _ModelRegistry
            ModelRegistry = _ModelRegistry
        except ImportError:
            logger.warning("ModelRegistry module not found.")
            return None
    return ModelRegistry

def get_track_dna(circuit_name: str) -> Dict[str, Any]:
    """Retrieves track characteristics based on circuit name."""
    for key, dna in TRACK_DNA.items():
        if key in circuit_name:
            return dna
    return {'Type': 'Balanced', 'Overtaking': 5}

# --- SCIKIT-LEARN HELPERS ---
from sklearn.base import BaseEstimator, TransformerMixin

class RobustEncoder(BaseEstimator, TransformerMixin):
    """
    Encoder that maps categories to integers, handling unknown values gracefully.
    """
    def __init__(self):
        self.mapping = {}
        self.unknown_token = -1
        
    def fit(self, y: pd.Series):
        unique_labels = pd.Series(y).unique()
        self.mapping = {label: idx for idx, label in enumerate(unique_labels)}
        return self
        
    def transform(self, y: pd.Series):
        return pd.Series(y).map(lambda x: self.mapping.get(x, self.unknown_token)).values
        
    def fit_transform(self, y: pd.Series):
        return self.fit(y).transform(y)

# --- ELO RATING SYSTEM ---
class EloTracker:
    """
    Tracks and updates Elo ratings for Drivers and Teams.
    """
    def __init__(self, base: float = 1500.0):
        self.driver_ratings: Dict[str, float] = {}
        self.team_ratings: Dict[str, float] = {}
        self.base = base

    def get_rating(self, entity: str, is_team: bool = False) -> float:
        target = self.team_ratings if is_team else self.driver_ratings
        return target.get(entity, self.base)

    def update(self, df: pd.DataFrame) -> None:
        """
        Updates ratings based on race results.
        Expected columns: 'Driver', 'Team', 'Position'.
        """
        curr_d = {r['Driver']: self.get_rating(r['Driver']) for _, r in df.iterrows()}
        curr_t = {r['Team']: self.get_rating(r['Team'], True) for _, r in df.iterrows()}
        new_d, new_t = curr_d.copy(), curr_t.copy()
        
        drivers = list(curr_d.keys())
        # Pairwise comparison for all drivers in the race
        for i in range(len(drivers)):
            dA = drivers[i]
            tA = df[df['Driver'] == dA]['Team'].values[0]
            posA = df[df['Driver'] == dA]['Position'].values[0]
            
            for j in range(i + 1, len(drivers)):
                dB = drivers[j]
                tB = df[df['Driver'] == dB]['Team'].values[0]
                posB = df[df['Driver'] == dB]['Position'].values[0]
                
                # Scoring: 1.0 if A beats B, 0.0 if B beats A
                score = 1.0 if posA < posB else (0.0 if posA > posB else 0.5)
                
                # Update Driver Elo
                expected_score_d = 1 / (1 + 10 ** ((curr_d[dB] - curr_d[dA]) / 400))
                delta_d = 32 * (score - expected_score_d)
                new_d[dA] += delta_d
                new_d[dB] -= delta_d
                
                # Update Team Elo
                expected_score_t = 1 / (1 + 10 ** ((curr_t[tB] - curr_t[tA]) / 400))
                delta_t = 24 * (score - expected_score_t)
                new_t[tA] += delta_t
                new_t[tB] -= delta_t
        
        self.driver_ratings, self.team_ratings = new_d, new_t

    def to_dict(self) -> Dict[str, Any]:
        return {
            'driver_ratings': self.driver_ratings,
            'team_ratings': self.team_ratings,
            'base': self.base
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EloTracker':
        tracker = cls(base=data.get('base', 1500))
        tracker.driver_ratings = data.get('driver_ratings', {})
        tracker.team_ratings = data.get('team_ratings', {})
        return tracker

# --- CORE ENGINE ---
class DynastyEngine:
    """
    Hybrid Machine Learning Engine for F1 Race Prediction.
    Combines Elo Ratings, LightGBM Ranking, and Monte Carlo Simulations.
    """
    def __init__(self):
        self.model = None
        self.tracker = None
        self.encoders = None
        self.train_df = None
        self.residuals = None
        self.registry = None
        
        # Ensure model directory exists
        if not os.path.exists('models/saved'):
            os.makedirs('models/saved')

        # Initialize Registry if available
        reg_cls = _ensure_registry()
        if reg_cls:
            try:
                self.registry = reg_cls()
            except Exception as e:
                logger.warning(f"Failed to initialize ModelRegistry: {e}")

        self.load_artifacts()

    def load_artifacts(self) -> None:
        """Loads trained model, tracker, and encoders from disk."""
        try:
            if os.path.exists(MODEL_PATH):
                self.model = joblib.load(MODEL_PATH)
                
            if os.path.exists(TRACKER_PATH):
                tracker_data = joblib.load(TRACKER_PATH)
                if isinstance(tracker_data, dict):
                    self.tracker = EloTracker.from_dict(tracker_data)
                else:
                    self.tracker = EloTracker.from_dict(tracker_data.__dict__)
                    
            if os.path.exists(ENCODERS_PATH):
                artifacts = joblib.load(ENCODERS_PATH)
                self.encoders = artifacts.get('encoders')
                self.train_df = artifacts.get('train_df')
                self.residuals = artifacts.get('residuals')
                logger.info("✅ Dynasty Engine artifacts loaded successfully.")
                
                self.check_for_updates()
        except Exception as e:
            logger.error(f"⚠️ Could not load artifacts: {e}")

    def check_for_updates(self) -> None:
        """Checks for new race completion and triggers retraining if necessary."""
        try:
            if self.train_df is None or self.train_df.empty:
                return 

            last_year = self.train_df['Year'].max()
            last_round = self.train_df[self.train_df['Year'] == last_year]['Round'].max()
            
            _ensure_fastf1()
            now = datetime.now()
            schedule = ff1.get_event_schedule(now.year)
            completed = schedule[schedule['EventDate'] < now]
            
            if not completed.empty:
                latest = completed.iloc[-1]
                if (now.year > last_year) or (now.year == last_year and latest['RoundNumber'] > last_round):
                    logger.info(f"🔄 New data detected (Round {latest['RoundNumber']}). Retraining...")
                    self.train()
                else:
                    logger.info("✅ Engine is up to date.")
        except Exception as e:
            logger.warning(f"⚠️ Update check failed: {e}")

    def _fetch_training_data(self) -> pd.DataFrame:
        """Fetches historical race data from FastF1."""
        data = []
        current_year = datetime.now().year
        _ensure_fastf1()

        print("📡 Fetching historical race data...")
        for year in range(2021, current_year + 1):
            try:
                schedule = ff1.get_event_schedule(year)
                completed = schedule[schedule['EventDate'] < datetime.now()]
                
                for _, event in completed.iterrows():
                    # Simple heuristic: Session 5 is usually the race
                    if event.get('Session5', '') != 'Race':
                        continue
                        
                    try:
                        session = ff1.get_session(year, event['RoundNumber'], 'R')
                        session.load(laps=False, telemetry=False, weather=False, messages=False)
                        
                        if session.results.empty: continue
                        
                        dna = get_track_dna(event['EventName'])
                        for _, row in session.results.iterrows():
                            data.append({
                                'Year': year, 
                                'Round': event['RoundNumber'], 
                                'Circuit': event['EventName'],
                                'Track_Type': dna['Type'], 
                                'Overtaking_Fac': dna['Overtaking'],
                                'Driver': row['Abbreviation'], 
                                'Team': row['TeamName'],
                                'Grid': row['GridPosition'], 
                                'Position': row['Position'], 
                                'Status': row['Status']
                            })
                    except Exception as e:
                        logger.debug(f"Skipping {year} Round {event['RoundNumber']}: {e}")
            except Exception as e:
                logger.error(f"Error processing year {year}: {e}")
        
        return pd.DataFrame(data)

    def _engineer_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, EloTracker, tuple]:
        """Performs feature engineering: Elo updates, rolling stats, and encoding."""
        print("🔧 Engineering features...")
        df = df.sort_values(['Year', 'Round'])
        df['Position'] = pd.to_numeric(df['Position'], errors='coerce').fillna(20)
        
        tracker = EloTracker()
        d_elos, t_elos = [], []
        
        # Replay history to build Elo ratings
        for _, race in df.groupby(['Year', 'Round']):
            for _, row in race.iterrows():
                d_elos.append(tracker.get_rating(row['Driver']))
                t_elos.append(tracker.get_rating(row['Team'], is_team=True))
            tracker.update(race)
            
        df['Driver_Elo'] = d_elos
        df['Team_Elo'] = t_elos
        
        # Driver Form (Rolling 5 races)
        df['Form'] = df.groupby('Driver')['Position'].transform(
            lambda x: x.shift(1).rolling(5, min_periods=1).mean()
        )
        # Consistency (Rolling 5 std dev)
        df['Consistency'] = df.groupby('Driver')['Position'].transform(
            lambda x: x.shift(1).rolling(5, min_periods=1).std()
        ).fillna(3.0)
        # Track Type Affinity
        df['Type_Affinity'] = df.groupby(['Driver', 'Track_Type'])['Position'].transform(
            lambda x: x.shift(1).expanding().mean()
        )
        # Team Reliability
        df['Reliability'] = df.groupby('Team')['Status'].transform(
            lambda x: x.shift(1).isin(['Finished', '+1 Lap']).rolling(10).mean()
        ).fillna(0.8)
        
        df.fillna(0, inplace=True)
        
        # Encoders
        le_d, le_t, le_tt = RobustEncoder(), RobustEncoder(), RobustEncoder()
        df['Driver_ID'] = le_d.fit_transform(df['Driver'])
        df['Team_ID'] = le_t.fit_transform(df['Team'])
        df['Type_ID'] = le_tt.fit_transform(df['Track_Type'])
        
        return df, tracker, (le_d, le_t, le_tt)

    def train(self) -> bool:
        """Main training pipeline."""
        df = self._fetch_training_data()
        if df.empty:
            logger.error("No training data available.")
            return False
            
        df, tracker, encoders = self._engineer_features(df)
        
        # Features definition
        FEATS = ['Grid', 'Driver_Elo', 'Team_Elo', 'Form', 'Consistency', 
                 'Type_Affinity', 'Overtaking_Fac', 'Reliability', 
                 'Driver_ID', 'Team_ID', 'Type_ID']
        
        # Train/Val Split (Last 5 races as validation)
        df['Race_Index'] = df.groupby(['Year', 'Round']).ngroup()
        cutoff_idx = max(1, df['Race_Index'].max() - 4)
        
        train_mask = df['Race_Index'] < cutoff_idx
        val_mask = df['Race_Index'] >= cutoff_idx
        
        X_tr = df[train_mask][FEATS]
        y_tr = 21 - df[train_mask]['Position']  # Relevance score (higher is better)
        groups_tr = df[train_mask].groupby(['Year', 'Round']).size().to_numpy()
        
        # Train LightGBM Ranker
        print("🧠 Training LightGBM Ranker...")
        lgb = _ensure_lightgbm()
        params = {
            'objective': 'lambdarank',
            'metric': 'ndcg',
            'n_estimators': 600,
            'learning_rate': 0.03,
            'random_state': 42,
            'verbose': -1
        }
        model = lgb.LGBMRanker(**params)
        model.fit(X_tr, y_tr, group=groups_tr)
        
        # Evaluation
        val_df = df[val_mask]
        preds = model.predict(val_df[FEATS])
        residuals = []
        mae_accum = 0
        race_count = 0
        
        # Group by race to calculate ranks within that race
        curr_idx = 0
        for _, race in val_df.groupby(['Year', 'Round']):
            n_drivers = len(race)
            race_preds = preds[curr_idx : curr_idx + n_drivers]
            curr_idx += n_drivers
            
            predicted_ranks = (-race_preds).argsort().argsort() + 1
            actual_ranks = race['Position'].values
            
            diffs = actual_ranks - predicted_ranks
            residuals.extend(diffs)
            mae_accum += np.mean(np.abs(diffs))
            race_count += 1
            
        avg_mae = mae_accum / race_count if race_count > 0 else 0
        print(f"✅ Training Complete. Validation MAE: {avg_mae:.2f} positions")
        
        # Save Artifacts
        self.model = model
        self.tracker = tracker
        self.encoders = encoders
        self.train_df = df
        self.residuals = np.array(residuals)
        
        joblib.dump(self.model, MODEL_PATH)
        joblib.dump(self.tracker.to_dict(), TRACKER_PATH)
        joblib.dump({
            'encoders': self.encoders, 
            'train_df': self.train_df, 
            'residuals': self.residuals
        }, ENCODERS_PATH)
        
        return True

    def predict_next_race(self, year: int, race_name: str, 
                          weather_forecast: str = 'Dry', n_sims: int = 1000) -> pd.DataFrame:
        """
        Predicts outcomes for a specific race using Monte Carlo simulation.
        """
        if self.model is None:
            if not self.train():
                return pd.DataFrame()
                
        dna = get_track_dna(race_name)
        _ensure_fastf1()
        
        # 1. Get Grid (Qualifying Results or Projection)
        try:
            session = ff1.get_session(year, race_name, 'Q')
            session.load(laps=False, telemetry=False, weather=False, messages=False)
            if not session.results.empty:
                grid = session.results[['Abbreviation', 'TeamName', 'GridPosition']]
            else:
                raise ValueError("Empty qualifying results")
        except Exception:
            # Fallback to projection based on Elo
            latest_year = self.train_df['Year'].max()
            active_drivers = self.train_df[self.train_df['Year'] == latest_year].drop_duplicates('Driver')
            # Weighted average of Driver and Team Elo
            active_drivers['Proj_Score'] = (active_drivers['Driver_Elo'] * 0.6) + (active_drivers['Team_Elo'] * 0.4)
            grid = active_drivers.sort_values('Proj_Score', ascending=False)[['Driver', 'Team', 'Proj_Score']]
            grid.columns = ['Abbreviation', 'TeamName', 'Proj_Score']
            grid['GridPosition'] = range(1, len(grid) + 1)
            logger.info(f"Using projected grid for {race_name}")

        # 2. Prepare Features for Prediction
        N_DRIVERS = len(grid)
        le_d, le_t, le_tt = self.encoders
        FEATS = ['Grid', 'Driver_Elo', 'Team_Elo', 'Form', 'Consistency', 
                 'Type_Affinity', 'Overtaking_Fac', 'Reliability', 
                 'Driver_ID', 'Team_ID', 'Type_ID']
        
        rows = []
        for _, row in grid.iterrows():
            drv = row['Abbreviation']
            tm = row['TeamName']
            
            d_elo = self.tracker.get_rating(drv)
            t_elo = self.tracker.get_rating(tm, True)
            
            # Get latest stats or defaults
            hist = self.train_df[self.train_df['Driver'] == drv].tail(1)
            if not hist.empty:
                form = hist['Form'].values[0]
                cons = hist['Consistency'].values[0]
                rel = hist['Reliability'].values[0]
                aff = hist['Type_Affinity'].values[0]
            else:
                form, cons, rel, aff = 15, 4.0, 0.8, 15
                
            rows.append([
                row['GridPosition'], d_elo, t_elo, form, cons, aff, dna['Overtaking'], rel,
                le_d.transform([drv])[0], le_t.transform([tm])[0], le_tt.transform([dna['Type']])[0],
                drv
            ])
            
        pred_df = pd.DataFrame(rows, columns=FEATS + ['Driver'])
        
        # 3. Base Prediction
        pred_df['Base_Score'] = self.model.predict(pred_df[FEATS])
        pred_df = pred_df.sort_values('Base_Score', ascending=False).reset_index(drop=True)
        base_ranks = pred_df.index.values + 1
        
        # 4. Monte Carlo Simulation
        # Simulate variations based on historical residuals and consistency consistency
        sim_matrix = np.zeros((N_DRIVERS, N_DRIVERS))
        
        # Random error sampling from historical residuals
        random_errors = np.random.choice(self.residuals, size=(N_DRIVERS, n_sims))
        
        # Consistency Modifier: Less consistent drivers have higher variance
        cons_mod = (pred_df['Consistency'].values / 2.5).clip(0.5, 1.5)
        
        # Connect weather/track chaos
        weather_chaos = 1.5 if weather_forecast == 'Wet' else 1.0
        track_chaos = (0.5 + (dna['Overtaking'] / 10.0))
        total_chaos = weather_chaos * track_chaos
        
        final_perturbations = random_errors * cons_mod[:, np.newaxis] * total_chaos
        simulated_ranks = base_ranks[:, np.newaxis] + final_perturbations
        
        # Handle DNFs
        dnf_probs = 1.0 - pred_df['Reliability'].values
        if weather_forecast == 'Wet': dnf_probs *= 1.5
        
        # Apply DNF (999 rank) based on probability
        is_dnf = np.random.random((N_DRIVERS, n_sims)) < dnf_probs[:, np.newaxis]
        simulated_ranks[is_dnf] = 999
        
        # Aggregate Results
        for s in range(n_sims):
            col = simulated_ranks[:, s]
            # argsort twice gives the rank if sorted
            finishing_order = np.argsort(col)
            
            for rank, driver_idx in enumerate(finishing_order):
                # If driver didn't DNF (rank < 900), record their position
                if rank < N_DRIVERS and simulated_ranks[driver_idx, s] < 900:
                    sim_matrix[driver_idx, rank] += 1
                    
        probs = (sim_matrix / n_sims) * 100
        
        results = []
        for i, row in pred_df.iterrows():
            p = probs[i]
            results.append({
                'Driver': row['Driver'],
                'Win %': p[0],
                'Podium %': np.sum(p[:3]),
                'Points %': np.sum(p[:10]),
                'Avg Pos': np.sum(p * np.arange(1, N_DRIVERS+1)) / 100
            })
            
        return pd.DataFrame(results).sort_values('Win %', ascending=False)
