import streamlit as st
import fastf1
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import os
import pytz
from app.components.sidebar import render_sidebar

# Page Config
st.set_page_config(
    page_title="F1 HUB | The Ultimate Fan Experience",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inject Custom CSS
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("app/assets/custom.css")

# Enable Cache
if not os.path.exists('f1_cache'):
    os.makedirs('f1_cache')

# Configure retries BEFORE enabling cache/making requests
from utils.api_config import configure_fastf1_retries
configure_fastf1_retries()

fastf1.Cache.enable_cache('f1_cache')

# Render Sidebar
render_sidebar()

# --- Logic for Next Race ---
@st.cache_data(ttl=300)  # Reduced TTL to 5 mins for quicker season transition detection
def get_schedule_with_fallback():
    """
    Get event schedule with fallback to next year if current season is over.
    Returns (schedule, is_next_year_schedule, season_status).
    
    season_status can be:
    - 'active': Normal season, races ongoing
    - 'final_race_live': The final race of the season is currently in progress
    - 'season_ended': The final race has completed, showing next season
    - 'preseason': Showing pre-season testing from next year
    """
    now = datetime.datetime.now(pytz.utc)
    current_year = now.year
    
    try:
        schedule = fastf1.get_event_schedule(current_year)
        
        # Ensure date columns are timezone-aware
        for col in ['EventDate', 'Session1Date', 'Session2Date', 'Session3Date', 'Session4Date', 'Session5Date']:
            if col in schedule.columns:
                schedule[col] = pd.to_datetime(schedule[col], utc=True)
        
        # Check if there are any upcoming events (with 3-day buffer)
        upcoming = schedule[schedule['EventDate'] + datetime.timedelta(days=3) > now]
        
        if not upcoming.empty:
            # Check if this is the FINAL race of the season
            current_event = upcoming.iloc[0]
            max_round = schedule['RoundNumber'].max()
            is_final_race = current_event['RoundNumber'] == max_round
            
            if is_final_race:
                # Check if the final race has COMPLETED
                # Race typically lasts ~2 hours, add 3 hours buffer after Session5Date
                race_end_time = current_event['Session5Date'] + datetime.timedelta(hours=3)
                
                if now > race_end_time:
                    # Final race is done! Try to transition to next season
                    print(f"Season {current_year} complete! Checking for {current_year + 1} schedule...")
                    try:
                        next_year_schedule = fastf1.get_event_schedule(current_year + 1)
                        if not next_year_schedule.empty:
                            for col in ['EventDate', 'Session1Date', 'Session2Date', 'Session3Date', 'Session4Date', 'Session5Date']:
                                if col in next_year_schedule.columns:
                                    next_year_schedule[col] = pd.to_datetime(next_year_schedule[col], utc=True)
                            return next_year_schedule, True, 'season_ended'
                        else:
                            # 2026 schedule not available yet - show season complete
                            print(f"No {current_year + 1} schedule available yet")
                            return schedule, False, 'season_complete'
                    except Exception:
                        # If next year schedule fails, show season complete
                        return schedule, False, 'season_complete'
                
                elif now > current_event['Session5Date']:
                    # Final race is currently in progress
                    return schedule, False, 'final_race_live'
            
            # Normal active season
            return schedule, False, 'active'
        
        # No upcoming events in current year - fallback to next year (pre-season testing)
        try:
            next_year_schedule = fastf1.get_event_schedule(current_year + 1)
            if not next_year_schedule.empty:
                for col in ['EventDate', 'Session1Date', 'Session2Date', 'Session3Date', 'Session4Date', 'Session5Date']:
                    if col in next_year_schedule.columns:
                        next_year_schedule[col] = pd.to_datetime(next_year_schedule[col], utc=True)
                return next_year_schedule, True, 'preseason'
            else:
                # No next year schedule - show season complete message
                return schedule, False, 'season_complete'
        except Exception:
            return schedule, False, 'season_complete'
        
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return pd.DataFrame(), False, 'error'

from utils.race_utils import get_track_map_image

# --- Auto-Update Check ---
@st.cache_resource(ttl=3600) # Check max once per hour per session
def run_auto_update():
    try:
        from scripts.auto_update import check_and_update
        import threading
        # Run in a separate thread to not block UI load significantly
        # although for first run it might be better to block briefly or show a spinner?
        # Let's block briefly as it's critical data, but rely on the script's internal checks which are fast if no update needed.
        
        # We can also put it in a spinner
        check_and_update()
        return datetime.datetime.now()
    except Exception as e:
        print(f"Auto-update failed: {e}")
        return None

# --- Main Execution ---
if __name__ == "__main__":
    # Trigger Auto Update Check (Background-ish)
    run_auto_update()

    try:
        schedule, is_next_year, season_status = get_schedule_with_fallback()
        now_utc = datetime.datetime.now(pytz.utc)
        
        # Filter for upcoming events (with 3-day buffer)
        if not schedule.empty:
            future_races = schedule[schedule['EventDate'] + datetime.timedelta(days=3) > now_utc]
        else:
            future_races = pd.DataFrame()
        
        if not future_races.empty:
            next_race = future_races.iloc[0]
            
            # Countdown Logic - use Session5Date (race start) like Season Central
            # Fall back to EventDate if Session5Date is not available
            race_start = next_race.get('Session5Date')
            if pd.isna(race_start) or race_start is None:
                race_start = next_race['EventDate']
            
            time_left = race_start - now_utc
            event_name = next_race['EventName']
            round_num = next_race['RoundNumber']
            date_str = next_race['EventDate'].strftime('%d %b %Y')
            
            # Check if event is within 1 week (7 days)
            one_week = datetime.timedelta(days=7)
            is_within_week = time_left <= one_week
            
            # Always generate track map regardless of time distance
            track_map_img = get_track_map_image(next_race)
            
            if time_left.total_seconds() <= 0:
                # Race has started or finished
                countdown_str = "🏁 IN PROGRESS"
                location = f"{next_race['Location']}, {next_race['Country']}"
            elif is_within_week:
                # Event is within 1 week - show full countdown and location
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                countdown_str = f"{days}d {hours:02d}h {minutes:02d}m"
                location = f"{next_race['Location']}, {next_race['Country']}"
            else:
                # Event is more than 1 week away - show "Coming Soon" style
                countdown_str = "🗓️ Coming Soon"
                location = f"{date_str}"  # Show date instead of location
            
            # Context-aware status notes
            status_note = ""
            if season_status == 'final_race_live':
                status_note = "<div style='color: #FF1801; font-size: 0.85rem; margin-top: 8px; font-weight: 600;'>🏁 SEASON FINALE IN PROGRESS</div>"
            elif season_status == 'season_ended':
                status_note = "<div style='color: #00D4AA; font-size: 0.85rem; margin-top: 8px;'>✨ 2025 Season Complete • Gearing up for 2026!</div>"
            elif season_status == 'season_complete':
                status_note = "<div style='color: #00D4AA; font-size: 0.85rem; margin-top: 8px;'>🏆 2025 Season Complete • See you in 2026!</div>"
            elif season_status == 'preseason':
                status_note = "<div style='color: #888; font-size: 0.8rem; margin-top: 10px;'>📆 Pre-Season Testing</div>"
            
        else:
            event_name = "Season Ended"
            location = "See you next year!"
            round_num = "-"
            date_str = "-"
            countdown_str = "00d 00h 00m"
            track_map_img = None
            status_note = ""
    
    except Exception as e:
        st.error(f"Could not load schedule: {e}")
        event_name = "Data Error"
        location = "Check connection"
        round_num = "-"
        date_str = "-"
        countdown_str = "--"
        track_map_img = None
        status_note = ""
    
    # --- Main Content with Custom HTML ---
    
    # Hero Section
    st.markdown(f"""
    <div class="hero-container" style="display: flex; gap: 3rem; align-items: center; justify-content: center;">
    <div class="hero-content">
    <h1 class="hero-title">IGNITE YOUR <span class="text-gradient">PASSION</span></h1>
    <p class="hero-subtitle">Next Event: {event_name}{status_note}</p>
    <div style="display: flex; gap: 3rem; align-items: center; justify-content: center;">
    <div style="text-align: left;">
    <div class="hero-stat-label">Countdown</div>
    <div class="hero-stat">{countdown_str}</div>
    </div>
    <div style="text-align: left;">
    <div class="hero-stat-label">Location</div>
    <div style="font-size: 1.5rem; font-weight: 600;">{location}</div>
    </div>
    <div style="margin-left: 2rem;">
    {f'<img src="{track_map_img}" style="max-height: 160px; filter: drop-shadow(0 0 15px rgba(0, 243, 255, 0.3)); animation: fadeIn 2s ease-out;" />' if track_map_img else ''}
    </div>
    </div>
    </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Features Grid (Navigation)
    st.markdown("""
    <div class="features-grid">
    <a href="/analytics" class="feature-card" target="_self">
    <div class="card-icon">📊</div>
    <div class="card-title">Deep Dive Analytics</div>
    <div class="card-desc">Comprehensive telemetry and race data analysis.</div>
    </a>
    <a href="/predictions" class="feature-card" target="_self">
    <div class="card-icon">🔮</div>
    <div class="card-title">Race Predictions</div>
    <div class="card-desc">AI-powered insights for pole, podiums, and strategy.</div>
    </a>
    <a href="/live_monitor" class="feature-card" target="_self">
    <div class="card-icon">📡</div>
    <div class="card-title">Live Monitor</div>
    <div class="card-desc">Real-time race tracking and strategy monitoring.</div>
    </a>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.caption("© 2025 F1 HUB. Not affiliated with Formula 1.")
