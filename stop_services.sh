#!/bin/bash

echo "Stopping services..."

# Stop FastAPI server (port 8081)
lsof -t -i:8081 | xargs kill 2>/dev/null && echo "Stopped FastAPI server (8081)" || echo "FastAPI server (8081) not running"

# Stop FastAPI server (port 8000)
lsof -t -i:8000 | xargs kill 2>/dev/null && echo "Stopped service on port 8000" || echo "Port 8000 not in use"

# Stop website
pkill -f "npm run dev" && echo "Stopped website" || echo "Website not running"

# Stop mkdocs
pkill -f "mkdocs serve" && echo "Stopped mkdocs" || echo "MkDocs not running"

echo "All services stopped."
