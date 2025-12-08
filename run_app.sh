#!/bin/bash

# Synopsis: Execution script for F1 Analytics App on Linux/macOS.
# Description: Sets up the PYTHONPATH and launches the Streamlit application.

set -e

# Get the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Set PYTHONPATH to include the project root
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

echo -e "\033[0;36m🏎️  Starting F1 Analytics & Prediction App...\033[0m"
echo -e "\033[0;90m📂 Project Root: $SCRIPT_DIR\033[0m"

# Check if dependencies are installed
if ! command -v streamlit &> /dev/null; then
    echo -e "\033[0;33mStreamlit not found. Installing dependencies...\033[0m"
    pip install -r "$SCRIPT_DIR/requirements.txt"
fi

# Run the App
python3 -m streamlit run "$SCRIPT_DIR/app/main.py"
