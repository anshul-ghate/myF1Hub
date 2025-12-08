<#
.SYNOPSIS
    Execution script for F1 Analytics App on Windows.
.DESCRIPTION
    Sets up the PYTHONPATH and launches the Streamlit application.
    Ensure you have activated your virtual environment before running.
#>

$ErrorActionPreference = "Stop"

# Get the script's directory
$ScriptDir = $PSScriptRoot

# Set PYTHONPATH to include the project root
$env:PYTHONPATH = "$ScriptDir;$env:PYTHONPATH"

Write-Host "Starting F1 Analytics & Prediction App..." -ForegroundColor Cyan
Write-Host "Project Root: $ScriptDir" -ForegroundColor Gray

# Check if dependencies are installed (simple check)
if (-not (Get-Command "streamlit" -ErrorAction SilentlyContinue)) {
    Write-Warning "Streamlit not found. Installing dependencies..."
    pip install -r "$ScriptDir\requirements.txt"
}

# Run the App
try {
    python -m streamlit run "$ScriptDir\app\main.py"
}
catch {
    Write-Error "Failed to launch app. Please check the error logs."
}
