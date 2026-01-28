# API Reference

Complete documentation for the Reflexio client class and its methods.

---

## Table of Contents

- [ReflexioClient](#reflexioclient)
- [Authentication](#authentication)
- [Interaction Management](#interaction-management)
- [Request Management](#request-management)
- [Profile Management](#profile-management)
- [Configuration Management](#configuration-management)
- [Feedback Management](#feedback-management)
- [Agent Evaluation](#agent-evaluation)
- [Rerun and Manual Generation Operations](#rerun-and-manual-generation-operations)
- [Enums Reference](#enums-reference)
- [Notes](#notes)

---

## ReflexioClient

The main client class for interacting with the Reflexio API.

### Initialization

```python
from reflexio import ReflexioClient

client = ReflexioClient(api_key="", url_endpoint="")
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | str | No | `""` | API key for authentication. Can be set later via `client.api_key` |
| `url_endpoint` | str | No | Production URL | API endpoint URL |

**Examples:**

```python
# Initialize with endpoint, authenticate later
client = ReflexioClient(url_endpoint="http://127.0.0.1:8081/")

# Initialize with a previously saved API key (from token.api_key)
client = ReflexioClient(
    api_key="<your_saved_token.api_key>",  # From a previous login
    url_endpoint="http://127.0.0.1:8081/"
)
```

---

## Authentication

### `login`

Authenticate with the Reflexio API using email and password. The client automatically stores the API key after successful login.

```python
token = client.login(email, password)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | str | Yes | User email address |
| `password` | str | Yes | User password |

**Returns:** `Token` object

| Field | Type | Description |
|-------|------|-------------|
| `api_key` | str | Authentication token (never expires) |
| `token_type` | str | Type of token (e.g., "bearer") |

**Note:** After calling `login()`, the client automatically sets the API key internally. You don't need to manually assign it. The returned API key **never expires**, so you can save it and initialize the client directly with the `api_key` parameter for efficiency (avoiding the login call on subsequent sessions).

**Example:**

```python
# First-time login - client automatically stores the API key
token = client.login("user@example.com", "password")
print(f"Authenticated! Save token.api_key for future use: {token.api_key}")

# For subsequent sessions, initialize with the saved token.api_key (more efficient)
client = ReflexioClient(
    api_key=token.api_key,  # Use the saved token.api_key from a previous login
    url_endpoint="http://127.0.0.1:8081/"
)
# No login needed - ready to use immediately
```

---

## Interaction Management

### `publish_interaction`

Publish user interactions to the system. This is the primary method for sending data to Reflexio.

```python
response = client.publish_interaction(
    user_id,
    interactions,
    source="",
    agent_version="",
    request_group=None,
    wait_for_response=False
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | str | Yes | - | Unique identifier for the user |
| `interactions` | list[dict] | Yes | - | List of interaction dicts (see Interaction Dict Fields below) |
| `source` | str | No | `""` | Source category (e.g., "chat", "email", "support"), which can trigger specific profile extractor if set |
| `agent_version` | str | No | `""` | Version string for tracking agent iterations |
| `request_group` | str | No | `None` | Groups related requests together |
| `wait_for_response` | bool | No | `False` | If `True`, waits for server confirmation |

**Returns:**
- `PublishUserInteractionResponse` if `wait_for_response=True`
- `None` if `wait_for_response=False` (fire-and-forget mode)

#### Interaction Dict Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `role` | str | No | `"User"` | Role of the interaction participant: `"User"`, `"Agent"`, or `"System"` |
| `content` | str | No | `""` | Text content of the interaction |
| `shadow_content` | str | No | `""` | Alternative agent response for A/B testing and comparison (see [Shadow Content](schemas.md#shadow-content)) |
| `image_encoding` | str | No | `None` | Base64-encoded image data |
| `user_action` | str | No | `"NONE"` | Type of user action: `"NONE"`, `"CLICK"`, `"SCROLL"`, `"TYPE"` |
| `user_action_description` | str | No | `None` | Description of the user action |
| `interacted_image_url` | str | No | `None` | URL of any associated image |

#### PublishUserInteractionResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the publication was successful |
| `message` | str | Additional information about the operation |

#### Example 1: Basic Text Conversation

```python
# Simple conversation (fire-and-forget)
client.publish_interaction(
    user_id="user_123",
    interactions=[
        {"role": "User", "content": "What's the weather like?"},
        {"role": "Agent", "content": "It's sunny and 72°F today."}
    ],
    source="chat",
    request_group="session_001"
)
```

#### Example 2: Wait for Confirmation

```python
# Wait for server response
response = client.publish_interaction(
    user_id="user_123",
    interactions=[
        {"role": "User", "content": "I want to upgrade my plan"}
    ],
    source="support",
    wait_for_response=True
)

if response.success:
    print(f"Published successfully: {response.message}")
```

#### Example 3: Multi-Turn Conversation with Agent Version

```python
# Track which agent version handled the interaction
client.publish_interaction(
    user_id="customer_456",
    interactions=[
        {"role": "User", "content": "I need help choosing a laptop"},
        {"role": "Agent", "content": "I'd be happy to help! What's your budget?"},
        {"role": "User", "content": "Around $1000 for programming work"},
        {"role": "Agent", "content": "For programming, I recommend the ThinkPad X1..."}
    ],
    source="sales_chat",
    agent_version="v2.1.0",
    request_group="purchase_flow_789"
)
```

#### Example 4: Image Interactions

```python
import base64

def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# User shares an image
client.publish_interaction(
    user_id="user_123",
    interactions=[
        {
            "role": "User",
            "content": "What do you think of this outfit?",
            "image_encoding": encode_image("outfit.jpg")
        },
        {
            "role": "Agent",
            "content": "Great choice! The colors complement each other well."
        }
    ],
    source="styling_consultation",
    request_group="style_session_001"
)
```

#### Example 5: User Action Tracking

```python
# Track user behavior on your platform
client.publish_interaction(
    user_id="shopper_789",
    interactions=[
        {
            "user_action": "CLICK",
            "user_action_description": "Clicked 'Add to Cart' for MacBook Pro",
            "interacted_image_url": "https://store.com/products/macbook-pro.jpg"
        },
        {
            "user_action": "SCROLL",
            "user_action_description": "Scrolled through laptop accessories"
        }
    ],
    source="ecommerce",
    request_group="shopping_session_001"
)
```

---

### `search_interactions`

Search for user interactions using semantic queries.

```python
response = client.search_interactions(
    user_id="user_123",
    query="laptop recommendations",
    top_k=5,
    most_recent_k=10
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | str | Yes | - | Identifier of the user to search |
| `request_id` | str | No | `None` | Filter by specific request ID |
| `query` | str | No | `None` | Semantic search query |
| `start_time` | datetime | No | `None` | Filter by start time |
| `end_time` | datetime | No | `None` | Filter by end time |
| `top_k` | int | No | `None` | Maximum number of results to return |
| `most_recent_k` | int | No | `None` | Return most recent k interactions |

#### SearchInteractionResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the search was successful |
| `interactions` | list[Interaction] | List of matching interactions |
| `msg` | str | Additional message (optional) |

#### Interaction Schema (Returned Object)

| Field | Type | Description |
|-------|------|-------------|
| `interaction_id` | str | Unique identifier for the interaction |
| `user_id` | str | Identifier of the user |
| `request_id` | str | Identifier of the request |
| `created_at` | int | Unix timestamp when interaction was created |
| `role` | str | Role of the interaction participant |
| `content` | str | Text content of the interaction |
| `user_action` | str | Type of user action |
| `user_action_description` | str | Description of the user action |
| `interacted_image_url` | str | URL of any associated image |
| `image_encoding` | str | Base64 encoded image data |
| `embedding` | list[float] | Vector embedding of the interaction |

**Example:**

```python
# Search for interactions using kwargs
response = client.search_interactions(
    user_id="user_123",
    query="laptop recommendations budget",
    top_k=10
)

for interaction in response.interactions:
    print(f"[{interaction.role}]: {interaction.content}")
    print(f"  Request ID: {interaction.request_id}")
    print(f"  Created at: {interaction.created_at}")

# Search with time filter
from datetime import datetime, timedelta

response = client.search_interactions(
    user_id="user_123",
    query="product preferences",
    start_time=datetime.now() - timedelta(days=7),
    top_k=20
)

# Get most recent interactions without semantic search
response = client.search_interactions(
    user_id="user_123",
    most_recent_k=10
)
```

---

### `get_interactions`

Retrieve user interactions without semantic search.

```python
response = client.get_interactions(
    user_id="user_123",
    top_k=50
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | str | Yes | - | Identifier of the user to query |
| `start_time` | datetime | No | `None` | Filter by start time |
| `end_time` | datetime | No | `None` | Filter by end time |
| `top_k` | int | No | `30` | Maximum number of results to return |

#### GetInteractionsResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the request was successful |
| `interactions` | list[Interaction] | List of interactions |
| `msg` | str | Additional message (optional) |

**Example:**

```python
# Get recent interactions using kwargs
response = client.get_interactions(
    user_id="user_123",
    top_k=50
)

print(f"Found {len(response.interactions)} interactions")

# Get interactions within a time range
from datetime import datetime, timedelta

response = client.get_interactions(
    user_id="user_123",
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now(),
    top_k=100
)

for interaction in response.interactions:
    print(f"[{interaction.created_at}] {interaction.role}: {interaction.content[:50]}...")
```

---

### `delete_interaction`

Delete a specific user interaction.

```python
response = client.delete_interaction(
    user_id,
    interaction_id,
    wait_for_response=False
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | str | Yes | - | User identifier |
| `interaction_id` | str | Yes | - | Interaction ID to delete |
| `wait_for_response` | bool | No | `False` | Wait for confirmation |

#### DeleteUserInteractionResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the deletion was successful |
| `message` | str | Additional information about the operation |

**Example:**

```python
# Fire-and-forget deletion
client.delete_interaction(
    user_id="user_123",
    interaction_id="int_456"
)

# Wait for confirmation
response = client.delete_interaction(
    user_id="user_123",
    interaction_id="int_456",
    wait_for_response=True
)
if response.success:
    print(f"Deleted successfully: {response.message}")
else:
    print(f"Deletion failed: {response.message}")
```

---

## Request Management

### `get_requests`

Get requests with their associated interactions, grouped by request_group.

```python
response = client.get_requests(
    user_id="user_123",
    top_k=50
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | str | No | `None` | Filter by user ID |
| `request_id` | str | No | `None` | Filter by specific request ID |
| `start_time` | datetime | No | `None` | Filter by start time |
| `end_time` | datetime | No | `None` | Filter by end time |
| `top_k` | int | No | `30` | Maximum number of results to return |

#### GetRequestsResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the request was successful |
| `request_groups` | list[RequestGroup] | List of request groups with their requests |
| `msg` | str | Additional message (optional) |

#### RequestGroup Schema

| Field | Type | Description |
|-------|------|-------------|
| `request_group` | str | The request group identifier |
| `requests` | list[RequestData] | List of requests in this group |

#### RequestData Schema

| Field | Type | Description |
|-------|------|-------------|
| `request` | Request | The request object |
| `interactions` | list[Interaction] | List of interactions in this request |

#### Request Schema

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | str | Unique identifier for the request |
| `user_id` | str | Identifier of the user |
| `created_at` | int | Unix timestamp when request was created |
| `source` | str | Source of the request (e.g., "web_app", "mobile_app") |
| `agent_version` | str | Version of the agent that generated this request |
| `request_group` | str | Group identifier for related requests |

**Example:**

```python
# Get all requests for a user using kwargs
response = client.get_requests(
    user_id="user_123",
    top_k=50
)

for group in response.request_groups:
    print(f"Group: {group.request_group}")
    for req_data in group.requests:
        print(f"  Request: {req_data.request.request_id}")
        print(f"  Agent Version: {req_data.request.agent_version}")
        print(f"  Interactions: {len(req_data.interactions)}")

# Get requests within a time range
from datetime import datetime, timedelta

response = client.get_requests(
    user_id="user_123",
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now()
)

# Get a specific request by ID
response = client.get_requests(request_id="req_12345")
```

---

### `delete_request`

Delete a request and all its associated interactions.

```python
response = client.delete_request(
    request_id,
    wait_for_response=False
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `request_id` | str | Yes | - | Request ID to delete |
| `wait_for_response` | bool | No | `False` | Wait for confirmation |

#### DeleteRequestResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the deletion was successful |
| `message` | str | Additional information about the operation |

**Example:**

```python
# Fire-and-forget
client.delete_request(request_id="req_12345")

# Wait for confirmation
response = client.delete_request(
    request_id="req_12345",
    wait_for_response=True
)
if response.success:
    print(f"Deleted: {response.message}")
```

---

### `delete_request_group`

Delete all requests and interactions in a request group.

```python
response = client.delete_request_group(
    request_group,
    wait_for_response=False
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `request_group` | str | Yes | - | Request group to delete |
| `wait_for_response` | bool | No | `False` | Wait for confirmation |

#### DeleteRequestGroupResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the deletion was successful |
| `message` | str | Additional information about the operation |
| `deleted_requests_count` | int | Number of requests deleted |

**Example:**

```python
# Clean up after an experiment
response = client.delete_request_group(
    request_group="experiment_001",
    wait_for_response=True
)
if response.success:
    print(f"Deleted {response.deleted_requests_count} requests")

# Fire-and-forget cleanup
client.delete_request_group(request_group="old_session_data")
```

---

## Profile Management

### `search_profiles`

Search for user profiles using semantic queries.

```python
response = client.search_profiles(
    user_id="user_123",
    query="laptop preferences",
    threshold=0.7,
    top_k=5
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | str | Yes | - | Identifier of the user to search |
| `generated_from_request_id` | str | No | `None` | Filter by request ID that generated the profile |
| `query` | str | No | `None` | Semantic search query |
| `start_time` | datetime | No | `None` | Filter by start time |
| `end_time` | datetime | No | `None` | Filter by end time |
| `top_k` | int | No | `10` | Maximum number of results to return |
| `source` | str | No | `None` | Filter by interaction source |
| `custom_feature` | str | No | `None` | Filter by custom features |
| `threshold` | float | No | `0.7` | Similarity threshold (0.0-1.0) |

#### SearchUserProfileResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the search was successful |
| `user_profiles` | list[UserProfile] | List of matching profiles |
| `msg` | str | Additional message (optional) |

#### UserProfile Schema

| Field | Type | Description |
|-------|------|-------------|
| `profile_id` | str | Unique identifier for the profile |
| `user_id` | str | Identifier of the user |
| `profile_content` | str | Content of the user profile |
| `last_modified_timestamp` | int | Unix timestamp of last modification |
| `generated_from_request_id` | str | Request ID that generated this profile |
| `profile_time_to_live` | str | Time-to-live setting (see [ProfileTimeToLive](#profiletimetolive)) |
| `expiration_timestamp` | int | Unix timestamp when profile expires |
| `custom_features` | dict | Custom feature metadata |
| `source` | str | Source of the interaction that generated this profile |
| `embedding` | list[float] | Vector embedding of the profile |

**Example:**

```python
# Basic semantic search using kwargs
response = client.search_profiles(
    user_id="user_123",
    query="laptop preferences budget constraints",
    threshold=0.7
)

for profile in response.user_profiles:
    print(f"Profile: {profile.profile_content}")
    print(f"Source: {profile.source}")
    print(f"Created from request: {profile.generated_from_request_id}")

# Filter by source
response = client.search_profiles(
    user_id="user_123",
    query="product preferences",
    source="sales_chat",
    top_k=10,
    threshold=0.6
)

# Search with time filter
from datetime import datetime, timedelta

response = client.search_profiles(
    user_id="user_123",
    query="communication style",
    start_time=datetime.now() - timedelta(days=30),
    custom_feature="personality_traits"
)
```

---

### `get_profiles`

Retrieve user profiles.

```python
response = client.get_profiles(
    user_id="user_123",
    top_k=10
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | str | Yes | - | Identifier of the user to query |
| `start_time` | datetime | No | `None` | Filter by start time |
| `end_time` | datetime | No | `None` | Filter by end time |
| `top_k` | int | No | `30` | Maximum number of results to return |
| `status_filter` | list[Status \| str] | No | `None` | Filter by profile status. Accepts Status enum or string values (e.g., `"current"`, `"archived"`, `"pending"`) |
| `force_refresh` | bool | No | `False` | Bypass cache |

#### GetUserProfilesResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the request was successful |
| `user_profiles` | list[UserProfile] | List of user profiles |
| `msg` | str | Additional message (optional) |

**Example:**

```python
# Get cached profiles (faster) using kwargs
response = client.get_profiles(
    user_id="user_123",
    top_k=10
)

for profile in response.user_profiles:
    print(f"[{profile.source}] {profile.profile_content}")

# Force fresh data after publishing new interactions
response = client.get_profiles(
    user_id="user_123",
    top_k=10,
    force_refresh=True
)

# Get profiles within a time range
from datetime import datetime, timedelta

response = client.get_profiles(
    user_id="user_123",
    start_time=datetime.now() - timedelta(days=30),
    top_k=50
)

# Filter by status using enum
from reflexio_commons.api_schema.service_schemas import Status

response = client.get_profiles(
    user_id="user_123",
    status_filter=[Status.CURRENT]
)

# Filter by status using string (equivalent to above)
response = client.get_profiles(
    user_id="user_123",
    status_filter=["current"]
)
```

---

### `get_all_profiles`

Get profiles across all users (admin operation).

```python
response = client.get_all_profiles(limit=100)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | int | No | `100` | Maximum profiles to return |

**Returns:** `GetUserProfilesResponse` with profiles from all users

**Example:**

```python
# Get profiles from all users
all_profiles = client.get_all_profiles(limit=50)

# Group by user
from collections import defaultdict
by_user = defaultdict(list)

for profile in all_profiles.user_profiles:
    by_user[profile.user_id].append(profile)

for user_id, profiles in by_user.items():
    print(f"User {user_id}: {len(profiles)} profiles")
    for p in profiles[:3]:  # Show first 3
        print(f"  - {p.profile_content[:50]}...")
```

---

### `delete_profile`

Delete user profiles by ID or search query.

```python
response = client.delete_profile(
    user_id,
    profile_id="",
    search_query="",
    wait_for_response=False
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | str | Yes | - | User identifier |
| `profile_id` | str | No | `""` | Specific profile ID to delete |
| `search_query` | str | No | `""` | Delete profiles matching query |
| `wait_for_response` | bool | No | `False` | Wait for confirmation |

#### DeleteUserProfileResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the deletion was successful |
| `message` | str | Additional information about the operation |

**Example:**

```python
# Delete specific profile by ID
client.delete_profile(
    user_id="user_123",
    profile_id="prof_456"
)

# Delete profiles matching a search query
response = client.delete_profile(
    user_id="user_123",
    search_query="outdated preferences",
    wait_for_response=True
)
if response.success:
    print(f"Deleted profiles: {response.message}")

# Delete with confirmation
response = client.delete_profile(
    user_id="user_123",
    profile_id="prof_789",
    wait_for_response=True
)
```

---

### `get_profile_change_log`

Retrieve the history of profile changes.

```python
logs = client.get_profile_change_log()
```

#### ProfileChangeLogResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the request was successful |
| `profile_change_logs` | list[ProfileChangeLog] | List of profile change logs |

#### ProfileChangeLog Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Unique identifier for the change log |
| `user_id` | str | Identifier of the user whose profile changed |
| `request_id` | str | Request that triggered the change |
| `created_at` | int | Unix timestamp when the change occurred |
| `added_profiles` | list[UserProfile] | Profiles that were added |
| `removed_profiles` | list[UserProfile] | Profiles that were removed |
| `mentioned_profiles` | list[UserProfile] | Profiles that were referenced but not changed |

**Example:**

```python
logs = client.get_profile_change_log()

for log in logs.profile_change_logs:
    print(f"Request: {log.request_id}")
    print(f"  Added: {len(log.added_profiles)} profiles")
    for added in log.added_profiles:
        print(f"    + {added.profile_content[:50]}...")
    print(f"  Removed: {len(log.removed_profiles)} profiles")
    for removed in log.removed_profiles:
        print(f"    - {removed.profile_content[:50]}...")
```

---

## Configuration Management

### `get_config`

Get the current system configuration.

```python
config = client.get_config()
```

#### Config Schema

| Field | Type | Description |
|-------|------|-------------|
| `storage_config` | dict | Database storage configuration |
| `agent_context_prompt` | str | Global agent context prompt (optional) |
| `profile_extractor_configs` | list[dict] | Profile extraction configurations |
| `agent_feedback_configs` | list[dict] | Agent feedback configurations |

**Example:**

```python
config = client.get_config()
print(f"Profile extractors: {len(config.profile_extractor_configs)}")
print(f"Feedback configs: {len(config.agent_feedback_configs)}")

# Inspect profile extractors
for extractor in config.profile_extractor_configs:
    print(f"  Extractor: {extractor['profile_content_definition_prompt'][:50]}...")
```

---

### `set_config`

Set the system configuration.

```python
response = client.set_config(config)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `config` | dict | Yes | Configuration to set |

#### Config Dict Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `profile_extractor_configs` | list[dict] | No | Profile extraction configurations |
| `agent_feedback_configs` | list[dict] | No | Agent feedback configurations |
| `agent_context_prompt` | str | No | Global agent context prompt |

#### ProfileExtractorConfig Dict Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `profile_content_definition_prompt` | str | Yes | - | Prompt defining what to extract |
| `context_prompt` | str | No | `""` | Context for profile extraction |
| `metadata_definition_prompt` | str | No | `None` | Prompt for metadata extraction |
| `should_extract_profile_prompt_override` | str | No | `None` | Override for extraction conditions |

#### AgentFeedbackConfig Dict Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `feedback_name` | str | Yes | - | Name of the feedback type |
| `feedback_definition_prompt` | str | Yes | - | Prompt defining feedback extraction |
| `metadata_definition_prompt` | str | No | `None` | Prompt for metadata extraction |
| `feedback_aggregator_config` | dict | Yes | - | Configuration for aggregation |

#### FeedbackAggregatorConfig Dict Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `min_feedback_threshold` | int | No | `2` | Minimum feedbacks required for aggregation |

**Returns:** Dictionary with `success` and `message`

**Example:**

```python
config = client.get_config()

# Add profile extractors using dict format
config.profile_extractor_configs = [
    {
        "profile_content_definition_prompt": "Extract user preferences and interests",
        "context_prompt": "Analyzing customer conversations"
    },
    {
        "profile_content_definition_prompt": "Extract user technical skill level",
        "context_prompt": "Technical support interactions",
        "metadata_definition_prompt": "Include skill areas and proficiency levels"
    }
]

# Add feedback configuration using dict format
config.agent_feedback_configs = [
    {
        "feedback_name": "quality_feedback",
        "feedback_definition_prompt": "Extract feedback about response quality",
        "feedback_aggregator_config": {"min_feedback_threshold": 3}
    },
    {
        "feedback_name": "helpfulness_feedback",
        "feedback_definition_prompt": "Identify whether the response was helpful to the user",
        "feedback_aggregator_config": {"min_feedback_threshold": 5}
    }
]

response = client.set_config(config)
print(f"Config updated: {response['success']}")
```

---

## Feedback Management

### `search_raw_feedbacks`

Search for raw feedbacks using semantic/text search and advanced filtering.

```python
response = client.search_raw_feedbacks(
    query="user satisfaction",
    agent_version="v2.1.0",
    top_k=10
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | No | `None` | Query for semantic/text search |
| `user_id` | str | No | `None` | Filter by user (via request_id linkage) |
| `agent_version` | str | No | `None` | Filter by agent version |
| `feedback_name` | str | No | `None` | Filter by feedback name |
| `start_time` | datetime | No | `None` | Filter by start time |
| `end_time` | datetime | No | `None` | Filter by end time |
| `status_filter` | list[Status] | No | `None` | Filter by status (None for CURRENT, PENDING, ARCHIVED) |
| `top_k` | int | No | `10` | Maximum number of results to return |
| `threshold` | float | No | `0.5` | Similarity threshold for vector search |

#### SearchRawFeedbackResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the search was successful |
| `raw_feedbacks` | list[RawFeedback] | List of matching raw feedbacks |
| `msg` | str | Additional message (optional) |

**Example:**

```python
# Search with semantic query
response = client.search_raw_feedbacks(
    query="response quality issues",
    agent_version="v2.1.0",
    top_k=10
)

for fb in response.raw_feedbacks:
    print(f"Request: {fb.request_id}")
    print(f"  Content: {fb.feedback_content}")

# Filter by user and feedback name
response = client.search_raw_feedbacks(
    user_id="user_123",
    feedback_name="quality_feedback",
    top_k=20
)

# Search with time filter
from datetime import datetime, timedelta

response = client.search_raw_feedbacks(
    query="helpful",
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now(),
    threshold=0.6
)

# Filter by status
from reflexio_commons.api_schema.service_schemas import Status

response = client.search_raw_feedbacks(
    agent_version="v2.1.0",
    status_filter=[Status.CURRENT]
)
```

---

### `search_feedbacks`

Search for aggregated feedbacks using semantic/text search and advanced filtering.

```python
response = client.search_feedbacks(
    query="concise responses",
    agent_version="v2.1.0",
    feedback_status_filter="approved"
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | No | `None` | Query for semantic/text search |
| `agent_version` | str | No | `None` | Filter by agent version |
| `feedback_name` | str | No | `None` | Filter by feedback name |
| `start_time` | datetime | No | `None` | Filter by start time |
| `end_time` | datetime | No | `None` | Filter by end time |
| `status_filter` | list[Status] | No | `None` | Filter by status (None for CURRENT, PENDING, ARCHIVED) |
| `feedback_status_filter` | FeedbackStatus | No | `None` | Filter by feedback approval status (PENDING, APPROVED, REJECTED) |
| `top_k` | int | No | `10` | Maximum number of results to return |
| `threshold` | float | No | `0.5` | Similarity threshold for vector search |

#### SearchFeedbackResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the search was successful |
| `feedbacks` | list[Feedback] | List of matching feedbacks |
| `msg` | str | Additional message (optional) |

**Example:**

```python
# Search with semantic query
response = client.search_feedbacks(
    query="improve response clarity",
    agent_version="v2.1.0",
    top_k=10
)

for fb in response.feedbacks:
    print(f"Feedback: {fb.feedback_content}")
    print(f"  Status: {fb.feedback_status}")

# Filter by feedback status (only approved)
from reflexio_commons.api_schema.service_schemas import FeedbackStatus

response = client.search_feedbacks(
    agent_version="v2.1.0",
    feedback_status_filter=FeedbackStatus.APPROVED,
    top_k=20
)

# Search with time filter
from datetime import datetime, timedelta

response = client.search_feedbacks(
    query="user experience",
    start_time=datetime.now() - timedelta(days=30),
    feedback_name="quality_feedback",
    threshold=0.6
)

# Combine multiple filters
response = client.search_feedbacks(
    query="actionable suggestions",
    agent_version="v2.1.0",
    feedback_name="helpfulness",
    feedback_status_filter=FeedbackStatus.APPROVED,
    top_k=5
)
```

---

### `get_raw_feedbacks`

Retrieve raw feedback entries extracted from interactions.

```python
response = client.get_raw_feedbacks(
    limit=100,
    feedback_name="quality_feedback"
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | int | No | `100` | Maximum number of results to return |
| `feedback_name` | str | No | `None` | Filter by feedback name |
| `status_filter` | list[Status] | No | `None` | Filter by status |

#### GetRawFeedbacksResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the request was successful |
| `raw_feedbacks` | list[RawFeedback] | List of raw feedbacks |
| `msg` | str | Additional message (optional) |

#### RawFeedback Schema

| Field | Type | Description |
|-------|------|-------------|
| `raw_feedback_id` | int | Unique identifier for the feedback |
| `agent_version` | str | Version of the agent |
| `request_id` | str | Request ID that generated this feedback |
| `feedback_name` | str | Name of the feedback type |
| `created_at` | int | Unix timestamp when feedback was created |
| `feedback_content` | str | Content of the feedback |
| `embedding` | list[float] | Vector embedding of the feedback |

**Example:**

```python
# Get all raw feedbacks using kwargs
feedbacks = client.get_raw_feedbacks()

for fb in feedbacks.raw_feedbacks:
    print(f"Request: {fb.request_id}")
    print(f"  Feedback Name: {fb.feedback_name}")
    print(f"  Agent Version: {fb.agent_version}")
    print(f"  Content: {fb.feedback_content}")
    print(f"  Created: {fb.created_at}")

# Filter by feedback name
feedbacks = client.get_raw_feedbacks(
    feedback_name="quality_feedback",
    limit=50
)

# Filter by status
from reflexio_commons.api_schema.service_schemas import Status

feedbacks = client.get_raw_feedbacks(
    status_filter=[Status.CURRENT]
)

# Analyze feedback by agent version
from collections import defaultdict
by_version = defaultdict(list)

for fb in feedbacks.raw_feedbacks:
    by_version[fb.agent_version].append(fb)

for version, fbs in by_version.items():
    print(f"Agent {version}: {len(fbs)} feedbacks")
```

---

### `add_raw_feedback`

Add raw feedback directly to storage.

```python
response = client.add_raw_feedback(
    raw_feedbacks=[
        {
            "agent_version": "v2.1.0",
            "request_id": "req_123",
            "feedback_name": "quality_feedback",
            "feedback_content": "User expressed satisfaction with response"
        }
    ]
)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `raw_feedbacks` | list[dict] | Yes | List of raw feedback entries to add |

#### RawFeedback Dict Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `agent_version` | str | Yes | - | Version of the agent |
| `request_id` | str | Yes | - | Request ID associated with the feedback |
| `feedback_name` | str | No | `""` | Name/category of the feedback |
| `feedback_content` | str | No | `""` | Content of the feedback |

#### AddRawFeedbackResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the operation was successful |
| `message` | str | Additional information about the operation |
| `added_count` | int | Number of feedbacks added |

**Example:**

```python
# Add single feedback
response = client.add_raw_feedback(
    raw_feedbacks=[
        {
            "agent_version": "v2.1.0",
            "request_id": "req_456",
            "feedback_name": "response_quality",
            "feedback_content": "Agent provided accurate and helpful information"
        }
    ]
)
print(f"Added {response.added_count} feedbacks")

# Add multiple feedbacks at once
response = client.add_raw_feedback(
    raw_feedbacks=[
        {
            "agent_version": "v2.1.0",
            "request_id": "req_001",
            "feedback_name": "helpfulness",
            "feedback_content": "Response was very helpful"
        },
        {
            "agent_version": "v2.1.0",
            "request_id": "req_002",
            "feedback_name": "clarity",
            "feedback_content": "Response could be clearer"
        }
    ]
)

if response.success:
    print(f"Successfully added {response.added_count} feedback entries")
```

---

### `add_feedbacks`

Add aggregated feedback directly to storage. Unlike `add_raw_feedback` which adds raw feedback entries that need to be aggregated, this method adds already-aggregated feedback entries.

```python
response = client.add_feedbacks(
    feedbacks=[
        {
            "agent_version": "v2.1.0",
            "feedback_name": "quality_feedback",
            "feedback_content": "Agent should provide more concise responses",
            "feedback_status": "approved",
            "feedback_metadata": "{}"
        }
    ]
)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `feedbacks` | list[dict] | Yes | List of aggregated feedback entries to add |

#### Feedback Dict Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `agent_version` | str | Yes | - | Version of the agent |
| `feedback_name` | str | No | `""` | Name/category of the feedback |
| `feedback_content` | str | Yes | - | Content of the aggregated feedback |
| `feedback_status` | FeedbackStatus | Yes | - | Approval status: `"pending"`, `"approved"`, or `"rejected"` |
| `feedback_metadata` | str | Yes | - | JSON string with additional metadata |

#### AddFeedbackResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the operation was successful |
| `message` | str | Additional information about the operation |
| `added_count` | int | Number of feedbacks added |

**Example:**

```python
# Add single aggregated feedback
response = client.add_feedbacks(
    feedbacks=[
        {
            "agent_version": "v2.1.0",
            "feedback_name": "response_quality",
            "feedback_content": "Agent should validate user input before processing",
            "feedback_status": "approved",
            "feedback_metadata": "{\"source\": \"manual_review\"}"
        }
    ]
)
print(f"Added {response.added_count} feedbacks")

# Add multiple aggregated feedbacks at once
response = client.add_feedbacks(
    feedbacks=[
        {
            "agent_version": "v2.1.0",
            "feedback_name": "helpfulness",
            "feedback_content": "Responses should include actionable next steps",
            "feedback_status": "approved",
            "feedback_metadata": "{}"
        },
        {
            "agent_version": "v2.1.0",
            "feedback_name": "clarity",
            "feedback_content": "Avoid technical jargon when explaining to users",
            "feedback_status": "pending",
            "feedback_metadata": "{}"
        }
    ]
)

if response.success:
    print(f"Successfully added {response.added_count} aggregated feedback entries")
```

---

### `get_feedbacks`

Retrieve aggregated feedback entries.

```python
response = client.get_feedbacks(
    feedback_name="quality_feedback",
    limit=10
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | int | No | `100` | Maximum number of results |
| `feedback_name` | str | No | `None` | Filter by feedback name |
| `status_filter` | list[Status] | No | `None` | Filter by status |
| `feedback_status_filter` | FeedbackStatus | No | `APPROVED` | Filter by feedback status |
| `force_refresh` | bool | No | `False` | Bypass cache |

#### GetFeedbacksResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the request was successful |
| `feedbacks` | list[Feedback] | List of aggregated feedbacks |
| `msg` | str | Additional message (optional) |

**Example:**

```python
# Get all aggregated feedbacks
feedbacks = client.get_feedbacks()

for fb in feedbacks.feedbacks:
    print(f"Feedback: {fb}")

# Filter by feedback name
feedbacks = client.get_feedbacks(
    feedback_name="quality_feedback",
    limit=10
)

# Force refresh after new data
feedbacks = client.get_feedbacks(force_refresh=True)

# Compare feedbacks across types
quality_feedbacks = client.get_feedbacks(feedback_name="quality_feedback")
helpfulness_feedbacks = client.get_feedbacks(feedback_name="helpfulness_feedback")
```

---

## Agent Evaluation

### `get_agent_success_evaluation_results`

Get agent success evaluation results to analyze performance.

```python
response = client.get_agent_success_evaluation_results(
    agent_version=None,
    limit=100
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agent_version` | str | No | `None` | Filter by specific agent version |
| `limit` | int | No | `100` | Maximum number of results to return |

#### GetAgentSuccessEvaluationResultsResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the request was successful |
| `results` | list[AgentSuccessEvaluationResult] | List of evaluation results |
| `msg` | str | Additional message (optional) |

#### AgentSuccessEvaluationResult Schema

| Field | Type | Description |
|-------|------|-------------|
| `result_id` | str | Unique identifier for the evaluation result |
| `agent_version` | str | Version of the agent being evaluated |
| `request_id` | str | Request ID that was evaluated |
| `created_at` | int | Unix timestamp when evaluation was created |
| `is_success` | bool | Whether the agent was successful |
| `failure_type` | str | Type of failure if unsuccessful |
| `failure_reason` | str | Detailed reason for failure |
| `agent_prompt_update` | str | Suggested improvement for the agent |

**Example:**

```python
# Get all results
response = client.get_agent_success_evaluation_results(limit=100)

# Calculate success rate
total = len(response.results)
successful = sum(1 for r in response.results if r.is_success)
print(f"Success rate: {successful/total*100:.1f}%")

# Review failures
print("\nFailure Analysis:")
for result in response.results:
    if not result.is_success:
        print(f"Request: {result.request_id}")
        print(f"  Failure Type: {result.failure_type}")
        print(f"  Reason: {result.failure_reason}")
        print(f"  Suggestion: {result.agent_prompt_update}")

# Compare agent versions
v1_results = client.get_agent_success_evaluation_results(
    agent_version="v1.0.0",
    limit=100
)
v2_results = client.get_agent_success_evaluation_results(
    agent_version="v2.0.0",
    limit=100
)

v1_success = sum(1 for r in v1_results.results if r.is_success)
v2_success = sum(1 for r in v2_results.results if r.is_success)

print(f"\nVersion Comparison:")
print(f"v1.0.0: {v1_success}/{len(v1_results.results)} successful")
print(f"v2.0.0: {v2_success}/{len(v2_results.results)} successful")

# Group failures by type
from collections import Counter
failure_types = Counter(
    r.failure_type for r in response.results if not r.is_success
)
print("\nFailure Types:")
for failure_type, count in failure_types.most_common():
    print(f"  {failure_type}: {count}")
```

---

## Rerun and Manual Generation Operations

Profile and feedback generation can be triggered in different modes:

| Mode | Method | Interactions | Output Status | Blocking | Use Case |
|------|--------|--------------|---------------|----------|----------|
| **Rerun** | `rerun_*_generation` | ALL interactions | PENDING | Optional | Test prompt changes, full regeneration |
| **Manual** | `manual_*_generation` | Window-sized (from config) | CURRENT | Fire-and-forget only | Force regeneration, fill gaps |

**Key Differences:**
- **Rerun**: Uses ALL interactions, outputs PENDING status (requires upgrade workflow), supports `wait_for_response`
- **Manual**: Uses `extraction_window_size` from config, outputs CURRENT status directly, always fire-and-forget

---

### `rerun_profile_generation`

Regenerate user profiles from ALL existing interactions. Creates profiles with PENDING status.

```python
response = client.rerun_profile_generation(
    user_id="user_123",
    wait_for_response=True
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | str | No | `None` | Specific user ID. If None, runs for all users |
| `start_time` | datetime | No | `None` | Filter interactions from this time |
| `end_time` | datetime | No | `None` | Filter interactions until this time |
| `source` | str | No | `None` | Filter by interaction source |
| `extractor_names` | list[str] | No | `None` | List of specific extractor names to run. If None, runs all extractors |
| `wait_for_response` | bool | No | `False` | Wait for operation to complete |

#### RerunProfileGenerationResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the operation was successful |
| `msg` | str | Additional information (optional) |
| `profiles_generated` | int | Number of profiles generated (optional) |
| `operation_id` | str | Operation identifier for tracking |

**Example:**

```python
# Rerun for all users (fire-and-forget)
client.rerun_profile_generation()

# Rerun for specific user using kwargs
response = client.rerun_profile_generation(
    user_id="user_123",
    wait_for_response=True
)

# Rerun with time filter
from datetime import datetime, timedelta

client.rerun_profile_generation(
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now(),
    source="chat"
)

# Rerun with only specific extractors
response = client.rerun_profile_generation(
    user_id="user_123",
    extractor_names=["preferences", "skills"],
    wait_for_response=True
)
print(f"Generated {response.profiles_generated} profiles")
```

---

### `manual_profile_generation`

Manually trigger profile generation with window-sized interactions (fire-and-forget). Creates profiles with CURRENT status directly (no upgrade needed).

```python
client.manual_profile_generation(user_id="user_123")
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | str | No | `None` | Specific user ID. If None, runs for all users |
| `source` | str | No | `None` | Filter by interaction source |
| `extractor_names` | list[str] | No | `None` | Specific extractors to run. If None, runs extractors with `allow_manual_trigger=True` |

**Returns:** `None` (fire-and-forget operation)

**Prerequisites:**
- `extraction_window_size` must be configured in your config
- Extractors must have `allow_manual_trigger=True` to be included

**Example:**

```python
# Force regeneration for a user (CURRENT status, fire-and-forget)
client.manual_profile_generation(user_id="user_123")

# Regenerate for all users with specific source
client.manual_profile_generation(source="chat")

# Run specific extractors only
client.manual_profile_generation(
    user_id="user_123",
    extractor_names=["preferences"]
)
```

---

### `rerun_feedback_generation`

Regenerate feedback from ALL interactions for a specific agent version. Creates feedbacks with PENDING status.

```python
response = client.rerun_feedback_generation(
    agent_version="v2.1.0",
    wait_for_response=True
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agent_version` | str | Yes | - | Agent version to evaluate |
| `start_time` | datetime | No | `None` | Filter interactions from this time |
| `end_time` | datetime | No | `None` | Filter interactions until this time |
| `feedback_name` | str | No | `None` | Specific feedback type to generate |
| `wait_for_response` | bool | No | `False` | Wait for operation to complete |

#### RerunFeedbackGenerationResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the operation was successful |
| `msg` | str | Additional information (optional) |
| `feedbacks_generated` | int | Number of feedbacks generated (optional) |
| `operation_id` | str | Operation identifier for tracking |

**Example:**

```python
# Rerun feedback for agent version using kwargs
client.rerun_feedback_generation(agent_version="v2.1.0")

# Rerun specific feedback type with wait
response = client.rerun_feedback_generation(
    agent_version="v2.1.0",
    feedback_name="response_quality",
    wait_for_response=True
)

# Rerun with time filter
from datetime import datetime, timedelta

client.rerun_feedback_generation(
    agent_version="v2.1.0",
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now()
)
```

---

### `manual_feedback_generation`

Manually trigger feedback generation with window-sized interactions (fire-and-forget). Creates feedbacks with CURRENT status directly (no upgrade needed).

```python
client.manual_feedback_generation(agent_version="v2.1.0")
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agent_version` | str | Yes | - | Agent version to evaluate |
| `source` | str | No | `None` | Filter by interaction source |
| `feedback_name` | str | No | `None` | Specific feedback type to generate |

**Returns:** `None` (fire-and-forget operation)

**Prerequisites:**
- `extraction_window_size` must be configured in your config
- Feedback configs must have `allow_manual_trigger=True` to be included

**Example:**

```python
# Force regeneration for an agent version (CURRENT status, fire-and-forget)
client.manual_feedback_generation(agent_version="v2.1.0")

# Regenerate with specific source filter
client.manual_feedback_generation(
    agent_version="v2.1.0",
    source="chat"
)

# Run for specific feedback type only
client.manual_feedback_generation(
    agent_version="v2.1.0",
    feedback_name="response_quality"
)
```

---

### `run_feedback_aggregation`

Aggregate raw feedbacks into consolidated insights using clustering.

```python
response = client.run_feedback_aggregation(
    agent_version="v2.1.0",
    feedback_name="response_quality"
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agent_version` | str | Yes | - | Agent version to aggregate for |
| `feedback_name` | str | Yes | - | Feedback type to aggregate |
| `wait_for_response` | bool | No | `False` | Wait for operation to complete |

#### RunFeedbackAggregationResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the aggregation was successful |
| `message` | str | Additional information |

**Example:**

```python
# Aggregate feedback for an agent version using kwargs
client.run_feedback_aggregation(
    agent_version="v2.1.0",
    feedback_name="response_quality"
)

# Wait for completion
response = client.run_feedback_aggregation(
    agent_version="v2.1.0",
    feedback_name="response_quality",
    wait_for_response=True
)

if response.success:
    print("Aggregation complete")
```

---

## Enums Reference

### UserActionType

Represents different types of user actions that can be tracked. Use as string values in dict format.

| Value | Description |
|-------|-------------|
| `"CLICK"` | Click interaction |
| `"SCROLL"` | Scroll interaction |
| `"TYPE"` | Type interaction |
| `"NONE"` | No specific interaction |

**Example:**

```python
# Track a click action
interaction = {
    "user_action": "CLICK",
    "user_action_description": "Clicked on product image"
}

# Track a scroll action
interaction = {
    "user_action": "SCROLL",
    "user_action_description": "Scrolled through recommendations"
}
```

---

### ProfileTimeToLive

Defines the time-to-live options for user profiles. Use as string values.

| Value | Description |
|-------|-------------|
| `"ONE_DAY"` | Profile expires after one day |
| `"ONE_WEEK"` | Profile expires after one week |
| `"ONE_MONTH"` | Profile expires after one month |
| `"ONE_QUARTER"` | Profile expires after one quarter |
| `"ONE_YEAR"` | Profile expires after one year |
| `"INFINITY"` | Profile never expires |

---

### Status

Represents the current status of a user profile. Use as string values.

| Value | Description |
|-------|-------------|
| `"CURRENT"` | Active profile currently in use |
| `"ARCHIVED"` | Profile has been archived |
| `"PENDING"` | Profile is pending approval or processing |
| `"ARCHIVE_IN_PROGRESS"` | Profile is being archived |

---

### FeedbackStatus

Represents the approval status of feedback. Use as string values.

| Value | Description |
|-------|-------------|
| `"PENDING"` | Feedback is pending review |
| `"APPROVED"` | Feedback has been approved |
| `"REJECTED"` | Feedback has been rejected |

---

## Notes

### `delete_feedback`

Delete a feedback by ID.

```python
response = client.delete_feedback(
    feedback_id,
    wait_for_response=False
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `feedback_id` | int | Yes | - | Feedback ID to delete |
| `wait_for_response` | bool | No | `False` | Wait for confirmation |

#### DeleteFeedbackResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the deletion was successful |
| `message` | str | Additional information about the operation |

**Example:**

```python
# Fire-and-forget
client.delete_feedback(feedback_id=123)

# Wait for confirmation
response = client.delete_feedback(
    feedback_id=123,
    wait_for_response=True
)
if response.success:
    print(f"Deleted: {response.message}")
```

---

### `delete_raw_feedback`

Delete a raw feedback by ID.

```python
response = client.delete_raw_feedback(
    raw_feedback_id,
    wait_for_response=False
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `raw_feedback_id` | int | Yes | - | Raw feedback ID to delete |
| `wait_for_response` | bool | No | `False` | Wait for confirmation |

#### DeleteRawFeedbackResponse Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the deletion was successful |
| `message` | str | Additional information about the operation |

**Example:**

```python
# Fire-and-forget
client.delete_raw_feedback(raw_feedback_id=456)

# Wait for confirmation
response = client.delete_raw_feedback(
    raw_feedback_id=456,
    wait_for_response=True
)
if response.success:
    print(f"Deleted: {response.message}")
```

---

### Fire-and-Forget Mode

The following methods use fire-and-forget mode by default (can use `wait_for_response=True` to wait):

- `publish_interaction`
- `delete_interaction`
- `delete_profile`
- `delete_request`
- `delete_request_group`
- `delete_feedback`
- `delete_raw_feedback`

The following methods are **always** fire-and-forget (no blocking option):

- `manual_profile_generation`
- `manual_feedback_generation`

**Behavior:**
- Returns `None` immediately
- Operation executes asynchronously in the background
- Errors are silently ignored
- For methods that support it, set `wait_for_response=True` to get confirmation

**Example:**

```python
# Fire-and-forget (fast, no confirmation)
client.publish_interaction(
    user_id="user_123",
    interactions=[{"role": "User", "content": "Hello"}]
)
# Returns None immediately, operation runs in background

# With confirmation (slower, but reliable)
response = client.publish_interaction(
    user_id="user_123",
    interactions=[{"role": "User", "content": "Hello"}],
    wait_for_response=True
)
if response.success:
    print("Published successfully")

# Always fire-and-forget (no wait option)
client.manual_profile_generation(user_id="user_123")
client.manual_feedback_generation(agent_version="v2.1.0")
```

---

### Caching

The following methods use caching to reduce API calls:

- `get_profiles` - Use `force_refresh=True` to bypass
- `get_feedbacks` - Use `force_refresh=True` to bypass

**Example:**

```python
# Uses cache (fast)
profiles = client.get_profiles(user_id="user_123")

# After publishing new interactions, force refresh
client.publish_interaction(
    user_id="user_123",
    interactions=[{"role": "User", "content": "New data"}],
    wait_for_response=True
)

# Bypass cache to get fresh data
profiles = client.get_profiles(
    user_id="user_123",
    force_refresh=True
)
```

---

### Synchronous API

All client methods are synchronous - no `await` needed. The client handles async operations internally.

```python
# All methods are synchronous
client = ReflexioClient(url_endpoint="http://127.0.0.1:8081/")
token = client.login("user@example.com", "password")
profiles = client.get_profiles(user_id="user_123")
# No async/await required
```
