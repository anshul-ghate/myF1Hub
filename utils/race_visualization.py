"""
Race Visualization Utilities

Core module for processing race telemetry data into visualization-ready formats.
Inspired by f1-race-replay but optimized for Streamlit/web-based visualization.

This module provides two modes:
1. FAST MODE: Uses position data only - loads in seconds (lap-by-lap snapshots)
2. FULL MODE: Uses complete telemetry - slower but accurate driver positions
"""

import os
import pickle
import numpy as np
import pandas as pd
from datetime import timedelta
from typing import Dict, List, Optional, Tuple, Any
from multiprocessing import Pool, cpu_count
import fastf1
import fastf1.plotting
import streamlit as st

from utils.api_config import configure_fastf1_retries

# Configure retries
configure_fastf1_retries()
import logging
logger = logging.getLogger(__name__)

# Constants
FPS = 4  # Frames per second (reduced from 10 to 4 for payload size optimization)
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
        logger.warning(f"Error getting driver colors: {e}")
        return {}


def get_circuit_rotation(session) -> float:
    """Get circuit rotation angle for proper display orientation."""
    try:
        circuit = session.get_circuit_info()
        return circuit.rotation if hasattr(circuit, 'rotation') else 0.0
    except Exception as e:
        logger.debug(f"Could not get circuit rotation: {e}")
        return 0.0


def _process_single_driver(args) -> Optional[Dict]:
    """Process telemetry data for a single driver - for parallel processing."""
    driver_no, session, driver_code = args
    
    try:
        laps_driver = session.laps.pick_drivers(driver_no)
        if laps_driver.empty:
            return None
        
        driver_max_lap = int(laps_driver.LapNumber.max()) if not laps_driver.empty else 0
        
        t_all, x_all, y_all = [], [], []
        dist_all, rel_dist_all = [], []
        lap_numbers, tyre_compounds = [], []
        speed_all, gear_all, drs_all = [], [], []
        
        total_dist_so_far = 0.0
        
        # Iterate laps in order
        for _, lap in laps_driver.iterlaps():
            try:
                lap_tel = lap.get_telemetry()
                if lap_tel is None or lap_tel.empty:
                    continue
                
                lap_number = int(lap.LapNumber)
                tyre_int = get_tyre_compound_int(lap.Compound)
                
                t_lap = lap_tel["SessionTime"].dt.total_seconds().to_numpy()
                x_lap = lap_tel["X"].to_numpy()
                y_lap = lap_tel["Y"].to_numpy()
                
                # Handle optional columns
                d_lap = lap_tel["Distance"].to_numpy() if "Distance" in lap_tel.columns else np.zeros_like(t_lap)
                rd_lap = lap_tel["RelativeDistance"].to_numpy() if "RelativeDistance" in lap_tel.columns else np.zeros_like(t_lap)
                speed_lap = lap_tel["Speed"].to_numpy() if "Speed" in lap_tel.columns else np.zeros_like(t_lap)
                gear_lap = lap_tel["nGear"].to_numpy() if "nGear" in lap_tel.columns else np.ones_like(t_lap)
                drs_lap = lap_tel["DRS"].to_numpy() if "DRS" in lap_tel.columns else np.zeros_like(t_lap)
                
                t_all.append(t_lap)
                x_all.append(x_lap)
                y_all.append(y_lap)
                dist_all.append(total_dist_so_far + d_lap)
                rel_dist_all.append(rd_lap)
                lap_numbers.append(np.full_like(t_lap, lap_number))
                tyre_compounds.append(np.full_like(t_lap, tyre_int))
                speed_all.append(speed_lap)
                gear_all.append(gear_lap)
                drs_all.append(drs_lap)
                
                # Update total distance for next lap
                if len(d_lap) > 0:
                    total_dist_so_far += d_lap[-1]
                
            except Exception as lap_err:
                logger.debug(f"Error processing lap for {driver_code}: {lap_err}")
                continue
        
        if not t_all:
            return None
        
        # Concatenate all arrays
        t_all = np.concatenate(t_all)
        x_all = np.concatenate(x_all)
        y_all = np.concatenate(y_all)
        dist_all = np.concatenate(dist_all)
        rel_dist_all = np.concatenate(rel_dist_all)
        lap_numbers = np.concatenate(lap_numbers)
        tyre_compounds = np.concatenate(tyre_compounds)
        speed_all = np.concatenate(speed_all)
        gear_all = np.concatenate(gear_all)
        drs_all = np.concatenate(drs_all)
        
        # Sort by time
        order = np.argsort(t_all)
        
        return {
            "code": driver_code,
            "data": {
                "t": t_all[order],
                "x": x_all[order],
                "y": y_all[order],
                "dist": dist_all[order],
                "rel_dist": rel_dist_all[order],
                "lap": lap_numbers[order],
                "tyre": tyre_compounds[order],
                "speed": speed_all[order],
                "gear": gear_all[order],
                "drs": drs_all[order],
            },
            "t_min": t_all.min(),
            "t_max": t_all.max(),
            "max_lap": driver_max_lap
        }
        
    except Exception as e:
        logger.warning(f"Error processing driver {driver_code}: {e}")
        return None


@st.cache_data(ttl=86400, show_spinner="Loading race data...")
def get_race_telemetry_frames(year: int, round_number: int, session_type: str = 'R', 
                               force_refresh: bool = False, full_mode: bool = False) -> Dict:
    """
    Get processed race data as frames for visualization.
    
    Args:
        year: Season year
        round_number: Race round number
        session_type: 'R' for Race, 'Q' for Qualifying, 'S' for Sprint
        force_refresh: Force refresh of cached data
        full_mode: If True, load full telemetry (SLOWER ~30s but accurate positions)
                   If False, use FAST mode (instant but approximate positions)
        
    Returns:
        Dict with keys: frames, driver_colors, track_statuses, total_laps, track_coords
    """
    enable_cache()
    
    # 1. Check cached computed data (Local Pickle - Legacy/Fast)
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    
    # Check Supabase Cache FIRST (The new "Instant" way)
    # We only check Supabase if full_mode is True (which is now default/only mode)
    # But even if full_mode is False, checking Supabase is fast.
    # Actually, we want to deprecate "Fast" mode eventually.
    
    try:
        from utils.db import get_supabase_client
        import zlib
        import json
        
        supabase = get_supabase_client()
        # Look for cache entry
        # Ideally we'd validte against updated_at, but for past races it's static
        res = supabase.table('race_telemetry_cache').select('frames_data, driver_colors, track_coords, track_statuses, circuit_rotation, event_name')\
            .eq('season_year', year).eq('round', round_number).eq('session_type', session_type).execute()
        
        if res.data:
            cached = res.data[0]
            logger.info(f"⚡ Loading from Supabase Cache: {year} R{round_number}")
            
            # Decompress frames
            frames_compressed = bytes.fromhex(cached['frames_data'][2:]) if cached['frames_data'].startswith('\\x') else cached['frames_data']
            # Supabase returns bytea as hex string typically prefixed with \x, but python client might handle it.
            # Actually, standard postgrest python client returns it as string or bytes depending on config.
            # Let's assume standard handling or handle string \x manually
            
            if isinstance(cached['frames_data'], str) and cached['frames_data'].startswith('\\x'):
                 frames_bytes = bytes.fromhex(cached['frames_data'][2:])
            elif isinstance(cached['frames_data'], str):
                 # Try latin1 fallback or assume it's raw
                 try:
                     frames_bytes = bytes.fromhex(cached['frames_data'])
                 except:
                     frames_bytes = cached['frames_data'].encode('latin1') # Binary string
            else:
                 frames_bytes = cached['frames_data']
            
            frames = json.loads(zlib.decompress(frames_bytes))
            
            return {
                "frames": frames,
                "driver_colors": cached['driver_colors'] or {},
                "track_statuses": cached['track_statuses'] or [],
                "total_laps": cached.get('total_laps', 0) or frames[-1]['lap'],
                "track_coords": cached['track_coords'] or {"x": [], "y": []},
                "circuit_rotation": cached.get('circuit_rotation', 0.0),
                "event_name": cached.get('event_name', f"{year} Round {round_number}"),
                "_from_cache": True
            }
    except Exception as e:
        logger.debug(f"Supabase cache miss/error: {e}")

    # 2. Local File Cache (Fallback)
    mode_suffix = "full" if full_mode else "fast"
    cache_file = f"{CACHE_DIR}/{year}_R{round_number}_{session_type}_{mode_suffix}.pkl"
    
    if os.path.exists(cache_file) and not force_refresh:
        try:
            with open(cache_file, "rb") as f:
                logger.info(f"⚡ Loading from Local Pickle: {cache_file}")
                data = pickle.load(f)
                data['_from_cache'] = True
                return data
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
    
    # Load session - minimize data loaded based on mode
    session = fastf1.get_session(year, round_number, session_type)
    
    # FAST mode: only load laps, no telemetry
    # FULL mode: load telemetry for accurate positions
    session.load(
        telemetry=full_mode,  # Only load telemetry if full_mode
        weather=False,        # Skip weather (not essential)
        laps=True,           # Always need laps
        messages=False       # Skip messages
    )
    
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
    
    max_lap_number = int(laps['LapNumber'].max())
    
    if full_mode:
        # FULL MODE: Load complete telemetry and resample
        frames = build_race_frames(session, drivers, driver_codes, max_lap_number)
    else:
        # FAST MODE: Use lap-by-lap snapshots (original approach)
        frames = _build_frames_fast_mode(session, drivers, driver_codes, laps, max_lap_number)
    
    # Get track coordinates from fastest lap
    track_x, track_y = [], []
    try:
        fastest = laps.pick_fastest()
        if fastest is not None:
            tel = fastest.get_telemetry()
            if tel is not None and not tel.empty and 'X' in tel.columns:
                track_x = tel['X'].iloc[::5].tolist()  # Sample every 5th point
                track_y = tel['Y'].iloc[::5].tolist()
    except Exception as e:
        logger.warning(f"Could not get track coordinates: {e}")
    
    # Get track status
    track_statuses = _get_track_statuses(session)
    
    # Build result
    result = {
        "frames": frames,
        "driver_colors": get_driver_colors(session),
        "track_statuses": track_statuses,
        "total_laps": max_lap_number,
        "track_coords": {"x": track_x, "y": track_y},
        "circuit_rotation": get_circuit_rotation(session),
        "event_name": session.event['EventName'],
    }
    
    # Save to cache
    try:
        with open(cache_file, "wb") as f:
            pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(f"Saved telemetry cache: {cache_file}")
    except Exception as e:
        logger.error(f"Cache save failed: {e}")
    
    return result


def build_race_frames(session, drivers, driver_codes, max_lap_number) -> List[Dict]:
    """Build frames using full telemetry data - accurate driver positions."""
    
    logger.info(f"Processing {len(drivers)} drivers with full telemetry...")
    
    # Process drivers (can use parallel processing for speed)
    driver_data = {}
    global_t_min = None
    global_t_max = None
    
    for driver_no in drivers:
        driver_code = driver_codes.get(driver_no, f"#{driver_no}")
        result = _process_single_driver((driver_no, session, driver_code))
        
        if result is None:
            continue
        
        driver_data[result["code"]] = result["data"]
        
        t_min = result["t_min"]
        t_max = result["t_max"]
        
        global_t_min = t_min if global_t_min is None else min(global_t_min, t_min)
        global_t_max = t_max if global_t_max is None else max(global_t_max, t_max)
    
    if global_t_min is None or global_t_max is None:
        raise ValueError("No valid telemetry data found for any driver")
    
    # Create timeline (start from zero)
    timeline = np.arange(global_t_min, global_t_max, DT) - global_t_min
    
    # Resample each driver's telemetry onto the common timeline
    resampled_data = {}
    
    for code, data in driver_data.items():
        t = data["t"] - global_t_min  # Shift to start at 0
        
        # Sort by time
        order = np.argsort(t)
        t_sorted = t[order]
        
        # Resample all arrays
        resampled_data[code] = {
            "x": np.interp(timeline, t_sorted, data["x"][order]),
            "y": np.interp(timeline, t_sorted, data["y"][order]),
            "dist": np.interp(timeline, t_sorted, data["dist"][order]),
            "rel_dist": np.interp(timeline, t_sorted, data["rel_dist"][order]),
            "lap": np.round(np.interp(timeline, t_sorted, data["lap"][order])).astype(int),
            "tyre": np.round(np.interp(timeline, t_sorted, data["tyre"][order])).astype(int),
            "speed": np.interp(timeline, t_sorted, data["speed"][order]),
            "gear": np.round(np.interp(timeline, t_sorted, data["gear"][order])).astype(int),
            "drs": np.round(np.interp(timeline, t_sorted, data["drs"][order])).astype(int),
        }
    
    # Build frames
    frames = []
    driver_codes_list = list(resampled_data.keys())
    
    for i in range(len(timeline)):
        t = timeline[i]
        snapshot = []
        
        for code in driver_codes_list:
            d = resampled_data[code]
            snapshot.append({
                "code": code,
                "dist": float(d["dist"][i]),
                "x": float(d["x"][i]),
                "y": float(d["y"][i]),
                "lap": int(d["lap"][i]),
                "rel_dist": float(d["rel_dist"][i]),
                "tyre": int(d["tyre"][i]),
                "speed": float(d["speed"][i]),
                "gear": int(d["gear"][i]),
                "drs": int(d["drs"][i]),
            })
        
        if not snapshot:
            continue
        
        # Sort by race distance to get positions (leader = largest distance)
        snapshot.sort(key=lambda r: r["dist"], reverse=True)
        
        leader_lap = snapshot[0]["lap"] if snapshot else 1
        
        # Build frame data
        frame_data = {}
        for idx, car in enumerate(snapshot):
            code = car["code"]
            position = idx + 1
            
            frame_data[code] = {
                "x": round(car["x"], 1),
                "y": round(car["y"], 1),
                "dist": round(car["dist"], 1),
                "lap": car["lap"],
                "rel_dist": round(car["rel_dist"], 4),
                "tyre": car["tyre"],
                "position": position,
                "speed": round(car["speed"], 1),
                "gear": car["gear"],
                "drs": car["drs"],
            }
        
        frames.append({
            "t": round(t, 2),
            "lap": leader_lap,
            "drivers": frame_data,
        })
    
    logger.info(f"Built {len(frames)} frames from full telemetry")
    return frames


def _build_frames_fast_mode(session, drivers, driver_codes, laps, max_lap_number) -> List[Dict]:
    """Build frames using lap-by-lap position data only - fast but approximate."""
    
    logger.info("Building frames in fast mode (lap snapshots)...")
    
    # Get track coordinates for positioning
    track_x, track_y = [], []
    try:
        fastest = laps.pick_fastest()
        if fastest is not None:
            tel = fastest.get_telemetry()
            if tel is not None and not tel.empty and 'X' in tel.columns:
                track_x = tel['X'].iloc[::10].tolist()
                track_y = tel['Y'].iloc[::10].tolist()
    except:
        pass
    
    num_track_points = len(track_x)
    
    # Build one frame per lap
    frames = []
    
    for lap_num in range(1, max_lap_number + 1):
        lap_data = laps[laps['LapNumber'] == lap_num].copy()
        
        if lap_data.empty:
            continue
        
        # Sort by position
        lap_data = lap_data.sort_values('Position')
        
        frame_drivers = {}
        for _, lap in lap_data.iterrows():
            try:
                driver_abbr = lap.get('Driver') or driver_codes.get(lap.get('DriverNumber'))
                if not driver_abbr:
                    continue
                
                position = int(lap['Position']) if pd.notna(lap['Position']) else 20
                
                # Calculate driver position on track based on race position
                if num_track_points > 0:
                    spacing = 1.0 / 20
                    track_progress = 0.75 - (position - 1) * spacing
                    track_progress = max(0.05, min(0.95, track_progress))
                    
                    track_idx = int(track_progress * num_track_points) % num_track_points
                    driver_x = track_x[track_idx]
                    driver_y = track_y[track_idx]
                else:
                    driver_x = 0
                    driver_y = 0
                    track_progress = 0
                
                # Get tyre compound
                compound = str(lap.get('Compound', 'UNKNOWN'))
                tyre_int = get_tyre_compound_int(compound)
                
                # Get lap time
                lap_time = lap.get('LapTime')
                if pd.notna(lap_time):
                    lap_time_secs = lap_time.total_seconds()
                else:
                    lap_time_secs = None
                
                frame_drivers[driver_abbr] = {
                    'position': position,
                    'lap': int(lap_num),
                    'tyre': tyre_int,
                    'lap_time': lap_time_secs,
                    'x': driver_x,
                    'y': driver_y,
                    'speed': 0,
                    'gear': 0,
                    'drs': 0,
                    'dist': track_progress * 100 if num_track_points > 0 else 0,
                }
            except Exception as e:
                continue
        
        # Approximate time (90 seconds per lap average)
        approx_time = lap_num * 90.0
        
        frames.append({
            't': approx_time,
            'lap': lap_num,
            'drivers': frame_drivers,
        })
    
    logger.info(f"Built {len(frames)} frames from lap data")
    return frames


def _get_track_statuses(session) -> List[Dict]:
    """Extract track status changes from session."""
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
                except Exception:
                    continue
            
            # Set end times
            for i in range(len(track_statuses) - 1):
                track_statuses[i]['end_time'] = track_statuses[i + 1]['start_time']
    except Exception:
        pass
    
    return track_statuses


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
