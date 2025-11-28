import streamlit as st
import fastf1
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import os
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
fastf1.Cache.enable_cache('f1_cache')

# Render Sidebar
render_sidebar()

# --- Logic for Next Race ---
@st.cache_data(ttl=3600)
def get_schedule():
    now = datetime.datetime.now()
    schedule = fastf1.get_event_schedule(now.year)
    if schedule['EventDate'].max() < now:
        schedule = fastf1.get_event_schedule(now.year + 1)
    return schedule

@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_track_map_image(_event):
    """
    Generate a track map image for the given event.
    Implements multi-year fallback logic to handle newly added tracks.
    Note: _event uses underscore prefix to prevent Streamlit from hashing it for caching.
    """
    try:
        event_location = _event['Location']
        event_country = _event['Country']
        event_name = _event['EventName']
        current_year = _event['EventDate'].year
        
        # Try multiple years backward
        for year_offset in range(1, 4):  # Try 3 previous years
            try:
                year = current_year - year_offset
                print(f"Attempting to load track map for {event_name} from {year}...")
                
                # Get schedule for this year
                schedule_year = fastf1.get_event_schedule(year)
                
                # Try matching by Location first (most reliable)
                matching_event = schedule_year[schedule_year['Location'] == event_location]
                
                # Fallback to Country match
                if matching_event.empty:
                    matching_event = schedule_year[schedule_year['Country'] == event_country]
                
                # Fallback to EventName partial match
                if matching_event.empty:
                    # Try to find similar event names (e.g., "Monaco Grand Prix" matches "Monaco")
                    matching_event = schedule_year[
                        schedule_year['EventName'].str.contains(event_location, case=False, na=False)
                    ]
                
                if not matching_event.empty:
                    round_num = matching_event.iloc[0]['RoundNumber']
                    
                    # Try Qualifying session first
                    for session_type in ['Q', 'R']:  # Qualifying, then Race
                        try:
                            session = fastf1.get_session(year, round_num, session_type)
                            session.load(laps=True, telemetry=True, weather=False, messages=False)
                            
                            # Get fastest lap telemetry
                            lap = session.laps.pick_fastest()
                            if lap is None or lap.empty:
                                continue
                                
                            pos = lap.get_telemetry().add_distance().add_relative_distance()
                            
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
                            
                            print(f"✓ Successfully loaded track map from {year} {session_type} session")
                            return f"data:image/svg+xml;base64,{img_str}"
                            
                        except Exception as session_error:
                            print(f"  Session {session_type} failed: {session_error}")
                            continue
                            
            except Exception as year_error:
                print(f"  Year {year} failed: {year_error}")
                continue
        
        # If all attempts failed
        print(f"⚠ Could not generate track map for {event_name} after trying 3 years")
        return None
        
    except Exception as e:
        print(f"❌ Error generating track map: {e}")
        return None

try:
    schedule = get_schedule()
    now = datetime.datetime.now()
    future_races = schedule[schedule['EventDate'] > now]
    
    if not future_races.empty:
        next_race = future_races.iloc[0]
        
        # Countdown Logic
        time_left = next_race['EventDate'] - now
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        countdown_str = f"{days}d {hours}h {minutes}m"
        
        event_name = next_race['EventName']
        location = f"{next_race['Location']}, {next_race['Country']}"
        round_num = next_race['RoundNumber']
        date_str = next_race['EventDate'].strftime('%d %b %Y')
        
        # Generate Track Map
        track_map_img = get_track_map_image(next_race)
        
    else:
        event_name = "Season Ended"
        location = "See you next year!"
        round_num = "-"
        date_str = "-"
        countdown_str = "00d 00h 00m"
        track_map_img = None

except Exception as e:
    st.error(f"Could not load schedule: {e}")
    event_name = "Data Error"
    location = "Check connection"
    round_num = "-"
    date_str = "-"
    countdown_str = "--"
    track_map_img = None

# --- Main Content with Custom HTML ---

# Hero Section
st.markdown(f"""
<div class="hero-container" style="display: flex; gap: 3rem; align-items: center; justify-content: center;">
<div class="hero-content">
<h1 class="hero-title">IGNITE YOUR <span class="text-gradient">PASSION</span></h1>
<p class="hero-subtitle">Next Event: {event_name}</p>
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
