#!/bin/bash

# Navigate to the jarvis project root
cd ~/Projects/jarvis

echo "Starting Python Agent Microservice in the background..."
# Run uvicorn in the background, logging to a file to keep the terminal clean
.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8000 > uvicorn.log 2>&1 &
UVICORN_PID=$!

# Give it a second to spin up
sleep 2

echo "Starting Friday Core (Rust Async Client)..."
cd friday_core
cargo run --release

# When the Rust client exits, clean up the Python server
echo "Cleaning up background Python service..."
kill $UVICORN_PID
