import streamlit as st
import pandas as pd
import time
import plotly.express as px
from utils.db import get_supabase_client
from app.components.sidebar import render_sidebar

# Inject Custom CSS
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("app/assets/custom.css")

# Render Sidebar
render_sidebar()

st.set_page_config(page_title="Live Race Monitor", page_icon="📺", layout="wide")

supabase = get_supabase_client()

def get_races():
    res = supabase.table('races').select('id, name, season_year, round').order('season_year', desc=True).order('round', desc=True).execute()
    return pd.DataFrame(res.data)

races_df = get_races()

if races_df.empty:
    st.warning("No races found.")
else:
    # Race Selection
    years = sorted(races_df['season_year'].unique(), reverse=True)
    selected_year = st.selectbox("Select Season", years)
    
    races_in_year = races_df[races_df['season_year'] == selected_year].sort_values('round', ascending=False)
    
    # Create a mapping for the selectbox
    race_map = {f"R{row['round']} - {row['name']}": row for _, row in races_in_year.iterrows()}
    
    selected_race_label = st.selectbox("Select Race to Monitor", list(race_map.keys()))
    selected_race_id = race_map[selected_race_label]['id']

    # Initialize Session State for Replay
    if 'replay_lap' not in st.session_state:
        st.session_state.replay_lap = 1
    if 'is_playing' not in st.session_state:
        st.session_state.is_playing = False

    # Controls
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 4])
    with col_ctrl1:
        if st.button("▶️ Play"):
            st.session_state.is_playing = True
    with col_ctrl2:
        if st.button("⏸️ Pause"):
            st.session_state.is_playing = False
            
    # Fetch Data (Cached)
    @st.cache_data
    def get_full_race_data(race_id):
        # Fetch Laps with Drivers
        laps_res = supabase.table('laps').select('*').eq('race_id', race_id).order('lap_number').execute()
        drivers_res = supabase.table('drivers').select('*').execute()
        
        laps = pd.DataFrame(laps_res.data)
        drivers = pd.DataFrame(drivers_res.data)
        
        if not laps.empty and not drivers.empty:
            laps = laps.merge(drivers, left_on='driver_id', right_on='id', how='left')
        return laps

    full_laps_df = get_full_race_data(selected_race_id)
    
    if full_laps_df.empty:
        st.error("No data for this race.")
    else:
        max_laps = int(full_laps_df['lap_number'].max())
        
        with col_ctrl3:
            st.session_state.replay_lap = st.slider("Current Lap", 1, max_laps, st.session_state.replay_lap)

        # Auto-Play Logic
        if st.session_state.is_playing:
            if st.session_state.replay_lap < max_laps:
                st.session_state.replay_lap += 1
                time.sleep(1) # 1 second per lap replay speed
                st.rerun()
            else:
                st.session_state.is_playing = False

        current_lap = st.session_state.replay_lap
        
        # --- DASHBOARD ---
        
        # Filter data up to current lap
        current_data = full_laps_df[full_laps_df['lap_number'] == current_lap].sort_values('position')
        
        # 1. Leaderboard
        st.subheader(f"Leaderboard - Lap {current_lap}/{max_laps}")
        
        # Display columns: Pos, Driver, Gap, Tyre, Last Lap Time
        if not current_data.empty:
            leaderboard_df = current_data[['position', 'code', 'gap_to_leader', 'compound', 'tyre_life', 'lap_time']].copy()
            leaderboard_df.columns = ['Pos', 'Driver', 'Gap (s)', 'Tyre', 'Life', 'Last Lap']
            
            # Highlight leader
            def highlight_leader(s):
                return ['background-color: #2E8B57' if s.name == 0 else '' for v in s]
            
            # Safe formatter for Gap
            def format_gap(val):
                if val is None: return ""
                try: return f"{float(val):.3f}"
                except: return str(val)

            st.dataframe(leaderboard_df.set_index('Pos').style.format({'Gap (s)': format_gap}), use_container_width=True)
        
        # 2. Telemetry / Pace Analysis
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("Lap Time Evolution")
            # Show history up to current lap
            history_data = full_laps_df[full_laps_df['lap_number'] <= current_lap]
            
            # Filter top 5 drivers for clarity
            top_drivers = current_data.head(5)['driver_id'].tolist()
            plot_data = history_data[history_data['driver_id'].isin(top_drivers)]
            
            # Convert lap_time interval to seconds
            def parse_time(t):
                try: return pd.to_timedelta(t).total_seconds()
                except: return None
            plot_data['lap_time_s'] = plot_data['lap_time'].apply(parse_time)
            
            fig_pace = px.line(plot_data, x='lap_number', y='lap_time_s', color='code', 
                               title="Top 5 Pace Comparison", labels={'lap_time_s': 'Lap Time (s)'})
            st.plotly_chart(fig_pace, use_container_width=True)
            
        with col_g2:
            st.subheader("Tyre Degradation Monitor")
            # Scatter plot of Lap Time vs Tyre Life for current compound
            fig_deg = px.scatter(plot_data, x='tyre_life', y='lap_time_s', color='code', size='lap_number',
                                 title="Tyre Life vs Pace (Bubble Size = Lap Number)")
            st.plotly_chart(fig_deg, use_container_width=True)

        # 3. AI Strategy Insight
        st.markdown("---")
        st.subheader("🤖 AI Strategy Chief")
        
        from utils.ai import get_ai_insight
        
        # Prepare context for AI
        if not current_data.empty:
            leader = current_data.iloc[0]
            context = f"Lap {current_lap}/{max_laps}. Leader: {leader['code']} on {leader['compound']} tyres (Life: {leader['tyre_life']}). "
            
            # Add top 3 gaps
            for i in range(1, min(4, len(current_data))):
                row = current_data.iloc[i]
                gap_str = f"+{float(row['gap_to_leader']):.1f}s" if row['gap_to_leader'] is not None else "N/A"
                context += f"P{i+1} {row['code']} ({gap_str}, {row['compound']}, Life: {row['tyre_life']}). "
            
            if st.button("🧠 Generate Strategy Insight"):
                with st.spinner("Analyzing race telemetry..."):
                    insight = get_ai_insight(context)
                    st.success(insight)
        else:
            st.info("Waiting for race data...")
