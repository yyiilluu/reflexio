#!/bin/bash

# Start first service
uvicorn reflexio.server.api:app --host 0.0.0.0 --port 8081 --reload --reload-include "*.json" &

# Start website
npm run dev --prefix reflexio/website &

# Start mkdocs documentation server
mkdocs serve -f reflexio/public_docs/mkdocs.yml --dev-addr 0.0.0.0:8082 &

# Keep container running
wait
