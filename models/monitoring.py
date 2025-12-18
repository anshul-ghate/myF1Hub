
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
try:
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset, TargetDriftPreset, DataQualityPreset
    from evidently import ColumnMapping
    EVIDENTLY_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Evidently MLOps Monitoring not available: {e}")
    EVIDENTLY_AVAILABLE = False
    Report = None
    DataDriftPreset = None
    ColumnMapping = None


# Paths
MONITORING_DIR = 'monitoring'
REPORTS_DIR = os.path.join(MONITORING_DIR, 'reports')

if not os.path.exists(REPORTS_DIR):
    os.makedirs(REPORTS_DIR)

class ModelMonitor:
    """
    Monitors data drift and model performance using Evidently.
    """
    
    def __init__(self):
        self.column_mapping = ColumnMapping()
        self.column_mapping.target = 'position'  # Assuming position is the target
        self.column_mapping.prediction = 'prediction'
        self.column_mapping.numerical_features = [
             'grid_position', 'driver_elo', 'team_elo', 'rain_probability'
        ]
        # flexible mapping handling
        
    def generate_drift_report(self, reference_data: pd.DataFrame, current_data: pd.DataFrame, filename=None):
        """
        Generates a data drift report comparing reference (training) data vs current (inference) data.
        
        Args:
            reference_data: DataFrame used for training
            current_data: New data (e.g. from the upcoming race)
            filename: Optional filename for the report
            
        Returns:
            Path to the generated HTML report
        """
        
        if not EVIDENTLY_AVAILABLE:
            print("❌ Evidently not available.")
            return None
            
        # Filter explicitly ensuring we only check features that exist in both
        common_cols = [c for c in reference_data.columns if c in current_data.columns]
        
        report = Report(metrics=[
            DataDriftPreset(),
            DataQualityPreset()
        ])
        
        try:
             report.run(reference_data=reference_data[common_cols], current_data=current_data[common_cols], column_mapping=None)
        except Exception as e:
            print(f"Error running drift report: {e}")
            return None

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"drift_report_{timestamp}.html"
            
        filepath = os.path.join(REPORTS_DIR, filename)
        report.save_html(filepath)
        
        print(f"✅ Drift report saved to {filepath}")
        return filepath

    def check_model_performance(self, reference_data: pd.DataFrame, current_data: pd.DataFrame):
        """
        Checks model performance drift (Target Drift). 
        Requires 'target' column to be present in current_data (post-race).
        """
        if 'position' not in current_data.columns:
            print("⚠️ Cannot check target drift: 'position' column missing from current data.")
            return None
            
        report = Report(metrics=[
            TargetDriftPreset()
        ])
        
        report.run(reference_data=reference_data, current_data=current_data, column_mapping=self.column_mapping)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(REPORTS_DIR, f"target_drift_{timestamp}.html")
        report.save_html(filepath)
        print(f"✅ Target drift report saved to {filepath}")
        return filepath

if __name__ == "__main__":
    # Test stub
    df_ref = pd.DataFrame({
        'grid_position': np.random.randint(1, 20, 100),
        'driver_elo': np.random.normal(1500, 100, 100),
        'position': np.random.randint(1, 20, 100)
    })
    
    df_cur = pd.DataFrame({
        'grid_position': np.random.randint(1, 20, 20),
        'driver_elo': np.random.normal(1450, 100, 20), # Slight shift
        'position': np.random.randint(1, 20, 20)
    })
    
    monitor = ModelMonitor()
    monitor.generate_drift_report(df_ref, df_cur)
