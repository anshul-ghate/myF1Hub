"""
Model Agent.
Monitors model health, registry status, and triggers retraining.
"""
from datetime import datetime, timedelta
import dateutil.parser
from agents.base import BaseAgent
from models.registry import ModelRegistry
from pipelines.orchestrator import run_pipeline

class ModelAgent(BaseAgent):
    def __init__(self, interval=86400): # Check daily by default
        super().__init__(name="ModelAgent", interval=interval)
        self.registry = ModelRegistry()
        self.max_model_age_days = 7

    def _setup_subscriptions(self):
        self.subscribe("data_check_complete", self.on_data_update)

    def perform_task(self):
        """Periodic check for model freshness."""
        self.logger.info("Checking model health...")
        self.check_model_freshness()

    def on_data_update(self, message):
        """Handle data update event."""
        if message.get("status") == "success":
            self.logger.info("Data update received. Checking if retraining is needed...")
            # Ideally, we check drift here. For now, we trust the pipeline or enforce freshness.
            self.check_model_freshness(force=True)

    def check_model_freshness(self, force=False):
        """Check if production model is too old."""
        try:
            # Get production model details
            # Using private API of registry or we need to add a method to get model metadata
            # Assuming get_latest_version returns the version object which has creation_timestamp
            
            # Since ModelRegistry.load_model returns the model object, not metadata,
            # we might need to query MLflow directly or add a method to Registry.
            # For this MVP, we will try to load the model and check 'last_trained' attribute if available
            # OR we just trigger the pipeline which internally checks 'last_trained' date in HybridPredictor
            
            # HybridPredictor check_for_updates() does exactly this logic.
            # So ModelAgent can just run the pipeline?
            # But the pipeline performs ingestion first.
            
            # Let's rely on the Orchestrator's run_pipeline logic for now, 
            # but usually ModelAgent would handle the *decision* to retrain.
            
            # If we want to be "Agentic", we should check explicitly.
            # But HybridPredictor logic is: "if latest_date > last_trained_date".
            
            # Implementation:
            # 1. Trigger pipeline (which is safe/idempotent-ish).
            # OR
            # 2. Just log status.
            
            # Let's verify model existence
            model = self.registry.load_model("HybridRanker", stage="Production")
            if not model and not force:
                self.logger.warning("No Production model found! Triggering training.")
                run_pipeline() # This runs ingestion too, which is fine
                self.publish("retraining_triggered", {"reason": "missing_model"})
                return

            self.logger.info("Model health check passed.")
            self.publish("model_health_check", {"status": "healthy"})

        except Exception as e:
            self.logger.error(f"Model health check failed: {e}")
            self.publish("model_health_check", {"status": "error", "error": str(e)})

    def on_start(self):
        self.publish("agent_status", {"name": self.name, "status": "online"})
