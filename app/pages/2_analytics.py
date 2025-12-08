import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import fastf1
import fastf1
from utils.db import get_supabase_client
from app.components.sidebar import render_sidebar

# Inject Custom CSS
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("app/assets/custom.css")

# Render Sidebar
render_sidebar()

st.set_page_config(page_title="Race Analytics", page_icon="📈", layout="wide")

supabase = get_supabase_client()

@st.cache_data
def get_races():
    res = supabase.table('races').select('id, name, season_year, round').order('season_year', desc=True).order('round', desc=True).execute()
    return pd.DataFrame(res.data)

# @st.cache_data
def get_race_data(race_id):
    # Fetch laps
    print(f"Fetching laps for race_id: {race_id}")
    laps_res = supabase.table('laps').select('*').eq('race_id', race_id).execute()
    print(f"Laps fetched: {len(laps_res.data)}")
    laps = pd.DataFrame(laps_res.data)
    
    # Fetch drivers
    drivers_res = supabase.table('drivers').select('*').execute()
    drivers = pd.DataFrame(drivers_res.data)
    
    if not laps.empty and not drivers.empty:
        # Merge
        laps = laps.merge(drivers, left_on='driver_id', right_on='id', how='left')
    return laps

@st.cache_data
def load_fastf1_session(year, race_round):
    try:
        session = fastf1.get_session(year, race_round, 'R')
        session.load(telemetry=True, weather=False, messages=False)
        return session
    except Exception as e:
        return None

races_df = get_races()

if races_df.empty:
    st.warning("No race data found in database. Please run ingestion.")
else:
    # Race Selection
    # Race Selection
    years = sorted(races_df['season_year'].unique(), reverse=True)
    selected_year = st.selectbox("Select Season", years)
    
    races_in_year = races_df[races_df['season_year'] == selected_year].sort_values('round', ascending=False)
    
    # Create a mapping for the selectbox
    race_map = {f"R{row['round']} - {row['name']}": row for _, row in races_in_year.iterrows()}
    
    selected_race_label = st.selectbox("Select Race", list(race_map.keys()))
    selected_row = race_map[selected_race_label]
    
    selected_race_id = selected_row['id']
    selected_round = selected_row['round']

    laps_df = get_race_data(selected_race_id)

    if laps_df.empty:
        st.info("No lap data available for this race.")
    else:
        # Tabs
        tab1, tab2, tab3 = st.tabs(["📈 Race Overview", "🏎️ Circuit Analysis", "⚔️ Competitor Analysis"])
        
        with tab1:
            # 1. Lap Time Distribution
            st.subheader("Lap Time Distribution")
            # Convert interval string to seconds for plotting
            def parse_time(t):
                try:
                    return pd.to_timedelta(t).total_seconds()
                except:
                    return None
            
            laps_df['lap_time_s'] = laps_df['lap_time'].apply(parse_time)
            laps_df = laps_df.dropna(subset=['lap_time_s'])
            
            # Filter outliers (e.g., pit laps, SC)
            q95 = laps_df['lap_time_s'].quantile(0.95)
            clean_laps = laps_df[laps_df['lap_time_s'] < q95]

            # Check available columns for safe plotting
            driver_col = 'code' if 'code' in clean_laps.columns else 'driver_id'
            color_col = 'team_name' if 'team_name' in clean_laps.columns else (
                'team' if 'team' in clean_laps.columns else None
            )
            
            # Box plot for lap time distribution
            if color_col:
                fig_box = px.box(clean_laps, x=driver_col, y='lap_time_s', color=color_col, 
                                 title="Lap Time Distribution by Driver",
                                 labels={'lap_time_s': 'Lap Time (s)', driver_col: 'Driver'})
            else:
                fig_box = px.box(clean_laps, x=driver_col, y='lap_time_s', 
                                 title="Lap Time Distribution by Driver",
                                 labels={'lap_time_s': 'Lap Time (s)', driver_col: 'Driver'})
            st.plotly_chart(fig_box, width='stretch')

            # 2. Tyre Strategy
            st.subheader("Tyre Strategy")
            compound_col = 'compound' if 'compound' in clean_laps.columns else 'tyre_compound'
            lap_num_col = 'lap_number' if 'lap_number' in clean_laps.columns else 'LapNumber'
            
            if compound_col in clean_laps.columns:
                fig_tyre = px.scatter(clean_laps, x=lap_num_col, y=driver_col, color=compound_col, symbol=compound_col,
                                      title="Tyre Compound Usage per Lap",
                                      labels={lap_num_col: 'Lap Number', driver_col: 'Driver'})
                fig_tyre.update_traces(marker=dict(size=8))
                st.plotly_chart(fig_tyre, width='stretch')
            else:
                st.info("Tyre compound data not available for this race.")

        with tab2:
            st.subheader("Interactive Circuit Analysis")
            st.info("Loading high-resolution telemetry... This may take a few seconds.")
            
            session = load_fastf1_session(selected_year, selected_round)
            
            if session:
                # Select Visualization Type
                viz_type = st.radio("Select Visualization", ["3D Speed Map", "Gear Shift Map"], horizontal=True)
                
                lap = session.laps.pick_fastest()
                tel = lap.get_telemetry()
                
                # Add Z-axis (Elevation if available, otherwise simulate or use 0)
                # FastF1 telemetry has 'Z' for elevation in newer versions/tracks
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
                    st.plotly_chart(fig_3d, width='stretch')
                    
                else: # Gear Shift Map (Keep 2D for clarity or make 3D)
                    # Let's keep Gear Shift as 2D Matplotlib for now as it's cleaner for discrete segments, 
                    # OR upgrade to 3D. Let's try 3D for consistency!
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
                    st.plotly_chart(fig_3d, width='stretch')
                
            else:
                st.error("Failed to load FastF1 session data.")

        with tab3:
            st.subheader("Competitor Analysis")
            
            session = load_fastf1_session(selected_year, selected_round)
            
            if session:
                drivers = sorted(session.drivers)
                drivers = [d for d in drivers if d in session.results['Abbreviation'].values]
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    driver1 = st.selectbox("Driver 1", drivers, index=0)
                with col_d2:
                    driver2 = st.selectbox("Driver 2", drivers, index=1)
                    
                if driver1 and driver2:
                    laps1 = session.laps.pick_driver(driver1).pick_fastest()
                    laps2 = session.laps.pick_driver(driver2).pick_fastest()
                    
                    if not laps1.empty and not laps2.empty:
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
                        st.plotly_chart(fig_comp, width='stretch')
                        
                        # Plot Delta
                        fig_delta = go.Figure()
                        fig_delta.add_trace(go.Scatter(x=ref_tel['Distance'], y=delta_time, mode='lines', name=f"Delta ({driver2} to {driver1})", line=dict(color='white')))
                        fig_delta.add_hline(y=0, line_dash="dash", line_color="gray")
                        
                        fig_delta.update_layout(title=f"Time Delta: {driver2} relative to {driver1}", 
                                                xaxis_title="Distance (m)", yaxis_title="Delta (s)")
                        st.plotly_chart(fig_delta, width='stretch')
                        
                    else:
                        st.warning("One or both drivers do not have a valid fastest lap.")
            else:
                st.error("Failed to load FastF1 session data.")
