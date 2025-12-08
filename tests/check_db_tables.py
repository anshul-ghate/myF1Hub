import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import get_supabase_client

def check_tables():
    supabase = get_supabase_client()
    
    print("🔍 Checking 'results' table...")
    try:
        res = supabase.table('results').select('*').limit(1).execute()
        print(f"✅ 'results' table found. Rows: {len(res.data)}")
        if res.data:
            print(f"Sample: {res.data[0]}")
    except Exception as e:
        print(f"❌ Error accessing 'results': {e}")

    print("\n🔍 Checking 'race_results' table...")
    try:
        res = supabase.table('race_results').select('*').limit(1).execute()
        print(f"✅ 'race_results' table found. Rows: {len(res.data)}")
        if res.data:
            print(f"Sample keys: {list(res.data[0].keys())}")
            print(f"Sample data: {res.data[0]}")
    except Exception as e:
        print(f"❌ Error accessing 'race_results': {e}")

if __name__ == "__main__":
    check_tables()
