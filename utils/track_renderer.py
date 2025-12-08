"""
Track Renderer Utilities

Provides Plotly-based track visualization for race replays.
Renders circuit layout with driver positions, team colors, and track status.
"""

import numpy as np
import plotly.graph_objects as go
from typing import Dict, List, Tuple, Optional
import math


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color string."""
    return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'


def build_track_geometry(track_x: List[float], track_y: List[float], 
                         rotation: float = 0.0) -> Tuple[List[float], List[float]]:
    """
    Build track geometry with optional rotation.
    
    Args:
        track_x: List of X coordinates
        track_y: List of Y coordinates
        rotation: Rotation angle in degrees
    
    Returns:
        Tuple of (rotated_x, rotated_y) lists
    """
    if not track_x or not track_y:
        return [], []
    
    x = np.array(track_x)
    y = np.array(track_y)
    
    if rotation != 0:
        # Rotate around center
        cx, cy = np.mean(x), np.mean(y)
        rad = np.deg2rad(rotation)
        cos_r, sin_r = np.cos(rad), np.sin(rad)
        
        tx, ty = x - cx, y - cy
        x = tx * cos_r - ty * sin_r + cx
        y = tx * sin_r + ty * cos_r + cy
    
    return x.tolist(), y.tolist()


def get_track_status_style(status: str) -> Dict:
    """Get styling for track based on status."""
    styles = {
        "1": {"color": "#444444", "width": 8},  # Green - normal
        "2": {"color": "#FFD700", "width": 10},  # Yellow flag
        "4": {"color": "#FF8C00", "width": 10},  # Safety Car
        "5": {"color": "#FF0000", "width": 12},  # Red flag
        "6": {"color": "#FF4500", "width": 10},  # VSC
        "7": {"color": "#FF6347", "width": 10},  # VSC Ending
    }
    return styles.get(status, styles["1"])


def create_track_figure(track_coords: Dict, rotation: float = 0.0,
                       height: int = 500, track_status: str = "1") -> go.Figure:
    """
    Create base track figure.
    
    Args:
        track_coords: Dict with 'x' and 'y' keys containing coordinate lists
        rotation: Circuit rotation angle
        height: Figure height in pixels
        track_status: Current track status code
    
    Returns:
        Plotly Figure object
    """
    x, y = build_track_geometry(track_coords.get("x", []), 
                                 track_coords.get("y", []), 
                                 rotation)
    
    style = get_track_status_style(track_status)
    
    fig = go.Figure()
    
    # Add track outline
    if x and y:
        # Track asphalt (thick gray line)
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode='lines',
            line=dict(color=style["color"], width=style["width"]),
            name='Track',
            hoverinfo='skip',
            showlegend=False
        ))
        
        # Track center line (thin white dashed)
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode='lines',
            line=dict(color='#666666', width=1, dash='dot'),
            name='Center',
            hoverinfo='skip',
            showlegend=False
        ))
    
    # Configure layout
    fig.update_layout(
        height=height,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            scaleanchor="y",
            scaleratio=1,
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
        ),
        showlegend=False,
        dragmode=False,
    )
    
    return fig


def add_driver_markers(fig: go.Figure, frame_data: Dict, 
                       driver_colors: Dict[str, Tuple[int, int, int]],
                       track_coords: Dict, rotation: float = 0.0,
                       selected_driver: Optional[str] = None) -> go.Figure:
    """
    Add driver position markers to the track figure.
    
    Args:
        fig: Existing Plotly Figure
        frame_data: Frame data with driver positions
        driver_colors: Dict mapping driver codes to RGB colors
        track_coords: Track coordinates for rotation
        rotation: Circuit rotation angle
        selected_driver: Highlighted driver code
    
    Returns:
        Updated Figure
    """
    if not frame_data or "drivers" not in frame_data:
        return fig
    
    drivers = frame_data["drivers"]
    
    # Calculate rotation parameters if needed
    if rotation != 0:
        track_x = np.array(track_coords.get("x", [0]))
        track_y = np.array(track_coords.get("y", [0]))
        cx, cy = np.mean(track_x), np.mean(track_y)
        rad = np.deg2rad(rotation)
        cos_r, sin_r = np.cos(rad), np.sin(rad)
    else:
        cx, cy, cos_r, sin_r = 0, 0, 1, 0
    
    # Sort by position for layering (leader on top)
    sorted_drivers = sorted(drivers.items(), 
                           key=lambda x: x[1].get("position", 99))
    
    for code, data in reversed(sorted_drivers):  # Draw from back to front
        x, y = data.get("x", 0), data.get("y", 0)
        
        # Apply rotation
        if rotation != 0:
            tx, ty = x - cx, y - cy
            x = tx * cos_r - ty * sin_r + cx
            y = tx * sin_r + ty * cos_r + cy
        
        color = driver_colors.get(code, (128, 128, 128))
        hex_color = rgb_to_hex(color)
        
        position = data.get("position", "?")
        speed = data.get("speed", 0)
        lap = data.get("lap", 0)
        
        # Determine marker size
        marker_size = 20 if code == selected_driver else 14
        border_width = 3 if code == selected_driver else 1
        border_color = "#FFFFFF" if code == selected_driver else "#000000"
        
        fig.add_trace(go.Scatter(
            x=[x], y=[y],
            mode='markers+text',
            marker=dict(
                color=hex_color,
                size=marker_size,
                line=dict(color=border_color, width=border_width),
                symbol='circle',
            ),
            text=code,
            textposition='top center',
            textfont=dict(
                color='white' if code == selected_driver else '#CCCCCC',
                size=10 if code == selected_driver else 8,
                family='Arial Black',
            ),
            name=code,
            hovertemplate=(
                f"<b>{code}</b><br>"
                f"Position: P{position}<br>"
                f"Speed: {speed:.0f} km/h<br>"
                f"Lap: {lap}<br>"
                "<extra></extra>"
            ),
            showlegend=False
        ))
    
    return fig


def render_track_map(track_coords: Dict, frame_data: Dict,
                     driver_colors: Dict[str, Tuple[int, int, int]],
                     rotation: float = 0.0, height: int = 500,
                     selected_driver: Optional[str] = None,
                     track_status: str = "1") -> go.Figure:
    """
    Render complete track map with driver positions.
    
    Args:
        track_coords: Dict with 'x' and 'y' coordinate lists
        frame_data: Current frame data with driver positions
        driver_colors: Driver to color mapping
        rotation: Circuit rotation angle
        height: Figure height
        selected_driver: Highlighted driver
        track_status: Current track status code
    
    Returns:
        Complete Plotly Figure
    """
    fig = create_track_figure(track_coords, rotation, height, track_status)
    fig = add_driver_markers(fig, frame_data, driver_colors, 
                            track_coords, rotation, selected_driver)
    return fig


def create_position_chart(frames: List[Dict], selected_drivers: List[str] = None,
                          driver_colors: Dict[str, Tuple[int, int, int]] = None,
                          height: int = 300) -> go.Figure:
    """
    Create a position history chart.
    
    Args:
        frames: List of frame data
        selected_drivers: Drivers to show (None = top 10)
        driver_colors: Color mapping
        height: Chart height
    
    Returns:
        Plotly Figure
    """
    fig = go.Figure()
    
    if not frames:
        return fig
    
    # Collect position data
    driver_positions = {}
    times = []
    
    for frame in frames:
        t = frame.get("t", 0)
        times.append(t / 60)  # Convert to minutes
        
        for code, data in frame.get("drivers", {}).items():
            if code not in driver_positions:
                driver_positions[code] = []
            driver_positions[code].append(data.get("position", 20))
    
    # Filter to selected drivers or top 10
    if selected_drivers:
        drivers_to_show = selected_drivers
    else:
        # Get drivers who were ever in top 10
        all_positions = {}
        for code, positions in driver_positions.items():
            all_positions[code] = min(positions)
        drivers_to_show = sorted(all_positions.keys(), 
                                key=lambda x: all_positions[x])[:10]
    
    # Add traces
    for code in drivers_to_show:
        if code not in driver_positions:
            continue
        
        color = driver_colors.get(code, (128, 128, 128)) if driver_colors else (128, 128, 128)
        hex_color = rgb_to_hex(color)
        
        fig.add_trace(go.Scatter(
            x=times[:len(driver_positions[code])],
            y=driver_positions[code],
            mode='lines',
            name=code,
            line=dict(color=hex_color, width=2),
            hovertemplate=f"{code}: P%{{y}}<extra></extra>"
        ))
    
    fig.update_layout(
        height=height,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(11,12,16,0.8)',
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(
            title="Time (minutes)",
            gridcolor='rgba(255,255,255,0.1)',
            showgrid=True,
        ),
        yaxis=dict(
            title="Position",
            gridcolor='rgba(255,255,255,0.1)',
            showgrid=True,
            autorange="reversed",  # P1 at top
            dtick=1,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10),
        ),
        font=dict(color='white'),
    )
    
    return fig


def create_lap_time_chart(frames: List[Dict], selected_drivers: List[str],
                          driver_colors: Dict[str, Tuple[int, int, int]] = None,
                          height: int = 300) -> go.Figure:
    """
    Create a lap time progression chart.
    
    This is a simplified version - actual lap times would need to be 
    calculated from the frame data or fetched separately.
    """
    fig = go.Figure()
    
    # Placeholder - would need actual lap time data
    fig.update_layout(
        height=height,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(11,12,16,0.8)',
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(title="Lap", gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(title="Lap Time (s)", gridcolor='rgba(255,255,255,0.1)'),
        font=dict(color='white'),
    )
    
    return fig


def create_speed_trace(frames: List[Dict], driver_code: str,
                       driver_colors: Dict[str, Tuple[int, int, int]] = None,
                       height: int = 200) -> go.Figure:
    """
    Create a speed trace for a specific driver.
    """
    fig = go.Figure()
    
    if not frames or not driver_code:
        return fig
    
    times = []
    speeds = []
    
    for frame in frames:
        drivers = frame.get("drivers", {})
        if driver_code in drivers:
            times.append(frame.get("t", 0) / 60)
            speeds.append(drivers[driver_code].get("speed", 0))
    
    color = driver_colors.get(driver_code, (128, 128, 128)) if driver_colors else (128, 128, 128)
    hex_color = rgb_to_hex(color)
    
    fig.add_trace(go.Scatter(
        x=times,
        y=speeds,
        mode='lines',
        name=driver_code,
        line=dict(color=hex_color, width=2),
        fill='tozeroy',
        fillcolor=f'rgba{color + (0.2,)}',
    ))
    
    fig.update_layout(
        height=height,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(11,12,16,0.8)',
        margin=dict(l=40, r=20, t=10, b=40),
        xaxis=dict(title="Time (min)", gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(title="Speed (km/h)", gridcolor='rgba(255,255,255,0.1)', range=[0, 400]),
        showlegend=False,
        font=dict(color='white'),
    )
    
    return fig
