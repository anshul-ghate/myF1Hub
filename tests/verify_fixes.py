import sys
import os
import time
import logging

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_logger_async():
    print("Testing Async Logger...")
    from utils.logger import get_logger, SupabaseHandler
    
    logger = get_logger("TestLogger")
    
    # Check if handler is present
    has_supabase = any(isinstance(h, SupabaseHandler) for h in logger.handlers)
    print(f"Has SupabaseHandler: {has_supabase}")
    
    if has_supabase:
        # Check if thread is alive
        handler = next(h for h in logger.handlers if isinstance(h, SupabaseHandler))
        if hasattr(handler, 'worker_thread'):
            print(f"Worker thread alive: {handler.worker_thread.is_alive()}")
        else:
            print("ERROR: SupabaseHandler missing worker_thread attribute (Fix failed?)")
            
    logger.info("Test message (should be async)")
    print("Logged test message.")

def test_backfill_timeout_import():
    print("\nTesting Backfill Script Import...")
    try:
        from scripts.backfill_telemetry import process_race_with_timeout
        print("Import successful: process_race_with_timeout exists.")
    except ImportError:
        print("ERROR: Could not import process_race_with_timeout")
    except Exception as e:
        print(f"ERROR on import: {e}")

def main():
    test_logger_async()
    test_backfill_timeout_import()
    print("\nVerification Complete.")

if __name__ == "__main__":
    main()
