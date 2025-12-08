import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.ai import RaceEngineer

try:
    engineer = RaceEngineer()
    print(f"Engineer available: {engineer.available}")
    response = engineer.ask("Who won the 2023 championship?")
    print(f"Response: {response}")
except Exception as e:
    print(f"CRASHED: {e}")
