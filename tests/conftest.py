
import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# --- 0. Add project root to sys.path for module discovery ---
# This ensures 'models', 'utils', etc. can be imported in test files
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- 1. Set Mock Env Vars EARLY (Before any imports) ---
os.environ['SUPABASE_URL'] = 'https://mock.supabase.co'
os.environ['SUPABASE_KEY'] = 'mock-key'

# --- 2. Mock modules that cause side-effects on import ---

# Mock 'supabase' package itself to prevent network calls
sys.modules['supabase'] = MagicMock()
sys.modules['gotrue'] = MagicMock()

@pytest.fixture
def mock_supabase():
    return sys.modules['supabase']
