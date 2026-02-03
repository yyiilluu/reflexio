# Demo: Conversation Simulator & Viewer

Simulates multi-turn conversations between two LLM agents (customer and support agent), with optional Reflexio or mem0 context injection. Includes a web viewer for live streaming and replaying conversations.

## Files

| File | Description |
|------|-------------|
| `scenarios.py` | Scenario definitions — system prompts, opening messages, and parameters for each simulation |
| `simulate_conversation.py` | Conversation engine — runs customer/agent LLM loop, writes JSONL output |
| `serve_viewer.py` | FastAPI server — serves viewer UI, REST + SSE endpoints for simulation and playback |
| `viewer.html` | Browser UI — live-stream simulations, replay past conversations, publish to Reflexio/mem0 |
| `output/` | Generated JSONL conversation files (gitignored) |

## Quick Start

### CLI simulation

```shell
python demo/simulate_conversation.py
python demo/simulate_conversation.py --scenario request_refund --model gpt-4o --max-turns 20
```

### Web viewer

```shell
uvicorn serve_viewer:app --host 0.0.0.0 --port 8083 --reload --reload-dir demo --app-dir demo
# Open http://localhost:8083
```

## Scenarios

- `devops_backup_failure` — DevOps lead needs help with S3 backup timeouts and monitoring
- `request_refund` — Customer disputes an unrecognized charge and requests a refund
- `restaurant_togo_order` — Customer orders food but has a peanut allergy conflicting with their choice
- `isp_outage_wfh` — Customer already tried basic troubleshooting but agent re-suggests it; area outage is the real cause
- `subscription_cancel_upgrade` — PM wants to cancel but actually needs a team plan they don't know exists
- `language_travel_prep` — Traveler needs practical Japanese phrases in 2 weeks, not a full curriculum
- `coding_interview_help` — Developer preparing for interviews needs problem patterns, not textbook theory
- `investment_short_term` — Saver needs low-risk options for 18-month house down payment, not standard portfolio advice

## Context Injection

The simulator can inject context from external memory systems into the agent's system prompt each turn:

- **Reflexio** — fetches user profiles and agent feedback via `ReflexioClient`
- **mem0** — fetches memories via `MemoryClient` (requires `MEM0_API_KEY` in `.env`)

## API Endpoints (serve_viewer.py)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve viewer HTML |
| GET | `/api/scenarios` | List available scenarios |
| GET | `/api/conversations` | List saved conversation files |
| GET | `/api/conversation/{filename}` | Get turns + scenario for a conversation |
| POST | `/api/simulate` | Run simulation, return filename |
| POST | `/api/simulate/stream` | Run simulation with SSE streaming |
| POST | `/api/reflexio/login` | Login to Reflexio server |
| GET | `/api/reflexio/status` | Check Reflexio login status |
| POST | `/api/reflexio/publish` | Publish conversation to Reflexio |
| POST | `/api/mem0/publish` | Publish conversation to mem0 |
