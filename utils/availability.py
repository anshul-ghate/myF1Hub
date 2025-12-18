"""
Availability & Resilience Patterns

This module implements resilience patterns for external dependencies:
- Circuit Breaker: Prevents cascading failures when a service is down.
- Fallback: Provides default behavior when primary methods fail.
"""

import time
import functools
from typing import Callable, Any, Optional, Dict
from datetime import datetime, timedelta
import threading
from utils.logger import get_logger

logger = get_logger("Availability")

class CircuitBreakerOpenException(Exception):
    """Raised when the circuit breaker is open."""
    pass

class CircuitBreaker:
    """
    Circuit Breaker implementation.
    
    States:
    - CLOSED: Normal operation. Calls go through.
    - OPEN: Service is down. Calls fail fast.
    - HALF-OPEN: Probings. Allow one call effectively to check recovery.
    """
    
    def __init__(self, 
                 name: str, 
                 failure_threshold: int = 5, 
                 recovery_timeout: int = 60,
                 expected_exceptions: tuple = (Exception,)):
        """
        Args:
            name: Name of the circuit (e.g. 'FastF1', 'Supabase')
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before probing (Half-Open)
            expected_exceptions: Exceptions that count as failures
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.RLock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute the function with circuit breaker logic."""
        with self._lock:
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    logger.info(f"Circuit {self.name} is HALF-OPEN, probing...")
                else:
                    raise CircuitBreakerOpenException(f"Circuit {self.name} is OPEN")
            
            if self.state == "HALF_OPEN":
                # In half-open, we allow one call. If it fails, back to open.
                # If success, back to closed.
                pass

        try:
            result = func(*args, **kwargs)
            
            # Success
            with self._lock:
                if self.state == "HALF_OPEN":
                    logger.info(f"Circuit {self.name} closed (recovered).")
                
                if self.failure_count > 0:
                    self.failure_count = 0
                self.state = "CLOSED"
            
            return result
            
        except self.expected_exceptions as e:
            with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.state == "HALF_OPEN" or self.failure_count >= self.failure_threshold:
                    if self.state != "OPEN":
                        logger.error(f"Circuit {self.name} OPENED after {self.failure_count} failures. Last error: {e}")
                    self.state = "OPEN"
            
            raise e

# Global Circuit Breakers
_breakers: Dict[str, CircuitBreaker] = {}

def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name, **kwargs)
    return _breakers[name]

def circuit_breaker(name: str, **cb_kwargs):
    """Decorator to apply circuit breaker to a function."""
    def decorator(func):
        cb = get_circuit_breaker(name, **cb_kwargs)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return cb.call(func, *args, **kwargs)
        return wrapper
    return decorator

def with_fallback(fallback_value: Any = None, fallback_func: Callable = None):
    """
    Decorator to provide fallback value on failure.
    Catches exceptions (including CircuitBreakerOpenException) and returns fallback.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Function {func.__name__} failed, using fallback. Error: {e}")
                
                if fallback_func:
                    return fallback_func(*args, **kwargs)
                return fallback_value
        return wrapper
    return decorator

if __name__ == "__main__":
    # Test
    @circuit_breaker("test_breaker", failure_threshold=2, recovery_timeout=2)
    def risky_call(should_fail=False):
        if should_fail:
            raise ValueError("Boom")
        return "Success"

    print("Call 1 (Success):", risky_call())
    try:
        print("Call 2 (Fail):", risky_call(True))
    except:
        print("Caught failure 1")
    try:
        print("Call 3 (Fail):", risky_call(True))
    except:
        print("Caught failure 2")
        
    try:
        print("Call 4 (Should be Open):", risky_call())
    except CircuitBreakerOpenException:
        print("Circuit is OPEN correctly")
        
    time.sleep(2.1)
    print("Call 5 (Recovery):", risky_call())
