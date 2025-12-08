from utils.db import get_supabase_client

def check_drivers():
    supabase = get_supabase_client()
    print("Checking drivers table...")
    res = supabase.table('drivers').select('count', count='exact').execute()
    print(f"Total drivers: {res.count}")
    
    if res.count > 0:
        res = supabase.table('drivers').select('abbreviation, surname').limit(5).execute()
        print("Sample drivers:", res.data)

if __name__ == "__main__":
    check_drivers()
