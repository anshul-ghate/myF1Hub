"""
Time Simulation Utility

Provides a way to simulate the application running at a specific past date/time.
This is useful for testing and debugging race weekend scenarios.

Usage:
1. Set environment variable F1_DEBUG_MODE=true
2. Set F1_SIMULATED_DATE=2024-12-06T14:00:00+00:00 (ISO format with timezone)
3. The app will behave as if it's that date/time

Example:
    # In PowerShell
    $env:F1_DEBUG_MODE = "true"
    $env:F1_SIMULATED_DATE = "2024-12-06T14:00:00+00:00"
    python -m streamlit run app/main.py
"""

import os
import datetime
import pytz
import streamlit as st
from typing import Optional


def is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return os.getenv('F1_DEBUG_MODE', '').lower() in ('true', '1', 'yes')


def get_simulated_date() -> Optional[datetime.datetime]:
    """Get the simulated date from environment variable."""
    simulated = os.getenv('F1_SIMULATED_DATE')
    if not simulated:
        return None
    
    try:
        # Parse ISO format datetime
        dt = datetime.datetime.fromisoformat(simulated.replace('Z', '+00:00'))
        
        # Ensure timezone aware
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        
        return dt
    except Exception as e:
        print(f"⚠️ Invalid F1_SIMULATED_DATE format: {e}")
        return None


def get_current_time() -> datetime.datetime:
    """
    Get current time, or simulated time if in debug mode.
    
    This function should be used throughout the app instead of datetime.now()
    to enable time travel testing.
    """
    if is_debug_mode():
        simulated = get_simulated_date()
        if simulated:
            return simulated
    
    return datetime.datetime.now(pytz.utc)


def get_current_year() -> int:
    """Get current year (or simulated year if in debug mode)."""
    return get_current_time().year




def get_race_weekend_status(race_date: datetime.datetime, 
                            session_5_date: Optional[datetime.datetime] = None) -> str:
    """
    Determine the status of a race weekend relative to current (or simulated) time.
    
    Returns one of:
    - 'upcoming': Race hasn't started yet
    - 'race_weekend': Currently in the race weekend (before race)
    - 'race_live': Race is currently happening
    - 'completed': Race has finished
    """
    now = get_current_time()
    
    # Ensure race_date is timezone-aware
    if race_date.tzinfo is None:
        race_date = pytz.utc.localize(race_date)
    
    # If session_5_date (race time) is provided, use it
    if session_5_date is not None:
        if session_5_date.tzinfo is None:
            session_5_date = pytz.utc.localize(session_5_date)
        
        # Race is "live" from Session5Date to Session5Date + 3 hours
        race_end_estimate = session_5_date + datetime.timedelta(hours=3)
        
        if now < session_5_date - datetime.timedelta(days=3):
            return 'upcoming'
        elif now < session_5_date:
            return 'race_weekend'
        elif now < race_end_estimate:
            return 'race_live'
        else:
            return 'completed'
    
    # Fallback: use race_date only
    race_day_end = race_date + datetime.timedelta(hours=18)  # Assume race ends by 6pm
    
    if now < race_date - datetime.timedelta(days=2):
        return 'upcoming'
    elif now < race_date:
        return 'race_weekend'
    elif now < race_day_end:
        return 'race_live'
    else:
        return 'completed'


# Test
if __name__ == "__main__":
    print(f"Debug mode: {is_debug_mode()}")
    print(f"Current time: {get_current_time()}")
    print(f"Current year: {get_current_year()}")
