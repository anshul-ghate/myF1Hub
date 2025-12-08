from models.hybrid_predictor import HybridPredictor
import traceback

def force_train():
    print("🚀 Force Training Hybrid Predictor on 2024 Data...")
    
    try:
        predictor = HybridPredictor()
        
        # Force train with min_year=2024
        print("Starting training (min_year=2024)...")
        success = predictor.train(min_year=2024)
        
        if success:
            print("✅ Training Successful!")
        else:
            print("❌ Training Failed.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    force_train()
