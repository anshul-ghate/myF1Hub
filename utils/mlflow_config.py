import mlflow
import os
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("MLflowConfig")

# Configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns")
EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "F1_PitWall_AI")

def configure_mlflow():
    """
    Configure MLflow for the application.
    Sets the tracking URI and ensures the experiment exists.
    """
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        logger.info(f"MLflow tracking URI set to: {MLFLOW_TRACKING_URI}")
        
        # Check if experiment exists, create if not
        experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
        if experiment is None:
            mlflow.create_experiment(EXPERIMENT_NAME)
            logger.info(f"Created new MLflow experiment: {EXPERIMENT_NAME}")
        else:
            logger.info(f"Using existing MLflow experiment: {EXPERIMENT_NAME}")
            
        mlflow.set_experiment(EXPERIMENT_NAME)
        
    except Exception as e:
        logger.error(f"Failed to configure MLflow: {e}")
        # We might not want to raise here to allow offline mode if needed, 
        # but for MLOps it's critical.
        raise

def get_experiment_id():
    """Get the current experiment ID."""
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    return experiment.experiment_id if experiment else None
