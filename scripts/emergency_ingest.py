from data.ingest_data_enhanced import ingest_enhanced_race_data
import traceback

def emergency_ingest():
    print("🚨 Starting Emergency Ingestion for 2024 (Rounds 1-5)...")
    
    for round_num in range(1, 6):
        try:
            print(f"\n--- Ingesting 2024 Round {round_num} ---")
            ingest_enhanced_race_data(2024, round_num)
            print(f"✅ Finished Round {round_num}")
        except Exception as e:
            print(f"❌ Failed Round {round_num}: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    emergency_ingest()
