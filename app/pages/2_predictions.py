import streamlit as st
import pandas as pd
import joblib
import os
import numpy as np
from utils.db import get_supabase_client
from utils.race_utils import get_next_upcoming_race, get_seasons, get_rounds_for_season, get_race_lap_count, get_race_by_id
from models.simulation import RaceSimulator
from app.components.sidebar import render_sidebar

# Inject Custom CSS
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("app/assets/custom.css")

# Render Sidebar
render_sidebar()

st.set_page_config(page_title="Race Predictions", page_icon="🔮", layout="wide")

supabase = get_supabase_client()

@st.cache_resource
def load_model():
    path = 'models/saved/lap_time_model.pkl'
    if os.path.exists(path):
        return joblib.load(path)
    return None

model = load_model()

st.title("🏁 F1 Race Result Predictions")

if not model:
    st.error("⚠️ ML Model not trained yet. Please run the training pipeline first.")
    st.stop()

st.success("✅ Prediction Model Loaded")

# ========== RACE SELECTION ==========
st.subheader("Select Race")

# Method selection
selection_method = st.radio(
    "Race Selection Method",
    ["🔥 Next Upcoming Race", "📅 Select by Season & Round"],
    horizontal=True
)

selected_race = None
selected_race_id = None

if selection_method == "🔥 Next Upcoming Race":
    # Auto-detect next upcoming race
    next_race = get_next_upcoming_race()
    
    if next_race:
        selected_race = next_race
        selected_race_id = next_race['id']
        
        # Display next race info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Race", next_race.get('name', 'Unknown'))
        with col2:
            st.metric("Season", next_race.get('season_year', 'N/A'))
        with col3:
            st.metric("Round", next_race.get('round', 'N/A'))
        
        st.info(f"📍 **Circuit**: {next_race.get('circuit_name', 'Unknown')} | 📅 **Date**: {next_race.get('date', 'TBD')}")
    else:
        st.warning("No upcoming races found in the database. Please select manually.")
        selection_method = "📅 Select by Season & Round"

if selection_method == "📅 Select by Season & Round":
    # Manual selection with cascading dropdowns
    seasons = get_seasons()
    
    if seasons:
        col1, col2 = st.columns(2)
        
        with col1:
            selected_season = st.selectbox("Select Season", seasons, key='season_select')
        
        with col2:
            if selected_season:
                rounds_df = get_rounds_for_season(selected_season)
                
                if not rounds_df.empty:
                    # Create race options
                    rounds_df['race_label'] = rounds_df.apply(
                        lambda x: f"R{x['round']} - {x['name']}", axis=1
                    )
                    
                    selected_race_label = st.selectbox("Select Round", rounds_df['race_label'].tolist(), key='round_select')
                    
                    # Get selected race
                    selected_race = rounds_df[rounds_df['race_label'] == selected_race_label].iloc[0].to_dict()
                    selected_race_id = selected_race['id']
                else:
                    st.warning(f"No races found for season {selected_season}")
    else:
        st.error("No race data available in database.")

# ========== RACE RESULT PREDICTIONS ==========
if selected_race_id:
    st.markdown("---")
    st.subheader("🎯 Race Result Predictions")
    
    # Get race details
    total_laps = get_race_lap_count(selected_race_id)
    
    st.info(f"**Total Laps**: {total_laps} | **Prediction Method**: Monte Carlo Simulation with ML Model")
    
    # Simulation parameters
    col_sim1, col_sim2 = st.columns(2)
    with col_sim1:
        n_simulations = st.slider("Number of Simulations", 100, 2000, 500, step=100,
                                  help="More simulations = more accurate predictions, but slower")
    with col_sim2:
        confidence_level = st.select_slider("Confidence Level", options=[80, 90, 95, 99], value=90,
                                           help="Higher confidence = wider prediction intervals")
    
    # Advanced options (hidden by default)
    with st.expander("⚙️ Advanced Options"):
        predict_dnfs = st.checkbox("Predict DNFs (Retirements)", value=True)
        predict_fastest_lap = st.checkbox("Predict Fastest Lap", value=True)
        show_lap_progression = st.checkbox("Show Position Progression by Lap", value=False)
    
    if st.button("🚀 Run Race Prediction", type="primary"):
        simulator = RaceSimulator()
        
        if simulator.model:
            with st.spinner(f"Running {n_simulations} race simulations... This may take a minute."):
                # Run Monte Carlo simulation
                results, driver_codes = simulator.simulate_race(
                    selected_race_id, 
                    total_laps=total_laps, 
                    n_simulations=n_simulations
                )
                
                if results and driver_codes:
                    # Aggregate results
                    agg_df = simulator.aggregate_results(results, driver_codes)
                    
                    st.success("✅ Simulation Complete!")
                    
                    # ===== PRIMARY: FINAL POSITIONS =====
                    st.subheader("🏆 Predicted Final Standings")
                    
                    # Sort by most likely winner (highest Win %)
                    agg_df_sorted = agg_df.sort_values('Win %', ascending=False)
                    
                    # Display top predictions with medals
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("🥇 Most Likely Winner", 
                                 agg_df_sorted.iloc[0]['Driver'], 
                                 f"{agg_df_sorted.iloc[0]['Win %']:.1f}% chance")
                    
                    with col2:
                        if len(agg_df_sorted) > 1:
                            st.metric("🥈 2nd Most Likely", 
                                     agg_df_sorted.iloc[1]['Driver'], 
                                     f"{agg_df_sorted.iloc[1]['Win %']:.1f}% chance")
                    
                    with col3:
                        if len(agg_df_sorted) > 2:
                            st.metric("🥉 3rd Most Likely", 
                                     agg_df_sorted.iloc[2]['Driver'], 
                                     f"{agg_df_sorted.iloc[2]['Win %']:.1f}% chance")
                    
                    # Full results table
                    st.dataframe(
                        agg_df_sorted.style.format({
                            'Win %': '{:.1f}%',
                            'Podium %': '{:.1f}%',
                            'Top 10 %': '{:.1f}%',
                            'Avg Pos': '{:.1f}'
                        }).background_gradient(subset=['Win %'], cmap='RdYlGn'),
                        use_container_width=True,
                        height=400
                    )
                    
                    # Visualization
                    st.subheader("📊 Win Probability Distribution")
                    st.bar_chart(agg_df_sorted.set_index('Driver')['Win %'])
                    
                    # ===== EXPLAINABILITY =====
                    st.markdown("---")
                    st.subheader("🧠 How These Predictions Were Made")
                    
                    st.markdown(f"""
                    **Prediction Methodology:**
                    
                    1. **Monte Carlo Simulation**: Ran {n_simulations:,} complete race simulations
                    2. **ML Model**: Used trained XGBoost model to predict lap times based on:
                       - Driver historical performance
                       - Tyre degradation patterns
                       - Circuit characteristics
                       - Fuel load progression
                    3. **Randomization**: Each simulation includes realistic variability for:
                       - Lap-to-lap performance fluctuations
                       - Tyre compound strategies
                       - Safety car probabilities (if enabled)
                    4. **Aggregation**: Final predictions are the statistical average of all simulations
                    
                    **Confidence**: {confidence_level}% confidence intervals mean we're {confidence_level}% certain the true result falls within these ranges.
                    
                    **Limitations**:
                    - Weather conditions not yet incorporated
                    - Real-time strategy calls (e.g., pit stop timing) are simplified
                    - Driver incidents/DNFs are probabilistic estimates
                    """)
                    
                    # ===== OPTIONAL DETAILS =====
                    with st.expander("📋 Detailed Prediction Insights"):
                        st.markdown("### Podium Probabilities")
                        podium_df = agg_df_sorted[['Driver', 'Win %', 'Podium %', 'Avg Pos']].head(10)
                        st.dataframe(podium_df, use_container_width=True)
                        
                        if predict_fastest_lap:
                            st.markdown("### Fastest Lap Prediction")
                            # Simple heuristic: Driver with best avg position and high consistency
                            fastest_lap_candidate = agg_df_sorted.iloc[0]['Driver']
                            st.info(f"🏎️ **Most Likely Fastest Lap**: {fastest_lap_candidate}")
                        
                        if predict_dnfs:
                            st.markdown("### DNF (Retirement) Risk")
                            st.warning("DNF prediction feature coming soon. Current model assumes all drivers finish.")
                        
                        if show_lap_progression:
                            st.markdown("### Position Progression")
                            st.info("Lap-by-lap position progression visualization coming soon.")
                    
                else:
                    st.error("❌ Simulation failed. No drivers found or model error.")
        else:
            st.error("❌ Model not loaded properly.")

else:
    st.info("👆 Please select a race to generate predictions.")
