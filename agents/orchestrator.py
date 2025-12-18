"""
Agent Orchestrator.
Manages the lifecycle of all AI agents.
"""
import time
import signal
import sys
from typing import List
from agents.base import BaseAgent
from utils.logger import get_logger

logger = get_logger("AgentOrchestrator")

class AgentOrchestrator:
    def __init__(self):
        self.agents: List[BaseAgent] = []
        self.running = False

    def register_agent(self, agent: BaseAgent):
        self.agents.append(agent)
        logger.info(f"Registered agent: {agent.name}")

    def start_all(self):
        logger.info("Starting all agents...")
        self.running = True
        for agent in self.agents:
            agent.start()
            
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_all()

    def stop_all(self):
        logger.info("Stopping all agents...")
        self.running = False
        for agent in self.agents:
            agent.stop()
        logger.info("System shutdown complete.")
        sys.exit(0)

    def _handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}")
        self.stop_all()

if __name__ == "__main__":
    from agents.data_agent import DataAgent
    from agents.model_agent import ModelAgent
    from agents.strategy_agent import StrategyAgent

    orch = AgentOrchestrator()
    
    # Register Agents
    orch.register_agent(DataAgent())     # Interval: 1h
    orch.register_agent(ModelAgent())    # Interval: 24h
    orch.register_agent(StrategyAgent()) # Interval: 10m
    
    orch.start_all()
