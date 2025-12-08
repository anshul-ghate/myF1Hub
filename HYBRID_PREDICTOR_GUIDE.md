# Hybrid F1 Prediction Engine - Quick Start Guide

## Overview

The new **Hybrid Prediction Engine v8.0** combines multiple machine learning approaches for the most accurate F1 race predictions:

- **LightGBM Ranker** + **XGBoost Regressor** (multi-model ensemble)
- **25+ engineered features** from all data sources
- **Monte Carlo simulation** with 5,000-10,000 iterations
- **Auto-retraining** when new race data is available

---

## Quick Start

### 1. Run the App

```bash
python -m streamlit run app/main.py
```

Navigate to **Race Predictions** page (🔮 icon in sidebar)

### 2. Generate a Prediction

1. Select a race (use "Next Upcoming Race" or manual selection)
2. Configure parameters:
   - **Simulations**: 1,000-10,000 (more = more accurate but slower)
   - **Weather**: Dry or Wet
   - **Show Insights**: Toggle feature importances
3. Click **"Run Hybrid Prediction"**

### 3. Interpret Results

**Top Section**: Most likely winner + podium finishers with win probabilities

**Full Table**: All drivers with:
- Win %: Probability of P1 finish
- Podium %: Probability of P1-P3 finish
- Points %: Probability of P1-P10 finish
- Top 5 %: Probability of P1-P5 finish
- Avg Pos: Expected finishing position
- DNF %: Did Not Finish probability

**Feature Importances**: Shows which factors most influence predictions

---

## What's New vs Previous Approaches

### Dynasty Engine v7.0 (Old)
✅ Elo ratings, track DNA
❌ Limited features (11 features)
❌ Single model approach

### Race Simulator (Old)
✅ Lap-by-lap simulation
❌ Simple feature engineering
❌ No ensemble methods

### Hybrid Engine v8.0 (NEW) ⭐
✅ **Multi-model ensemble** (LightGBM + XGBoost)
✅ **25+ comprehensive features**:
  - Driver: Form, consistency, circuit history, quali vs race delta
  - Team: Reliability, pit stop efficiency
  - Circuit: Type, overtaking difficulty, SC probability
  - Weather: Temperature, humidity, rainfall
  - Strategic: Grid positions, historical patterns
✅ **Advanced Monte Carlo** with driver-specific uncertainty
✅ **Auto-retraining** on new data
✅ **Explainability** via feature importances

---

## Training the Model

### Automatic (Recommended)

Model auto-trains when:
- First time running the app
- New race data is detected

### Manual Training

```bash
python -c "from models.hybrid_predictor import HybridPredictor; hp = HybridPredictor(); hp.train()"
```

Training time: **5-15 minutes** (depends on data size)

---

## Testing & Validation

Run the test suite:

```bash
python tests/test_hybrid_predictor.py
```

Tests:
1. ✅ Initialization
2. ✅ Model Training
3. ✅ Race Prediction
4. ✅ Feature Importances

---

## Architecture

```
Hybrid Predictor
├── Stage 1: Feature Engineering (enhanced_features.py)
│   ├── Driver features (8 metrics)
│   ├── Team features (4 metrics)
│   ├── Circuit features (6 metrics)
│   └── Weather features (5 metrics)
│
├── Stage 2: Multi-Model Ensemble (hybrid_predictor.py)
│   ├── LightGBM Ranker (60% weight)
│   ├── XGBoost Regressor (40% weight)
│   └── Weighted combination
│
└── Stage 3: Monte Carlo Simulation
    ├── 5,000-10,000 simulations
    ├── Driver-specific uncertainty
    ├── Weather chaos multiplier
    └── DNF probability modeling
```

---

## Data Sources Used

The hybrid engine utilizes ALL available database tables:

- ✅ `races` - Race metadata and schedule
- ✅ `race_results` - Final positions and grid
- ✅ `drivers` - Driver information
- ✅ `laps` - Lap-by-lap timing data
- ✅ `weather` - Track conditions
- ✅ `pit_stops` - Pit strategy data
- ✅ `qualifying` - Grid positions
- ✅ Dynasty Engine Elo ratings
- ✅ Track DNA characteristics

---

## Troubleshooting

**Error: "No models found"**
→ Model needs training. Will auto-train on first run.

**Error: "Prediction failed"**
→ Check if race has qualifying data or historical driver data.

**Slow predictions**
→ Reduce simulation count (1,000-3,000 for faster results).

**Models out of date**
→ Restart app to trigger update check and auto-retraining.

---

## Performance Expectations

Based on backtesting (results may vary):

| Metric | Target |
|--------|--------|
| Winner Accuracy | >60% |
| Top 3 Accuracy | >50% |
| Top 10 Overlap | >70% |
| Mean Position Error | <3.0 positions |

---

## Future Enhancements

Potential improvements:
- [ ] Neural network third model
- [ ] Tire degradation modeling
- [ ] Strategy optimization
- [ ] Real-time updates during race weekend
- [ ] Backtesting dashboard
- [ ] Confidence intervals per driver

---

## Credits

**Hybrid Engine v8.0**
- LightGBM Ranker (inspired by Dynasty Engine v7.0)
- XGBoost Position Predictor (new)
- Enhanced Feature Engineering (25+ features)
- Multi-Model Ensemble Architecture (new)

Powered by FastF1, Supabase, and open-source ML libraries.
