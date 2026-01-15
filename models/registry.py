import mlflow
import mlflow.sklearn
import mlflow.lightgbm
import mlflow.xgboost
from mlflow.tracking import MlflowClient
from typing import Optional, Dict, Any, Union
import pandas as pd
import numpy as np
from datetime import datetime

from utils.logger import get_logger
from utils.mlflow_config import configure_mlflow, EXPERIMENT_NAME

logger = get_logger("ModelRegistry")

class ModelRegistry:
    """
    Wrapper for MLflow Model Registry operations.
    Handles model logging, loading, and stage transitions.
    """
    
    def __init__(self):
        configure_mlflow()
        self.client = MlflowClient()
        
    def log_model(self, 
                  model: Any, 
                  model_name: str, 
                  model_type: str,
                  metrics: Dict[str, float], 
                  params: Dict[str, Any],
                  artifacts: Optional[Dict[str, str]] = None,
                  input_example: Optional[Union[pd.DataFrame, np.ndarray]] = None,
                  register_model: bool = True):
        """
        Log a model to MLflow and optionally register it.
        
        Args:
            model: The trained model object
            model_name: Name to register the model under (e.g. "DynastyRanker")
            model_type: "sklearn", "lightgbm", "xgboost"
            metrics: Dictionary of evaluation metrics
            params: Dictionary of hyperparameters
            artifacts: Dictionary of extra file paths to log
            input_example: Sample input for signature inference
            register_model: Whether to register as a new version
        """
        try:
            with mlflow.start_run(run_name=f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M')}"):
                # Log params and metrics
                mlflow.log_params(params)
                mlflow.log_metrics(metrics)
                
                # Log artifacts
                if artifacts:
                    for name, path in artifacts.items():
                        mlflow.log_artifact(path, artifact_path="extras")
                
                # Log Model based on type
                if model_type == "sklearn":
                    mlflow.sklearn.log_model(
                        sk_model=model, 
                        name="model",
                        registered_model_name=model_name if register_model else None,
                        input_example=input_example
                    )
                elif model_type == "lightgbm":
                    mlflow.lightgbm.log_model(
                        lgbm_model=model, 
                        name="model", 
                        registered_model_name=model_name if register_model else None,
                        input_example=input_example
                    )
                elif model_type == "xgboost":
                    mlflow.xgboost.log_model(
                        xgb_model=model, 
                        name="model", 
                        registered_model_name=model_name if register_model else None,
                        input_example=input_example
                    )
                else:
                    # Fallback to generic pyfunc or pickle
                    mlflow.sklearn.log_model(
                        sk_model=model, 
                        name="model", 
                        registered_model_name=model_name if register_model else None
                    )
                
                logger.info(f"Successfully logged model: {model_name} (Type: {model_type})")
                
        except Exception as e:
            logger.error(f"Failed to log model {model_name}: {e}")
            raise

    def load_model(self, model_name: str, stage: str = "Production") -> Any:
        """
        Load a model from the registry.
        Tries to load 'Production' first, then 'Staging', then 'None' (latest).
        """
        try:
            # Try specified stage
            model_uri = f"models:/{model_name}/{stage}"
            logger.info(f"Attempting to load model from: {model_uri}")
            
            # Helper to load based on flavor - usually pyfunc is enough for prediction
            # But if we need the native object (e.g. for further training or specific attrs),
            # we might need specific loaders. 
            # For now, let's try generic load_model which returns the native flavor if possible
            # or use specific loaders associated with the registry metadata if we tracked it.
            
            # Simple approach: try loading as PyFunc first for generic use
            # But wait, PyFunc might not expose feature_importances_. 
            # We should probably use the specific flavors.
            
            # Let's inspect potential versions first to know the flavor? 
            # Or just try/except generic flavors.
            
            try:
                # Try generic load (works for sklearn/lgbm if logged correctly)
                return mlflow.pyfunc.load_model(model_uri)
            except:
                 # If pyfunc fails, we might need specific
                 pass
                 
            # If we really need the underlying model object (e.g. LightGBM Booster)
            # we might need to use mlflow.lightgbm.load_model(model_uri)
            # But we don't know the type here easily without querying.
            
            # Getting run info to determine flavor is cleaner
            latest = self.client.get_latest_versions(model_name, stages=[stage])
            if not latest:
                logger.warning(f"No {stage} model found for {model_name}")
                if stage == "Production":
                     return self.load_model(model_name, "Staging")
                if stage == "Staging":
                     return self.load_model(model_name, "None") # Latest
                return None
                
            run_id = latest[0].run_id
            # This is complex. Let's stick to a robust default:
            # If we know what we are loading (caller usually knows), we could have `load_lightgbm_model` etc.
            # For now, return generic pyfunc, it handles prediction well.
            
            return mlflow.pyfunc.load_model(model_uri)

        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return None
            
    def load_native_model(self, model_name: str, stage: str = "Production", flavor: str = "sklearn") -> Any:
        """Load the native model object (e.g. sklearn estimator, XGBoost booster)."""
        model_uri = f"models:/{model_name}/{stage}"
        try:
            if flavor == "sklearn":
                return mlflow.sklearn.load_model(model_uri)
            elif flavor == "lightgbm":
                return mlflow.lightgbm.load_model(model_uri)
            elif flavor == "xgboost":
                return mlflow.xgboost.load_model(model_uri)
            else:
                return mlflow.pyfunc.load_model(model_uri)
        except Exception as e:
            logger.error(f"Failed to load native model {model_name} (flavor: {flavor}): {e}")
            return None

    def get_model_metadata(self, model_name: str, stage: str = "Production") -> Optional[Any]:
        """Get metadata for a specific model stage."""
        try:
            latest = self.client.get_latest_versions(model_name, stages=[stage])
            if not latest:
                return None
            return latest[0]
        except Exception as e:
            logger.error(f"Failed to get metadata for {model_name}: {e}")
            return None

    def transition_stage(self, model_name: str, version: int, stage: str):
        """Transition a model version to a new stage."""
        try:
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage,
                archive_existing_versions=True # Archive previous Prod versions
            )
            logger.info(f"Transitioned {model_name} v{version} to {stage}")
        except Exception as e:
            logger.error(f"Failed to transition model stage: {e}")
            raise
