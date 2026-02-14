#!/bin/bash

# Configurable ports (override via env vars for worktree dev)
BACKEND_PORT=${BACKEND_PORT:-8081}
FRONTEND_PORT=${FRONTEND_PORT:-8080}
DOCS_PORT=${DOCS_PORT:-8082}
export API_BACKEND_URL=${API_BACKEND_URL:-"http://localhost:${BACKEND_PORT}"}

# Start first service
uvicorn reflexio.server.api:app --host 0.0.0.0 --port ${BACKEND_PORT} --reload --reload-include "*.json" &

# Start website
(cd reflexio/website && npx next dev -p ${FRONTEND_PORT}) &

# Start mkdocs documentation server
mkdocs serve -f reflexio/public_docs/mkdocs.yml --dev-addr 0.0.0.0:${DOCS_PORT} &

# Keep container running
wait
