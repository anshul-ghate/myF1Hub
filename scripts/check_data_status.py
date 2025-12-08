from utils.db import get_supabase_client

def check_completed_races():
    supabase = get_supabase_client()
    
    print("Checking for completed races...")
    
    # Check total races
    res = supabase.table('races').select('count', count='exact').execute()
    print(f"Total races in DB: {res.count}")
    
    # Check completed races since 2021
    res = supabase.table('races')\
        .select('count', count='exact')\
        .eq('ingestion_complete', True)\
        .gte('season_year', 2021)\
        .execute()
        
    print(f"Completed races (ingestion_complete=True) since 2021: {res.count}")
    
    if res.count == 0:
        print("⚠️ No completed races found! This explains why training fails.")
        print("Checking if any races have results...")
        
        # Check if any race has results despite ingestion_complete=False
        res = supabase.table('race_results').select('race_id').limit(1).execute()
        if res.data:
            print("✅ Found race_results data. 'ingestion_complete' flag might be missing.")
        else:
            print("❌ No race_results data found either.")

if __name__ == "__main__":
    check_completed_races()
