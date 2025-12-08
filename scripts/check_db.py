from utils.db import get_supabase_client

def check_db():
    supabase = get_supabase_client()
    
    tables = ['races', 'drivers', 'laps', 'race_results']
    for t in tables:
        try:
            res = supabase.table(t).select('count', count='exact').limit(1).execute()
            print(f"Table '{t}': {res.count} rows")
        except Exception as e:
            print(f"Error checking table '{t}': {e}")

    # Check specific race results
    race_id = '09c16b34-6bc1-4b38-8fd7-f54e9c8c5032' # Sao Paulo
    res = supabase.table('race_results').select('driver_id').eq('race_id', race_id).execute()
    print(f"Drivers in race_results for Sao Paulo: {len(res.data)}")

if __name__ == "__main__":
    check_db()
