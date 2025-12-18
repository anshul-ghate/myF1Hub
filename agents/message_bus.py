"""
Simple In-Memory Message Bus for Agent Communication.
"""
from typing import Dict, List, Any, Callable
from collections import defaultdict
from utils.logger import get_logger

logger = get_logger("MessageBus")

class MessageBus:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MessageBus, cls).__new__(cls)
            cls._instance.subscribers = defaultdict(list)
        return cls._instance

    def subscribe(self, topic: str, handler: Callable):
        """Subscribe a handler function to a topic."""
        self.subscribers[topic].append(handler)
        logger.debug(f"Subscribed to {topic}")

    def publish(self, topic: str, message: Any):
        """Publish a message to a topic."""
        logger.debug(f"Publishing to {topic}: {message}")
        if topic in self.subscribers:
            for handler in self.subscribers[topic]:
                try:
                    handler(message)
                except Exception as e:
                    logger.error(f"Error handling message on {topic}: {e}")

# Global instance
bus = MessageBus()
