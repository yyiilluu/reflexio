# Request Management Examples

This guide provides practical examples for working with requests and request groups in Reflexio.

## Setup

```python
from reflexio import ReflexioClient

# Initialize and authenticate (login automatically sets the API key)
client = ReflexioClient(url_endpoint="http://127.0.0.1:8081/")
token = client.login("your_email@example.com", "your_password")
# token.api_key contains your API key - save it for future use (it never expires)

# Or initialize with a previously saved API key (more efficient - skips login)
# client = ReflexioClient(api_key=token.api_key, url_endpoint="http://127.0.0.1:8081/")
```

## Basic Request Publishing

### Publishing a Request

```python
# Publish a request (generates profiles and feedback)
response = client.publish_interaction(
    user_id="user_123",
    interactions=[
        {"role": "User", "content": "What's the weather like?"},
        {"role": "Agent", "content": "I'll check the weather for you."}
    ],
    source="web_app",
    agent_version="v1.0.0",
    wait_for_response=True
)

print(f"Success: {response.success}")
```

### Publishing with Request Group

```python
# Group related requests together
client.publish_interaction(
    user_id="user_123",
    interactions=[...],
    request_group="onboarding_session_001",
    source="mobile_app",
    agent_version="v1.0.0"
)
```

## Retrieving Requests

### Get All Requests in a Group

```python
# Retrieve all requests for a user
response = client.get_requests(user_id="user_456")

# Iterate through request groups
for request_group in response.request_groups:
    print(f"\nRequest Group: {request_group.request_group}")

    # Each group contains multiple requests
    for request_data in request_group.requests:
        request = request_data.request
        interactions = request_data.interactions

        print(f"  Request ID: {request.request_id}")
        print(f"  Agent Version: {request.agent_version}")
        print(f"  Source: {request.source}")
        print(f"  Interaction Count: {len(interactions)}")

        # Access individual interactions
        for interaction in interactions:
            print(f"    - {interaction.role}: {interaction.content[:50]}...")
```

### Filter Requests by User

```python
# Get all requests for a specific user with limit
response = client.get_requests(
    user_id="user_123",
    top_k=50
)

# Count requests per group
for request_group in response.request_groups:
    print(f"Group: {request_group.request_group}")
    print(f"  Requests: {len(request_group.requests)}")

# Filter by time range
from datetime import datetime, timedelta

response = client.get_requests(
    user_id="user_123",
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now()
)
```

## Deleting Requests

### Delete a Single Request

```python
# Delete a specific request and all its interactions
response = client.delete_request(
    request_id="req_12345",
    wait_for_response=True
)

if response.success:
    print(f"Deleted: {response.message}")
```

### Delete an Entire Request Group

```python
# Delete all requests in a group (useful for cleanup)
response = client.delete_request_group(
    request_group="session_001",
    wait_for_response=True
)

if response.success:
    print(f"Deleted {response.deleted_requests_count} requests")
    print(f"Message: {response.message}")
```

### Fire-and-Forget Deletion

```python
# Non-blocking deletion (doesn't wait for response)
client.delete_request_group(
    request_group="old_session",
    wait_for_response=False
)
# Continues immediately without waiting
```

## Advanced Patterns

### Session-Based Organization

```python
import uuid

# Create a unique session ID
session_id = str(uuid.uuid4())

# Track all requests in a session (using dict format)
interactions_in_session = [
    [{"role": "User", "content": "First question"}],
    [{"role": "User", "content": "Follow-up question"}],
    [{"role": "User", "content": "Final question"}]
]

for interaction_batch in interactions_in_session:
    client.publish_interaction(
        user_id="user_123",
        interactions=interaction_batch,
        request_group=f"session_{session_id}",
        source="chat_interface"
    )

# Later: retrieve entire session
session_data = client.get_requests(user_id="user_123")
```

### Cleaning Up Old Sessions

```python
# List of completed sessions to clean up
completed_sessions = [
    "session_2024_01",
    "session_2024_02",
    "test_run_abc"
]

# Delete all at once
for session_id in completed_sessions:
    response = client.delete_request_group(
        request_group=session_id,
        wait_for_response=True
    )
    if response.success:
        print(f"Cleaned up {session_id}: {response.deleted_count} requests deleted")
```

## Common Patterns

### Pattern 1: Session with Cleanup

```python
session_id = "temp_session_123"

try:
    # Run session
    client.publish_interaction(
        user_id="user_test",
        interactions=[...],
        request_group=session_id
    )

    # Retrieve results
    results = client.get_requests(user_id="user_test")

    # Process results...

finally:
    # Always clean up
    client.delete_request_group(
        request_group=session_id,
        wait_for_response=True
    )
```

### Pattern 2: Versioned Sessions

```python
from datetime import datetime

# Create versioned session name
session_version = f"session_{datetime.now().strftime('%Y%m%d')}"

# Publish with version tracking
client.publish_interaction(
    user_id="user_123",
    interactions=[...],
    request_group=session_version,
    agent_version="v1.0"
)
```

## Related Documentation

- [Requests and Groups Concepts](../concepts/requests-and-groups.md)
- [Publishing Interactions](./user-interactions.md)
- [Client API Reference](../api-reference/client.md)
