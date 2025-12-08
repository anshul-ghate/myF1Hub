from utils.db import get_supabase_client
import pandas as pd

def debug():
    supabase = get_supabase_client()
    year = 2025
    race_name_pattern = "São Paulo"
    
    print("1. Querying Races...")
    try:
        res = supabase.table('races').select('id, name').eq('season_year', year).ilike('name', f'%{race_name_pattern}%').execute()
        print(f"Found races: {res.data}")
        if not res.data: return
        race_id = res.data[0]['id']
    except Exception as e:
        print(f"Error querying races: {e}")
        return

    print(f"\n2. Querying Results for {race_id}...")
    try:
        res = supabase.table('results').select('driver_id, position, grid').eq('race_id', race_id).execute()
        print(f"Found {len(res.data)} results.")
        if not res.data: return
        driver_ids = [r['driver_id'] for r in res.data]
    except Exception as e:
        print(f"Error querying results: {e}")
        return

    print(f"\n3. Querying Drivers ({len(driver_ids)} IDs)...")
    try:
        res = supabase.table('drivers').select('id, code').in_('id', driver_ids).execute()
        print(f"Found {len(res.data)} drivers.")
    except Exception as e:
        print(f"Error querying drivers: {e}")

if __name__ == "__main__":
    debug()
