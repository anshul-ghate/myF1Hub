from models.hybrid_predictor import HybridPredictor

def test_hybrid_training():
    print("Initializing HybridPredictor...")
    predictor = HybridPredictor()
    
    print("Starting training...")
    success = predictor.train(min_year=2023) # Train on small subset for speed
    
    if success:
        print("✅ Hybrid training completed successfully!")
    else:
        print("❌ Hybrid training failed.")

if __name__ == "__main__":
    test_hybrid_training()
