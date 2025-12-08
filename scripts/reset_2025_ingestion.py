from utils.db import get_supabase_client

def reset_2025():
    supabase = get_supabase_client()
    print("Resetting ingestion_complete for 2025 races...")
    
    res = supabase.table('races').update({'ingestion_complete': False}).eq('season_year', 2025).execute()
    
    print(f"Updated {len(res.data) if res.data else 'unknown'} races.")

if __name__ == "__main__":
    reset_2025()
