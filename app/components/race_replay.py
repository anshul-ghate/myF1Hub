"""
Race Replay Components

Reusable Streamlit components for race visualization.
Provides leaderboard, playback controls, telemetry panels, and weather widgets.
"""

import streamlit as st
from typing import Dict, List, Optional, Callable, Tuple
import math


def format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS or MM:SS."""
    if seconds is None or math.isnan(seconds):
        return "--:--"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_gap(gap_seconds: float) -> str:
    """Format gap to leader as string."""
    if gap_seconds is None or gap_seconds == 0:
        return "LEADER"
    if math.isnan(gap_seconds):
        return "--"
    return f"+{gap_seconds:.1f}s"


def get_tyre_emoji(tyre_int: int) -> str:
    """Get emoji for tyre compound."""
    tyres = {
        1: "🔴",  # SOFT
        2: "🟡",  # MEDIUM  
        3: "⚪",  # HARD
        4: "🟢",  # INTERMEDIATE
        5: "🔵",  # WET
        0: "⚫",  # UNKNOWN
    }
    return tyres.get(tyre_int, "⚫")


def get_tyre_name(tyre_int: int) -> str:
    """Get name for tyre compound."""
    tyres = {
        1: "SOFT",
        2: "MEDIUM",
        3: "HARD",
        4: "INTER",
        5: "WET",
        0: "N/A",
    }
    return tyres.get(tyre_int, "N/A")


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex string."""
    return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'


def render_leaderboard(frame_data: Dict, driver_colors: Dict, 
                       selected_driver: Optional[str] = None,
                       on_driver_click: bool = True) -> Optional[str]:
    """
    Render race leaderboard with clickable driver rows.
    
    Args:
        frame_data: Current frame data with driver positions
        driver_colors: Dict mapping driver codes to RGB tuples
        selected_driver: Currently selected driver code
        on_driver_click: If True, makes rows clickable
    
    Returns:
        Selected driver code if clicked, else None
    """
    if not frame_data or "drivers" not in frame_data:
        st.info("No leaderboard data available")
        return None
    
    drivers = frame_data["drivers"]
    
    # Sort by position
    sorted_drivers = sorted(drivers.items(), 
                           key=lambda x: x[1].get("position", 99))
    
    # Calculate gaps
    leader_dist = sorted_drivers[0][1].get("dist", 0) if sorted_drivers else 0
    
    clicked_driver = None
    
    # Custom CSS for leaderboard
    st.markdown("""
    <style>
    .leaderboard-row {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        margin: 2px 0;
        border-radius: 8px;
        background: rgba(31, 40, 51, 0.6);
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .leaderboard-row:hover {
        background: rgba(255, 24, 1, 0.2);
        transform: translateX(5px);
    }
    .leaderboard-row.selected {
        background: rgba(255, 24, 1, 0.4);
        border-left: 4px solid #FF1801;
    }
    .position-badge {
        font-weight: bold;
        font-size: 1.1rem;
        width: 30px;
        text-align: center;
    }
    .driver-code {
        font-weight: 600;
        font-size: 1rem;
        margin-left: 10px;
        width: 50px;
    }
    .tyre-indicator {
        margin-left: 10px;
    }
    .gap-display {
        margin-left: auto;
        font-size: 0.9rem;
        color: #C5C6C7;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("### 📊 Leaderboard")
    
    for code, data in sorted_drivers:
        pos = data.get("position", "?")
        tyre = data.get("tyre", 0)
        dist = data.get("dist", 0)
        lap = data.get("lap", 0)
        
        # Calculate gap (simplified - by distance)
        gap = (leader_dist - dist) / 1000 * 3.6  # Approx gap in seconds
        gap_str = format_gap(gap) if pos > 1 else "LEADER"
        
        color = driver_colors.get(code, (128, 128, 128))
        hex_color = rgb_to_hex(color)
        
        is_selected = code == selected_driver
        row_class = "leaderboard-row selected" if is_selected else "leaderboard-row"
        
        # Create button for each row
        col1, col2 = st.columns([10, 1])
        with col1:
            if st.button(
                f"P{pos} | {code} {get_tyre_emoji(tyre)} | LAP {lap} | {gap_str}",
                key=f"driver_{code}",
                width='stretch',
                type="secondary" if not is_selected else "primary"
            ):
                clicked_driver = code
    
    return clicked_driver


def render_playback_controls(current_time: float, max_time: float,
                             current_lap: int, total_laps: int,
                             is_playing: bool, playback_speed: float) -> Dict:
    """
    Render playback controls for race replay.
    
    Returns:
        Dict with updated control states
    """
    result = {
        "is_playing": is_playing,
        "speed": playback_speed,
        "seek_time": None,
        "seek_lap": None,
    }
    
    st.markdown("### ⏯️ Playback Controls")
    
    # Main controls row
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 2])
    
    with col1:
        if st.button("⏮️", help="Restart", width='stretch'):
            result["seek_time"] = 0
            
    with col2:
        if st.button("⏪", help="Rewind 30s", width='stretch'):
            result["seek_time"] = max(0, current_time - 30)
            
    with col3:
        if is_playing:
            if st.button("⏸️", help="Pause", width='stretch'):
                result["is_playing"] = False
        else:
            if st.button("▶️", help="Play", width='stretch'):
                result["is_playing"] = True
                
    with col4:
        if st.button("⏩", help="Forward 30s", width='stretch'):
            result["seek_time"] = min(max_time, current_time + 30)
            
    with col5:
        speed_options = [0.5, 1.0, 2.0, 4.0, 8.0]
        current_idx = speed_options.index(playback_speed) if playback_speed in speed_options else 1
        
        if st.button(f"🔄 {playback_speed}x", help="Change speed", width='stretch'):
            next_idx = (current_idx + 1) % len(speed_options)
            result["speed"] = speed_options[next_idx]
    
    # Time/Lap display
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**⏱️ Time:** {format_time(current_time)}")
    with col2:
        st.markdown(f"**🏁 Lap:** {current_lap}/{total_laps}")
    
    # Seek slider
    seek_time = st.slider(
        "Seek",
        min_value=0.0,
        max_value=max_time,
        value=current_time,
        step=1.0,
        format="%.0f s",
        label_visibility="collapsed"
    )
    
    if abs(seek_time - current_time) > 2:  # Only trigger if significantly different
        result["seek_time"] = seek_time
    
    return result


def render_driver_telemetry(frame_data: Dict, driver_code: str,
                            driver_colors: Dict) -> None:
    """
    Render detailed telemetry panel for selected driver.
    """
    if not frame_data or not driver_code:
        st.info("Select a driver to view telemetry")
        return
    
    drivers = frame_data.get("drivers", {})
    if driver_code not in drivers:
        st.warning(f"No data for {driver_code}")
        return
    
    data = drivers[driver_code]
    color = driver_colors.get(driver_code, (128, 128, 128))
    hex_color = rgb_to_hex(color)
    
    # Driver header
    st.markdown(f"""
    <div style="background: linear-gradient(90deg, {hex_color}44, transparent);
                padding: 15px; border-radius: 10px; margin-bottom: 15px;
                border-left: 4px solid {hex_color};">
        <h3 style="margin: 0; color: white;">📊 {driver_code}</h3>
        <p style="margin: 5px 0 0 0; color: #C5C6C7;">Position: P{data.get('position', '?')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Telemetry metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        speed = data.get("speed", 0)
        st.metric("🏎️ Speed", f"{speed:.0f} km/h")
        
    with col2:
        gear = data.get("gear", 0)
        st.metric("⚙️ Gear", str(int(gear)))
        
    with col3:
        drs = data.get("drs", 0)
        drs_status = "OPEN" if drs > 10 else "CLOSED"
        st.metric("📡 DRS", drs_status)
        
    with col4:
        tyre = data.get("tyre", 0)
        st.metric("🔴 Tyre", get_tyre_name(tyre))
    
    # Additional stats
    col1, col2 = st.columns(2)
    
    with col1:
        lap = data.get("lap", 0)
        st.metric("🔄 Current Lap", str(int(lap)))
        
    with col2:
        dist = data.get("dist", 0)
        st.metric("📏 Distance", f"{dist/1000:.2f} km")


def render_weather_widget(weather_data: Optional[Dict]) -> None:
    """
    Render weather conditions widget.
    """
    st.markdown("### 🌡️ Weather")
    
    if not weather_data:
        st.info("No weather data available")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        track_temp = weather_data.get("track_temp")
        if track_temp is not None:
            st.metric("🛤️ Track", f"{track_temp:.1f}°C")
        
        humidity = weather_data.get("humidity")
        if humidity is not None:
            st.metric("💧 Humidity", f"{humidity:.0f}%")
    
    with col2:
        air_temp = weather_data.get("air_temp")
        if air_temp is not None:
            st.metric("🌡️ Air", f"{air_temp:.1f}°C")
        
        wind_speed = weather_data.get("wind_speed")
        wind_dir = weather_data.get("wind_direction")
        if wind_speed is not None:
            dir_str = format_wind_direction(wind_dir)
            st.metric("🌬️ Wind", f"{wind_speed:.0f} km/h {dir_str}")
    
    # Rain status
    rain_state = weather_data.get("rain_state", "DRY")
    rain_color = "#00FF00" if rain_state == "DRY" else "#0080FF"
    st.markdown(f"""
    <div style="text-align: center; padding: 10px; border-radius: 8px;
                background: {rain_color}22; border: 1px solid {rain_color};">
        {'🌧️ RAINING' if rain_state != 'DRY' else '☀️ DRY CONDITIONS'}
    </div>
    """, unsafe_allow_html=True)


def format_wind_direction(degrees: Optional[float]) -> str:
    """Convert wind direction degrees to compass direction."""
    if degrees is None:
        return ""
    
    deg_norm = degrees % 360
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = int((deg_norm / 22.5) + 0.5) % len(dirs)
    return dirs[idx]


def render_track_status_banner(track_statuses: List[Dict], current_time: float) -> None:
    """
    Render track status banner (flags, safety car, etc.)
    """
    current_status = "1"  # Default: Green
    
    for status in track_statuses:
        start = status.get("start_time", 0)
        end = status.get("end_time")
        
        if start <= current_time and (end is None or current_time < end):
            current_status = status.get("status", "1")
            break
    
    status_config = {
        "1": {"text": "GREEN FLAG", "color": "#00FF00", "bg": "#00FF0022"},
        "2": {"text": "⚠️ YELLOW FLAG", "color": "#FFD700", "bg": "#FFD70033"},
        "4": {"text": "🚗 SAFETY CAR", "color": "#FF8C00", "bg": "#FF8C0033"},
        "5": {"text": "🔴 RED FLAG", "color": "#FF0000", "bg": "#FF000044"},
        "6": {"text": "⚠️ VIRTUAL SAFETY CAR", "color": "#FF4500", "bg": "#FF450033"},
        "7": {"text": "VSC ENDING", "color": "#FF6347", "bg": "#FF634733"},
    }
    
    config = status_config.get(current_status, status_config["1"])
    
    if current_status != "1":
        st.markdown(f"""
        <div style="text-align: center; padding: 12px; border-radius: 8px;
                    background: {config['bg']}; border: 2px solid {config['color']};
                    font-weight: bold; font-size: 1.2rem; color: {config['color']};
                    animation: pulse 1.5s infinite;">
            {config['text']}
        </div>
        <style>
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}
        </style>
        """, unsafe_allow_html=True)


def render_session_selector(available_years: List[int] = None) -> Tuple[int, int, str]:
    """
    Render session selection controls.
    
    Returns:
        Tuple of (year, round_number, session_type)
    """
    if available_years is None:
        available_years = list(range(2024, 2018, -1))  # 2024 down to 2019
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        year = st.selectbox("📅 Year", available_years, index=0)
    
    with col2:
        # Would need to fetch actual rounds for the year
        round_number = st.number_input("🔢 Round", min_value=1, max_value=24, value=1)
    
    with col3:
        session_type = st.selectbox(
            "📋 Session",
            ["Race", "Sprint", "Qualifying"],
            index=0
        )
        
        session_map = {"Race": "R", "Sprint": "S", "Qualifying": "Q"}
        session_code = session_map[session_type]
    
    return year, round_number, session_code
