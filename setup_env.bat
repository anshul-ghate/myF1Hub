@echo off
TITLE F1 Analytics App - Setup & Update

echo ===================================================
echo       F1 Analytics & Prediction App Setup
echo ===================================================

echo.
echo [1/4] Installing Dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 goto :error

echo.
echo [2/4] Checking Database Connection...
python -c "from utils.db import get_supabase_client; print('Connection OK' if get_supabase_client() else 'Connection Failed')"
if %errorlevel% neq 0 goto :error

echo.
echo [3/4] Running Bulk Ingestion & Training (2018-Present)...
echo WARNING: This may take a long time. Press Ctrl+C to skip if already done.
timeout /t 5
set PYTHONPATH=%~dp0
python data/ingest_bulk.py

echo.
echo [4/4] Launching App...
python -m streamlit run app/main.py

goto :eof

:error
echo.
echo [ERROR] An error occurred. Please check the logs above.
pause
