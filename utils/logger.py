"""
Enhanced Logging Utility for F1 PitWall AI

Features:
- Structured logging with JSON format
- Correlation IDs for request tracing
- Context managers for operation tracking
- Integration with custom exceptions
- Multiple handlers (console, file, Supabase)
"""

import logging
import json
import uuid
import time
import functools
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager
import threading

# Thread-local storage for correlation ID
_context = threading.local()


def get_correlation_id() -> str:
    """Get current correlation ID or generate a new one."""
    if not hasattr(_context, 'correlation_id'):
        _context.correlation_id = str(uuid.uuid4())[:8]
    return _context.correlation_id


def set_correlation_id(correlation_id: str):
    """Set correlation ID for the current thread."""
    _context.correlation_id = correlation_id


def clear_correlation_id():
    """Clear correlation ID for the current thread."""
    if hasattr(_context, 'correlation_id'):
        delattr(_context, 'correlation_id')


class StructuredFormatter(logging.Formatter):
    """
    Formatter that outputs structured JSON logs.
    Includes correlation ID, timestamps, and structured metadata.
    """
    
    def __init__(self, include_json: bool = False):
        super().__init__()
        self.include_json = include_json
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        
        # Add location info
        log_data["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None
            }
        
        # Add custom fields from extra
        if hasattr(record, 'extra_data'):
            log_data["extra"] = record.extra_data
        
        if self.include_json:
            return json.dumps(log_data)
        else:
            # Human-readable format with correlation ID
            return (
                f"{log_data['timestamp']} | "
                f"{log_data['correlation_id']} | "
                f"{log_data['level']:8s} | "
                f"{log_data['logger']:20s} | "
                f"{log_data['message']}"
            )


class ContextLogger(logging.Logger):
    """
    Enhanced logger with context support and structured logging.
    """
    
    def __init__(self, name: str, level: int = logging.NOTSET):
        super().__init__(name, level)
        self._context: Dict[str, Any] = {}
    
    def with_context(self, **kwargs) -> 'ContextLogger':
        """Add context that will be included in all subsequent logs."""
        self._context.update(kwargs)
        return self
    
    def clear_context(self):
        """Clear all context."""
        self._context.clear()
    
    def _log_with_extra(self, level: int, msg: str, args, exc_info=None, extra=None, **kwargs):
        """Log with extra data merged."""
        extra = extra or {}
        extra['extra_data'] = {**self._context, **kwargs}
        super()._log(level, msg, args, exc_info=exc_info, extra=extra)
    
    def info(self, msg: str, *args, **kwargs):
        extra_data = kwargs.pop('extra', {})
        self._log_with_extra(logging.INFO, msg, args, **extra_data)
    
    def warning(self, msg: str, *args, **kwargs):
        extra_data = kwargs.pop('extra', {})
        self._log_with_extra(logging.WARNING, msg, args, **extra_data)
    
    def error(self, msg: str, *args, exc_info=False, **kwargs):
        extra_data = kwargs.pop('extra', {})
        self._log_with_extra(logging.ERROR, msg, args, exc_info=exc_info, **extra_data)
    
    def debug(self, msg: str, *args, **kwargs):
        extra_data = kwargs.pop('extra', {})
        self._log_with_extra(logging.DEBUG, msg, args, **extra_data)


class SupabaseHandler(logging.Handler):
    """
    Handler that sends logs to Supabase database.
    Batches logs and sends asynchronously to avoid blocking.
    """
    
    def __init__(self, component_name: str, min_level: int = logging.WARNING):
        super().__init__()
        self.component = component_name
        self.setLevel(min_level)  # Only log warnings and above to DB
        self._supabase = None
    
    @property
    def supabase(self):
        """Lazy load Supabase client."""
        if self._supabase is None:
            try:
                from utils.db import get_supabase_client
                self._supabase = get_supabase_client()
            except Exception:
                pass
        return self._supabase
    
    def emit(self, record: logging.LogRecord):
        if self.supabase is None:
            return
        
        try:
            log_entry = {
                "level": record.levelname,
                "component": self.component,
                "message": self.format(record),
                "correlation_id": get_correlation_id(),
                "metadata": {
                    "filename": record.filename,
                    "lineno": record.lineno,
                    "funcName": record.funcName
                }
            }
            
            # Add exception details if present
            if record.exc_info and record.exc_info[1]:
                exc = record.exc_info[1]
                log_entry["metadata"]["exception_type"] = type(exc).__name__
                
                # Check for our custom exceptions
                if hasattr(exc, 'to_dict'):
                    log_entry["metadata"]["exception_details"] = exc.to_dict()
            
            # Fire and forget
            self.supabase.table("app_logs").insert(log_entry).execute()
            
        except Exception as e:
            # Fallback to stderr to avoid infinite recursion
            import sys
            print(f"Failed to log to Supabase: {e}", file=sys.stderr)


def get_logger(name: str, level: int = logging.INFO, json_format: bool = False) -> ContextLogger:
    """
    Get or create an enhanced logger.
    
    Args:
        name: Logger name (usually module name)
        level: Logging level
        json_format: Whether to output JSON formatted logs
    
    Returns:
        ContextLogger instance with configured handlers
    """
    # Register our custom logger class
    logging.setLoggerClass(ContextLogger)
    
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Console Handler with structured format
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredFormatter(include_json=json_format))
    console_handler.setLevel(level)
    logger.addHandler(console_handler)
    
    # Supabase Handler (warnings and above only)
    try:
        supabase_handler = SupabaseHandler(name, min_level=logging.WARNING)
        supabase_handler.setFormatter(StructuredFormatter(include_json=False))
        logger.addHandler(supabase_handler)
    except Exception:
        pass  # Supabase not available, continue without it
    
    return logger


@contextmanager
def log_operation(logger: logging.Logger, operation: str, **context):
    """
    Context manager for logging operation start/end with timing.
    
    Usage:
        with log_operation(logger, "data_ingestion", race_id="123"):
            # do work
    """
    start_time = time.time()
    correlation_id = str(uuid.uuid4())[:8]
    set_correlation_id(correlation_id)
    
    logger.info(f"Starting: {operation}", extra=context)
    
    try:
        yield
        duration = time.time() - start_time
        logger.info(
            f"Completed: {operation}",
            extra={**context, "duration_seconds": round(duration, 3)}
        )
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Failed: {operation}",
            exc_info=True,
            extra={
                **context,
                "duration_seconds": round(duration, 3),
                "error": str(e)
            }
        )
        raise
    finally:
        clear_correlation_id()


def log_function_call(logger: logging.Logger = None):
    """
    Decorator to log function entry, exit, and timing.
    
    Usage:
        @log_function_call(logger)
        def my_function(arg1, arg2):
            pass
    """
    def decorator(func: Callable):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            
            # Don't log sensitive kwargs
            safe_kwargs = {k: v for k, v in kwargs.items() if 'key' not in k.lower() and 'password' not in k.lower()}
            
            logger.debug(f"Calling {func_name}", extra={"args_count": len(args), "kwargs": list(safe_kwargs.keys())})
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.debug(f"Completed {func_name}", extra={"duration_seconds": round(duration, 3)})
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Error in {func_name}: {e}", exc_info=True, extra={"duration_seconds": round(duration, 3)})
                raise
        
        return wrapper
    return decorator


# ============== Exception Integration ==============

def log_exception(logger: logging.Logger, exception: Exception, context: Dict[str, Any] = None):
    """
    Log an exception with full details.
    Works with both standard exceptions and F1BaseException.
    """
    context = context or {}
    
    # Check if it's our custom exception
    if hasattr(exception, 'to_dict'):
        exc_data = exception.to_dict()
        logger.error(
            f"[{exc_data['error_code']}] {exc_data['message']}",
            extra={**context, "exception": exc_data}
        )
    else:
        logger.error(
            f"[{type(exception).__name__}] {str(exception)}",
            exc_info=True,
            extra=context
        )


# ============== Convenience Loggers ==============

# Pre-configured loggers for common components
def get_data_logger() -> ContextLogger:
    """Logger for data ingestion and processing."""
    return get_logger("f1.data")

def get_model_logger() -> ContextLogger:
    """Logger for ML model operations."""
    return get_logger("f1.model")

def get_api_logger() -> ContextLogger:
    """Logger for external API interactions."""
    return get_logger("f1.api")

def get_app_logger() -> ContextLogger:
    """Logger for Streamlit application."""
    return get_logger("f1.app")
