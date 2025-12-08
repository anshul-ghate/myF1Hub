from models.enhanced_features import F1FeatureEngineer
from utils.db import get_supabase_client
import traceback

def debug_features():
    print("🔍 Debugging Feature Engineering...")
    supabase = get_supabase_client()
    
    # Get one completed race
    res = supabase.table('races')\
        .select('id, name, season_year')\
        .eq('ingestion_complete', True)\
        .gte('season_year', 2023)\
        .limit(1)\
        .execute()
        
    if not res.data:
        print("❌ No completed races found.")
        return
        
    race = res.data[0]
    print(f"Testing with race: {race['name']} ({race['season_year']}) ID: {race['id']}")
    
    engineer = F1FeatureEngineer()
    
    try:
        print("Building training dataset...")
        X, y, metadata = engineer.build_training_dataset([race['id']], include_target=True)
        
        if X.empty:
            print("❌ Resulting X is empty.")
        else:
            print(f"✅ Success! Generated {len(X)} samples.")
            print("Columns:", X.columns.tolist())
            print("Sample:", X.iloc[0].to_dict())
            
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    with open('debug_log.txt', 'w', encoding='utf-8') as f:
        sys.stdout = f
        sys.stderr = f
        debug_features()
