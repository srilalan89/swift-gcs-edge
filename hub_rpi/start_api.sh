#!/bin/bash
# Script to start the Flask API in the background

echo "Starting Hub Manager Flask API..."
cd "$(dirname "$0")"
nohup python3 hub_manager_api.py > api.log 2>&1 &
echo "API started. Check 'api.log' for details."
