"""
Test and validate the Hybrid Prediction Engine
"""

from models.hybrid_predictor import HybridPredictor
import pandas as pd


def test_initialization():
    """Test that the hybrid predictor initializes properly."""
    print("=" * 60)
    print("TEST 1: Initialization")
    print("=" * 60)
    
    try:
        predictor = HybridPredictor()
        print("✅ Hybrid Predictor initialized successfully")
        
        # Check components
        assert predictor.feature_engineer is not None, "Feature engineer not initialized"
        print("✅ Feature Engineer loaded")
        
        assert predictor.dynasty_engine is not None, "Dynasty engine not initialized"
        print("✅ Dynasty Engine loaded")
        
        print("\n✅ Initialization Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"❌ Initialization Test FAILED: {e}\n")
        return False


def test_training():
    """Test model training on historical data."""
    print("=" * 60)
    print("TEST 2: Model Training")
    print("=" * 60)
    
    try:
        predictor = HybridPredictor()
        
        print("Starting training (this may take 5-10 minutes)...")
        success = predictor.train(min_year=2023)  # Train on recent data only for faster testing
        
        if success:
            print("✅ Training completed successfully")
            
            # Check models were created
            assert predictor.ranker_model is not None, "Ranker model not created"
            print("✅ Ranker model created")
            
            assert predictor.position_model is not None, "Position model not created"
            print("✅ Position model created")
            
            assert len(predictor.feature_names) > 0, "No features captured"
            print(f"✅ {len(predictor.feature_names)} features captured")
            
            print("\n✅ Training Test PASSED\n")
            return True
        else:
            print("❌ Training returned False\n")
            return False
            
    except Exception as e:
        print(f"❌ Training Test FAILED: {e}\n")
        return False


def test_prediction():
    """Test prediction on a race."""
    print("=" * 60)
    print("TEST 3: Race Prediction")
    print("=" * 60)
    
    try:
        predictor = HybridPredictor()
        
        # If models don't exist, train first
        if predictor.ranker_model is None:
            print("Models don't exist. Training first...")
            predictor.train(min_year=2023)
        
        # Test prediction on a recent race
        print("\nRunning prediction for 2024 Monaco Grand Prix...")
        results_df = predictor.predict_race(
            year=2024,
            race_name="Monaco",
            weather_forecast="Dry",
            n_sims=1000  # Fewer sims for faster testing
        )
        
        if results_df is not None and not results_df.empty:
            print("✅ Prediction completed")
            print(f"✅ Generated predictions for {len(results_df)} drivers")
            
            # Check required columns
            required_cols = ['Driver', 'Win %', 'Podium %', 'Points %', 'Avg Pos']
            for col in required_cols:
                assert col in results_df.columns, f"Missing column: {col}"
            print(f"✅ All required columns present")
            
            # Display top 3
            print("\n🏆 Predicted Top 3:")
            for idx, row in results_df.head(3).iterrows():
                print(f"   P{idx + 1}: {row['Driver']} - {row['Win %']:.1f}% win chance")
            
            print("\n✅ Prediction Test PASSED\n")
            return True
        else:
            print("❌ Prediction returned empty results\n")
            return False
            
    except Exception as e:
        print(f"❌ Prediction Test FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_feature_importances():
    """Test feature importance extraction."""
    print("=" * 60)
    print("TEST 4: Feature Importances")
    print("=" * 60)
    
    try:
        predictor = HybridPredictor()
        
        # Check if we have feature importances
        if not predictor.feature_importances:
            print("No feature importances. Training model first...")
            predictor.train(min_year=2023)
        
        importances_df = predictor.get_feature_importances(top_n=10)
        
        if importances_df is not None and not importances_df.empty:
            print("✅ Feature importances extracted")
            print(f"✅ Got {len(importances_df)} top features")
            
            print("\n📊 Top 10 Most Important Features:")
            for idx, row in importances_df.iterrows():
                print(f"   {row['Feature']}: {row['Importance']:.4f}")
            
            print("\n✅ Feature Importances Test PASSED\n")
            return True
        else:
            print("❌ No feature importances available\n")
            return False
            
    except Exception as e:
        print(f"❌ Feature Importances Test FAILED: {e}\n")
        return False


def run_all_tests():
    """Run all validation tests."""
    print("\n" + "=" * 60)
    print("HYBRID PREDICTOR VALIDATION SUITE")
    print("=" * 60 + "\n")
    
    results = {
        "Initialization": test_initialization(),
        "Training": test_training(),
        "Prediction": test_prediction(),
        "Feature Importances": test_feature_importances()
    }
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:30} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Hybrid Predictor is working correctly.")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Please review errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
