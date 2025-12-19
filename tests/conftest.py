
import pytest
import os
import sys
from unittest.mock import MagicMock

# --- 1. Mock Supabase BEFORE Imports ---
# We need to mock utils.db.supabase and create_client to prevent connection attempts
sys.modules['supabase'] = MagicMock()
sys.modules['gotrue'] = MagicMock()

# Mock specific utilities that might be imported
mock_supabase_client = MagicMock()
mock_db_module = MagicMock()
mock_db_module.get_supabase_client.return_value = mock_supabase_client
mock_db_module.supabase = mock_supabase_client
sys.modules['utils.db'] = mock_db_module

# --- 2. Mock FastF1 ---
# FastF1 often tries to hit the internet or create cache dirs
mock_fastf1 = MagicMock()
mock_fastf1.Cache.enable_cache = MagicMock()
sys.modules['fastf1'] = mock_fastf1

# --- 3. Mock Env Vars ---
@pytest.fixture(autouse=True)
def mock_env():
    """Set mock environment variables for all tests."""
    os.environ['SUPABASE_URL'] = 'https://mock.supabase.co'
    os.environ['SUPABASE_KEY'] = 'mock-key'
    yield
    if 'SUPABASE_URL' in os.environ:
        del os.environ['SUPABASE_URL']
    if 'SUPABASE_KEY' in os.environ:
        del os.environ['SUPABASE_KEY']

@pytest.fixture
def mock_supabase():
    return mock_supabase_client
