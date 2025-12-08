# F1 Prediction Model Approach

This document provides a detailed technical overview of the machine learning models and prediction methodology used in PitWall AI.

## Table of Contents

1. [Overview](#overview)
2. [DynastyEngine - LightGBM Ranker](#dynastyengine---lightgbm-ranker)
3. [HybridPredictor - XGBoost Ensemble](#hybridpredictor---xgboost-ensemble)
4. [Monte Carlo Simulation](#monte-carlo-simulation)
5. [Feature Engineering Pipeline](#feature-engineering-pipeline)
6. [Track DNA System](#track-dna-system)
7. [Elo Rating System](#elo-rating-system)
8. [Model Training & Evaluation](#model-training--evaluation)

---

## Overview

PitWall AI employs a **multi-model ensemble approach** to predict F1 race outcomes. The system combines:

1. **LightGBM LambdaRank** - Optimized for ranking race positions
2. **XGBoost Regressor** - Predicts expected finishing position
3. **Monte Carlo Simulation** - Generates probability distributions
4. **Elo Rating System** - Tracks dynamic driver/team performance

This approach allows us to:
- Capture complex non-linear relationships in race data
- Quantify uncertainty through probabilistic predictions
- Adapt to changing performance levels throughout a season
- Account for circuit-specific characteristics

---

## DynastyEngine - LightGBM Ranker

### Architecture

The DynastyEngine is the core prediction model, using **LightGBM's LambdaRank** objective which is specifically designed for learning-to-rank problems.

```python
lgb_params = {
    'objective': 'lambdarank',
    'metric': 'ndcg',
    'num_leaves': 31,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'verbose': -1,
    'n_estimators': 200
}
```

### Key Components

1. **Position Ranking Optimization**
   - Unlike regression which predicts absolute positions, LambdaRank optimizes for correct ordering
   - Uses NDCG (Normalized Discounted Cumulative Gain) as the evaluation metric
   - Better captures the relative nature of race finishing positions

2. **Residual Modeling**
   - After training, residuals (actual - predicted) are stored
   - These residuals capture uncertainty and variance in predictions
   - Used in Monte Carlo simulations to add realistic noise

3. **Incremental Updates**
   - Checks for new race data automatically
   - Retrains when new results are available
   - Maintains Elo ratings across training sessions

### Training Data

- **Historical races from 2021-present** (configurable)
- **Features per driver-race combination**:
  - Driver Elo rating
  - Team Elo rating
  - Track type encoding
  - Overtaking difficulty score
  - Weather conditions

---

## HybridPredictor - XGBoost Ensemble

### Architecture

The HybridPredictor adds an XGBoost layer on top of DynastyEngine for enhanced accuracy:

```python
xgb_params = {
    'objective': 'reg:squarederror',
    'learning_rate': 0.1,
    'max_depth': 6,
    'n_estimators': 150,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0
}
```

### How It Works

1. **Feature Aggregation**
   - Combines DynastyEngine features with enhanced features
   - Includes recent form (last 3 races)
   - Adds qualifying position and grid penalties

2. **Position Regression**
   - Predicts expected finishing position directly
   - Complementary to LightGBM's ranking approach
   - Helps calibrate absolute position expectations

3. **Model Blending**
   - Final prediction combines both models:
   ```python
   blended_score = 0.6 * lgbm_rank + 0.4 * xgb_position
   ```

---

## Monte Carlo Simulation

### Purpose

Monte Carlo simulation converts point predictions into **probability distributions**, answering questions like:
- "What's the probability of Max Verstappen winning?"
- "How likely is a podium finish for McLaren?"

### Algorithm

```python
def simulate_race(n_simulations=5000):
    results = []
    
    for sim in range(n_simulations):
        # 1. Get base predictions from ML models
        base_predictions = model.predict(features)
        
        # 2. Add noise from residual distribution
        noise = sample_from_residuals(driver)
        simulated_position = base_predictions + noise
        
        # 3. Handle first-lap incidents
        if random() < first_lap_incident_rate:
            apply_random_position_changes()
        
        # 4. Apply reliability factors
        if random() < dnf_probability[team]:
            simulated_position = DNF
        
        # 5. Rank drivers by simulated position
        race_result = rank_drivers(simulated_position)
        results.append(race_result)
    
    # Aggregate results
    return calculate_probabilities(results)
```

### Key Features

1. **Residual Sampling**
   - Uses historical prediction errors to model uncertainty
   - Different drivers have different variance profiles
   - Maintains realistic prediction intervals

2. **DNF Modeling**
   - Team-specific reliability factors based on historical DNF rates
   - Mechanical failures, crashes, and other incidents modeled

3. **Wet Weather Adjustments**
   - Modified variance in wet conditions
   - Some drivers perform better/worse in rain (rain masters)

---

## Feature Engineering Pipeline

### Input Features

| Feature | Description | Type |
|---------|-------------|------|
| `driver_elo` | Current driver Elo rating | Numeric |
| `team_elo` | Current team Elo rating | Numeric |
| `track_type` | Circuit classification | Categorical |
| `overtaking_score` | Track overtaking difficulty (1-10) | Numeric |
| `is_wet` | Weather conditions | Binary |
| `grid_position` | Qualifying grid position | Numeric |
| `recent_form` | Average finish last 3 races | Numeric |
| `track_experience` | Races at this circuit | Numeric |

### Feature Transformations

```python
class FeatureEngineer:
    def transform(self, df):
        # One-hot encode track type
        track_dummies = pd.get_dummies(df['track_type'], prefix='track')
        
        # Scale Elo ratings
        df['driver_elo_scaled'] = (df['driver_elo'] - 1500) / 200
        df['team_elo_scaled'] = (df['team_elo'] - 1500) / 200
        
        # Recent form normalization
        df['recent_form_norm'] = df['recent_form'] / 20
        
        return pd.concat([df, track_dummies], axis=1)
```

### Robust Encoding

A custom `RobustEncoder` handles unseen categorical values:

```python
class RobustEncoder:
    """Handles unknown categories gracefully during prediction."""
    
    def fit(self, y):
        self.mapping = {val: idx for idx, val in enumerate(y.unique())}
        self.unknown_token = -1
    
    def transform(self, y):
        return y.map(lambda x: self.mapping.get(x, self.unknown_token))
```

---

## Track DNA System

### Circuit Classification

Each F1 circuit has unique characteristics that affect race outcomes. The Track DNA system classifies circuits:

```python
TRACK_DNA = {
    'Bahrain': {'Type': 'Balanced', 'Overtaking': 8},
    'Saudi': {'Type': 'Street_Fast', 'Overtaking': 7},
    'Australia': {'Type': 'Street_Fast', 'Overtaking': 6},
    'Japan': {'Type': 'Technical', 'Overtaking': 4},
    'China': {'Type': 'Balanced', 'Overtaking': 7},
    'Miami': {'Type': 'Street_Fast', 'Overtaking': 6},
    'Monaco': {'Type': 'Technical', 'Overtaking': 1},
    'Spain': {'Type': 'Technical', 'Overtaking': 4},
    'Canada': {'Type': 'High_Speed', 'Overtaking': 8},
    'Austria': {'Type': 'High_Speed', 'Overtaking': 8},
    'UK': {'Type': 'High_Speed', 'Overtaking': 5},
    'Hungary': {'Type': 'Technical', 'Overtaking': 3},
    'Belgium': {'Type': 'High_Speed', 'Overtaking': 7},
    'Netherlands': {'Type': 'Technical', 'Overtaking': 2},
    'Italy': {'Type': 'High_Speed', 'Overtaking': 9},
    'Azerbaijan': {'Type': 'Street_Fast', 'Overtaking': 8},
    'Singapore': {'Type': 'Technical', 'Overtaking': 3},
    'USA': {'Type': 'Balanced', 'Overtaking': 6},
    'Mexico': {'Type': 'Balanced', 'Overtaking': 6},
    'Brazil': {'Type': 'Balanced', 'Overtaking': 9},
    'Las Vegas': {'Type': 'Street_Fast', 'Overtaking': 8},
    'Qatar': {'Type': 'High_Speed', 'Overtaking': 6},
    'Abu Dhabi': {'Type': 'Balanced', 'Overtaking': 5},
}
```

### Track Type Characteristics

| Type | Description | Impact on Predictions |
|------|-------------|----------------------|
| **High_Speed** | Long straights, high top speeds | Favors power unit strength, more position changes |
| **Technical** | Complex corner sequences | Favors driver skill, aero setup, fewer overtakes |
| **Street_Fast** | Street circuits with fast sections | Higher variance, safety car likelihood |
| **Balanced** | Mix of characteristics | Most neutral predictions |

---

## Elo Rating System

### Overview

The Elo system provides a dynamic rating for drivers and teams that updates after each race.

### Algorithm

```python
class EloTracker:
    def __init__(self, base=1500):
        self.driver_ratings = {}
        self.team_ratings = {}
        self.base = base
    
    def update(self, race_results):
        K = 32  # Update factor
        
        for i, driver_a in enumerate(race_results):
            for j, driver_b in enumerate(race_results):
                if i >= j:
                    continue
                
                # Expected score
                rating_a = self.driver_ratings[driver_a]
                rating_b = self.driver_ratings[driver_b]
                expected_a = 1 / (1 + 10**((rating_b - rating_a) / 400))
                
                # Actual score (1 if A finished ahead, 0 otherwise)
                actual_a = 1 if i < j else 0
                
                # Update ratings
                delta = K * (actual_a - expected_a)
                self.driver_ratings[driver_a] += delta
                self.driver_ratings[driver_b] -= delta
```

### Features

1. **Separate Driver and Team Ratings**
   - Driver ratings capture individual performance
   - Team ratings capture car competitiveness
   - Both contribute independently to predictions

2. **Pairwise Comparisons**
   - Every driver is compared against every other driver in each race
   - More meaningful than simple position-based updates

3. **Persistence**
   - Ratings are saved and loaded between training sessions
   - Enables continuous tracking across seasons

---

## Model Training & Evaluation

### Training Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    Training Pipeline                         │
├─────────────────────────────────────────────────────────────┤
│  1. Data Collection                                          │
│     └── Fetch race results via FastF1 API                   │
├─────────────────────────────────────────────────────────────┤
│  2. Feature Engineering                                      │
│     ├── Calculate/update Elo ratings                        │
│     ├── Encode track characteristics                        │
│     └── Generate training features                          │
├─────────────────────────────────────────────────────────────┤
│  3. Model Training                                           │
│     ├── Train LightGBM ranker                               │
│     ├── Train XGBoost regressor                             │
│     └── Calculate and store residuals                       │
├─────────────────────────────────────────────────────────────┤
│  4. Model Persistence                                        │
│     ├── Save model artifacts                                │
│     ├── Save encoders                                       │
│     └── Save Elo tracker state                              │
└─────────────────────────────────────────────────────────────┘
```

### Evaluation Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **NDCG** | Ranking quality metric | > 0.85 |
| **Position MAE** | Mean absolute position error | < 3.0 |
| **Top-3 Accuracy** | % correct podium predictions | > 60% |
| **Winner Accuracy** | % correct winner predictions | > 40% |

### Validation Strategy

- **Train/Test Split**: Last 3 races used as holdout
- **Cross-Validation**: 5-fold CV on historical data
- **Out-of-Sample**: New season races as ultimate test

---

## Future Improvements

1. **Qualifying Prediction Model** - Separate model for qualifying positions
2. **Pit Strategy Optimization** - ML-based tire strategy recommendations
3. **Weather Integration** - Real-time weather API integration
4. **Driver Form Tracking** - Short-term performance momentum
5. **Team Development Curves** - Model car development over season

---

## References

- [LightGBM LambdaRank](https://lightgbm.readthedocs.io/en/latest/Parameters.html#objective)
- [Elo Rating System](https://en.wikipedia.org/wiki/Elo_rating_system)
- [FastF1 Documentation](https://docs.fastf1.dev/)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
