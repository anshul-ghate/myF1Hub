"""
F1 PitWall AI - Custom Exception Hierarchy

This module defines a structured exception hierarchy for the entire application.
Using typed exceptions enables:
- Better error handling and recovery
- Structured logging with error categorization
- Graceful degradation based on error type
- Improved debugging and monitoring

Exception Hierarchy:
    F1BaseException
    ├── DataError
    │   ├── IngestionError
    │   ├── ValidationError
    │   └── FreshnessError
    ├── ModelError
    │   ├── TrainingError
    │   ├── PredictionError
    │   └── ModelNotFoundError
    ├── APIError
    │   ├── RateLimitError
    │   ├── ConnectionError
    │   └── AuthenticationError
    └── ConfigurationError
"""

from typing import Optional, Dict, Any
from datetime import datetime


class F1BaseException(Exception):
    """
    Base exception for all F1 PitWall AI errors.
    
    Attributes:
        message: Human-readable error description
        error_code: Unique error identifier for logging/monitoring
        details: Additional context about the error
        timestamp: When the error occurred
        recoverable: Whether the error can be automatically recovered from
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "F1_UNKNOWN",
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = False,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.utcnow()
        self.recoverable = recoverable
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "recoverable": self.recoverable
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.error_code}): {self.message}"


# ============== DATA ERRORS ==============

class DataError(F1BaseException):
    """Base class for all data-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code=kwargs.pop("error_code", "DATA_ERROR"), **kwargs)


class IngestionError(DataError):
    """Error during data ingestion from FastF1 or other sources."""
    
    def __init__(
        self,
        message: str,
        source: str = "unknown",
        year: Optional[int] = None,
        round_num: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "source": source,
            "year": year,
            "round": round_num
        })
        super().__init__(
            message,
            error_code="DATA_INGESTION_ERROR",
            details=details,
            recoverable=True,  # Usually can retry
            **kwargs
        )


class DataValidationError(DataError):
    """Error when data fails validation checks."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "field": field,
            "expected": str(expected),
            "actual": str(actual)
        })
        super().__init__(
            message,
            error_code="DATA_VALIDATION_ERROR",
            details=details,
            recoverable=False,
            **kwargs
        )


class DataFreshnessError(DataError):
    """Error when data is stale beyond acceptable threshold."""
    
    def __init__(
        self,
        message: str,
        data_age_hours: Optional[float] = None,
        threshold_hours: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "data_age_hours": data_age_hours,
            "threshold_hours": threshold_hours
        })
        super().__init__(
            message,
            error_code="DATA_FRESHNESS_ERROR",
            details=details,
            recoverable=True,  # Can trigger refresh
            **kwargs
        )


class DatabaseError(DataError):
    """Error during database operations."""
    
    def __init__(
        self,
        message: str,
        operation: str = "unknown",
        table: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "operation": operation,
            "table": table
        })
        super().__init__(
            message,
            error_code="DATABASE_ERROR",
            details=details,
            recoverable=True,
            **kwargs
        )


# ============== MODEL ERRORS ==============

class ModelError(F1BaseException):
    """Base class for all ML model-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code=kwargs.pop("error_code", "MODEL_ERROR"), **kwargs)


class ModelNotFoundError(ModelError):
    """Error when a required model artifact is not found."""
    
    def __init__(
        self,
        message: str,
        model_name: str = "unknown",
        model_path: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "model_name": model_name,
            "model_path": model_path
        })
        super().__init__(
            message,
            error_code="MODEL_NOT_FOUND",
            details=details,
            recoverable=True,  # Can trigger training
            **kwargs
        )


class TrainingError(ModelError):
    """Error during model training."""
    
    def __init__(
        self,
        message: str,
        model_name: str = "unknown",
        training_samples: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "model_name": model_name,
            "training_samples": training_samples
        })
        super().__init__(
            message,
            error_code="TRAINING_ERROR",
            details=details,
            recoverable=False,
            **kwargs
        )


class PredictionError(ModelError):
    """Error during model prediction."""
    
    def __init__(
        self,
        message: str,
        model_name: str = "unknown",
        race_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "model_name": model_name,
            "race_name": race_name
        })
        super().__init__(
            message,
            error_code="PREDICTION_ERROR",
            details=details,
            recoverable=True,  # May fallback to heuristic
            **kwargs
        )


class ModelDriftError(ModelError):
    """Error when model drift exceeds acceptable threshold."""
    
    def __init__(
        self,
        message: str,
        drift_score: Optional[float] = None,
        threshold: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "drift_score": drift_score,
            "threshold": threshold
        })
        super().__init__(
            message,
            error_code="MODEL_DRIFT_ERROR",
            details=details,
            recoverable=True,  # Trigger retraining
            **kwargs
        )


# ============== API ERRORS ==============

class APIError(F1BaseException):
    """Base class for all external API-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code=kwargs.pop("error_code", "API_ERROR"), **kwargs)


class RateLimitError(APIError):
    """Error when API rate limit is exceeded."""
    
    def __init__(
        self,
        message: str,
        api_name: str = "unknown",
        retry_after_seconds: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "api_name": api_name,
            "retry_after_seconds": retry_after_seconds
        })
        super().__init__(
            message,
            error_code="RATE_LIMIT_ERROR",
            details=details,
            recoverable=True,
            **kwargs
        )


class APIConnectionError(APIError):
    """Error when unable to connect to external API."""
    
    def __init__(
        self,
        message: str,
        api_name: str = "unknown",
        url: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "api_name": api_name,
            "url": url
        })
        super().__init__(
            message,
            error_code="API_CONNECTION_ERROR",
            details=details,
            recoverable=True,
            **kwargs
        )


class APIAuthenticationError(APIError):
    """Error when API authentication fails."""
    
    def __init__(
        self,
        message: str,
        api_name: str = "unknown",
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "api_name": api_name
        })
        super().__init__(
            message,
            error_code="API_AUTH_ERROR",
            details=details,
            recoverable=False,  # Requires config fix
            **kwargs
        )


# ============== CONFIGURATION ERRORS ==============

class ConfigurationError(F1BaseException):
    """Error related to application configuration."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "config_key": config_key
        })
        super().__init__(
            message,
            error_code="CONFIG_ERROR",
            details=details,
            recoverable=False,
            **kwargs
        )


# ============== HELPER FUNCTIONS ==============

def is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable."""
    if isinstance(error, F1BaseException):
        return error.recoverable
    
    # Check for common retryable errors
    error_msg = str(error).lower()
    retryable_patterns = [
        'connection', 'timeout', '10054', 'reset', 'closed',
        'network', 'eof', 'broken pipe', 'rate limit', '429', '503'
    ]
    return any(pattern in error_msg for pattern in retryable_patterns)


def get_retry_delay(error: Exception, attempt: int, base_delay: float = 1.0) -> float:
    """Calculate retry delay with exponential backoff and jitter."""
    import random
    
    if isinstance(error, RateLimitError) and error.details.get("retry_after_seconds"):
        return error.details["retry_after_seconds"]
    
    # Exponential backoff with jitter
    delay = base_delay * (2 ** attempt)
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter
