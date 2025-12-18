"""
Base Agent Class.
"""
from abc import ABC, abstractmethod
import threading
import time
import json
import os
from datetime import datetime
from typing import Dict, Any
from utils.logger import get_logger
from agents.message_bus import bus

STATUS_FILE = "data/agent_status.json"


class BaseAgent(ABC):
    def __init__(self, name: str, interval: int = 60):
        self.name = name
        self.interval = interval # Loop interval in seconds
        self.logger = get_logger(f"Agent.{name}")
        self.running = False
        self.thread = None
        self._setup_subscriptions()

    def _setup_subscriptions(self):
        """Override to subscribe to topics."""
        pass

    
    def _update_status_file(self, state: str, details: Dict = None):
        """Update the agent's status in the shared JSON file."""
        try:
            if not os.path.exists('data'):
                os.makedirs('data')
                
            data = {}
            if os.path.exists(STATUS_FILE):
                try:
                    with open(STATUS_FILE, 'r') as f:
                        data = json.load(f)
                except:
                    data = {}
            
            data[self.name] = {
                "state": state,
                "last_heartbeat": datetime.now().isoformat(),
                "interval": self.interval,
                "details": details or {}
            }
            
            with open(STATUS_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to update status file: {e}")

    def start(self):
        """Start the agent's main loop."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self._update_status_file("running", {"started_at": datetime.now().isoformat()})
        self.logger.info(f"{self.name} started.")
        self.on_start()

    def stop(self):
        """Stop the agent."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        self._update_status_file("stopped", {"stopped_at": datetime.now().isoformat()})
        self.logger.info(f"{self.name} stopped.")
        self.on_stop()

    def _run_loop(self):
        """Internal loop runner."""
        while self.running:
            try:
                self._update_status_file("active") # Heartbeat
                self.perform_task()
            except Exception as e:
                self.logger.error(f"Error in {self.name} loop: {e}")
                self._update_status_file("error", {"last_error": str(e)})
            
            time.sleep(self.interval)

    @abstractmethod
    def perform_task(self):
        """Main autonomous task to run periodically."""
        pass

    def on_start(self):
        pass

    def on_stop(self):
        pass

    def publish(self, topic: str, message: Any):
        bus.publish(topic, message)

    def subscribe(self, topic: str, handler):
        bus.subscribe(topic, handler)
