import pandas as pd
import numpy as np
import os
import logging
import warnings
from datetime import datetime
import joblib

# Lazy imports for heavy modules
ff1 = None
lgb = None
mlflow = None
ModelRegistry = None

def _ensure_fastf1():
    """Lazy load FastF1 and configure cache."""
    global ff1
    if ff1 is None:
        import fastf1 as _ff1
        ff1 = _ff1
        from utils.api_config import configure_fastf1_retries
        configure_fastf1_retries()
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        ff1.Cache.enable_cache(CACHE_DIR)
    return ff1

def _ensure_lightgbm():
    """Lazy load LightGBM."""
    global lgb
    if lgb is None:
        import lightgbm as _lgb
        lgb = _lgb
    return lgb

def _ensure_mlflow():
    """Lazy load MLflow."""
    global mlflow
    if mlflow is None:
        import mlflow as _mlflow
        import mlflow.lightgbm
        mlflow = _mlflow
    return mlflow

def _ensure_registry():
    """Lazy load ModelRegistry."""
    global ModelRegistry
    if ModelRegistry is None:
        from models.registry import ModelRegistry as _ModelRegistry
        ModelRegistry = _ModelRegistry
    return ModelRegistry

from sklearn.base import BaseEstimator, TransformerMixin

# Suppress warnings
warnings.filterwarnings('ignore')
logging.getLogger('fastf1').setLevel(logging.ERROR)

# Module logger
logger = logging.getLogger(__name__)

# --- CONFIG ---
CACHE_DIR = 'f1_cache_dynasty'
MODEL_PATH = 'models/saved/dynasty_model.pkl'
TRACKER_PATH = 'models/saved/dynasty_tracker.pkl'
ENCODERS_PATH = 'models/saved/dynasty_encoders.pkl'

if not os.path.exists('models/saved'):
    os.makedirs('models/saved')

# --- TRACK DNA ---
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

def get_track_dna(circuit_name):
    for key in TRACK_DNA:
        if key in circuit_name: return TRACK_DNA[key]
    return {'Type': 'Balanced', 'Overtaking': 5}

# --- ROBUST ENCODER ---
class RobustEncoder(BaseEstimator, TransformerMixin):
    def __init__(self):
        self.mapping = {}
        self.unknown_token = -1
        
    def fit(self, y):
        unique_labels = pd.Series(y).unique()
        self.mapping = {label: idx for idx, label in enumerate(unique_labels)}
        return self
        
    def transform(self, y):
        return pd.Series(y).map(lambda x: self.mapping.get(x, self.unknown_token)).values
        
    def fit_transform(self, y):
        return self.fit(y).transform(y)

# --- ELO TRACKER ---
class EloTracker:
    def __init__(self, base=1500):
        self.driver_ratings = {}
        self.team_ratings = {}
        self.base = base

    def get_rating(self, entity, is_team=False):
        target = self.team_ratings if is_team else self.driver_ratings
        return target.get(entity, self.base)

    def update(self, df):
        curr_d = {r['Driver']: self.get_rating(r['Driver']) for _, r in df.iterrows()}
        curr_t = {r['Team']: self.get_rating(r['Team'], True) for _, r in df.iterrows()}
        new_d, new_t = curr_d.copy(), curr_t.copy()
        
        drivers = list(curr_d.keys())
        for i in range(len(drivers)):
            dA = drivers[i]
            tA = df[df['Driver'] == dA]['Team'].values[0]
            posA = df[df['Driver'] == dA]['Position'].values[0]
            for j in range(i + 1, len(drivers)):
                dB = drivers[j]
                tB = df[df['Driver'] == dB]['Team'].values[0]
                posB = df[df['Driver'] == dB]['Position'].values[0]
                
                score = 1.0 if posA < posB else (0.0 if posA > posB else 0.5)
                
                EA = 1 / (1 + 10 ** ((curr_d[dB] - curr_d[dA]) / 400))
                delta_d = 32 * (score - EA)
                new_d[dA] += delta_d; new_d[dB] -= delta_d
                
                ETA = 1 / (1 + 10 ** ((curr_t[tB] - curr_t[tA]) / 400))
                delta_t = 24 * (score - ETA)
                new_t[tA] += delta_t; new_t[tB] -= delta_t
        
        self.driver_ratings, self.team_ratings = new_d, new_t

    def to_dict(self):
        """Serialize tracker state to a dictionary for pickling."""
        return {
            'driver_ratings': self.driver_ratings,
            'team_ratings': self.team_ratings,
            'base': self.base
        }

    @classmethod
    def from_dict(cls, data):
        """Reconstruct an EloTracker from a serialized dictionary."""
        tracker = cls(base=data.get('base', 1500))
        tracker.driver_ratings = data.get('driver_ratings', {})
        tracker.team_ratings = data.get('team_ratings', {})
        return tracker

# --- MAIN ENGINE ---
class DynastyEngine:
    def __init__(self):
        self.model = None
        self.tracker = None
        self.encoders = None
        self.train_df = None
        self.residuals = None
        try:
            self.registry = _ensure_registry()()
        except Exception as e:
            print(f"⚠️ ModelRegistry unavailable: {e}")
            self.registry = None
        self.load_artifacts()

    def load_artifacts(self):
        try:
            if os.path.exists(MODEL_PATH):
                self.model = joblib.load(MODEL_PATH)
            if os.path.exists(TRACKER_PATH):
                tracker_data = joblib.load(TRACKER_PATH)
                # Handle both old (object) and new (dict) formats
                if isinstance(tracker_data, dict):
                    self.tracker = EloTracker.from_dict(tracker_data)
                else:
                    # Legacy: object was pickled directly, extract its state
                    self.tracker = EloTracker.from_dict(tracker_data.__dict__)
            if os.path.exists(ENCODERS_PATH):
                artifacts = joblib.load(ENCODERS_PATH)
                self.encoders = artifacts['encoders']
                self.train_df = artifacts['train_df']
                self.residuals = artifacts['residuals']
                print("✅ Dynasty Engine artifacts loaded.")
                
                # Check for updates on load
                self.check_for_updates()
        except Exception as e:
            print(f"⚠️ Could not load artifacts: {e}")

    def check_for_updates(self):
        """
        Check if new race data is available and retrain if needed.
        """
        try:
            if self.train_df is None or self.train_df.empty:
                return # Let explicit train() handle it
                
            last_trained_year = self.train_df['Year'].max()
            last_trained_round = self.train_df[self.train_df['Year'] == last_trained_year]['Round'].max()
            
            # Get latest completed race from FastF1
            current_year = datetime.now().year
            _ensure_fastf1()  # Ensure FastF1 is loaded
            schedule = ff1.get_event_schedule(current_year)
            completed = schedule[schedule['EventDate'] < datetime.now()]
            
            if not completed.empty:
                latest_race = completed.iloc[-1]
                latest_year = current_year
                latest_round = latest_race['RoundNumber']
                
                # Compare
                if latest_year > last_trained_year or (latest_year == last_trained_year and latest_round > last_trained_round):
                    print(f"🔄 New race data found (Round {latest_round}). Retraining Dynasty Engine...")
                    self.train()
                else:
                    print("✅ Dynasty Engine is up to date.")
                    
        except Exception as e:
            print(f"⚠️ Error checking for updates: {e}")

    def train(self):
        print("⚙️ Training Dynasty Engine...")
        data = []
        current_year = datetime.now().year
        
        for year in range(2021, current_year + 1):
            try:
                schedule = ff1.get_event_schedule(year)
                if schedule.empty: continue
                if schedule['EventDate'].dt.tz is not None:
                    schedule['EventDate'] = schedule['EventDate'].dt.tz_localize(None)
                
                completed = schedule[schedule['EventDate'] < datetime.now()]
                
                for _, event in completed.iterrows():
                    # Check for Race session (Session5 is usually Race, but verify name)
                    # FastF1 schedule columns can vary, but usually Session5 is Race
                    # Safer to check session names if possible, but standard is Session5=Race
                    if event.get('Session5', '') != 'Race': continue
                    
                    try:
                        session = ff1.get_session(year, event['RoundNumber'], 'R')
                        session.load(laps=False, telemetry=False, weather=False, messages=False)
                        if session.results.empty: continue
                        
                        dna = get_track_dna(event['EventName'])
                        for _, row in session.results.iterrows():
                            data.append({
                                'Year': year, 'Round': event['RoundNumber'], 'Circuit': event['EventName'],
                                'Track_Type': dna['Type'], 'Overtaking_Fac': dna['Overtaking'],
                                'Driver': row['Abbreviation'], 'Team': row['TeamName'],
                                'Grid': row['GridPosition'], 'Position': row['Position'], 'Status': row['Status']
                            })
                    except Exception as e:
                        logger.debug(f"Failed to load session for round {event['RoundNumber']}: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Failed to process year {year}: {e}")
                continue
            
        df = pd.DataFrame(data)
        if df.empty: return False
        
        # Feature Engineering
        df = df.sort_values(['Year', 'Round'])
        df['Position'] = pd.to_numeric(df['Position'], errors='coerce').fillna(20)
        
        tracker = EloTracker()
        d_elos, t_elos = [], []
        
        for _, race in df.groupby(['Year', 'Round']):
            for _, row in race.iterrows():
                d_elos.append(tracker.get_rating(row['Driver']))
                t_elos.append(tracker.get_rating(row['Team'], is_team=True))
            tracker.update(race)
            
        df['Driver_Elo'] = d_elos
        df['Team_Elo'] = t_elos
        df['Form'] = df.groupby('Driver')['Position'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        df['Consistency'] = df.groupby('Driver')['Position'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).std()).fillna(3.0)
        df['Type_Affinity'] = df.groupby(['Driver', 'Track_Type'])['Position'].transform(lambda x: x.shift(1).expanding().mean())
        df['Reliability'] = df.groupby('Team')['Status'].transform(lambda x: x.shift(1).isin(['Finished', '+1 Lap']).rolling(10).mean()).fillna(0.8)
        df.fillna(0, inplace=True)
        
        le_d, le_t, le_tt = RobustEncoder(), RobustEncoder(), RobustEncoder()
        df['Driver_ID'] = le_d.fit_transform(df['Driver'])
        df['Team_ID'] = le_t.fit_transform(df['Team'])
        df['Type_ID'] = le_tt.fit_transform(df['Track_Type'])
        
        FEATS = ['Grid', 'Driver_Elo', 'Team_Elo', 'Form', 'Consistency', 'Type_Affinity', 'Overtaking_Fac', 'Reliability', 'Driver_ID', 'Team_ID', 'Type_ID']
        
        # Split
        unique_races = df[['Year', 'Round']].drop_duplicates().sort_values(['Year', 'Round'])
        cutoff_idx = max(1, len(unique_races) - 5)
        
        df['Race_Index'] = df.groupby(['Year', 'Round']).ngroup()
        train_mask = df['Race_Index'] < cutoff_idx
        val_mask = df['Race_Index'] >= cutoff_idx
        
        X_tr, y_tr = df[train_mask][FEATS], 21 - df[train_mask]['Position']
        g_tr = df[train_mask].groupby(['Year', 'Round']).size().to_numpy()
        
        g_tr = df[train_mask].groupby(['Year', 'Round']).size().to_numpy()
        
        # Train Model
        lgb = _ensure_lightgbm()  # Ensure LightGBM is loaded
        params = {
            'objective': 'lambdarank',
            'metric': 'ndcg',
            'n_estimators': 600,
            'learning_rate': 0.03,
            'random_state': 42
        }
        model = lgb.LGBMRanker(**params)
        model.fit(X_tr, y_tr, group=g_tr)
        
        # Calculate Validation Metrics
        preds = model.predict(df[val_mask][FEATS])
        residuals = []
        curr = 0
        mae_accum = 0
        count = 0
        
        for _, grp in df[val_mask].groupby(['Year', 'Round']):
            n = len(grp)
            p = preds[curr:curr+n]
            curr += n
            ranks = (-p).argsort().argsort() + 1
            res = grp['Position'].values - ranks
            residuals.extend(res)
            mae_accum += np.abs(res).mean()
            count += 1
            
        avg_mae = mae_accum / count if count > 0 else 0
        
        # Save Artifacts locally first (needed for inference)
        self.model = model
        self.tracker = tracker
        self.encoders = (le_d, le_t, le_tt)
        self.train_df = df
        self.residuals = np.array(residuals)
        
        joblib.dump(self.model, MODEL_PATH)
        joblib.dump(self.tracker.to_dict(), TRACKER_PATH)
        joblib.dump({'encoders': self.encoders, 'train_df': self.train_df, 'residuals': self.residuals}, ENCODERS_PATH)
        
        # Log to MLflow Registry (if available)
        if self.registry:
            try:
                self.registry.log_model(
                    model=model,
                    model_name="DynastyRanker",
                    model_type="lightgbm",
                    metrics={"val_mae": avg_mae},
                    params=params,
                    artifacts={
                        "tracker": TRACKER_PATH,
                        "encoders": ENCODERS_PATH
                    }
                )
            except Exception as e:
                print(f"⚠️ MLflow logging failed: {e}")
        
        print("✅ Dynasty Engine trained, saved, and logged to Registry.")
        return True

    def predict_next_race(self, year, race_name, weather_forecast='Dry', n_sims=1000):
        if self.model is None:
            if not self.train():
                return None
                
        dna = get_track_dna(race_name)
        
        # Grid Acquisition
        try:
            session = ff1.get_session(year, race_name, 'Q')
            session.load(laps=False, telemetry=False, weather=False, messages=False)
            if not session.results.empty:
                grid = session.results[['Abbreviation', 'TeamName', 'GridPosition']]
            else: raise ValueError
        except Exception as e:
            # Grid acquisition failed, use projection
            logger.info(f"Qualifying data unavailable for {race_name} ({year}), using projected grid: {e}")
            latest_year = self.train_df['Year'].max()
            active = self.train_df[self.train_df['Year'] == latest_year].drop_duplicates('Driver')
            active['Proj_Score'] = (active['Driver_Elo'] * 0.6) + (active['Team_Elo'] * 0.4)
            grid = active.sort_values('Proj_Score', ascending=False)[['Driver', 'Team', 'Proj_Score']]
            grid.columns = ['Abbreviation', 'TeamName', 'Proj_Score']
            grid['GridPosition'] = range(1, len(grid) + 1)
            
        N_DRIVERS = len(grid)
        le_d, le_t, le_tt = self.encoders
        FEATS = ['Grid', 'Driver_Elo', 'Team_Elo', 'Form', 'Consistency', 'Type_Affinity', 'Overtaking_Fac', 'Reliability', 'Driver_ID', 'Team_ID', 'Type_ID']
        rows = []
        
        for _, row in grid.iterrows():
            drv = row['Abbreviation']
            tm = row['TeamName']
            
            d_elo = self.tracker.get_rating(drv)
            t_elo = self.tracker.get_rating(tm, True)
            
            hist = self.train_df[self.train_df['Driver'] == drv].tail(1)
            if not hist.empty:
                form = hist['Form'].values[0]
                cons = hist['Consistency'].values[0]
                rel = hist['Reliability'].values[0]
                aff = hist['Type_Affinity'].values[0]
            else:
                form = 15; cons = 4.0; rel = 0.8; aff = 15
                
            rows.append([row['GridPosition'], d_elo, t_elo, form, cons, aff, dna['Overtaking'], rel, 
                         le_d.transform([drv])[0], le_t.transform([tm])[0], le_tt.transform([dna['Type']])[0], drv])
                         
        p_df = pd.DataFrame(rows, columns=FEATS + ['Driver'])
        
        # Simulation
        p_df['Base_Score'] = self.model.predict(p_df[FEATS])
        p_df = p_df.sort_values('Base_Score', ascending=False).reset_index(drop=True)
        base_ranks = p_df.index.values + 1
        
        matrix = np.zeros((N_DRIVERS, N_DRIVERS))
        errors = np.random.choice(self.residuals, size=(N_DRIVERS, n_sims))
        
        weather_mod = 1.5 if weather_forecast == 'Wet' else 1.0
        cons_mod = (p_df['Consistency'].values / 2.5).clip(0.5, 1.5)
        chaos_mod = (0.5 + (dna['Overtaking'] / 10.0)) * weather_mod
        
        final_errors = errors * cons_mod[:, np.newaxis] * chaos_mod
        sim_ranks = base_ranks[:, np.newaxis] + final_errors
        
        dnf_probs = 1.0 - p_df['Reliability'].values
        if weather_forecast == 'Wet': dnf_probs *= 1.5
        
        sim_ranks[np.random.random((N_DRIVERS, n_sims)) < dnf_probs[:, np.newaxis]] = 999
        
        for s in range(n_sims):
            col = sim_ranks[:, s]
            finishers = np.argsort(col)
            for r, idx in enumerate(finishers):
                if r < N_DRIVERS and sim_ranks[idx, s] < 900:
                    matrix[idx, r] += 1
                    
        probs = (matrix / n_sims) * 100
        output = []
        for i, row in p_df.iterrows():
            p = probs[i]
            output.append({
                'Driver': row['Driver'],
                'Win %': p[0],
                'Podium %': np.sum(p[:3]),
                'Points %': np.sum(p[:10]),
                'Avg Pos': np.sum(p * np.arange(1, N_DRIVERS+1)) / 100
            })
            
        return pd.DataFrame(output).sort_values('Win %', ascending=False)
