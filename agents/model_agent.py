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
            # Check existense and metadata
            metadata = self.registry.get_model_metadata("HybridRanker", stage="Production")
            
            if not metadata and not force:
                self.logger.warning("No Production model found! Triggering training.")
                run_pipeline()
                self.publish("retraining_triggered", {"reason": "missing_model"})
                return

            # Check age
            if metadata:
                creation_time = datetime.fromtimestamp(metadata.creation_timestamp / 1000)
                age = datetime.now() - creation_time
                self.logger.info(f"Model age: {age.days} days (Created: {creation_time})")

                if age.days > self.max_model_age_days or force:
                    self.logger.info("Model is too old or force update requested. Triggering pipeline...")
                    run_pipeline()
                    self.publish("retraining_triggered", {"reason": "model_stale", "age_days": age.days})
                    return

            self.logger.info("Model health check passed.")
            self.publish("model_health_check", {"status": "healthy"})

        except Exception as e:
            self.logger.error(f"Model health check failed: {e}")
            self.publish("model_health_check", {"status": "error", "error": str(e)})

    def on_start(self):
        self.publish("agent_status", {"name": self.name, "status": "online"})
