#!/bin/bash

echo "Stopping services..."

# Stop FastAPI server (port 8081)
PIDS=$(lsof -t -i:8081 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs kill 2>/dev/null
    sleep 1
    # Force kill any survivors (uvicorn reload workers can ignore SIGTERM)
    PIDS=$(lsof -t -i:8081 2>/dev/null)
    [ -n "$PIDS" ] && echo "$PIDS" | xargs kill -9 2>/dev/null
    echo "Stopped FastAPI server (8081)"
else
    echo "FastAPI server (8081) not running"
fi

# Stop FastAPI server (port 8000)
PIDS=$(lsof -t -i:8000 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs kill 2>/dev/null
    sleep 1
    PIDS=$(lsof -t -i:8000 2>/dev/null)
    [ -n "$PIDS" ] && echo "$PIDS" | xargs kill -9 2>/dev/null
    echo "Stopped service on port 8000"
else
    echo "Port 8000 not in use"
fi

# Stop website
pkill -f "npm run dev" && echo "Stopped website" || echo "Website not running"

# Stop mkdocs
pkill -f "mkdocs serve" && echo "Stopped mkdocs" || echo "MkDocs not running"

echo "All services stopped."
