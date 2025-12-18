"""
Data Agent.
Monitors race schedule and data freshness.
Triggers ingestion and materialization pipelines.
"""
from agents.base import BaseAgent
from pipelines.orchestrator import run_pipeline
import traceback

class DataAgent(BaseAgent):
    def __init__(self, interval=3600): # Check every hour by default
        super().__init__(name="DataAgent", interval=interval)

    def perform_task(self):
        self.logger.info("Checking for new data...")
        try:
            # We defer to the pipeline orchestrator logic which handles
            # checking vs DB and ingesting if needed.
            # In a more granular agent, we might check first, then publish "DataNeeded" event.
            # For now, we run the pipeline directly.
            
            run_pipeline()
            
            self.publish("data_check_complete", {"status": "success"})
            
        except Exception as e:
            self.logger.error(f"Data pipeline execution failed: {e}")
            self.publish("data_check_failed", {"error": str(e)})

    def on_start(self):
        self.publish("agent_status", {"name": self.name, "status": "online"})
