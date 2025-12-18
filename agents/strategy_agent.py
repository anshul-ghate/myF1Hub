"""
Strategy Agent.
Proactive agent that monitors race weekends and generates AI strategy insights.
"""
from datetime import datetime, timedelta
from agents.base import BaseAgent
from utils.ai import RaceEngineer
from utils.race_utils import get_schedule_with_fallback
import pytz

class StrategyAgent(BaseAgent):
    def __init__(self, interval=600): # Check every 10 minutes
        super().__init__(name="StrategyAgent", interval=interval)
        self.engineer = RaceEngineer()

    def perform_task(self):
        self.logger.info("Analyzing race calendar for strategic insights...")
        
        # Check if we are in a race weekend
        # Simplified logic: Get next race
        try:
            current_date = datetime.now()
            # This is a heuristic. In production we'd use robust schedule checking
            
            # For demonstration, we just generate a general insight about the "Next" race
            # We assume the AI Engineer can handle general queries
            
            insight = self.engineer.get_ai_insight("Provide a strategic outlook for the current/next F1 race weekend.")
            
            if insight:
                self.logger.info("Generated new strategic insight.")
                # We could save this to DB or publish
                self.publish("strategy_insight", {"content": insight, "timestamp": datetime.now().isoformat()})
                
                # Update status details with latest insight
                self._update_status_file("active", {"latest_insight": insight[:100] + "..."})
            
        except Exception as e:
            self.logger.error(f"Strategy analysis failed: {e}")

    def on_start(self):
        self.publish("agent_status", {"name": self.name, "status": "online"})
