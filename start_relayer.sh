#!/bin/bash

# Start the GenLayer Oracle Relayer
# This script monitors markets and delivers AI verdicts to EVM chains

echo "🚀 Starting GenLayer Oracle Relayer..."
echo "Monitoring Oracle Hub: 0x5286D78605d6D255A2FfF4911cC57ef35692e461"
echo "Delivering to Polygon Amoy: 0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79"
echo ""

cd /workspaces/GenGen/relayer
python relayer_keeper.py