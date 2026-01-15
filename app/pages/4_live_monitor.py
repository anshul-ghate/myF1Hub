"""
Live Race Monitor Page

Real-time race visualization during live sessions.
Shows track positions, leaderboard, telemetry, and weather in real-time.
Falls back to demo/past race data when no live session is active.
"""

import streamlit as st
import time
import requests
import pandas as pd
import fastf1
from datetime import datetime, timezone, timedelta
import os
import pytz
from utils.logger import get_logger
from utils.time_simulation import get_current_time

logger = get_logger(__name__)

# Page Config - must be first
st.set_page_config(
    page_title="Live Monitor | F1 HUB",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inject Custom CSS
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except Exception as e:
        logger.warning(f"Failed to load CSS {file_name}: {e}")

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
    create_position_chart
)
from app.components.race_replay import (
    render_leaderboard,
    render_driver_telemetry,
    render_weather_widget,
    render_track_status_banner,
    format_time,
    rgb_to_hex,
    get_tyre_emoji,
    get_tyre_name
)

# Enable FastF1 cache
from utils.api_config import configure_fastf1_retries
configure_fastf1_retries()

if not os.path.exists('f1_cache'):
    os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')


# ---------- OPENF1 API INTEGRATION ----------
OPENF1_BASE_URL = "https://api.openf1.org/v1"


@st.cache_data(ttl=5)
def get_live_session():
    """Check if there's a live session happening."""
    try:
        response = requests.get(f"{OPENF1_BASE_URL}/sessions", timeout=5)
        if response.status_code == 200:
            sessions = response.json()
            if sessions:
                # Get most recent session
                latest = sessions[-1]
                return latest
    except Exception as e:
        logger.warning(f"OpenF1 session check failed: {e}")
    return None


@st.cache_data(ttl=3)
def get_live_positions():
    """Get current driver positions from OpenF1."""
    try:
        response = requests.get(
            f"{OPENF1_BASE_URL}/position",
            params={"session_key": "latest"},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.debug(f"OpenF1 positions failed: {e}")
    return []


@st.cache_data(ttl=3)
def get_live_car_data():
    """Get car telemetry data from OpenF1."""
    try:
        response = requests.get(
            f"{OPENF1_BASE_URL}/car_data",
            params={"session_key": "latest"},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.debug(f"OpenF1 car data failed: {e}")
    return []


@st.cache_data(ttl=3)
def get_live_drivers():
    """Get driver info from OpenF1."""
    try:
        response = requests.get(
            f"{OPENF1_BASE_URL}/drivers",
            params={"session_key": "latest"},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"OpenF1 drivers failed: {e}")
    return []


@st.cache_data(ttl=10)
def get_live_weather():
    """Get weather data from OpenF1."""
    try:
        response = requests.get(
            f"{OPENF1_BASE_URL}/weather",
            params={"session_key": "latest"},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[-1]  # Most recent
    except Exception as e:
        logger.warning(f"OpenF1 weather failed: {e}")
    return None


def check_upcoming_session():
    """Check if there's an upcoming session soon."""
    try:
        now = get_current_time()
        schedule = fastf1.get_event_schedule(now.year)
        
        for _, event in schedule.iterrows():
            for session_col in ['Session1Date', 'Session2Date', 'Session3Date', 'Session4Date', 'Session5Date']:
                if session_col in event and pd.notna(event[session_col]):
                    session_time = pd.to_datetime(event[session_col], utc=True)
                    
                    # Session within next 2 hours or currently running
                    if now - timedelta(hours=4) <= session_time <= now + timedelta(hours=2):
                        return {
                            "event_name": event['EventName'],
                            "session_time": session_time,
                            "is_live": now >= session_time,
                            "time_until": (session_time - now).total_seconds() if session_time > now else 0
                        }
        return None
    except Exception as e:
        logger.error(f"Schedule check failed: {e}")
        return None


# ---------- SESSION STATE ----------
if 'live_mode' not in st.session_state:
    st.session_state.live_mode = 'checking'  # 'live', 'demo', 'checking'
if 'live_selected_driver' not in st.session_state:
    st.session_state.live_selected_driver = None
if 'demo_data' not in st.session_state:
    st.session_state.demo_data = None
if 'demo_time' not in st.session_state:
    st.session_state.demo_time = 0.0
if 'demo_playing' not in st.session_state:
    st.session_state.demo_playing = False
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True


# ---------- MAIN PAGE ----------
st.markdown("""
<div style="text-align: center; padding: 20px 0;">
    <h1 style="font-size: 2.5rem; margin: 0;">📡 Live Monitor</h1>
    <p style="color: #C5C6C7; margin-top: 10px;">
        Real-time race tracking and telemetry visualization
    </p>
</div>
""", unsafe_allow_html=True)


# ---------- CHECK LIVE SESSION STATUS ----------
live_session = get_live_session()
upcoming = check_upcoming_session()

if live_session and live_session.get("session_key"):
    st.session_state.live_mode = 'live'
elif upcoming and upcoming.get("is_live"):
    st.session_state.live_mode = 'live'  
elif upcoming:
    st.session_state.live_mode = 'upcoming'
else:
    st.session_state.live_mode = 'demo'


# ---------- MODE: LIVE ----------
if st.session_state.live_mode == 'live':
    # Live indicator
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: center; gap: 10px;
                background: rgba(255, 0, 0, 0.2); padding: 10px 20px; border-radius: 10px;
                border: 2px solid #FF0000; margin-bottom: 20px;">
        <div style="width: 15px; height: 15px; background: #FF0000; border-radius: 50%;
                    animation: pulse 1s infinite;"></div>
        <span style="font-weight: bold; font-size: 1.2rem; color: #FF0000;">LIVE</span>
        <span style="color: #C5C6C7;">| Session in progress</span>
    </div>
    <style>
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Auto-refresh toggle
    col1, col2 = st.columns([3, 1])
    with col2:
        st.session_state.auto_refresh = st.checkbox("🔄 Auto-refresh", value=st.session_state.auto_refresh)
    
    st.markdown("---")
    
    # Get live data
    positions = get_live_positions()
    car_data = get_live_car_data()
    drivers_info = get_live_drivers()
    weather = get_live_weather()
    
    # Build driver color map
    driver_colors = {}
    driver_map = {}
    for d in drivers_info:
        code = d.get("name_acronym", "???")
        color_str = d.get("team_colour", "888888")
        try:
            r, g, b = int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16)
            driver_colors[code] = (r, g, b)
        except Exception:
            driver_colors[code] = (128, 128, 128)
        driver_map[d.get("driver_number")] = code
    
    # Build frame-like data structure for position display
    current_frame = {"drivers": {}}
    
    if positions:
        # Get most recent position for each driver
        latest_positions = {}
        for p in positions:
            driver_num = p.get("driver_number")
            if driver_num not in latest_positions:
                latest_positions[driver_num] = p
        
        for driver_num, p in latest_positions.items():
            code = driver_map.get(driver_num, f"#{driver_num}")
            current_frame["drivers"][code] = {
                "position": p.get("position", 99),
                "lap": 0,  # Would need lap data
                "x": 0,
                "y": 0,
                "speed": 0,
                "tyre": 0,
                "gear": 0,
                "drs": 0,
                "dist": 0,
            }
    
    # Merge car telemetry
    if car_data:
        for c in car_data[-20:]:  # Get recent entries
            driver_num = c.get("driver_number")
            code = driver_map.get(driver_num)
            if code and code in current_frame["drivers"]:
                current_frame["drivers"][code].update({
                    "speed": c.get("speed", 0),
                    "gear": c.get("n_gear", 0),
                    "drs": c.get("drs", 0),
                })
    
    # Layout
    col_main, col_side = st.columns([2, 1])
    
    with col_main:
        st.markdown("### 📊 Live Standings")
        
        if current_frame["drivers"]:
            # Sort by position
            sorted_drivers = sorted(
                current_frame["drivers"].items(),
                key=lambda x: x[1].get("position", 99)
            )
            
            # Create leaderboard
            for code, data in sorted_drivers[:20]:
                pos = data.get("position", "?")
                speed = data.get("speed", 0)
                gear = data.get("gear", 0)
                
                color = driver_colors.get(code, (128, 128, 128))
                hex_color = rgb_to_hex(color)
                
                is_selected = code == st.session_state.live_selected_driver
                
                col_pos, col_driver, col_stats = st.columns([1, 2, 3])
                
                with col_pos:
                    st.markdown(f"**P{pos}**")
                with col_driver:
                    if st.button(f"{code}", key=f"live_{code}", type="primary" if is_selected else "secondary"):
                        st.session_state.live_selected_driver = code if not is_selected else None
                        st.rerun()
                with col_stats:
                    st.markdown(f"🏎️ {speed} km/h | ⚙️ G{gear}")
        else:
            st.info("Waiting for position data...")
    
    with col_side:
        # Weather
        st.markdown("### 🌡️ Conditions")
        if weather:
            render_weather_widget({
                "track_temp": weather.get("track_temperature"),
                "air_temp": weather.get("air_temperature"),
                "humidity": weather.get("humidity"),
                "wind_speed": weather.get("wind_speed"),
                "wind_direction": weather.get("wind_direction"),
                "rain_state": "RAINING" if weather.get("rainfall", 0) > 0 else "DRY"
            })
        else:
            st.info("Weather data loading...")
        
        # Selected driver
        if st.session_state.live_selected_driver:
            st.markdown("---")
            render_driver_telemetry(
                current_frame,
                st.session_state.live_selected_driver,
                driver_colors
            )
    
    # Auto-refresh
    if st.session_state.auto_refresh:
        time.sleep(5)
        st.rerun()


# ---------- MODE: UPCOMING ----------
elif st.session_state.live_mode == 'upcoming' and upcoming:
    time_until = upcoming.get("time_until", 0)
    hours = int(time_until // 3600)
    minutes = int((time_until % 3600) // 60)
    
    st.markdown(f"""
    <div style="text-align: center; padding: 40px; background: rgba(255, 165, 0, 0.1);
                border-radius: 20px; border: 2px solid #FFA500; margin: 30px 0;">
        <h2 style="color: #FFA500; margin: 0;">⏳ Session Starting Soon</h2>
        <h1 style="margin: 20px 0;">{upcoming.get('event_name', 'Formula 1')}</h1>
        <div style="font-size: 2rem; font-weight: bold; color: #FF1801;">
            {hours}h {minutes:02d}m
        </div>
        <p style="color: #C5C6C7; margin-top: 20px;">
            Live monitoring will begin automatically when the session starts.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Demo mode option
    st.markdown("---")
    st.markdown("### 🎮 While You Wait...")
    
    if st.button("🏁 View Demo Race Replay", type="primary", width='stretch'):
        st.session_state.live_mode = 'demo'
        st.rerun()
    
    # Auto-check for session start
    if st.session_state.auto_refresh:
        time.sleep(30)
        st.rerun()


# ---------- MODE: DEMO (No Live Session) ----------
else:
    # No live session message
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: center; gap: 10px;
                background: rgba(100, 100, 100, 0.2); padding: 10px 20px; border-radius: 10px;
                border: 2px solid #666; margin-bottom: 20px;">
        <span style="font-weight: bold; color: #888;">⭕ NO LIVE SESSION</span>
        <span style="color: #C5C6C7;">| Demo mode with historical data</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("💡 There's no live F1 session right now. Showing demo replay with historical data.")
    
    st.markdown("---")
    
    # Load demo data (most recent completed race)
    demo_year = 2024
    demo_round = 1  # Bahrain GP
    
    if st.session_state.demo_data is None:
        with st.spinner("Loading demo race data..."):
            try:
                st.session_state.demo_data = get_race_telemetry_frames(demo_year, demo_round, 'R')
            except Exception as e:
                logger.error(f"Could not load demo data: {e}")
                st.error(f"Could not load demo data. Please try again later.")
                st.session_state.demo_data = {}
    
    demo_data = st.session_state.demo_data
    
    if demo_data and demo_data.get("frames"):
        frames = demo_data["frames"]
        driver_colors = demo_data.get("driver_colors", {})
        track_coords = demo_data.get("track_coords", {"x": [], "y": []})
        track_statuses = demo_data.get("track_statuses", [])
        total_laps = demo_data.get("total_laps", 0)
        rotation = demo_data.get("circuit_rotation", 0.0)
        event_name = demo_data.get("event_name", "Demo Race")
        
        max_time = frames[-1]["t"] if frames else 0
        current_time = st.session_state.demo_time
        
        # Get current frame
        current_frame = get_frame_at_time(frames, current_time)
        current_lap = current_frame.get("lap", 1) if current_frame else 1
        
        # Demo controls
        col1, col2, col3 = st.columns([1, 1, 3])
        
        with col1:
            if st.session_state.demo_playing:
                if st.button("⏸️ Pause", width='stretch'):
                    st.session_state.demo_playing = False
            else:
                if st.button("▶️ Play Demo", width='stretch', type="primary"):
                    st.session_state.demo_playing = True
        
        with col2:
            if st.button("🔄 Restart", width='stretch'):
                st.session_state.demo_time = 0.0
                st.rerun()
        
        with col3:
            st.markdown(f"**{event_name}** | Lap {current_lap}/{total_laps} | {format_time(current_time)}")
        
        st.markdown("---")
        
        # Track status
        current_status = "1"
        for status in track_statuses:
            if status.get("start_time", 0) <= current_time:
                if status.get("end_time") is None or current_time < status["end_time"]:
                    current_status = status.get("status", "1")
        
        render_track_status_banner(track_statuses, current_time)
        
        # Main layout
        col_track, col_sidebar = st.columns([2, 1])
        
        with col_track:
            if track_coords.get("x") and current_frame:
                fig = render_track_map(
                    track_coords=track_coords,
                    frame_data=current_frame,
                    driver_colors=driver_colors,
                    rotation=rotation,
                    height=400,
                    selected_driver=st.session_state.live_selected_driver,
                    track_status=current_status
                )
                st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
        
        with col_sidebar:
            if current_frame:
                clicked = render_leaderboard(
                    current_frame,
                    driver_colors,
                    selected_driver=st.session_state.live_selected_driver
                )
                if clicked:
                    st.session_state.live_selected_driver = clicked
                    st.rerun()
            
            st.markdown("---")
            weather = current_frame.get("weather") if current_frame else None
            render_weather_widget(weather)
        
        # Auto-play demo
        if st.session_state.demo_playing:
            new_time = current_time + (1.0 / FPS) * 2.0  # 2x speed for demo
            
            if new_time >= max_time:
                st.session_state.demo_playing = False
                st.session_state.demo_time = 0.0
            else:
                st.session_state.demo_time = new_time
            
            time.sleep(1.0 / FPS)
            st.rerun()
    
    else:
        st.warning("Demo data could not be loaded. Try refreshing the page.")
    
    # Link to Past Races
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 20px;">
        <p style="color: #C5C6C7;">Want full replay control?</p>
        <a href="/past_races" target="_self" class="feature-card" style="display: inline-block; padding: 15px 30px;">
            🏁 Go to Past Races
        </a>
    </div>
    """, unsafe_allow_html=True)


# Footer
st.markdown("---")
st.caption("Live data powered by OpenF1 API. Historical data by FastF1.")
