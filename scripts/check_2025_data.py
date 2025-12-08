from utils.db import get_supabase_client

def check_2025_data():
    supabase = get_supabase_client()
    print("🔍 Checking 2025 Data Integrity...")
    
    # Check Races
    res = supabase.table('races').select('count', count='exact').eq('season_year', 2025).eq('ingestion_complete', True).execute()
    print(f"Completed 2025 Races: {res.count}")
    
    # Check Results for ALL completed races
    races = supabase.table('races').select('id, name').eq('season_year', 2025).eq('ingestion_complete', True).execute()
    
    valid_races = 0
    for race in races.data:
        res = supabase.table('race_results').select('count', count='exact').eq('race_id', race['id']).execute()
        if res.count > 0:
            valid_races += 1
            # print(f"✅ {race['name']}: {res.count} results")
        else:
            pass
            # print(f"❌ {race['name']}: 0 results")
            
    print(f"Races with results: {valid_races} / {len(races.data)}")

if __name__ == "__main__":
    check_2025_data()
