"""
F1 PitWall AI - Local Pipeline Runner

A configurable, observable local scheduler for the data pipeline.
This script can be run as a background service to automatically
check for new race data and trigger ingestion/training.

Usage:
  python -m pipelines.local_runner          # Run once
  python -m pipelines.local_runner --daemon # Run as daemon (continuous)
  python -m pipelines.local_runner --status # Check pipeline status
"""

import argparse
import os
import sys
import time
import yaml
from datetime import datetime, timedelta
from pathlib import Path

# Adjust path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.orchestrator import run_pipeline
from utils.db import get_supabase_client
from utils.logger import get_logger

logger = get_logger("LocalPipelineRunner")

# Config path
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    """Load pipeline configuration from YAML file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    else:
        logger.warning(f"Config not found at {CONFIG_PATH}, using defaults")
        return {
            'schedule': {'check_interval_hours': 6},
            'training': {'auto_retrain': True},
            'monitoring': {'log_level': 'INFO'}
        }


def get_pipeline_status():
    """Get current pipeline and database status."""
    supabase = get_supabase_client()
    
    status = {
        'timestamp': datetime.now().isoformat(),
        'database': {},
        'last_ingestion': None,
        'models': {}
    }
    
    # Database counts
    try:
        races = supabase.table('races').select('count', count='exact').execute()
        complete = supabase.table('races').select('count', count='exact').eq('ingestion_status', 'COMPLETE').execute()
        pending = supabase.table('races').select('count', count='exact').eq('ingestion_status', 'PENDING').execute()
        laps = supabase.table('laps').select('count', count='exact').execute()
        results = supabase.table('race_results').select('count', count='exact').execute()
        
        status['database'] = {
            'total_races': races.count,
            'complete_races': complete.count,
            'pending_races': pending.count,
            'total_laps': laps.count,
            'race_results': results.count
        }
        
        # Last ingested race
        last_race = supabase.table('races')\
            .select('name, season_year, round, updated_at')\
            .eq('ingestion_status', 'COMPLETE')\
            .order('updated_at', desc=True)\
            .limit(1)\
            .execute()
        
        if last_race.data:
            status['last_ingestion'] = {
                'race': f"{last_race.data[0]['season_year']} R{last_race.data[0]['round']} - {last_race.data[0]['name']}",
                'updated_at': last_race.data[0].get('updated_at')
            }
            
    except Exception as e:
        logger.error(f"Error getting database status: {e}")
        status['error'] = str(e)
    
    # Model status
    model_paths = [
        'models/saved/hybrid/ranker_model.pkl',
        'models/saved/hybrid/position_model.pkl',
        'models/saved/dynasty_model.pkl'
    ]
    
    for path in model_paths:
        if os.path.exists(path):
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            status['models'][path] = {
                'exists': True,
                'last_modified': mtime.isoformat()
            }
        else:
            status['models'][path] = {'exists': False}
    
    return status


def print_status(status):
    """Pretty print pipeline status."""
    print("\n" + "=" * 50)
    print("🏎️  F1 PITWALL AI - PIPELINE STATUS")
    print("=" * 50)
    print(f"📅 Timestamp: {status['timestamp']}")
    
    print("\n📊 DATABASE:")
    db = status.get('database', {})
    print(f"  Total Races:    {db.get('total_races', 'N/A')}")
    print(f"  Complete:       {db.get('complete_races', 'N/A')}")
    print(f"  Pending:        {db.get('pending_races', 'N/A')}")
    print(f"  Total Laps:     {db.get('total_laps', 'N/A')}")
    print(f"  Race Results:   {db.get('race_results', 'N/A')}")
    
    if status.get('last_ingestion'):
        print(f"\n🏁 LAST INGESTION:")
        print(f"  Race:      {status['last_ingestion']['race']}")
        print(f"  Updated:   {status['last_ingestion'].get('updated_at', 'N/A')}")
    
    print("\n🤖 MODELS:")
    for path, info in status.get('models', {}).items():
        name = Path(path).stem
        if info.get('exists'):
            print(f"  ✅ {name}: {info['last_modified']}")
        else:
            print(f"  ❌ {name}: Not found")
    
    print("=" * 50 + "\n")


def run_once(config):
    """Run the pipeline once."""
    logger.info("🚀 Running pipeline (single execution)...")
    
    try:
        run_pipeline()
        logger.info("✅ Pipeline execution complete")
        return True
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        return False


def run_daemon(config):
    """Run as a daemon, checking on schedule."""
    interval_hours = config.get('schedule', {}).get('check_interval_hours', 6)
    interval_seconds = interval_hours * 3600
    
    logger.info(f"🔄 Starting daemon mode (check every {interval_hours} hours)")
    
    while True:
        try:
            logger.info(f"⏰ Pipeline check at {datetime.now().isoformat()}")
            run_pipeline()
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
        
        logger.info(f"💤 Sleeping for {interval_hours} hours...")
        time.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description="F1 PitWall AI - Local Pipeline Runner")
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (continuous)')
    parser.add_argument('--status', action='store_true', help='Check pipeline status')
    parser.add_argument('--config', type=str, help='Path to config file')
    
    args = parser.parse_args()
    
    # Load config
    config = load_config()
    
    if args.status:
        status = get_pipeline_status()
        print_status(status)
        return
    
    if args.daemon:
        run_daemon(config)
    else:
        run_once(config)


if __name__ == "__main__":
    main()
