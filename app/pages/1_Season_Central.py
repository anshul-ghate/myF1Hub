import streamlit as st

# Page Config - MUST be first Streamlit command
st.set_page_config(page_title="Season Central", page_icon="🏁", layout="wide")

import pandas as pd
import fastf1
import datetime
import pytz
from utils.race_utils import (
    get_next_upcoming_race, 
    get_current_standings, 
    get_latest_completed_session,
    get_session_results,
    get_track_map_image
)
from app.components.sidebar import render_sidebar

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

# Initialize Engine with error handling
@st.cache_resource
def load_engine():
    try:
        from models.dynasty_engine import DynastyEngine
        return DynastyEngine()
    except Exception as e:
        st.warning(f"⚠️ Dynasty Engine unavailable: {e}")
        return None

engine = load_engine()

# --- HELPER: Team Colors ---
TEAM_COLORS = {
    'Red Bull Racing': '#0600EF',
    'Mercedes': '#00D2BE',
    'Ferrari': '#DC0000',
    'McLaren': '#FF8700',
    'Aston Martin': '#006F62',
    'Alpine': '#0090FF',
    'Williams': '#005AFF',
    'RB': '#2B4562',
    'Haas F1 Team': '#FFFFFF',
    'Kick Sauber': '#52E252',
    'Alfa Romeo': '#900000', 
    'AlphaTauri': '#2B4562'
}

def get_team_color(team_name):
    return TEAM_COLORS.get(team_name, '#FFFFFF')

def highlight_team(row):
    color = get_team_color(row['Team' if 'Team' in row else 'TeamName'])
    return [f'border-left: 5px solid {color}' for _ in row]

# --- HEADER ---
current_year = datetime.datetime.now().year
st.title(f"🏁 F1 {current_year} Season Central")

# --- 1. CURRENT RACE WEEKEND ---
st.subheader("📅 Current Race Weekend")

# Get Schedule
schedule = fastf1.get_event_schedule(current_year)
now_utc = datetime.datetime.now(pytz.utc)

# Find next or active race (EventDate + 1 day buffer)
# Ensure columns are datetime
for col in ['EventDate', 'Session1Date', 'Session2Date', 'Session3Date', 'Session4Date', 'Session5Date']:
    if col in schedule.columns:
        schedule[col] = pd.to_datetime(schedule[col], utc=True)

# Filter for future or recent events (within 3 days past)
upcoming = schedule[schedule['EventDate'] + datetime.timedelta(days=3) > now_utc]

if not upcoming.empty:
    next_event = upcoming.iloc[0]
    
    # Ensure track_img is defined before use
    track_img = get_track_map_image(next_event)

    col_map, col_info = st.columns([1, 1])
    
    with col_map:
        if track_img:
            st.markdown(f'''
            <div style="width: 500px; height: 600px; border-radius: 12px; border: 1px solid #333; overflow: hidden; display: flex; align-items: center; justify-content: center; background: #1a1a1a;">
                <img src="{track_img}" style="width: 100%; height: 100%; object-fit: contain;">
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.info("Track map currently unavailable.")

    with col_info:
        st.markdown(f"## {next_event['EventName']}")
        st.markdown(f"**Round {next_event['RoundNumber']}** • {next_event['Location']}, {next_event['Country']}")
        
        # Countdown to Race
        race_start = next_event['Session5Date'] # Usually the race
        
        if pd.notna(race_start):
            delta = race_start - now_utc
            if delta.total_seconds() > 0:
                d = delta.days
                h, r = divmod(delta.seconds, 3600)
                m, s = divmod(r, 60)
                st.markdown(f"""
                <div style="background: rgba(255, 24, 1, 0.1); border: 1px solid #FF1801; border-radius: 8px; padding: 15px; text-align: center; margin-bottom: 20px;">
                    <h4 style="margin:0; color: #aaa;">RACE START IN</h4>
                    <h1 style="margin:0; font-size: 3em; font-family: monospace; color: white;">
                        {d}d {h:02d}h {m:02d}m
                    </h1>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.success("🏁 **RACE STARTED / FINISHED**")

        # Session Schedule
        st.markdown("### 🗓️ Session Schedule")
        sessions_df = []
        for i in range(1, 6):
            s_name = next_event[f'Session{i}']
            s_date = next_event[f'Session{i}Date']
            if s_name and pd.notna(s_date):
                status = "✅ Completed" if s_date < now_utc else "🔜 Upcoming"
                if abs((s_date - now_utc).total_seconds()) < 7200 and s_date < now_utc: # Within 2 hours
                    status = "🔴 LIVE / Recent"
                    
                sessions_df.append({
                    "Session": s_name,
                    "Time (Local/UTC)": s_date.strftime('%a %H:%M'),
                    "Status": status
                })
        
        st.dataframe(pd.DataFrame(sessions_df), hide_index=True, width='stretch')

else:
    # Fallback: Show most recent completed event (off-season)
    completed = schedule[schedule['EventDate'] < now_utc]
    
    if not completed.empty:
        next_event = completed.iloc[-1]  # Most recent completed
        
        st.info(f"📅 **Off-Season** - Showing most recent event from {current_year}")
        
        # Track map
        track_img = get_track_map_image(next_event)
        
        col_map, col_info = st.columns([1, 1])
        
        with col_map:
            if track_img:
                st.markdown(f'''
                <div style="width: 500px; height: 600px; border-radius: 12px; border: 1px solid #333; overflow: hidden; display: flex; align-items: center; justify-content: center; background: #1a1a1a;">
                    <img src="{track_img}" style="width: 100%; height: 100%; object-fit: contain;">
                </div>
                ''', unsafe_allow_html=True)
            else:
                st.info("Track map currently unavailable.")
        
        with col_info:
            st.markdown(f"## {next_event['EventName']}")
            st.markdown(f"**Round {next_event['RoundNumber']}** • {next_event['Location']}, {next_event['Country']}")
            
            # Show "Season Complete" instead of countdown
            st.markdown(f"""
            <div style="background: rgba(0, 200, 100, 0.1); border: 1px solid #00C864; border-radius: 8px; padding: 15px; text-align: center; margin-bottom: 20px;">
                <h4 style="margin:0; color: #aaa;">SEASON {current_year}</h4>
                <h1 style="margin:0; font-size: 2em; color: #00C864;">
                    ✅ COMPLETE
                </h1>
            </div>
            """, unsafe_allow_html=True)
            
            # Session Schedule (all completed)
            st.markdown("### 🗓️ Session Schedule")
            sessions_df = []
            for i in range(1, 6):
                s_name = next_event[f'Session{i}']
                s_date = next_event[f'Session{i}Date']
                if s_name and pd.notna(s_date):
                    sessions_df.append({
                        "Session": s_name,
                        "Time (Local/UTC)": s_date.strftime('%a %H:%M'),
                        "Status": "✅ Completed"
                    })
            
            st.dataframe(pd.DataFrame(sessions_df), hide_index=True, width='stretch')
    else:
        # Try previous year if current year has no events yet
        try:
            prev_schedule = fastf1.get_event_schedule(current_year - 1)
            for col in ['EventDate', 'Session1Date', 'Session2Date', 'Session3Date', 'Session4Date', 'Session5Date']:
                if col in prev_schedule.columns:
                    prev_schedule[col] = pd.to_datetime(prev_schedule[col], utc=True)
            
            prev_completed = prev_schedule[prev_schedule['EventDate'] < now_utc]
            if not prev_completed.empty:
                next_event = prev_completed.iloc[-1]
                st.info(f"📅 Showing last event from {current_year - 1} season")
                
                track_img = get_track_map_image(next_event)
                col_map, col_info = st.columns([1, 1])
                
                with col_map:
                    if track_img:
                        st.markdown(f'''
                        <div style="width: 500px; height: 600px; border-radius: 12px; border: 1px solid #333; overflow: hidden; display: flex; align-items: center; justify-content: center; background: #1a1a1a;">
                            <img src="{track_img}" style="width: 100%; height: 100%; object-fit: contain;">
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.info("Track map currently unavailable.")
                
                with col_info:
                    st.markdown(f"## {next_event['EventName']}")
                    st.markdown(f"**Round {next_event['RoundNumber']}** • {next_event['Location']}, {next_event['Country']}")
                    st.success(f"🏁 **{current_year - 1} Season Finale**")
            else:
                st.info("No events found. Check back soon for the new season schedule.")
        except Exception as e:
            st.info("No upcoming events found for this season.")

st.markdown("---")

# --- 2. LATEST ACTION ---
st.subheader("⏱️ Latest Action")

with st.spinner("Fetching latest results..."):
    latest_session = get_latest_completed_session()

if latest_session:
    st.markdown(f"**{latest_session['EventName']} - {latest_session['Session']}**")
    
    results = get_session_results(latest_session['Year'], latest_session['Round'], latest_session['SessionType'])
    
    if not results.empty:
        # Split into Top 10 and 11-20
        col_res1, col_res2 = st.columns(2)
        
        # Format: Rank | Driver | Team | Time
        # Apply Team Colors
        
        with col_res1:
            st.markdown("#### Top 10")
            chunk1 = results.iloc[:10].reset_index(drop=True)
            chunk1.index += 1
            st.dataframe(
                chunk1.style.apply(highlight_team, axis=1), 
                width='stretch',
                column_config={
                    "Position": st.column_config.NumberColumn("Pos", format="%d")
                }
            )

        with col_res2:
            st.markdown("#### 11 - 20")
            chunk2 = results.iloc[10:20].reset_index(drop=True)
            if not chunk2.empty:
                chunk2.index = range(11, 11 + len(chunk2))
                st.dataframe(
                    chunk2.style.apply(highlight_team, axis=1), 
                    width='stretch',
                    column_config={
                        "Position": st.column_config.NumberColumn("Pos", format="%d")
                    }
                )
    else:
        st.warning("Results data unavailable.")
else:
    st.info("No recent session data.")

st.markdown("---")

# --- 3. STANDINGS ---
st.subheader("🏆 Championship Standings")
col_stand1, col_stand2 = st.columns(2)

with st.spinner("Refreshing standings..."):
    d_stand, c_stand = get_current_standings(current_year)

with col_stand1:
    st.markdown("### 🏎️ Drivers")
    if not d_stand.empty:
        d_stand = d_stand[['Driver', 'Points']] # Ensure columns
        # Apply team color mapping if we had Team info in driver standings. 
        # get_current_standings returns Driver, Points. 
        # We might need to fetch Team for drivers to do color coding properly here.
        
        ordered_teams = [] # Placeholder if we don't have team data in d_stand
        
        st.dataframe(
            d_stand.style.background_gradient(subset=['Points'], cmap='Reds'),
            width='stretch',
            height=400,
            column_config={
                "index": st.column_config.NumberColumn("Rank", format="%d"),
            }
        )

with col_stand2:
    st.markdown("### 🛠️ Constructors")
    if not c_stand.empty:
        st.dataframe(
            c_stand.style.apply(highlight_team, axis=1),
            width='stretch',
            height=400,
            column_config={
                "index": st.column_config.NumberColumn("Rank", format="%d"),
            }
        )

st.markdown("---")

# --- 4. QUICK PREDICTION ---
st.subheader("🔮 Quick Prediction")
st.info("AI-powered prediction for the upcoming race.")

if not upcoming.empty:
    race_obj = upcoming.iloc[0]
    
    col_pred_btn, col_pred_res = st.columns([1, 3])
    
    with col_pred_btn:
        if st.button("🚀 Run Prediction", type="primary", width='stretch'):
            st.session_state['run_quick_pred'] = True
    
    if st.session_state.get('run_quick_pred'):
        if engine is None:
            st.error("⚠️ Prediction engine is not available. Please check the application logs.")
        else:
            with st.spinner(f"Simulating {race_obj['EventName']}..."):
                # Use Dynasty Engine logic
                try:
                    preds = engine.predict_next_race(
                        year=race_obj['EventDate'].year,
                        race_name=race_obj['EventName'],
                        n_sims=500
                    )
                    
                    if preds is not None and not preds.empty:
                        top_pred = preds.head(5)
                        st.success("Prediction Complete!")
                        
                        # Display as metrics
                        cols = st.columns(5)
                        for i, (idx, row) in enumerate(top_pred.iterrows()):
                            with cols[i]:
                                st.metric(
                                    label=f"P{i+1}: {row['Driver']}",
                                    value=f"{row['Win %']:.1f}% Win",
                                    delta=f"Avg Pos: {row['Avg Pos']:.1f}"
                                )
                        
                        st.caption("Based on 500 Monte Carlo simulations using current season form and track characteristics.")
                    else:
                        st.error("Prediction model returned no data. Ensure data ingestion is up to date.")
                except Exception as e:
                    st.error(f"Prediction Error: {e}")

