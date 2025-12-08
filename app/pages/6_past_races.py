"""
Past Races Page

Historical race replay visualization with full telemetry, playback controls,
and interactive track map. Inspired by f1-race-replay but optimized for web.
"""

import streamlit as st
import time
import fastf1
import pandas as pd
from datetime import datetime
import os

# Page Config - must be first
st.set_page_config(
    page_title="Past Races | F1 HUB",
    page_icon="🏁",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inject Custom CSS
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except:
        pass

local_css("app/assets/custom.css")

# Render Sidebar
from app.components.sidebar import render_sidebar
render_sidebar()

# Import visualization utilities
from utils.race_visualization import (
    get_race_telemetry_frames,
    get_frame_at_time,
    FPS
)
from utils.track_renderer import (
    render_track_map,
    create_position_chart,
    create_speed_trace
)
from app.components.race_replay import (
    render_leaderboard,
    render_playback_controls,
    render_driver_telemetry,
    render_weather_widget,
    render_track_status_banner,
    format_time
)

# Enable FastF1 cache
from utils.api_config import configure_fastf1_retries
configure_fastf1_retries()

if not os.path.exists('f1_cache'):
    os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')


# ---------- SESSION STATE INITIALIZATION ----------
if 'past_race_time' not in st.session_state:
    st.session_state.past_race_time = 0.0
if 'past_race_playing' not in st.session_state:
    st.session_state.past_race_playing = False
if 'past_race_speed' not in st.session_state:
    st.session_state.past_race_speed = 1.0
if 'past_race_selected_driver' not in st.session_state:
    st.session_state.past_race_selected_driver = None
if 'past_race_data' not in st.session_state:
    st.session_state.past_race_data = None
if 'past_race_key' not in st.session_state:
    st.session_state.past_race_key = None


# ---------- HELPER FUNCTIONS ----------
@st.cache_data(ttl=3600)
def get_event_schedule(year: int, _cache_date: str = None):
    """Get event schedule for a given year, filtered to completed events only."""
    try:
        from datetime import datetime
        import pytz
        
        schedule = fastf1.get_event_schedule(year)
        # Filter only actual races (exclude testing)
        schedule = schedule[schedule['RoundNumber'] > 0].copy()
        
        # Ensure EventDate is timezone-aware
        if 'EventDate' in schedule.columns:
            schedule['EventDate'] = pd.to_datetime(schedule['EventDate'], utc=True)
        
        # Filter to only completed events (event date in the past)
        now = datetime.now(pytz.utc)
        schedule = schedule[schedule['EventDate'] < now]
        
        return schedule
    except Exception as e:
        st.error(f"Could not load schedule: {e}")
        return pd.DataFrame()

# Get today's date for cache key
from datetime import date
_today = str(date.today())




def get_available_sessions(year: int, round_num: int):
    """Get available session types for a given event."""
    sessions = ["Race"]
    try:
        event = fastf1.get_event(year, round_num)
        # Check for sprint
        if hasattr(event, 'EventFormat'):
            if 'sprint' in str(event.EventFormat).lower():
                sessions.append("Sprint")
        sessions.append("Qualifying")
    except:
        pass
    return sessions


# ---------- MAIN PAGE ----------
st.markdown("""
<div style="text-align: center; padding: 20px 0;">
    <h1 style="font-size: 2.5rem; margin: 0;">🏁 Past Races</h1>
    <p style="color: #C5C6C7; margin-top: 10px;">
        Replay historical races with full telemetry visualization
    </p>
</div>
""", unsafe_allow_html=True)

# ---------- SESSION SELECTION ----------
st.markdown("---")

col_year, col_race, col_session, col_load = st.columns([1, 2, 1, 1])

with col_year:
    # Available years (2025 is current season, include all back to 2019)
    available_years = list(range(2025, 2018, -1))
    selected_year = st.selectbox("📅 Year", available_years, index=0)

with col_race:
    # Get races for selected year (cache key includes date for daily refresh)
    schedule = get_event_schedule(selected_year, _cache_date=_today)
    
    if not schedule.empty:
        # Create race options
        race_options = {}
        for _, row in schedule.iterrows():
            label = f"R{int(row['RoundNumber'])} - {row['EventName']}"
            race_options[label] = int(row['RoundNumber'])
        
        selected_race_label = st.selectbox("🏎️ Race", list(race_options.keys()))
        selected_round = race_options[selected_race_label]
    else:
        st.warning(f"No completed races found for {selected_year}. Select an earlier year.")
        selected_round = None

with col_session:
    if selected_round is not None:
        session_options = get_available_sessions(selected_year, selected_round)
        selected_session = st.selectbox("📋 Session", session_options)
        
        session_map = {"Race": "R", "Sprint": "S", "Qualifying": "Q"}
        session_code = session_map.get(selected_session, "R")
    else:
        st.selectbox("📋 Session", ["Race"], disabled=True)
        selected_session = "Race"
        session_code = "R"

with col_load:
    st.write("")  # Spacer
    st.write("")  # Spacer
    load_button = st.button("🔄 Load Race", type="primary", width='stretch', 
                            disabled=(selected_round is None))

# Check if we need to load new data
if selected_round is not None:
    current_key = f"{selected_year}_{selected_round}_{session_code}"
    
    if load_button or (st.session_state.past_race_key != current_key and st.session_state.past_race_data is None):
        if load_button:
            st.session_state.past_race_key = current_key
            st.session_state.past_race_time = 0.0
            st.session_state.past_race_playing = False
            st.session_state.past_race_selected_driver = None
            
            with st.spinner(f"Loading {selected_session} data for {selected_year} Round {selected_round}..."):
                try:
                    data = get_race_telemetry_frames(selected_year, selected_round, session_code)
                    st.session_state.past_race_data = data
                    st.success(f"Loaded {data['event_name']} - {data['total_laps']} laps, {len(data['frames'])} frames")
                except Exception as e:
                    st.error(f"Failed to load race data: {e}")
                    st.session_state.past_race_data = None


# ---------- VISUALIZATION ----------
race_data = st.session_state.past_race_data

if race_data and race_data.get("frames"):
    frames = race_data["frames"]
    driver_colors = race_data.get("driver_colors", {})
    track_coords = race_data.get("track_coords", {"x": [], "y": []})
    track_statuses = race_data.get("track_statuses", [])
    total_laps = race_data.get("total_laps", 0)
    rotation = race_data.get("circuit_rotation", 0.0)
    event_name = race_data.get("event_name", "Race")
    
    max_time = frames[-1]["t"] if frames else 0
    current_time = st.session_state.past_race_time
    
    # Get current frame
    current_frame = get_frame_at_time(frames, current_time)
    current_lap = current_frame.get("lap", 1) if current_frame else 1
    
    # Get current track status
    current_status = "1"
    for status in track_statuses:
        if status.get("start_time", 0) <= current_time:
            if status.get("end_time") is None or current_time < status["end_time"]:
                current_status = status.get("status", "1")
    
    # ---------- TRACK STATUS BANNER ----------
    render_track_status_banner(track_statuses, current_time)
    
    st.markdown("---")
    
    # ---------- MAIN LAYOUT ----------
    col_track, col_sidebar = st.columns([2, 1])
    
    with col_track:
        # Event header
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <h2 style="margin: 0;">{event_name}</h2>
            <div style="text-align: right;">
                <span style="font-size: 1.5rem; font-weight: bold; color: #FF1801;">
                    LAP {current_lap}/{total_laps}
                </span>
                <br>
                <span style="color: #C5C6C7;">
                    {format_time(current_time)}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Track map
        if track_coords.get("x") and current_frame:
            fig = render_track_map(
                track_coords=track_coords,
                frame_data=current_frame,
                driver_colors=driver_colors,
                rotation=rotation,
                height=450,
                selected_driver=st.session_state.past_race_selected_driver,
                track_status=current_status
            )
            st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
        else:
            st.info("Track map not available for this session")
        
        # Playback controls
        st.markdown("---")
        
        controls = render_playback_controls(
            current_time=current_time,
            max_time=max_time,
            current_lap=current_lap,
            total_laps=total_laps,
            is_playing=st.session_state.past_race_playing,
            playback_speed=st.session_state.past_race_speed
        )
        
        # Update state based on controls
        if controls["is_playing"] != st.session_state.past_race_playing:
            st.session_state.past_race_playing = controls["is_playing"]
        if controls["speed"] != st.session_state.past_race_speed:
            st.session_state.past_race_speed = controls["speed"]
        if controls["seek_time"] is not None:
            st.session_state.past_race_time = controls["seek_time"]
            st.rerun()
    
    with col_sidebar:
        # Leaderboard
        if current_frame:
            clicked = render_leaderboard(
                current_frame,
                driver_colors,
                selected_driver=st.session_state.past_race_selected_driver
            )
            if clicked:
                st.session_state.past_race_selected_driver = clicked
                st.rerun()
        
        st.markdown("---")
        
        # Weather
        weather = current_frame.get("weather") if current_frame else None
        render_weather_widget(weather)
    
    # ---------- SELECTED DRIVER DETAILS ----------
    if st.session_state.past_race_selected_driver:
        st.markdown("---")
        
        col_tel, col_chart = st.columns([1, 2])
        
        with col_tel:
            render_driver_telemetry(
                current_frame,
                st.session_state.past_race_selected_driver,
                driver_colors
            )
            
            # Clear selection button
            if st.button("✖️ Clear Selection", width='stretch'):
                st.session_state.past_race_selected_driver = None
                st.rerun()
        
        with col_chart:
            st.markdown("### 📈 Position History")
            pos_fig = create_position_chart(
                frames,
                selected_drivers=[st.session_state.past_race_selected_driver],
                driver_colors=driver_colors,
                height=250
            )
            st.plotly_chart(pos_fig, width='stretch')
    
    # ---------- AUTO-PLAY LOGIC ----------
    if st.session_state.past_race_playing:
        # Advance time
        new_time = current_time + (1.0 / FPS) * st.session_state.past_race_speed
        
        if new_time >= max_time:
            st.session_state.past_race_playing = False
            st.session_state.past_race_time = max_time
        else:
            st.session_state.past_race_time = new_time
        
        # Short sleep then rerun for animation
        time.sleep(1.0 / FPS)
        st.rerun()

else:
    # No data loaded
    st.markdown("""
    <div style="text-align: center; padding: 60px 20px; background: rgba(31, 40, 51, 0.6);
                border-radius: 20px; margin: 30px 0;">
        <div style="font-size: 4rem; margin-bottom: 20px;">🏁</div>
        <h2 style="margin: 0 0 15px 0;">Select a Race to Replay</h2>
        <p style="color: #C5C6C7; max-width: 500px; margin: 0 auto;">
            Choose a year, race, and session from the dropdowns above, then click 
            <strong>Load Race</strong> to start the replay visualization.
        </p>
        <div style="margin-top: 30px; color: #888;">
            <p>📊 Watch driver positions evolve in real-time</p>
            <p>🏎️ Track speeds, gears, and DRS status</p>
            <p>🌡️ Monitor weather conditions throughout the race</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick start suggestions
    st.markdown("### 🚀 Quick Start Suggestions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="feature-card" style="padding: 20px;">
            <h4>🏆 2024 Bahrain GP</h4>
            <p style="color: #C5C6C7; font-size: 0.9rem;">Season opener with close racing</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="feature-card" style="padding: 20px;">
            <h4>🌧️ 2023 Monaco GP</h4>
            <p style="color: #C5C6C7; font-size: 0.9rem;">Wet-dry drama at the streets of Monaco</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="feature-card" style="padding: 20px;">
            <h4>🔥 2023 Las Vegas GP</h4>
            <p style="color: #C5C6C7; font-size: 0.9rem;">Night race on the famous Strip</p>
        </div>
        """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.caption("Data provided by FastF1. Processing may take a moment for first-time loads.")
