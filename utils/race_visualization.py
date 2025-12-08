"""
Race Visualization Utilities

Core module for processing race telemetry data into visualization-ready formats.
Inspired by f1-race-replay but optimized for Streamlit/web-based visualization.

This module provides two modes:
1. FAST MODE (default): Uses position data only - loads in seconds
2. FULL MODE: Uses complete telemetry - very slow but more detailed
"""

import os
import pickle
import numpy as np
import pandas as pd
from datetime import timedelta
from typing import Dict, List, Optional, Tuple, Any
import fastf1
import fastf1.plotting
import streamlit as st

from utils.api_config import configure_fastf1_retries

# Configure retries
configure_fastf1_retries()

# Constants
FPS = 5  # Frames per second for replay (reduced for faster processing)
DT = 1 / FPS
CACHE_DIR = "data/computed_telemetry"


def enable_cache():
    """Enable FastF1 cache."""
    cache_path = 'f1_cache'
    if not os.path.exists(cache_path):
        os.makedirs(cache_path)
    fastf1.Cache.enable_cache(cache_path)


def get_tyre_compound_int(compound: str) -> int:
    """Convert tyre compound string to integer for visualization."""
    compounds = {
        'SOFT': 1,
        'MEDIUM': 2,
        'HARD': 3,
        'INTERMEDIATE': 4,
        'WET': 5,
        'UNKNOWN': 0,
    }
    return compounds.get(str(compound).upper(), 0)


def get_tyre_color(compound_int: int) -> str:
    """Get color for tyre compound."""
    colors = {
        1: '#FF3333',  # SOFT - Red
        2: '#FFD700',  # MEDIUM - Yellow
        3: '#FFFFFF',  # HARD - White
        4: '#00FF00',  # INTERMEDIATE - Green
        5: '#0080FF',  # WET - Blue
        0: '#888888',  # UNKNOWN - Gray
    }
    return colors.get(compound_int, '#888888')


def get_driver_colors(session) -> Dict[str, Tuple[int, int, int]]:
    """Get team colors for all drivers in the session."""
    try:
        color_mapping = fastf1.plotting.get_driver_color_mapping(session)
        
        rgb_colors = {}
        for driver, hex_color in color_mapping.items():
            hex_color = hex_color.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            rgb_colors[driver] = rgb
        return rgb_colors
    except Exception as e:
        print(f"Error getting driver colors: {e}")
        return {}


def get_circuit_rotation(session) -> float:
    """Get circuit rotation angle for proper display orientation."""
    try:
        circuit = session.get_circuit_info()
        return circuit.rotation if hasattr(circuit, 'rotation') else 0.0
    except:
        return 0.0


@st.cache_data(ttl=86400, show_spinner="Loading race data...")
def get_race_telemetry_frames(year: int, round_number: int, session_type: str = 'R', 
                               force_refresh: bool = False) -> Dict:
    """
    Get processed race data as frames for visualization using FAST mode.
    
    This uses position/lap data instead of full telemetry for much faster loading.
    
    Returns:
        Dict with keys: frames, driver_colors, track_statuses, total_laps, track_coords
    """
    enable_cache()
    
    # Check for cached computed data
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    
    cache_file = f"{CACHE_DIR}/{year}_R{round_number}_{session_type}_fast.pkl"
    
    if os.path.exists(cache_file) and not force_refresh:
        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Cache load failed: {e}")
    
    # Load session WITHOUT full telemetry (much faster!)
    session = fastf1.get_session(year, round_number, session_type)
    session.load(telemetry=False, weather=True, laps=True)
    
    drivers = session.drivers
    laps = session.laps
    
    if laps.empty:
        raise ValueError("No lap data available for this session")
    
    # Get driver codes
    driver_codes = {}
    for num in drivers:
        try:
            driver_codes[num] = session.get_driver(num)["Abbreviation"]
        except:
            driver_codes[num] = f"#{num}"
    
    # Get results for final positions
    try:
        results = session.results
    except:
        results = None
    
    # Process laps into frames - one frame per lap
    all_laps_data = []
    
    for driver_no in drivers:
        driver_code = driver_codes.get(driver_no, f"#{driver_no}")
        driver_laps = laps.pick_drivers(driver_no)
        
        if driver_laps.empty:
            continue
        
        for _, lap in driver_laps.iterrows():
            try:
                lap_num = int(lap['LapNumber'])
                lap_time = lap.get('LapTime')
                if pd.notna(lap_time):
                    lap_time_secs = lap_time.total_seconds()
                else:
                    lap_time_secs = None
                
                # Get position 
                position = lap.get('Position', 20)
                if pd.isna(position):
                    position = 20
                
                # Get tyre compound
                compound = str(lap.get('Compound', 'UNKNOWN'))
                tyre_int = get_tyre_compound_int(compound)
                
                all_laps_data.append({
                    'driver': driver_code,
                    'lap': lap_num,
                    'position': int(position),
                    'lap_time': lap_time_secs,
                    'tyre': tyre_int,
                })
            except Exception as e:
                continue
    
    if not all_laps_data:
        raise ValueError("No valid lap data found")
    
    # Convert to DataFrame for easier processing
    laps_df = pd.DataFrame(all_laps_data)
    max_lap = int(laps_df['lap'].max())
    
    # Build frames - one per lap
    frames = []
    
    for lap_num in range(1, max_lap + 1):
        lap_data = laps_df[laps_df['lap'] == lap_num]
        
        if lap_data.empty:
            continue
        
        # Sort by position
        lap_data = lap_data.sort_values('position')
        
        frame_drivers = {}
        for _, row in lap_data.iterrows():
            driver_code = row['driver']
            frame_drivers[driver_code] = {
                'position': int(row['position']),
                'lap': int(row['lap']),
                'tyre': int(row['tyre']),
                'lap_time': row['lap_time'],
                # Placeholder coordinates (will use track layout)
                'x': 0,
                'y': 0,
                'speed': 0,
                'gear': 0,
                'drs': 0,
                'dist': 0,
            }
        
        # Calculate time offset (rough estimate based on lap number)
        # Assuming average lap time of 90 seconds
        approx_time = lap_num * 90.0
        
        frames.append({
            't': approx_time,
            'lap': lap_num,
            'drivers': frame_drivers,
        })
    
    # Get track coordinates from fastest lap
    track_x, track_y = [], []
    try:
        # Try to get track layout from circuit info
        circuit_info = session.get_circuit_info()
        if hasattr(circuit_info, 'corners'):
            corners = circuit_info.corners
            if hasattr(corners, 'X') and hasattr(corners, 'Y'):
                track_x = corners.X.tolist()
                track_y = corners.Y.tolist()
    except:
        pass
    
    # If no track coords, try fastest lap (but with limited telemetry)
    if not track_x:
        try:
            fastest = session.laps.pick_fastest()
            if fastest is not None:
                tel = fastest.get_telemetry()
                if tel is not None and not tel.empty:
                    track_x = tel['X'].tolist()
                    track_y = tel['Y'].tolist()
        except:
            pass
    
    # Get track status
    track_statuses = []
    try:
        track_status = session.track_status
        if track_status is not None and not track_status.empty:
            for status in track_status.to_dict('records'):
                try:
                    seconds = status['Time'].total_seconds()
                    track_statuses.append({
                        'status': str(status['Status']),
                        'start_time': seconds,
                        'end_time': None,
                    })
                except:
                    continue
            
            # Set end times
            for i in range(len(track_statuses) - 1):
                track_statuses[i]['end_time'] = track_statuses[i + 1]['start_time']
    except:
        pass
    
    result = {
        "frames": frames,
        "driver_colors": get_driver_colors(session),
        "track_statuses": track_statuses,
        "total_laps": max_lap,
        "track_coords": {"x": track_x, "y": track_y},
        "circuit_rotation": get_circuit_rotation(session),
        "event_name": session.event['EventName'],
    }

    # Save to cache
    try:
        with open(cache_file, "wb") as f:
            pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        print(f"Cache save failed: {e}")

    return result


def get_frame_at_time(frames: List[Dict], time_seconds: float) -> Optional[Dict]:
    """Get the frame closest to the given time."""
    if not frames:
        return None
    
    for frame in frames:
        if frame["t"] >= time_seconds:
            return frame
    
    return frames[-1]


def get_frame_at_lap(frames: List[Dict], lap: int) -> Optional[Dict]:
    """Get the first frame of a specific lap."""
    for frame in frames:
        if frame["lap"] >= lap:
            return frame
    return frames[-1] if frames else None


def get_track_status_color(status: str) -> str:
    """Get color for track status."""
    status_colors = {
        "1": "#00FF00",  # Green - All clear
        "2": "#FFFF00",  # Yellow - Yellow flag
        "4": "#FFA500",  # Orange - Safety Car
        "5": "#FF0000",  # Red - Red flag
        "6": "#FF8C00",  # Dark Orange - VSC
        "7": "#FF8C00",  # Dark Orange - VSC Ending
    }
    return status_colors.get(status, "#00FF00")


def get_track_status_text(status: str) -> str:
    """Get text description for track status."""
    status_text = {
        "1": "GREEN FLAG",
        "2": "YELLOW FLAG",
        "4": "SAFETY CAR",
        "5": "RED FLAG",
        "6": "VSC",
        "7": "VSC ENDING",
    }
    return status_text.get(status, "")
