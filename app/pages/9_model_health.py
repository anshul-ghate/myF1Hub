
import streamlit as st
import pandas as pd
import mlflow
from mlflow.tracking import MlflowClient
import os
import streamlit.components.v1 as components

# Page Config
st.set_page_config(page_title="Model Health", page_icon="🏥", layout="wide")

st.title("🏥 Model Health & MLOps Dashboard")

# Tabs
tab1, tab2, tab3 = st.tabs(["🧪 Experiment Tracking", "📉 Drift Monitoring", "⚙️ System Status"])

# --- TAB 1: EXPERIMENT TRACKING ---
with tab1:
    st.header("MLflow Experiments")
    
    try:
        mlflow.set_tracking_uri("file:./mlruns")
        client = MlflowClient()
        
        experiments = client.search_experiments()
        
        if not experiments:
             st.warning("No MLflow experiments found.")
        else:
             selected_exp = st.selectbox("Select Experiment", experiments, format_func=lambda x: x.name)
             
             if selected_exp:
                 runs = mlflow.search_runs(experiment_ids=[selected_exp.experiment_id])
                 
                 if not runs.empty:
                     st.dataframe(runs.sort_values("start_time", ascending=False).head(10))
                     
                     st.subheader("Latest Run Metrics")
                     latest_run = runs.iloc[0]
                     cols = st.columns(4)
                     
                     metrics = [c for c in runs.columns if c.startswith("metrics.")]
                     for i, metric in enumerate(metrics[:8]): # Show first 8 metrics
                         name = metric.replace("metrics.", "")
                         val = latest_run[metric]
                         cols[i % 4].metric(name, f"{val:.4f}")
                 else:
                     st.info("No runs found for this experiment.")
                     
    except Exception as e:
        st.error(f"Could not connect to MLflow: {e}")

# --- TAB 2: DRIFT MONITORING ---
with tab2:
    st.header("Drift & Quality Reports")
    
    REPORTS_DIR = "monitoring/reports"
    if not os.path.exists(REPORTS_DIR):
        st.info("No drift reports directory found. Run a monitoring job first.")
    else:
        reports = [f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")]
        
        if not reports:
            st.info("No reports generated yet.")
        else:
            selected_report = st.selectbox("Select Report", sorted(reports, reverse=True))
            
            if selected_report:
                report_path = os.path.join(REPORTS_DIR, selected_report)
                
                with open(report_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                st.download_button("Download Report", html_content, file_name=selected_report, mime='text/html')
                
                st.write("---")
                components.html(html_content, height=1000, scrolling=True)

# --- TAB 3: SYSTEM STATUS ---
with tab3:
    st.header("System Status")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Model Artifacts")
        if os.path.exists("models/saved/hybrid/ranker_model.pkl"):
            st.success("✅ Hybrid Ranker Model Found")
        else:
            st.error("❌ Hybrid Ranker Model Missing")
            
        if os.path.exists("models/saved/dynasty_model.pkl"):
            st.success("✅ Dynasty Model Found")
        else:
            st.error("❌ Dynasty Model Missing")
            
    with col2:
        st.subheader("Data Status")
        if os.path.exists("f1_cache_dynasty"):
             files = len(os.listdir("f1_cache_dynasty"))
             st.info(f"📁 Cache Size: {files} items")
        else:
             st.warning("⚠️ Cache directory missing")

