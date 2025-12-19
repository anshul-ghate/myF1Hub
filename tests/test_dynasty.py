
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from models.dynasty_engine import get_track_dna, EloTracker

# --- Tests for Helper Functions ---

def test_get_track_dna_known():
    """Test retrieving DNA for a known circuit."""
    dna = get_track_dna('Monaco Grand Prix')
    assert dna['Type'] == 'Street_Slow'
    assert dna['Overtaking'] == 1

def test_get_track_dna_fallback():
    """Test fallback mechanism for unknown circuit."""
    dna = get_track_dna('Unknown Grand Prix')
    assert dna['Type'] == 'Balanced'
    assert dna['Overtaking'] == 5

# --- Tests for EloTracker ---

def test_elo_tracker_initialization():
    """Test that EloTracker initializes with default values."""
    tracker = EloTracker()
    assert tracker.drivers == {'VER': 1500} # As defined in code
    assert tracker.teams == {'Red Bull Racing': 1500}

def test_elo_tracker_get_rating():
    """Test getting ratings."""
    tracker = EloTracker()
    # Test known driver
    assert tracker.get_rating('VER', is_driver=True) == 1500
    
    # Test unknown driver (should return default)
    assert tracker.get_rating('UNKNOWN_DRIVER', is_driver=True) == 1350
    
    # Test constructor
    assert tracker.get_rating('Red Bull Racing', is_driver=False) == 1500

def test_elo_update():
    """Test Elo calculation logic."""
    tracker = EloTracker()
    # Simple update simulation
    # If VER (1500) beats PER (1420), VER should gain little, PER lose little.
    
    # Mocking the update method logic if needed, or testing side effects if method exposes them.
    # For now, we test the probability function which is pure logic.
    prob = tracker.expected_score(1500, 1500)
    assert prob == 0.5
    
    prob_fav = tracker.expected_score(1600, 1500)
    assert prob_fav > 0.5
