import streamlit as st

# Page Config - MUST be first Streamlit command
st.set_page_config(page_title="Race Analytics", page_icon="📈", layout="wide")

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import fastf1
import fastf1.plotting
from datetime import datetime
from utils.db import get_supabase_client
from app.components.sidebar import render_sidebar
from utils.logger import get_logger
from utils.time_simulation import get_current_time, get_current_year

logger = get_logger(__name__)

# Inject Custom CSS
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except:
        pass

local_css("app/assets/custom.css")

# Render Sidebar
render_sidebar()


supabase = get_supabase_client()

@st.cache_data(ttl=3600)
def get_available_years(_simulated_time=None):
    """Get available years from FastF1 (2018+)"""
    current_year = get_current_year()
    # Assume we want to show up to the current simulated year
    return list(range(current_year, 2017, -1))  # 2018 to current year

@st.cache_data(ttl=3600)
def get_schedule_for_year(year, _simulated_time=None):
    """Get race schedule for a given year"""
    try:
        schedule = fastf1.get_event_schedule(year)
        # Filter to completed events and exclude testing
        schedule = schedule[schedule['RoundNumber'] > 0]
        schedule['EventDate'] = pd.to_datetime(schedule['EventDate'], utc=True)
        completed = schedule[schedule['EventDate'] < get_current_time()]
        return completed
    except Exception as e:
        logger.error(f"Failed to fetch schedule for {year}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_available_sessions(year, round_num):
    """Get available session types for a given event"""
    try:
        event = fastf1.get_event(year, round_num)
        sessions = []
        for i in range(1, 6):
            session_name = event.get(f'Session{i}')
            if session_name and pd.notna(session_name):
                sessions.append(session_name)
        return sessions
    except Exception as e:
        logger.warning(f"Failed to get sessions: {e}")
        return ['Race']  # Default fallback

@st.cache_data
def load_fastf1_session(year, race_round, session_type='R'):
    """Load FastF1 session with specified type"""
    try:
        session = fastf1.get_session(year, race_round, session_type)
        session.load(telemetry=True, weather=False, messages=False)
        return session
    except Exception as e:
        logger.warning(f"Failed to load FastF1 session: {e}")
        return None

# --- HEADER ---
st.title("📈 Race Analytics")

# --- CASCADING SELECTORS ---
col1, col2, col3 = st.columns(3)

with col1:
    # Pass current time to force cache invalidation on time change
    current_sim_time = get_current_time()
    years = get_available_years(_simulated_time=current_sim_time)
    selected_year = st.selectbox("🗓️ Season", years)

with col2:
    schedule = get_schedule_for_year(selected_year, _simulated_time=current_sim_time)
    if schedule.empty:
        st.warning(f"No completed races in {selected_year}")
        st.stop()
    
    # Create race options
    race_options = {f"R{row['RoundNumber']}: {row['EventName']}": row['RoundNumber'] 
                   for _, row in schedule.iterrows()}
    selected_race_label = st.selectbox("🏁 Race Weekend", list(race_options.keys()))
    selected_round = race_options[selected_race_label]

with col3:
    sessions = get_available_sessions(selected_year, selected_round)
    # Map display names to FastF1 codes
    session_code_map = {
        'Practice 1': 'FP1', 'Practice 2': 'FP2', 'Practice 3': 'FP3',
        'Qualifying': 'Q', 'Race': 'R', 'Sprint': 'S', 'Sprint Qualifying': 'SQ',
        'Sprint Shootout': 'SS'
    }
    selected_session = st.selectbox("📋 Session", sessions)
    session_code = session_code_map.get(selected_session, 'R')

st.markdown("---")

# Load session from FastF1 (works even if DB is empty)
with st.spinner(f"Loading {selected_session} data..."):
    session = load_fastf1_session(selected_year, selected_round, session_code)

if session is None or session.laps.empty:
    st.error("Failed to load session data. Please try a different selection.")
    st.stop()

# Build laps DataFrame from FastF1
laps_df = session.laps.copy()
laps_df['driver_code'] = laps_df['Driver']

if laps_df.empty:
    st.info("No lap data available for this session.")
else:
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📈 Race Overview", "🏎️ Circuit Analysis", "⚔️ Competitor Analysis"])
    
    with tab1:
        # 1. Lap Time Distribution
        st.subheader("Lap Time Distribution")
        
        # Use LapTime from FastF1 directly
        if 'LapTime' in laps_df.columns:
            laps_df['lap_time_s'] = laps_df['LapTime'].dt.total_seconds()
        elif 'lap_time_ms' in laps_df.columns:
            laps_df['lap_time_s'] = laps_df['lap_time_ms'] / 1000.0
        else:
            st.warning("No lap time data available for this session.")
            st.stop()
        
        laps_df = laps_df.dropna(subset=['lap_time_s'])
        
        # Filter outliers (e.g., pit laps, SC)
        q95 = laps_df['lap_time_s'].quantile(0.95)
        clean_laps = laps_df[laps_df['lap_time_s'] < q95]

        # Check available columns for safe plotting
        driver_col = 'Driver' if 'Driver' in clean_laps.columns else 'driver_code'
        color_col = 'Team' if 'Team' in clean_laps.columns else None
        
        # Build dynamic color map using FastF1
        team_color_map = {}
        if color_col:
            unique_teams = clean_laps[color_col].unique()
            for team in unique_teams:
                try:
                    # fastf1.plotting.team_color returns hex (e.g. #ff0000)
                    # We use a fallback just in case
                    c = fastf1.plotting.team_color(team)
                    team_color_map[team] = c
                except:
                    # Fallback to hardcoded map if FastF1 fails
                    backup_colors = {
                        'Red Bull Racing': '#0600EF', 'Red Bull': '#0600EF',
                        'Mercedes': '#00D2BE',
                        'Ferrari': '#DC0000',
                        'McLaren': '#FF8700',
                        'Aston Martin': '#006F62',
                        'Alpine': '#0090FF',
                        'Williams': '#005AFF',
                        'RB': '#2B4562', 'AlphaTauri': '#2B4562', 'Toro Rosso': '#469BFF',
                        'Haas F1 Team': '#FFFFFF', 'Haas': '#FFFFFF',
                        'Kick Sauber': '#52E252', 'Sauber': '#52E252', 'Alfa Romeo': '#900000',
                        'Racing Point': '#F596C8', 'Force India': '#F596C8',
                        'Renault': '#FFF500'
                    }
                    team_color_map[team] = backup_colors.get(team, '#555555')

        # Box plot for lap time distribution
        if color_col:
            fig_box = px.box(clean_laps, x=driver_col, y='lap_time_s', color=color_col, 
                             title="Lap Time Distribution by Driver",
                             labels={'lap_time_s': 'Lap Time (s)', driver_col: 'Driver'},
                             color_discrete_map=team_color_map)
        else:
            fig_box = px.box(clean_laps, x=driver_col, y='lap_time_s', 
                             title="Lap Time Distribution by Driver",
                             labels={'lap_time_s': 'Lap Time (s)', driver_col: 'Driver'})
        st.plotly_chart(fig_box,  width="stretch")

        # 2. Tyre Strategy
        st.subheader("Tyre Strategy")
        compound_col = 'Compound' if 'Compound' in clean_laps.columns else 'compound'
        lap_num_col = 'LapNumber' if 'LapNumber' in clean_laps.columns else 'lap_number'
        
        if compound_col in clean_laps.columns:
            fig_tyre = px.scatter(clean_laps, x=lap_num_col, y=driver_col, color=compound_col, symbol=compound_col,
                                  title="Tyre Compound Usage per Lap",
                                  labels={lap_num_col: 'Lap Number', driver_col: 'Driver'})
            fig_tyre.update_traces(marker=dict(size=8))
            st.plotly_chart(fig_tyre,  width="stretch")
        else:
            st.info("Tyre compound data not available for this session.")

    with tab2:
        st.subheader("Interactive Circuit Analysis")
        
        # Session already loaded above
        if session:
            # Select Visualization Type
            viz_type = st.radio("Select Visualization", ["3D Speed Map", "Gear Shift Map"], horizontal=True)
            
            lap = session.laps.pick_fastest()
            if lap is None or lap.empty:
                st.warning("No valid fastest lap found for this session.")
            else:
                tel = lap.get_telemetry()
                
                # Add Z-axis (Elevation if available, otherwise use 0)
                if 'Z' not in tel.columns:
                    tel['Z'] = 0
                
                if viz_type == "3D Speed Map":
                    fig_3d = px.scatter_3d(tel, x='X', y='Y', z='Z', color='Speed',
                                          title=f"{session.event.EventName} - 3D Speed Map",
                                          color_continuous_scale='Plasma',
                                          opacity=0.8)
                    fig_3d.update_traces(marker=dict(size=3))
                    fig_3d.update_layout(scene=dict(aspectmode='data', xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False)),
                                         margin=dict(l=0, r=0, b=0, t=30),
                                         paper_bgcolor='rgba(0,0,0,0)',
                                         plot_bgcolor='rgba(0,0,0,0)',
                                         font=dict(color='white'))
                    st.plotly_chart(fig_3d, width="stretch")
                    
                else:  # Gear Shift Map
                    fig_3d = px.scatter_3d(tel, x='X', y='Y', z='Z', color='nGear',
                                          title=f"{session.event.EventName} - 3D Gear Shift Map",
                                          color_continuous_scale='Viridis',
                                          opacity=0.8)
                    fig_3d.update_traces(marker=dict(size=3))
                    fig_3d.update_layout(scene=dict(aspectmode='data', xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False)),
                                         margin=dict(l=0, r=0, b=0, t=30),
                                         paper_bgcolor='rgba(0,0,0,0)',
                                         plot_bgcolor='rgba(0,0,0,0)',
                                         font=dict(color='white'))
                    st.plotly_chart(fig_3d, width="stretch")
        else:
            st.error("Failed to load FastF1 session data.")

    with tab3:
        st.subheader("Competitor Analysis")
        
        if session:
            drivers = sorted(session.drivers)
            drivers = [d for d in drivers if d in session.results['Abbreviation'].values]
            
            if len(drivers) < 2:
                st.warning("Not enough drivers with valid data for comparison.")
            else:
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    driver1 = st.selectbox("Driver 1", drivers, index=0)
                with col_d2:
                    driver2 = st.selectbox("Driver 2", drivers, index=min(1, len(drivers)-1))
                    
                if driver1 and driver2 and driver1 != driver2:
                    laps1 = session.laps.pick_driver(driver1).pick_fastest()
                    laps2 = session.laps.pick_driver(driver2).pick_fastest()
                    
                    if laps1 is not None and laps2 is not None and not laps1.empty and not laps2.empty:
                        tel1 = laps1.get_telemetry().add_distance()
                        tel2 = laps2.get_telemetry().add_distance()
                        
                        # Calculate Delta
                        delta_time, ref_tel, compare_tel = fastf1.utils.delta_time(laps1, laps2)
                        
                        # Plot Speed Trace
                        fig_comp = go.Figure()
                        fig_comp.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Speed'], mode='lines', name=driver1, line=dict(color='cyan')))
                        fig_comp.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Speed'], mode='lines', name=driver2, line=dict(color='magenta')))
                        
                        fig_comp.update_layout(title=f"Speed Comparison: {driver1} vs {driver2}", 
                                               xaxis_title="Distance (m)", yaxis_title="Speed (km/h)")
                        st.plotly_chart(fig_comp,  width="stretch")
                        
                        # Plot Delta
                        fig_delta = go.Figure()
                        fig_delta.add_trace(go.Scatter(x=ref_tel['Distance'], y=delta_time, mode='lines', name=f"Delta ({driver2} to {driver1})", line=dict(color='white')))
                        fig_delta.add_hline(y=0, line_dash="dash", line_color="gray")
                        
                        fig_delta.update_layout(title=f"Time Delta: {driver2} relative to {driver1}", 
                                                xaxis_title="Distance (m)", yaxis_title="Delta (s)")
                        st.plotly_chart(fig_delta,  width="stretch")
                        
                    else:
                        st.warning("One or both drivers do not have a valid fastest lap.")
                elif driver1 == driver2:
                    st.info("Please select two different drivers for comparison.")
        else:
            st.error("Failed to load FastF1 session data.")

