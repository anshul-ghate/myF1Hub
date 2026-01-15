import sys
import os
import logging
from pathlib import Path

# Adjust path to include project root
sys.path.append(os.getcwd())

from models.hybrid_predictor import HybridPredictor
from models.dynasty_engine import DynastyEngine
from utils.logger import get_logger

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = get_logger("FullRetrain")

def run():
    logger.info("🚀 Starting Full Model Retraining Pipeline...")
    
    # 1. Hybrid Predictor (Lap Times, Position, Win Prob)
    logger.info("--- [1/2] Training Hybrid Predictor ---")
    try:
        predictor = HybridPredictor()
        predictor.train()
        logger.info("✅ Hybrid Predictor trained successfully.")
    except Exception as e:
        logger.error(f"❌ Hybrid Predictor failed: {e}")

    # 2. Dynasty Engine (Elo Ratings, Simulation, Long-term stats)
    logger.info("--- [2/2] Training Dynasty Engine ---")
    try:
        engine = DynastyEngine()
        engine.train()
        logger.info("✅ Dynasty Engine trained successfully.")
    except Exception as e:
        logger.error(f"❌ Dynasty Engine failed: {e}")

    logger.info("🏁 Retraining Pipeline Complete.")

if __name__ == "__main__":
    run()
