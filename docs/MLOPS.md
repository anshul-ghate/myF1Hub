# MLOps Architecture & Guide

This document explains the MLOps infrastructure implemented for the F1 Strategy AI.

## 1. Experiment Tracking (MLflow)
We use **MLflow** to track all model training experiments.
- **Tracking URI**: Local `mlruns/` directory.
- **Experiments**:
    - `F1_Dynasty_Engine`: Tracks the ranking model (Elo + History).
    - `F1_Hybrid_Predictor`: Tracks the ensemble model (XGBoost + LightGBM).

### How to View Experiments
Run the following command in the terminal:
```bash
mlflow ui
```
Then open `http://localhost:5000` in your browser.

### Logged Information
- **Parameters**: `learning_rate`, `n_estimators`, `max_depth`, etc.
- **Metrics**: `ndcg`, `rmse`, `mae`.
- **Artifacts**: The serialized `.pkl` model files and feature importance plots.

## 2. Model Drift Monitoring (Evidently)
We use **Evidently** to detect data drift and model performance degradation.

- **Reports Location**: `monitoring/reports/`
- **Dashboard**: View reports in the Streamlit app under the **Model Health** page.

### generating a Report
Use the `ModelMonitor` class in `models/monitoring.py`:
```python
from models.monitoring import ModelMonitor
monitor = ModelMonitor()
monitor.generate_drift_report(train_df, new_data_df)
```

## 3. Training Pipeline
The training pipeline is triggered via:
1. **Manual Trigger**: `python scripts/run_pipeline.py`
2. **Auto-Update**: The `HybridPredictor` checks for new race data on initialization and retrains if necessary.
