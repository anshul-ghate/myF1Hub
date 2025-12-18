"""
Pydantic Schemas for Data Validation

This module defines validation schemas for all data flowing through the system.
Using Pydantic ensures:
- Type safety at runtime
- Clear error messages for invalid data
- Automatic serialization/deserialization
- Schema documentation
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum


# ============== ENUMS ==============

class TyreCompound(str, Enum):
    """Valid tyre compounds."""
    SOFT = "SOFT"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    INTERMEDIATE = "INTERMEDIATE"
    WET = "WET"


class TrackStatus(str, Enum):
    """Track status codes from FastF1."""
    GREEN = "1"
    YELLOW = "2"
    SC = "4"
    RED = "5"
    VSC = "6"
    SC_ENDING = "7"


class SessionType(str, Enum):
    """F1 session types."""
    FP1 = "FP1"
    FP2 = "FP2"
    FP3 = "FP3"
    QUALIFYING = "Q"
    SPRINT = "S"
    RACE = "R"


class IngestionStatus(str, Enum):
    """Race data ingestion status."""
    PENDING = "PENDING"
    QUALI = "QUALI"
    COMPLETE = "COMPLETE"


# ============== DRIVER SCHEMAS ==============

class DriverBase(BaseModel):
    """Base driver information."""
    code: str = Field(..., min_length=2, max_length=3, description="Driver abbreviation (e.g., VER)")
    given_name: str = Field(..., min_length=1, description="Driver first name")
    family_name: str = Field(..., min_length=1, description="Driver last name")
    nationality: Optional[str] = Field(None, max_length=3, description="Country code")
    
    @field_validator('code')
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        return v.upper()


class DriverCreate(DriverBase):
    """Schema for creating a new driver."""
    ergast_driver_id: str = Field(..., description="Unique driver ID from Ergast")


class Driver(DriverBase):
    """Full driver model with database ID."""
    id: str = Field(..., description="Database UUID")
    
    class Config:
        from_attributes = True


# ============== RACE SCHEMAS ==============

class RaceBase(BaseModel):
    """Base race information."""
    season_year: int = Field(..., ge=1950, le=2100, description="Season year")
    round: int = Field(..., ge=1, le=30, description="Round number")
    name: str = Field(..., min_length=1, description="Race name")
    race_date: datetime = Field(..., description="Race date")
    race_time: Optional[str] = Field(None, description="Race time")
    
    @field_validator('name')
    @classmethod
    def clean_name(cls, v: str) -> str:
        return v.strip()


class RaceCreate(RaceBase):
    """Schema for creating a new race."""
    circuit_id: Optional[str] = Field(None, description="Circuit UUID")
    ergast_race_id: Optional[str] = None


class Race(RaceBase):
    """Full race model with database ID."""
    id: str
    circuit_id: Optional[str] = None
    ingestion_status: IngestionStatus = IngestionStatus.PENDING
    
    class Config:
        from_attributes = True


# ============== LAP SCHEMAS ==============

class LapBase(BaseModel):
    """Base lap information."""
    lap_number: int = Field(..., ge=1, le=100, description="Lap number")
    compound: Optional[str] = Field(None, description="Tyre compound")
    tyre_life: Optional[int] = Field(None, ge=0, le=60, description="Laps on current tyres")
    position: Optional[int] = Field(None, ge=1, le=25, description="Race position")
    is_accurate: bool = Field(True, description="FastF1 accuracy flag")
    track_status: Optional[str] = Field(None, description="Track status code")


class LapCreate(LapBase):
    """Schema for creating a lap record. Uses milliseconds for times."""
    race_id: str
    driver_id: str
    lap_time_ms: Optional[int] = Field(None, description="Lap time in milliseconds")
    sector_1_ms: Optional[int] = Field(None, description="Sector 1 time in ms")
    sector_2_ms: Optional[int] = Field(None, description="Sector 2 time in ms")
    sector_3_ms: Optional[int] = Field(None, description="Sector 3 time in ms")
    fuel_load: Optional[float] = Field(None, ge=0, le=115, description="Fuel load in kg")
    gap_to_leader_ms: Optional[int] = Field(None, description="Gap to leader in ms")
    fresh_tyre: Optional[bool] = None


class LapData(LapBase):
    """Full lap model with computed fields."""
    race_id: str
    driver_id: str
    lap_time_ms: Optional[int] = None
    
    @property
    def lap_time_seconds(self) -> Optional[float]:
        """Convert milliseconds to seconds."""
        return self.lap_time_ms / 1000.0 if self.lap_time_ms else None
    
    class Config:
        from_attributes = True


# ============== RACE RESULT SCHEMAS ==============

class RaceResultBase(BaseModel):
    """Base race result information."""
    position: Optional[int] = Field(None, ge=1, le=25, description="Finishing position")
    grid: Optional[int] = Field(None, ge=1, le=25, description="Grid position")
    points: float = Field(0.0, ge=0, le=30, description="Points scored")
    status: str = Field("Finished", description="Finishing status")


class RaceResultCreate(RaceResultBase):
    """Schema for creating a race result."""
    race_id: str
    driver_id: str
    laps_completed: Optional[int] = Field(None, ge=0, description="Laps completed")


class RaceResult(RaceResultBase):
    """Full race result model."""
    race_id: str
    driver_id: str
    driver_code: Optional[str] = None
    team: Optional[str] = None
    
    class Config:
        from_attributes = True


# ============== PREDICTION SCHEMAS ==============

class PredictionInput(BaseModel):
    """Input for race prediction."""
    year: int = Field(..., ge=2020, le=2100)
    race_name: str = Field(..., min_length=1)
    weather_forecast: str = Field("Dry", pattern="^(Dry|Wet)$")
    n_simulations: int = Field(5000, ge=100, le=50000)
    
    @field_validator('race_name')
    @classmethod
    def clean_race_name(cls, v: str) -> str:
        return v.strip()


class DriverPrediction(BaseModel):
    """Single driver prediction result."""
    driver: str
    team: str
    grid: int
    win_probability: float = Field(..., ge=0, le=100)
    podium_probability: float = Field(..., ge=0, le=100)
    points_probability: float = Field(..., ge=0, le=100)
    avg_position: float = Field(..., ge=1, le=25)
    dnf_probability: float = Field(..., ge=0, le=100)
    explanation: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_probabilities(self):
        if self.win_probability > self.podium_probability:
            raise ValueError("Win probability cannot exceed podium probability")
        return self


class RacePrediction(BaseModel):
    """Complete race prediction output."""
    race_name: str
    year: int
    weather: str
    simulations: int
    predictions: List[DriverPrediction]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = "hybrid_v8"


# ============== ELO SCHEMAS ==============

class EloRating(BaseModel):
    """Elo rating for a driver or team."""
    entity: str
    rating: float = Field(1500, ge=1000, le=2500)
    is_team: bool = False
    last_updated: Optional[datetime] = None


class EloSnapshot(BaseModel):
    """Snapshot of all Elo ratings."""
    drivers: Dict[str, float]
    teams: Dict[str, float]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============== WEATHER SCHEMAS ==============

class WeatherData(BaseModel):
    """Weather conditions."""
    air_temp: float = Field(..., ge=-20, le=60, description="Air temperature in Celsius")
    track_temp: float = Field(..., ge=-10, le=80, description="Track temperature in Celsius")
    humidity: float = Field(..., ge=0, le=100, description="Humidity percentage")
    rainfall: bool = Field(False, description="Whether it's raining")
    wind_speed: float = Field(0, ge=0, le=100, description="Wind speed in km/h")
    wind_direction: Optional[int] = Field(None, ge=0, le=360, description="Wind direction in degrees")
    
    @property
    def is_wet(self) -> bool:
        return self.rainfall


# ============== TELEMETRY SCHEMAS ==============

class TelemetryStats(BaseModel):
    """Aggregated telemetry statistics for a lap."""
    race_id: str
    driver_id: str
    lap_number: int = Field(..., ge=1)
    speed_max: float = Field(..., ge=0, le=400, description="Max speed in km/h")
    speed_avg: float = Field(..., ge=0, le=350, description="Average speed in km/h")
    throttle_avg: float = Field(..., ge=0, le=100, description="Average throttle %")
    brake_avg: float = Field(..., ge=0, le=100, description="Average brake %")
    gear_shifts: int = Field(..., ge=0, description="Number of gear shifts")


# ============== VALIDATION HELPERS ==============

def validate_lap_time_string(lap_time: str) -> float:
    """
    Convert lap time string to seconds.
    Formats: "1:32.456" or "0:01:32.456"
    """
    try:
        parts = lap_time.split(':')
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        elif len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        else:
            raise ValueError(f"Invalid lap time format: {lap_time}")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Could not parse lap time '{lap_time}': {e}")


def validate_race_results(results: List[Dict[str, Any]]) -> List[RaceResultCreate]:
    """Validate a list of race results."""
    validated = []
    for i, result in enumerate(results):
        try:
            validated.append(RaceResultCreate(**result))
        except Exception as e:
            raise ValueError(f"Invalid result at index {i}: {e}")
    return validated


def validate_driver_grid(drivers: List[Dict[str, Any]], expected_count: int = 20) -> bool:
    """Validate that grid data is complete."""
    if len(drivers) < expected_count:
        return False
    
    positions = [d.get('grid') or d.get('position') for d in drivers]
    positions = [p for p in positions if p is not None]
    
    # Check for duplicates
    if len(positions) != len(set(positions)):
        return False
    
    return True
