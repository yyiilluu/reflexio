# Reflexio Client

Python client library for the Reflexio API. Build agents with persistent memory by automatically extracting and managing user profiles from interactions.

## Key Features

- **User Interaction Management** - Track text, images, and user actions with semantic search
- **Request & Experiment Management** - Organize interactions with request groups for session tracking and context management
- **Automatic Profile Extraction** - Generate user profiles from interactions using configurable prompts
- **Agent Feedback System** - Collect and aggregate feedback from user interactions
- **Agent Performance Evaluation** - Automated evaluation of agent success with improvement suggestions
- **Semantic Search** - Vector-based search across interactions and profiles
- **Flexible Configuration** - Customize storage, profile extraction, and feedback generation

## Installation

```bash
pip install reflexio-client
```

## Quick Start

```python
import reflexio
from reflexio_commons.api_schema.service_schemas import InteractionData, UserActionType

# Initialize with API endpoint
client = reflexio.ReflexioClient(url_endpoint="http://127.0.0.1:8081/")

# Authenticate (API key is automatically set, and never expires)
token = client.login("user@example.com", "password")
# token.api_key contains your API key - save it to skip login in future sessions

# Publish interaction (fire-and-forget by default)
client.publish_interaction(
    user_id="user_123",
    interactions=[
        InteractionData(
            role="User",
            content="I'm interested in your premium plan"
        )
    ],
    request_group="req_001",
    source="chat"
)

# Get all user profiles
profiles = client.get_profiles(user_id="user_123")

# Search relevant profiles
profiles = client.search_profiles(
    user_id="user_123",
    query="premium plan interest",
    threshold=0.7
)

# Get feedback
feedbacks = client.get_feedbacks()
```

## Core Concepts

The following diagram shows how the core data entities relate to each other:

![Data Model Diagram](assets/data-model-diagram.svg)

### Interactions
The most basic unit of data in Reflexio. Each interaction represents a single piece of user activity—text messages, images (base64-encoded), or user actions (clicks, scrolls, etc.). Interactions are the source from which all other outputs (profiles, feedback, evaluations) are generated.

### Requests & Request Groups
A **Request** is what the client sends to Reflexio each time, bundling one or more interactions together with metadata (source, agent version, timestamps). A **Request Group** connects multiple requests under the same context—useful for organizing all requests within a single conversation session. [Learn more →](concepts/requests-and-groups.md)

### User Profiles
Insights automatically extracted from interactions based on your configured profile extractors for each user. Each profile captures specific information about the user (preferences, context, history) and supports semantic search to retrieve relevant user information across conversation history.

### Feedback
Agent-level insights derived from user interactions across all users. Unlike profiles (which are per-user), feedback helps improve the agent itself at a specific version.

The feedback system has two levels: **Raw Feedback** is extracted from individual interactions, capturing specific observations or suggestions. **Aggregated Feedback** combines multiple raw feedbacks (grouped by `feedback_name` and `agent_version`) once a threshold is met, providing actionable insights to improve agent behavior over time.

### Evaluation Results
Automated assessments of agent success or failure for each request. The evaluation system analyzes interactions to determine if the agent achieved its goal, identifies failure types and reasons when unsuccessful, and suggests prompt improvements.

When shadow content is present, the evaluation system also compares regular and shadow responses to measure quality differences and win rates.

### Fire-and-Forget Mode
Methods like `publish_interaction`, `delete_interaction`, `delete_profile`, `delete_request`, and `delete_request_group` support fire-and-forget mode (default) for better performance. Set `wait_for_response=True` to get response data.

## Documentation

### Getting Started
- [Quick Start Guide](getting-started/quickstart.md) - Step-by-step tutorial
- [Installation Guide](getting-started/installation.md) - Setup instructions
- [Configuration Guide](getting-started/configuration.md) - Complete configuration reference

### Core Concepts
- [Interactions](concepts/interactions.md) - Understanding interaction types and patterns
- [Requests & Groups](concepts/requests-and-groups.md) - Request management and session organization
- [User Profiles](concepts/user-profiles.md) - Profile extraction and management
- [Agent Feedback](concepts/agent-feedback.md) - Feedback system and aggregation

### API Reference
- [Client Methods](api-reference/client.md) - Complete method documentation
- [Data Schemas](api-reference/schemas.md) - Request and response models

### Examples
- [User Interactions](examples/user-interactions.md) - Publishing and searching interactions
- [Request Management](examples/request-management.md) - Working with requests and request groups
- [User Profiles](examples/user-profiles.md) - Profile search and management
- [Agent Feedbacks](examples/agent-feedback.md) - Agent self-improving feedbacks
- [Agent Evaluation](examples/agent-evaluation.md) - Analyzing agent performance
