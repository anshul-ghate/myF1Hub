
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

def test_imports():
    print("Testing imports...")
    try:
        import app.pages
        from models.dynasty_engine import DynastyEngine
        from utils.time_simulation import get_current_time
        print("✅ Core imports successful")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        sys.exit(1)

def test_debug_cleanup():
    print("Verifying debug cleanup...")
    from utils.time_simulation import get_current_time
    try:
        from utils.time_simulation import render_debug_panel
        print("❌ render_debug_panel still exists!")
        sys.exit(1)
    except ImportError:
        print("✅ render_debug_panel successfully removed")

if __name__ == "__main__":
    test_imports()
    test_debug_cleanup()
    print("🚀 Sanity check passed!")
