import streamlit as st

# Page Config - MUST be first Streamlit command
st.set_page_config(page_title="Race Predictions", page_icon="🔮", layout="wide")

import pandas as pd
import joblib
import os
import numpy as np
from utils.db import get_supabase_client
from utils.race_utils import get_next_upcoming_race, get_seasons, get_rounds_for_season, get_race_lap_count, get_race_by_id
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

# Lazy import heavy modules to improve page load time
@st.cache_resource
def load_predictor():
    """Load the hybrid predictor with error handling"""
    try:
        from models.hybrid_predictor import HybridPredictor
        predictor = HybridPredictor()
        return predictor
    except Exception as e:
        st.warning(f"⚠️ Hybrid Predictor unavailable: {e}")
        return None

# Cache in session state for performance within a session
if 'predictor' not in st.session_state:
    with st.spinner("Loading prediction engine..."):
        st.session_state['predictor'] = load_predictor()

# Check for reload button
if st.sidebar.button("🔄 Reload Predictor"):
    st.cache_resource.clear()
    st.session_state['predictor'] = load_predictor()
    st.rerun()
    
engine = st.session_state['predictor']

st.title("🏁 F1 Hybrid Prediction Engine v8.0")

# Check if engine is available
if engine is None:
    st.error("⚠️ Prediction Engine is not available. Please check the logs for errors.")
    st.info("The prediction system was unable to initialize. This may be due to missing dependencies or data issues.")
    st.stop()

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
selected_year = None
selected_race_name = None

if selection_method == "🔥 Next Upcoming Race":
    # Auto-detect next upcoming race
    next_race = get_next_upcoming_race()
    
    if next_race:
        selected_race = next_race
        selected_race_id = next_race['id']
        selected_year = next_race['season_year']
        selected_race_name = next_race['name']
        
        # Display next race info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Race", next_race.get('name', 'Unknown'))
        with col2:
            st.metric("Season", next_race.get('season_year', 'N/A'))
        with col3:
            st.metric("Round", next_race.get('round', 'N/A'))
        
        st.info(f"📍 **Circuit**: {next_race.get('circuit_name', 'Unknown')} | 📅 **Date**: {next_race.get('race_date', 'TBD')}")
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
                    selected_year = selected_race['season_year']
                    selected_race_name = selected_race['name']
                else:
                    st.warning(f"No races found for season {selected_season}")
    else:
        st.error("No race data available in database.")

# ========== RACE RESULT PREDICTIONS ==========
if selected_race_id:
    st.markdown("---")
    st.subheader("🎯 Race Result Predictions")
    
    st.info(f"**Engine**: Hybrid v8.0 (Multi-Model Ensemble + Monte Carlo) | **Powered by**: LightGBM Ranker + XGBoost + Enhanced Features")
    
    # Simulation parameters
    col_sim1, col_sim2, col_sim3 = st.columns(3)
    with col_sim1:
        n_simulations = st.slider("Number of Simulations", 1000, 10000, 5000, step=1000,
                                  help="More simulations = more accurate predictions, but slower")
    with col_sim2:
        weather_forecast = st.selectbox("Weather Forecast", ["Dry", "Wet"], 
                                       help="Wet weather increases chaos and DNF probability")
    with col_sim3:
        show_insights = st.checkbox("Show Feature Importances", value=True,
                                   help="Display which factors are most important for predictions")
    
    if st.button("🚀 Run Hybrid Prediction", type="primary"):
        with st.spinner(f"Running comprehensive prediction with {n_simulations:,} simulations..."):
            try:
                # Run Prediction
                results_df = engine.predict_race(
                    year=selected_year,
                    race_name=selected_race_name,
                    weather_forecast=weather_forecast,
                    n_sims=n_simulations
                )
                
                if results_df is not None and not results_df.empty:
                    st.success("✅ Prediction Complete!")
                    
                    # ===== TRACK INFORMATION =====
                    # Lazy import to avoid circular imports
                    try:
                        from models.dynasty_engine import get_track_dna
                        track_dna = get_track_dna(selected_race_name)
                    except ImportError:
                        track_dna = {}
                    
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.metric("Circuit Type", track_dna['Type'])
                    with col_info2:
                        st.metric("Overtaking Difficulty", f"{track_dna['Overtaking']}/10")
                    with col_info3:
                        st.metric("Weather", weather_forecast)
                    
                    st.markdown("---")
                    
                    # ===== PRIMARY: FINAL POSITIONS =====
                    st.subheader("🏆 Predicted Final Standings")
                    
                    # Display top predictions with medals
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        winner = results_df.iloc[0]
                        st.metric("🥇 Most Likely Winner", 
                                 winner['Driver'], 
                                 f"{winner['Win %']:.1f}% chance")
                        st.caption(f"Team: {winner['Team']} | Grid: P{winner['Grid']}")
                    
                    with col2:
                        if len(results_df) > 1:
                            second = results_df.iloc[1]
                            st.metric("🥈 2nd Most Likely", 
                                     second['Driver'], 
                                     f"{second['Win %']:.1f}% chance")
                            st.caption(f"Team: {second['Team']} | Grid: P{second['Grid']}")
                    
                    with col3:
                        if len(results_df) > 2:
                            third = results_df.iloc[2]
                            st.metric("🥉 3rd Most Likely", 
                                     third['Driver'], 
                                     f"{third['Win %']:.1f}% chance")
                            st.caption(f"Team: {third['Team']} | Grid: P{third['Grid']}")
                    
                    st.markdown("---")
                    
                    # Full results table with enhanced formatting
                    st.subheader("📊 Complete Prediction Breakdown")
                    
                    display_df = results_df.copy()
                    display_df = display_df.round({
                        'Win %': 1,
                        'Podium %': 1,
                        'Top 5 %': 1,
                        'Points %': 1,
                        'DNF %': 1,
                        'Avg Pos': 1
                    })
                    
                    # Select columns for main display (hide Explanation for cleaner table)
                    main_cols = ['Driver', 'Team', 'Grid', 'Win %', 'Podium %', 'Top 5 %', 'Points %', 'Avg Pos', 'DNF %']
                    
                    st.dataframe(
                        display_df[main_cols].style.format({
                            'Win %': '{:.1f}%',
                            'Podium %': '{:.1f}%',
                            'Top 5 %': '{:.1f}%',
                            'Points %': '{:.1f}%',
                            'DNF %': '{:.1f}%',
                            'Avg Pos': '{:.1f}'
                        }).background_gradient(subset=['Win %'], cmap='RdYlGn')
                          .background_gradient(subset=['Podium %'], cmap='Blues'),
                        use_container_width=True,
                        height=600
                    )
                    
                    # Driver Explanations Expander
                    with st.expander("📖 Driver-by-Driver Analysis", expanded=False):
                        for idx, row in display_df.iterrows():
                            st.markdown(f"**P{idx} {row['Driver']}** ({row['Team']}): {row.get('Explanation', 'N/A')}")
                    
                    # Visualization
                    st.subheader("📈 Win Probability Distribution")
                    chart_data = results_df.set_index('Driver')[['Win %', 'Podium %', 'Points %']]
                    st.bar_chart(chart_data)
                    
                    # ===== FEATURE IMPORTANCES =====
                    if show_insights:
                        st.markdown("---")
                        st.subheader("🧠 Model Insights & Feature Importances")
                        
                        feature_imp_df = engine.get_feature_importances(top_n=12)
                        
                        if feature_imp_df is not None:
                            col_chart, col_explain = st.columns([2, 1])
                            
                            with col_chart:
                                st.bar_chart(feature_imp_df.set_index('Feature')['Importance'])
                            
                            with col_explain:
                                st.markdown("""
                                **What This Means:**
                                
                                The chart shows which factors have the biggest impact on predictions:
                                
                                - **Elo Ratings**: Driver & team skill levels
                                - **Grid Position**: Starting position matters
                                - **Recent Form**: Last 5 races performance
                                - **Circuit History**: Track-specific experience
                                - **Weather**: Dry vs wet conditions
                                - **Reliability**: Team's DNF history
                                """)
                        else:
                            st.info("Feature importances not available (model may need retraining)")
                    
                    # ===== SHAP EXPLANATIONS =====
                    if getattr(engine, 'last_X_df', None) is not None:
                        st.markdown("---")
                        st.subheader("🕵️‍♀️ Individual Prediction Explainability (SHAP)")
                        
                        try:
                            import shap
                            import matplotlib.pyplot as plt
                            
                            shap_values = engine.explain_predictions(engine.last_X_df)
                            
                            if shap_values is not None:
                                # Driver selector
                                driver_list = getattr(engine, 'last_driver_names', [])
                                if driver_list:
                                    selected_driver_exp = st.selectbox("Select Driver to Explain", driver_list)
                                    driver_idx = driver_list.index(selected_driver_exp)
                                    
                                    col_shap, col_text = st.columns([2, 1])
                                    
                                    with col_shap:
                                        # Force matplotlib backend for Streamlit safety
                                        fig, ax = plt.subplots(figsize=(10, 6))
                                        shap.plots.waterfall(shap_values[driver_idx], show=False)
                                        st.pyplot(fig)
                                        plt.close(fig)
                                    
                                    with col_text:
                                        st.markdown(f"""
                                        **Interpretation for {selected_driver_exp}:**
                                        
                                        - **Red bars** push the prediction **higher** (better rank/result).
                                        - **Blue bars** push the prediction **lower**.
                                        - The base value is the average prediction.
                                        """)
                        except ImportError:
                            st.warning("SHAP library not found. Install it to see explanations.")
                        except Exception as e:
                            st.error(f"Could not generate SHAP plot: {e}")
                    
                    # ===== METHODOLOGY EXPLAINER =====
                    st.markdown("---")
                    st.subheader("🔬 Prediction Methodology")
                    
                    with st.expander("Click to see how predictions are made", expanded=False):
                        st.markdown(f"""
                        **Hybrid Prediction Pipeline:**
                        
                        **Stage 1: Feature Engineering** (25+ Features)
                        - Driver: Recent form, consistency, circuit history, qualifying vs race delta
                        - Team: Reliability score, pit stop efficiency, constructor standings
                        - Circuit: Track type, overtaking difficulty, safety car probability
                        - Weather: Temperature, humidity, rainfall forecast
                        - Strategic: Grid positions, tire allocation, historical patterns
                        
                        **Stage 2: Multi-Model Ensemble**
                        - **LightGBM Ranker**: Trained on 2021-present, learns optimal driver rankings
                        - **XGBoost Regressor**: Predicts exact finishing positions
                        - **Ensemble Weight**: 60% Ranker + 40% Regressor for balanced predictions
                        
                        **Stage 3: Monte Carlo Simulation** ({n_simulations:,} iterations)
                        - Base predictions adjusted by:
                          - Driver consistency (std dev of recent positions)
                          - Track overtaking difficulty ({track_dna['Overtaking']}/10)
                          - Weather chaos factor ({'1.5x' if weather_forecast == 'Wet' else '1.0x'})
                          - DNF probability (team reliability × weather multiplier)
                        
                        **Confidence Calculation:**
                        - Win %: Probability of finishing P1 across all simulations
                        - Podium %: P1-P3 finish probability
                        - Avg Pos: Expected finishing position (weighted average)
                        
                        **Data Sources:**
                        - Historical race results (2021-{selected_year})
                        - Lap-by-lap telemetry and timing data
                        - Weather conditions and forecasts
                        - Pit stop strategies and durations
                        - Driver/Team Elo ratings (dynamically updated)
                        """)
                    
                else:
                    st.error("❌ Prediction failed. Could not generate predictions. This may happen if:")
                    st.markdown("""
                    - Grid/qualifying data is unavailable
                    - Insufficient historical data for the drivers
                    - Model training is required (try restarting the app)
                    """)
                    
            except Exception as e:
                st.error(f"❌ Prediction error: {str(e)}")
                st.exception(e)

else:
    st.info("👆 Please select a race to generate predictions.")
