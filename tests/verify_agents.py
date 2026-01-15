import sys
import os
sys.path.append(os.getcwd())

from agents.model_agent import ModelAgent
from agents.strategy_agent import StrategyAgent
from unittest.mock import MagicMock

def test_model_agent():
    print("Testing ModelAgent...")
    # Mocking registry to avoid needing real MLflow server
    agent = ModelAgent()
    agent.registry = MagicMock()
    
    # Case 1: Missing model
    agent.registry.get_model_metadata.return_value = None
    agent.check_model_freshness() # Should verify logs or mocked pipeline call (but pipeline is complex to mock here without more work)
    print("ModelAgent missing model check executed (check logs manually if real logic ran).")

    # Case 2: Old model
    mock_meta = MagicMock()
    mock_meta.creation_timestamp = 1000 # Very old
    agent.registry.get_model_metadata.return_value = mock_meta
    agent.check_model_freshness()
    print("ModelAgent old model check executed.")

def test_strategy_agent():
    print("\nTesting StrategyAgent...")
    agent = StrategyAgent()
    
    # Mock engineer to avoid API calls or if key missing
    agent.engineer = MagicMock()
    agent.engineer.ask.return_value = "This is a mocked response from Olof."
    
    response = agent.chat("What is the undercut?")
    print(f"Chat Response: {response}")
    assert "Olof" in response
    
    agent.engineer.analyze_commentary.return_value = "Strategy: Box box box."
    analysis = agent.analyze_session_commentary("Lap 1: HAM leading.")
    print(f"Analysis Response: {analysis}")
    assert "Strategy" in analysis

if __name__ == "__main__":
    test_model_agent()
    test_strategy_agent()
