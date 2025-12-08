from data.ingest_data_enhanced import ingest_enhanced_race_data, ingest_qualifying_results
import traceback
import fastf1

def ingest_2025():
    print("🚀 Starting Ingestion for 2025 Season...")
    
    # Get schedule to know how many rounds
    try:
        schedule = fastf1.get_event_schedule(2025)
        rounds = schedule['RoundNumber'].max()
        print(f"Found {rounds} rounds in 2025 schedule.")
    except:
        rounds = 24 # Fallback
        print("Could not fetch schedule, assuming 24 rounds.")
        
    # Ingest all rounds
    for round_num in range(1, rounds + 1):
        try:
            print(f"\n--- Ingesting 2025 Round {round_num} ---")
            ingest_enhanced_race_data(2025, round_num)
            
            # Also ingest qualifying specifically if needed (though enhanced does it mostly)
            # But ingest_qualifying_results is good for the UPCOMING race (Abu Dhabi)
            # Abu Dhabi is likely the last round.
            
        except Exception as e:
            print(f"❌ Failed Round {round_num}: {e}")
            traceback.print_exc()
            
    # Ingest Qualifying for the Final Race (Abu Dhabi)
    # Assuming it's the last round
    print(f"\n--- Ingesting Qualifying for Final Round {rounds} ---")
    try:
        ingest_qualifying_results(2025, rounds)
    except Exception as e:
        print(f"❌ Failed Qualifying Ingestion: {e}")

if __name__ == "__main__":
    from utils.race_utils import get_latest_completed_session
    
    # Check what is the valid latest data
    latest = get_latest_completed_session()
    max_round = 24
    if latest and latest['Year'] == 2025:
        max_valid_round = latest['Round']
        print(f"Latest completed session: Round {max_valid_round} ({latest['Session']})")
    else:
        max_valid_round = 24 # Fallback or if current date is past 2025
        
    print(f"🚀 Starting Ingestion for 2025 Season (Up to Round {max_valid_round} verified)...")
    
    # Ingest loop
    for round_num in range(1, 25): # 24 rounds
        try:
             # Heuristic: Check if this round is in the past
             # We can use our auto_update logic or just try/except
             # Better: iterate all and let the ingest function handle it or catch errors
             # But let's use the robust functions
             
             if round_num > max_valid_round + 1: # Allow +1 for current weekend
                 print(f"Stopping at Round {round_num} (Future).")
                 break
                 
             print(f"\n--- Processing 2025 Round {round_num} ---")
             ingest_enhanced_race_data(2025, round_num)
             
             # Quali check for next race
             if round_num == max_valid_round + 1:
                 print("Checking for Qualifying data for current/next round...")
                 ingest_qualifying_results(2025, round_num)
             
        except Exception as e:
            print(f"ℹ️ Round {round_num} skipped or failed: {e}")
            # Don't print stack trace for future races, expected.
            
    print("\n✅ Ingestion Run Complete.")
