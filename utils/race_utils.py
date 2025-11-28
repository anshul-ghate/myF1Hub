"""
Utility functions for race selection and upcoming race detection.
"""
import pandas as pd
from datetime import datetime, timezone
from utils.db import get_supabase_client

supabase = get_supabase_client()


def get_next_upcoming_race():
    """
    Get the next upcoming race based on current date.
    Returns race dict or None if no upcoming races found.
    """
    try:
        # Get current date in UTC
        now = datetime.now(timezone.utc)
        
        # Fetch races with date information, ordered by date
        result = supabase.table('races').select('*').order('date', desc=False).execute()
        
        if not result.data:
            return None
        
        # Find the first race whose date is in the future
        for race in result.data:
            if race.get('date'):
                # Parse race date
                race_date = pd.to_datetime(race['date'])
                
                # Make timezone-aware if needed
                if race_date.tzinfo is None:
                    race_date = race_date.tz_localize(timezone.utc)
                
                # Compare with current time
                if race_date > now:
                    return race
        
        return None
    except Exception as e:
        print(f"Error getting next race: {e}")
        return None


def get_seasons():
    """
    Get list of unique seasons (years) from races table.
    Returns list of years in descending order.
    """
    try:
        result = supabase.table('races').select('season_year').execute()
        if not result.data:
            return []
        
        seasons = sorted(list(set([r['season_year'] for r in result.data])), reverse=True)
        return seasons
    except Exception as e:
        print(f"Error getting seasons: {e}")
        return []


def get_rounds_for_season(year):
    """
    Get all rounds for a specific season.
    Returns DataFrame with race info, ordered by round (descending).
    """
    try:
        result = supabase.table('races').select('*').eq('season_year', year).order('round', desc=True).execute()
        return pd.DataFrame(result.data)
    except Exception as e:
        print(f"Error getting rounds for season {year}: {e}")
        return pd.DataFrame()


def get_race_lap_count(race_id):
    """
    Get total number of laps for a specific race.
    First checks if 'laps' column exists in races table.
    If not, counts from laps table.
    Returns integer lap count.
    """
    try:
        # Try to get from races table first
        race_result = supabase.table('races').select('*').eq('id', race_id).execute()
        
        if race_result.data:
            race = race_result.data[0]
            # Check if 'laps' or 'total_laps' column exists
            if 'laps' in race and race['laps']:
                return int(race['laps'])
            if 'total_laps' in race and race['total_laps']:
                return int(race['total_laps'])
        
        # Fallback: Count from laps table
        laps_result = supabase.table('laps').select('lap_number').eq('race_id', race_id).order('lap_number', desc=True).limit(1).execute()
        
        if laps_result.data:
            return int(laps_result.data[0]['lap_number'])
        
        # Default fallback
        return 57
    except Exception as e:
        print(f"Error getting lap count for race {race_id}: {e}")
        return 57  # Default F1 race distance


def get_race_by_id(race_id):
    """Get race details by ID."""
    try:
        result = supabase.table('races').select('*').eq('id', race_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting race {race_id}: {e}")
        return None
