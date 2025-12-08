from utils.db import get_supabase_client

def check_2024_data():
    supabase = get_supabase_client()
    print("🔍 Checking 2024 Data Integrity...")
    
    # Get 2024 Round 1 Race ID
    res = supabase.table('races').select('id, name').eq('season_year', 2024).eq('round', 1).execute()
    if not res.data:
        print("❌ 2024 Round 1 Race NOT found in 'races' table.")
        return
        
    race = res.data[0]
    race_id = race['id']
    print(f"✅ Found Race: {race['name']} (ID: {race_id})")
    
    # Check Results
    res = supabase.table('race_results').select('count', count='exact').eq('race_id', race_id).execute()
    print(f"   Results count: {res.count}")
    
    # Check Laps
    res = supabase.table('laps').select('count', count='exact').eq('race_id', race_id).execute()
    print(f"   Laps count: {res.count}")
    
    # Check Weather
    res = supabase.table('weather').select('count', count='exact').eq('race_id', race_id).execute()
    print(f"   Weather count: {res.count}")
    
    # Check Pit Stops
    res = supabase.table('pit_stops').select('count', count='exact').eq('race_id', race_id).execute()
    print(f"   Pit Stops count: {res.count}")

if __name__ == "__main__":
    check_2024_data()
