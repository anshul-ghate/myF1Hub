#!/bin/bash

echo "==================================================="
echo "      F1 Analytics & Prediction App Setup"
echo "==================================================="

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

echo ""
echo "[1/4] Installing Dependencies..."
pip install -r requirements.txt

echo ""
echo "[2/4] Checking Database Connection..."
python3 -c "from utils.db import get_supabase_client; print('Connection OK' if get_supabase_client() else 'Connection Failed')"

echo ""
echo "[3/4] Running Bulk Ingestion & Training (2018-Present)..."
echo "WARNING: This may take a long time. Press Ctrl+C to skip if already done."
sleep 5
python3 data/ingest_bulk.py

echo ""
echo "[4/4] Launching App..."
python3 -m streamlit run app/main.py
