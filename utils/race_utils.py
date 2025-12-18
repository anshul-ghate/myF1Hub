import fastf1
import pandas as pd
from datetime import datetime, timezone
import streamlit as st
from utils.db import get_supabase_client
import matplotlib.pyplot as plt
import io
import base64

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Initialize Supabase
supabase = get_supabase_client()

# Configure FastF1 Retries
from utils.api_config import configure_fastf1_retries
configure_fastf1_retries()

@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_track_map_image(_event):
    """
    Generate a track map image for the given event.
    Tries multiple years to find telemetry data.
    Note: _event uses underscore prefix to prevent Streamlit from hashing it for caching.
    """
    try:
        event_location = _event['Location']
        event_country = _event['Country']
        event_name = _event['EventName']
        
        # Pre-season testing circuit mapping (year -> (location, country))
        TESTING_CIRCUITS = {
            2025: ('Sakhir', 'Bahrain'),  # Bahrain International Circuit
            2024: ('Sakhir', 'Bahrain'),
            2023: ('Sakhir', 'Bahrain'),
            2022: ('Barcelona', 'Spain'),  # Circuit de Barcelona-Catalunya
            2021: ('Sakhir', 'Bahrain'),
        }
        
        # Handle testing events - use mapped circuit instead of skipping
        is_testing = 'Testing' in str(event_name) or 'Test' in str(event_name) or _event.get('RoundNumber', 1) == 0
        
        if is_testing:
            event_year = _event['EventDate'].year
            if event_year in TESTING_CIRCUITS:
                event_location, event_country = TESTING_CIRCUITS[event_year]
                print(f"🧪 Pre-season testing: Using {event_location}, {event_country} for track map")
            else:
                print(f"⚠ Skipping track map for testing event: {event_name} (no circuit mapping)")
                return None
        
        event_year = _event['EventDate'].year
        
        # Try multiple years: current year first, then previous years
        years_to_try = [event_year, event_year - 1, event_year - 2, 2024, 2023]
        # Remove duplicates while preserving order
        years_to_try = list(dict.fromkeys(years_to_try))
        
        for year in years_to_try:
            try:
                print(f"🔍 Attempting to load track map for {event_location} from {year}...")
                
                # Get schedule for this year
                schedule_year = fastf1.get_event_schedule(year)
                
                # Filter out testing events (round 0)
                schedule_year = schedule_year[schedule_year['RoundNumber'] > 0]
                
                # Try matching by Location first (most reliable)
                matching_event = schedule_year[schedule_year['Location'] == event_location]
                
                # Fallback to Country match
                if matching_event.empty:
                    matching_event = schedule_year[schedule_year['Country'] == event_country]
                
                # Fallback to partial name match
                if matching_event.empty:
                    matching_event = schedule_year[schedule_year['EventName'].str.contains(event_location, case=False, na=False)]
                
                if matching_event.empty:
                    print(f"  ⚠ No matching event found in {year}")
                    continue
                
                round_num = int(matching_event.iloc[0]['RoundNumber'])
                
                # Try Qualifying session first (faster), fallback to Race
                for session_type in ['Q', 'R']:
                    try:
                        session = fastf1.get_session(year, round_num, session_type)
                        session.load(laps=True, telemetry=True, weather=False, messages=False)
                        
                        # Get fastest lap telemetry
                        lap = session.laps.pick_fastest()
                        if lap is not None and not getattr(lap, 'empty', True):
                            pos = lap.get_telemetry()
                            if pos is not None and not pos.empty and 'X' in pos.columns and 'Y' in pos.columns:
                                pos = pos.add_distance().add_relative_distance()
                                
                                # Create the plot
                                fig, ax = plt.subplots(figsize=(5, 3), facecolor='none')
                                ax.plot(pos['X'], pos['Y'], color='#FF1801', linewidth=2.5)
                                ax.axis('off')
                                ax.set_aspect('equal')
                                
                                # Save to buffer
                                buf = io.BytesIO()
                                fig.savefig(buf, format='svg', bbox_inches='tight', transparent=True)
                                buf.seek(0)
                                img_str = base64.b64encode(buf.getvalue()).decode('utf-8')
                                plt.close(fig)
                                
                                print(f"✓ Successfully loaded track map from {year} {session_type}")
                                return f"data:image/svg+xml;base64,{img_str}"
                    except Exception as sess_err:
                        print(f"  ⚠ {session_type} session failed: {sess_err}")
                        continue
                        
            except Exception as year_err:
                print(f"  ⚠ Year {year} failed: {year_err}")
                continue
        
        print(f"⚠ Could not generate track map for {event_name} after trying multiple years")
        return None
        
    except Exception as e:
        print(f"❌ Error generating track map: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_next_upcoming_race():
    """
    Get the next upcoming race based on current date.
    Returns race dict or None if no upcoming races found.
    """
    try:
        # Get current date in UTC
        now = datetime.now(timezone.utc)
        
        # Fetch races with date information, ordered by date
        # Note: schema_v3 uses 'race_date' column, not 'date'
        result = supabase.table('races').select('*').order('race_date', desc=False).execute()
        
        if not result.data:
            return None
        
        # Find the first race whose date is in the future
        for race in result.data:
            if race.get('race_date'):
                # Parse race date
                race_date = pd.to_datetime(race['race_date'])
                
                # Make timezone-aware if needed
                if race_date.tzinfo is None:
                    race_date = race_date.tz_localize(timezone.utc)
                
                # Compare with current time + buffer for race day
                # Allow race to show as "upcoming" for 24 hours after the midnight timestamp
                if (race_date + pd.Timedelta(hours=24)) > now:
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

def get_current_standings(year=None):
    """
    Fetch current driver and constructor standings by aggregating results from all completed races.
    """
    if year is None:
        year = datetime.now().year
        
    try:
        # Get schedule
        schedule = fastf1.get_event_schedule(year)
        completed = schedule[schedule['EventDate'] < datetime.now()]
        
        driver_points = {}
        driver_teams = {}
        constructor_points = {}
        
        # Iterate through all completed rounds to sum points
        for _, race in completed.iterrows():
            try:
                # Skip testing rounds (round 0 doesn't have sprint or race sessions)
                if race['RoundNumber'] == 0:
                    continue
                    
                # Check for Sprint
                if 'Sprint' in race['Session3']: # Heuristic for Sprint weekend
                     session = fastf1.get_session(year, race['RoundNumber'], 'Sprint')
                     session.load(laps=False, telemetry=False, weather=False, messages=False)
                     if not session.results.empty:
                         for _, row in session.results.iterrows():
                             driver = row['Abbreviation']
                             team = row['TeamName']
                             points = row['Points']
                             
                             driver_points[driver] = driver_points.get(driver, 0) + points
                             constructor_points[team] = constructor_points.get(team, 0) + points

                # Main Race
                session = fastf1.get_session(year, race['RoundNumber'], 'R')
                session.load(laps=False, telemetry=False, weather=False, messages=False)
                
                if not session.results.empty:
                    for _, row in session.results.iterrows():
                        driver = row['Abbreviation']
                        team = row['TeamName']
                        points = row['Points']
                        
                        driver_points[driver] = driver_points.get(driver, 0) + points
                        constructor_points[team] = constructor_points.get(team, 0) + points
                        
                        # Store driver-team mapping (most recent team)
                        if driver not in driver_teams or points > 0: # Update mapping preferrably when scoring or just last race
                           driver_teams[driver] = team
                        
            except Exception as e:
                print(f"Error processing round {race['RoundNumber']}: {e}")
                continue
                
        # Convert to DataFrame
        # Drivers
        d_data = []
        for dr, pts in driver_points.items():
            d_data.append({
                'Driver': dr,
                'Points': pts,
                'Team': driver_teams.get(dr, 'Unknown')
            })
            
        d_df = pd.DataFrame(d_data)
        if not d_df.empty:
            d_df = d_df.sort_values('Points', ascending=False).reset_index(drop=True)
            d_df.index += 1
        
        # Constructors
        c_df = pd.DataFrame(list(constructor_points.items()), columns=['Team', 'Points'])
        if not c_df.empty:
            c_df = c_df.sort_values('Points', ascending=False).reset_index(drop=True)
            c_df.index += 1
        
        return d_df, c_df
                
    except Exception as e:
        print(f"Error getting standings: {e}")
        
    return pd.DataFrame(), pd.DataFrame()

def get_latest_completed_session():
    """
    Find the absolute latest completed session (FP1, FP2, FP3, Q, Sprint, Race).
    Returns dict with session details.
    """
    try:
        now = datetime.now(timezone.utc)
        year = now.year
        
        # Get schedule for current year
        try:
            schedule = fastf1.get_event_schedule(year)
        except Exception:
            # Fallback for year boundary issues
            schedule = fastf1.get_event_schedule(year - 1)
            year = year - 1
        
        latest_session = None
        latest_time = None
        
        for _, event in schedule.iterrows():
            # Check all 5 possible sessions
            for i in range(1, 6):
                s_date_col = f'Session{i}Date'
                s_name_col = f'Session{i}'
                
                if s_date_col in event and pd.notna(event[s_date_col]):
                    # Get session time
                    s_time = event[s_date_col]
                    
                    # Ensure timezone awareness (FastF1 usually returns naive / local)
                    # We assume FastF1 returns local time but often it's UTC-ish or mixed.
                    # Best practice: Assign UTC if naive, then compare.
                    if s_time.tzinfo is None:
                        s_time = s_time.replace(tzinfo=timezone.utc)
                    
                    # Buffer: Allow 2 hours after session start for "completion"
                    # Session is "completed" roughly 2 hours after start (safe bet)
                    completion_time = s_time + pd.Timedelta(hours=2.5)
                        
                    if completion_time < now:
                        # It's a completed session
                        if latest_time is None or s_time > latest_time:
                            latest_time = s_time
                            
                            # Determine Session Type Code for FastF1
                            # R=Race, Q=Quali, S=Sprint, FP1/2/3
                            s_name = event[s_name_col]
                            s_type = 'R'
                            if 'Qualifying' in s_name: s_type = 'Q'
                            elif 'Sprint' in s_name: s_type = 'S'
                            elif 'Practice' in s_name: s_type = 'FP' + s_name[-1]
                            
                            latest_session = {
                                'Year': year,
                                'Round': int(event['RoundNumber']),
                                'EventName': event['EventName'],
                                'Session': s_name,
                                'SessionType': s_type,
                                'Date': s_time
                            }
                            
        return latest_session
        
    except Exception as e:
        print(f"Error finding latest session: {e}")
        return None

def get_session_status(year, round_num):
    """
    Get the status of all sessions for a specific round.
    Returns a dict mapping session type to boolean (completed or not).
    """
    try:
        schedule = fastf1.get_event_schedule(year)
        event = schedule[schedule['RoundNumber'] == round_num]
        
        if event.empty:
            return {}
            
        event = event.iloc[0]
        now = datetime.now(timezone.utc)
        status = {}
        
        for i in range(1, 6):
            s_name = event[f'Session{i}']
            s_date = event[f'Session{i}Date']
            
            if pd.isna(s_date): continue
            
            if s_date.tzinfo is None:
                s_date = s_date.replace(tzinfo=timezone.utc)
                
            # Completed if now > start + 2 hours
            is_complete = now > (s_date + pd.Timedelta(hours=2))
            
            # Map simplified names
            key = 'Race'
            if 'Qualifying' in s_name: key = 'Qualifying'
            elif 'Sprint' in s_name: key = 'Sprint'
            elif 'Practice' in s_name: key = 'Practice'
            
            # Store specific if needed, but mainly we care about Q and R
            if key not in status or is_complete: # Upgrade to True if multiple (e.g. Q1/Q2/Q3 logic complex, simplified here)
                status[s_name] = is_complete
                
        return status
    except Exception as e:
        print(f"Error getting session status: {e}")
        return {}

def get_session_results(year, round_num, session_type):
    """
    Fetch results for a specific session using FastF1.
    """
    try:
        session = fastf1.get_session(year, round_num, session_type)
        session.load(laps=False, telemetry=False, weather=False, messages=False)
        
        if not session.results.empty:
            df = session.results[['Position', 'Abbreviation', 'TeamName', 'Time']].head(20)
            # Format Time as string clean for display
            df['Time'] = df['Time'].astype(str).str.replace('0 days ', '')
            return df
            
    except Exception as e:
        print(f"Error fetching session results: {e}")
        
    return pd.DataFrame()
