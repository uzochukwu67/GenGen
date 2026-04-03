#!/bin/bash

echo "🔧 Installing GenLayer AI Prediction Markets Dependencies..."
echo ""

# Install Python dependencies for relayer
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install

echo ""
echo "✅ All dependencies installed!"
echo ""
echo "🚀 To start the system:"
echo "1. Frontend: cd frontend && npm run dev"
echo "2. Relayer: cd relayer && python relayer_keeper.py"
echo ""
echo "🌐 Frontend will be available at: http://localhost:3000"