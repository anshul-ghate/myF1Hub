from models.train_model import train_model
from models.dynasty_engine import DynastyEngine
from utils.db import get_supabase_client
import traceback

def full_retrain():
    print("🚀 Starting Full Model Retraining...")
    
    # 1. Train Lap Time Model
    print("\n--- Training Lap Time Model ---")
    try:
        supabase = get_supabase_client()
        # Get all completed races
        res = supabase.table('races').select('id').eq('ingestion_complete', True).execute()
        race_ids = [r['id'] for r in res.data]
        
        if race_ids:
            print(f"Training on {len(race_ids)} races...")
            train_model(race_ids)
        else:
            print("⚠️ No completed races found for Lap Time Model.")
            
    except Exception as e:
        print(f"❌ Lap Time Model Training Failed: {e}")
        traceback.print_exc()
        
    # 2. Train Dynasty Engine (Hybrid Predictor)
    print("\n--- Training Dynasty Engine ---")
    try:
        engine = DynastyEngine()
        success = engine.train()
        if success:
            print("✅ Dynasty Engine Trained Successfully.")
        else:
            print("❌ Dynasty Engine Training Failed.")
            
    except Exception as e:
        print(f"❌ Dynasty Engine Training Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    full_retrain()
