<#
.SYNOPSIS
    Interactive Local Run Script for F1 PitWall AI
.DESCRIPTION
    Simulates a complete first run of the system, walking the user through
    setup, ingestion, training, pipeline automation, and application launch.
#>

function Show-Header {
    Clear-Host
    Write-Host "=================================================================" -ForegroundColor Cyan
    Write-Host "           🏎️  F1 PITWALL AI - COMPLETE SYSTEM RUNNER  🏎️" -ForegroundColor Cyan
    Write-Host "=================================================================" -ForegroundColor Cyan
    Write-Host "Current Directory: $(Get-Location)"
    Write-Host "Date: $(Get-Date)"
    Write-Host "=================================================================`n"
}

function Show-Section {
    param([string]$Title)
    Write-Host "`n>> $Title" -ForegroundColor Yellow
}

function Ask-User {
    param([string]$Question)
    $response = Read-Host "$Question (y/n)"
    return $response -eq 'y' -or $response -eq 'Y'
}

# =================================================================
# 0. PRE-FLIGHT CHECKS
# =================================================================
Show-Header
# Set Python to use UTF-8 for I/O to handle emojis in logs
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Check Environment
Show-Section "Step 0: Pre-flight Checks"
Write-Host "Checking environment..."

if (Get-Command "python" -ErrorAction SilentlyContinue) {
    Write-Host "✅ Python found: $(python --version 2>&1)" -ForegroundColor Green
}
else {
    Write-Host "❌ Python not found! Please install Python 3.10+" -ForegroundColor Red
    exit
}

if (Get-Command "docker" -ErrorAction SilentlyContinue) {
    Write-Host "✅ Docker found: $(docker --version)" -ForegroundColor Green
}
else {
    Write-Host "⚠️  Docker not found. Docker features will be skipped." -ForegroundColor Yellow
}

# Check Database Connection
if (Ask-User "Test Database Connection?") {
    Write-Host "Testing Supabase connection..."
    try {
        # Use simpler quoting to avoid PowerShell/Python string conflicts
        python -c "from utils.db import get_supabase_client; s=get_supabase_client(); print(f'✅ Connected! Races: {s.table('races').select('count', count='exact').execute().count}')"
    }
    catch {
        Write-Host "❌ Database connection failed. Check .env file." -ForegroundColor Red
        if (-not (Ask-User "Continue anyway?")) { exit }
    }
}

# =================================================================
# 1. INFRASTRUCTURE & MONITORING
# =================================================================
Show-Section "Step 1: Infrastructure & Monitoring"

if (Ask-User "Start MLflow Tracking Server (Local)?") {
    Write-Host "Starting MLflow server on http://localhost:5000..."
    # Start in a new window to avoid log spam and process conflicts (WinError 10022)
    $mlflowJob = Start-Process "mlflow" -ArgumentList "ui", "--port", "5000" -PassThru
    Write-Host "✅ MLflow started (PID: $($mlflowJob.Id))" -ForegroundColor Green
    Start-Sleep -Seconds 3
}

# =================================================================
# 2. DATA INGESTION
# =================================================================
Show-Section "Step 2: Data Ingestion"

if (Ask-User "Run BULK Data Ingestion (Historical 2018-2025)?") {
    Write-Host "Starting bulk ingestion... This may take a while." -ForegroundColor Cyan
    python -m data.ingest_bulk
}

if (Ask-User "Run INCREMENTAL Ingestion (Check for recent races)?") {
    Write-Host "Checking for new race data..." -ForegroundColor Cyan
    # Run the orchestrator explicitly once
    python -c "from pipelines.orchestrator import run_pipeline; run_pipeline()"
}

# =================================================================
# 3. MODEL TRAINING
# =================================================================
Show-Section "Step 3: Model Training"

if (Ask-User "Train/Retrain Models (Lap Time & Dynasty Engine)?") {
    Write-Host "Starting model training..." -ForegroundColor Cyan
    python -m scripts.full_retrain
}

# =================================================================
# 4. PIPELINE AUTOMATION
# =================================================================
Show-Section "Step 4: Pipeline Automation"

if (Ask-User "Start Pipeline Daemon (Background Runner)?") {
    Write-Host "Starting local pipeline runner in daemon mode..." -ForegroundColor Cyan
    # Start in a new window so it keeps running
    Start-Process "python" -ArgumentList "-m", "pipelines.local_runner", "--daemon"
    Write-Host "✅ Pipeline daemon started in new window." -ForegroundColor Green
}
else {
    if (Ask-User "Check Pipeline Status?") {
        python -m pipelines.local_runner --status
    }
}

# =================================================================
# 5. APPLICATION LAUNCH
# =================================================================
Show-Section "Step 5: Application Launch"

if (Ask-User "Launch F1 PitWall Streamlit App?") {
    Write-Host "Starting Streamlit App..." -ForegroundColor Cyan
    streamlit run app/main.py
}

Write-Host "`n================================================================="
Write-Host "✅ Run Script Complete." -ForegroundColor Green
Write-Host "================================================================="
Pause
