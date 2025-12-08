<#
.SYNOPSIS
    First-time setup and execution script for F1 Analytics App.
.DESCRIPTION
    Handles virtual environment creation, dependencies, environment configuration, database ingestion, and launching the app.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

# --- Helper Function for Colors ---
function Print-Info ($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Print-Success ($msg) { Write-Host "[SUCCESS] $msg" -ForegroundColor Green }
function Print-Warning ($msg) { Write-Host "[WARNING] $msg" -ForegroundColor Yellow }
function Print-Error ($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

Clear-Host
Print-Info "Welcome to the F1 Analytics & Prediction App Helper!"
Print-Info "This script will prepare your environment and launch the application."
Write-Host ""

# --- 1. Python Check ---
Print-Info "Checking for Python..."
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Print-Error "Python is not installed or not in your PATH. Please install Python 3.9+."
    exit 1
}
$pyVer = python --version 2>&1
Print-Success "Found $pyVer"

# --- 2. Virtual Environment Setup ---
$VenvDir = Join-Path $ScriptDir ".venv"
$PythonCmd = "python" # Default fallback
if (-not (Test-Path $VenvDir)) {
    Print-Info "Creating virtual environment at $VenvDir..."
    try {
        python -m venv $VenvDir
        Print-Success "Virtual environment created."
    }
    catch {
        Print-Error "Failed to create virtual environment."
        exit 1
    }
}
else {
    Print-Info "Virtual environment already exists."
}

# Determine correct python executable path
if (Test-Path (Join-Path $VenvDir "Scripts\python.exe")) {
    $PythonCmd = Join-Path $VenvDir "Scripts\python.exe"
    $PipCmd = Join-Path $VenvDir "Scripts\pip.exe"
}
elseif (Test-Path (Join-Path $VenvDir "bin/python")) {
    $PythonCmd = Join-Path $VenvDir "bin/python"
    $PipCmd = Join-Path $VenvDir "bin/pip"
}
else {
    Print-Error "Could not locate python in expected venv paths. using system python."
    $PythonCmd = "python"
    $PipCmd = "pip"
}

# --- 3. Dependencies ---
Print-Info "Installing/Updating dependencies..."

# Check for corrupted packages (common issue on Windows)
$SitePackages = Join-Path $VenvDir "Lib\site-packages"
if (Test-Path $SitePackages) {
    $Corrupted = Get-ChildItem -Path $SitePackages -Filter "~*" -ErrorAction SilentlyContinue
    if ($Corrupted) {
        Print-Warning "Found corrupted packages (~ directories). Cleaning them up..."
        $Corrupted | Remove-Item -Recurse -Force
    }
}

try {
    # Install dependencies quietly to avoid buffer overflow in some terminals, but show errors
    $proc = Start-Process -FilePath $PipCmd -ArgumentList "install", "-r", "$ScriptDir\requirements.txt" -NoNewWindow -PassThru -Wait
    
    if ($proc.ExitCode -eq 0) {
        Print-Success "Dependencies installed."
    }
    else {
        throw "Pip install failed with exit code $($proc.ExitCode)" 
    }
}
catch {
    Print-Error "Failed to install dependencies. Ensure you have internet access."
    exit 1
}

# --- 4. Environment Configuration (.env) ---
$EnvFile = Join-Path $ScriptDir ".env"
$EnvExample = Join-Path $ScriptDir ".env.example"

if (-not (Test-Path $EnvFile)) {
    Print-Warning ".env file not found."
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Print-Success "Created .env from example."
        Print-Warning "CRITICAL: You must now update the .env file with your Supabase credentials!"
        Print-Warning "The script will pause. Please edit $EnvFile and then press Enter."
        # Open the file if possible, or just wait
        if (Get-Command "notepad" -ErrorAction SilentlyContinue) {
            notepad $EnvFile
        }
        Read-Host "Press Enter to continue after editing .env..."
    }
    else {
        Print-Error ".env.example missing! Please create .env manually."
        exit 1
    }
}
Print-Info "This checks for missing race data and downloads it. Takes time on first run."
$choice = Read-Host "Run Ingestion? (Y/N) [Default: Y]"
if ($choice -eq "" -or $choice -match "^[Yy]") {
    Print-Info "Running Ingestion... (This window may stay open for a while)"
    try {
        & $PythonCmd "$ScriptDir\data\ingest_bulk.py"
        Print-Success "Ingestion process finished."
    }
    catch {
        Print-Error "Ingestion script encountered an error."
    }
}
else {
    Print-Info "Skipping ingestion."
}

# --- 7. Launch App ---
Write-Host ""
Print-Success "Setup Complete! Launching Application..."
try {
    & $PythonCmd -m streamlit run "$ScriptDir\app\main.py"
}
catch {
    Print-Error "Failed to launch Streamlit app."
    Read-Host "Press Enter to exit..."
}
