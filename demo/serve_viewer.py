"""
FastAPI server for the Conversation Viewer demo UI.

Serves the viewer HTML and provides API endpoints for listing, viewing,
simulating, and deleting conversation JSONL files.

Usage:
    python demo/serve_viewer.py
    # Open http://localhost:8083
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

# Load demo/.env for MEM0_API_KEY etc.
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# Add demo/ to path so we can import sibling modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from reflexio.reflexio_client.reflexio import InteractionData, ReflexioClient
from scenarios import SCENARIOS
from simulate_conversation import simulate, simulate_stream

logger = logging.getLogger(__name__)

app = FastAPI(title="Conversation Viewer")

DEMO_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = DEMO_DIR / "output"
VIEWER_HTML = DEMO_DIR / "viewer.html"

# Module-level Reflexio client state
reflexio_client: Optional[ReflexioClient] = None


def match_scenario(filename: str) -> dict | None:
    """
    Match a JSONL filename to a scenario by checking if the filename starts with a scenario key.

    Args:
        filename (str): The JSONL filename (e.g. 'devops_backup_failure_20260131_234439.jsonl')

    Returns:
        dict | None: Scenario data dict if matched, None otherwise
    """
    for key, scenario in SCENARIOS.items():
        if filename.startswith(key):
            return {
                "key": key,
                "name": scenario.name,
                "description": scenario.description,
                "agent_system_prompt": scenario.agent_system_prompt,
                "customer_system_prompt": scenario.customer_system_prompt,
                "customer_opening_message": scenario.customer_opening_message,
                "max_turns": scenario.max_turns,
            }
    return None


@app.get("/")
async def serve_viewer():
    """Serve the viewer HTML page."""
    return FileResponse(VIEWER_HTML, media_type="text/html")


@app.get("/api/scenarios")
async def list_scenarios():
    """Return available simulation scenarios."""
    return JSONResponse(
        [
            {"key": key, "name": scenario.name, "description": scenario.description}
            for key, scenario in SCENARIOS.items()
        ]
    )


@app.get("/api/conversations")
async def list_conversations():
    """
    List all conversation JSONL files in the output directory.
    Returns filename, scenario name, description, timestamp, and turn count.
    Sorted most-recent first.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conversations = []

    for filepath in OUTPUT_DIR.glob("*.jsonl"):
        turn_count = 0
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    turn_count += 1

        scenario = match_scenario(filepath.name)
        # Extract timestamp from filename: scenario_YYYYMMDD_HHMMSS.jsonl
        timestamp = None
        stem = filepath.stem
        parts = stem.rsplit("_", 2)
        if len(parts) >= 3:
            try:
                ts_str = f"{parts[-2]}_{parts[-1]}"
                dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                timestamp = dt.isoformat()
            except ValueError:
                pass

        conversations.append(
            {
                "filename": filepath.name,
                "scenario_name": scenario["name"] if scenario else "unknown",
                "description": scenario["description"] if scenario else "",
                "timestamp": timestamp or filepath.stat().st_mtime,
                "turn_count": turn_count,
            }
        )

    conversations.sort(key=lambda c: c["timestamp"], reverse=True)
    return JSONResponse(conversations)


@app.get("/api/conversation/{filename}")
async def get_conversation(filename: str):
    """
    Return the turns array and matched scenario object for a conversation file.
    Validates against path traversal.
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = OUTPUT_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Conversation not found")

    turns = []
    with open(filepath) as f:
        for line in f:
            if line.strip():
                turns.append(json.loads(line))

    scenario = match_scenario(filename)
    return JSONResponse({"turns": turns, "scenario": scenario})


class SimulateRequest(BaseModel):
    scenario: str = "devops_backup_failure"
    model: str = "gpt-4o-mini"
    max_turns: int = 30
    reflexio_enabled: bool = False
    reflexio_user_id: str = ""
    reflexio_agent_version: str = "demo-v1"
    mem0_enabled: bool = False
    mem0_user_id: str = ""


def _build_reflexio_config(req: SimulateRequest) -> dict | None:
    """
    Build a reflexio_config dict from a SimulateRequest if Reflexio is enabled and client is logged in.

    Args:
        req (SimulateRequest): The simulation request

    Returns:
        dict | None: Config dict with client/user_id/agent_version, or None
    """
    if not req.reflexio_enabled or reflexio_client is None:
        return None
    return {
        "client": reflexio_client,
        "user_id": req.reflexio_user_id,
        "agent_version": req.reflexio_agent_version,
    }


def _build_mem0_config(req: SimulateRequest) -> dict | None:
    """
    Build a mem0_config dict from a SimulateRequest if mem0 is enabled and API key is available.

    Args:
        req (SimulateRequest): The simulation request

    Returns:
        dict | None: Config dict with api_key and user_id, or None
    """
    if not req.mem0_enabled:
        return None
    api_key = os.getenv("MEM0_API_KEY")
    if not api_key:
        return None
    return {
        "api_key": api_key,
        "user_id": req.mem0_user_id,
    }


@app.post("/api/simulate")
async def run_simulation(req: SimulateRequest):
    """
    Run a new conversation simulation using the specified scenario and model.
    Returns the new filename so the UI can load it.
    """
    if req.scenario not in SCENARIOS:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}")

    try:
        rc = _build_reflexio_config(req)
        mc = _build_mem0_config(req)
        output_path = simulate(
            req.scenario,
            req.model,
            req.max_turns,
            None,
            reflexio_config=rc,
            mem0_config=mc,
        )
        return JSONResponse({"filename": output_path.name})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulate/stream")
async def run_simulation_stream(req: SimulateRequest):
    """
    Run a conversation simulation and stream each turn as a Server-Sent Event.

    Event types:
    - scenario: scenario metadata (sent first)
    - turn: each conversation turn as it's generated
    - done: final event with the output filename
    - error: if something fails mid-stream
    """
    if req.scenario not in SCENARIOS:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}")

    rc = _build_reflexio_config(req)
    mc = _build_mem0_config(req)

    def event_generator():
        try:
            for item in simulate_stream(
                req.scenario,
                req.model,
                req.max_turns,
                reflexio_config=rc,
                mem0_config=mc,
            ):
                event_type = item["event"]
                data = json.dumps(item)
                yield f"event: {event_type}\ndata: {data}\n\n"
        except Exception as e:
            error_data = json.dumps({"event": "error", "message": str(e)})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- Reflexio endpoints ---


class ReflexioLoginRequest(BaseModel):
    email: str
    password: str
    reflexio_url: str = "http://localhost:8081"


class ReflexioPublishRequest(BaseModel):
    filename: str
    user_id: str
    agent_version: str = "demo-v1"
    source: str = ""


@app.post("/api/reflexio/login")
async def reflexio_login(req: ReflexioLoginRequest):
    """
    Login to a Reflexio server and store the client for subsequent operations.
    """
    global reflexio_client
    try:
        client = ReflexioClient(url_endpoint=req.reflexio_url)
        client.login(req.email, req.password)
        reflexio_client = client
        return JSONResponse({"success": True})
    except Exception as e:
        logger.warning(f"Reflexio login failed: {e}")
        raise HTTPException(status_code=401, detail=f"Login failed: {e}")


@app.get("/api/reflexio/status")
async def reflexio_status():
    """Return whether a Reflexio client is currently logged in."""
    return JSONResponse({"logged_in": reflexio_client is not None})


@app.post("/api/reflexio/publish")
async def reflexio_publish(req: ReflexioPublishRequest):
    """
    Publish a conversation's turns as interactions to Reflexio.
    """
    if reflexio_client is None:
        raise HTTPException(status_code=401, detail="Not logged in to Reflexio")

    if "/" in req.filename or "\\" in req.filename or ".." in req.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = OUTPUT_DIR / req.filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Conversation file not found")

    try:
        interactions = []
        with open(filepath) as f:
            for line in f:
                if not line.strip():
                    continue
                turn = json.loads(line)
                role = "User" if turn["role"] == "customer" else "Assistant"
                interactions.append(InteractionData(role=role, content=turn["content"]))

        reflexio_client.publish_interaction(
            user_id=req.user_id,
            interactions=interactions,
            source=req.source,
            agent_version=req.agent_version,
            wait_for_response=True,
        )
        return JSONResponse(
            {"success": True, "message": f"Published {len(interactions)} interactions"}
        )
    except Exception as e:
        logger.warning(f"Reflexio publish failed: {e}")
        raise HTTPException(status_code=500, detail=f"Publish failed: {e}")


# --- mem0 endpoints ---


class Mem0PublishRequest(BaseModel):
    filename: str
    user_id: str = "demo-user"


@app.post("/api/mem0/publish")
async def mem0_publish(req: Mem0PublishRequest):
    """
    Publish all interactions from a conversation to mem0 as memories.

    Args:
        req (Mem0PublishRequest): The publish request with filename and user_id
    """
    api_key = os.getenv("MEM0_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="MEM0_API_KEY not configured in demo/.env"
        )

    if "/" in req.filename or "\\" in req.filename or ".." in req.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = OUTPUT_DIR / req.filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Conversation file not found")

    try:
        from mem0 import MemoryClient

        client = MemoryClient(api_key=api_key)

        # Read conversation turns and format as messages
        messages = []
        with open(filepath) as f:
            for line in f:
                if not line.strip():
                    continue
                turn = json.loads(line)
                role = "user" if turn["role"] == "customer" else "assistant"
                messages.append({"role": role, "content": turn["content"]})

        if not messages:
            raise HTTPException(
                status_code=400, detail="No interactions found in conversation"
            )

        result = client.add(
            messages, user_id=req.user_id, version="v2", output_format="v1.1"
        )
        return JSONResponse(
            {
                "success": True,
                "message": f"Published {len(messages)} messages to mem0",
                "result": result,
            }
        )
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="mem0ai package not installed. Run: pip install mem0ai",
        )
    except Exception as e:
        logger.warning(f"mem0 publish failed: {e}")
        raise HTTPException(status_code=500, detail=f"Publish failed: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "serve_viewer:app",
        host="0.0.0.0",
        port=8083,
        reload=True,
        reload_dirs=[str(DEMO_DIR)],
    )
