from utils.db import get_supabase_client

def check_integrity():
    supabase = get_supabase_client()
    print("Checking race_results integrity...")
    
    # Get all completed races since 2021
    races = supabase.table('races')\
        .select('id, name, season_year')\
        .eq('ingestion_complete', True)\
        .eq('season_year', 2024)\
        .execute()
        
    if not races.data:
        print("No completed races found.")
        return

    print(f"Found {len(races.data)} completed races.")
    
    valid_races = 0
    empty_races = 0
    
    for race in races.data:
        # Check if results exist
        res = supabase.table('race_results').select('driver_id', count='exact').eq('race_id', race['id']).limit(1).execute()
        if res.count > 0:
            valid_races += 1
        else:
            empty_races += 1
            if empty_races <= 5:
                print(f"⚠️ Empty results for: {race['name']} ({race['season_year']})")
                
    print(f"\nSummary:")
    print(f"Valid Races (with results): {valid_races}")
    print(f"Empty Races (no results): {empty_races}")

if __name__ == "__main__":
    check_integrity()
