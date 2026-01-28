# Quick Start Guide

This guide helps you get Reflexio working end-to-end with your LLM agent.

## Installation

```bash
pip install reflexio
```

## Authentication

Reflexio supports two authentication methods:

=== "Python"

    ```python
    from reflexio import ReflexioClient

    # Option 1: Login with email/password (API key is automatically set)
    client = ReflexioClient(url_endpoint="http://127.0.0.1:8081/")
    token = client.login("your_email@example.com", "your_password")
    # token.api_key contains your API key - save it for future use (it never expires)

    # Option 2: Initialize with a previously saved API key (recommended for efficiency)
    client = ReflexioClient(
        api_key=token.api_key,  # Use the saved token.api_key from a previous login
        url_endpoint="http://127.0.0.1:8081/"
    )
    ```

=== "cURL"

    ```bash
    # Login with email/password to get API key
    curl -X POST "http://127.0.0.1:8081/token" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=your_email@example.com&password=your_password"

    # Response contains access_token (your API key)
    # {
    #   "access_token": "YOUR_API_KEY",
    #   "token_type": "bearer"
    # }

    # Use the API key in subsequent requests via Authorization header
    # -H "Authorization: Bearer YOUR_API_KEY"
    ```

## Configuration

Configure Reflexio via the **web portal** (recommended) or programmatically.

- **Web Portal**: Go to Settings in your Reflexio dashboard to configure profile extractors and feedback settings
- **Programmatic**: See the [Configuration Guide](configuration.md) or [API Reference](../api-reference/client.md#set_config)

## End-to-End Example: Agent with Memory

This example shows the complete workflow: retrieving user context, building an LLM prompt, and saving the conversation.

=== "Python"

    ```python
    from reflexio import ReflexioClient, InteractionData, UserActionType

    # Step 1: Login
    client = ReflexioClient(url_endpoint="http://127.0.0.1:8081/")
    token = client.login("your_email@example.com", "your_password")
    # Save token.api_key for future use (it never expires)

    # Step 2: Retrieve user context
    user_id = "user_123"

    # Get user profiles (semantic search)
    profiles_response = client.search_profiles(
        user_id=user_id,
        query="preferences interests",
        top_k=5
    )

    # Get agent feedback (guidelines from past interactions)
    feedbacks_response = client.get_feedbacks(limit=5)

    # Step 3: Build LLM prompt with context
    def build_prompt_with_memory(user_profiles, feedbacks, user_message):
        profile_context = "\n".join([
            f"- {p.profile_content}"
            for p in user_profiles
        ])

        feedback_context = "\n".join([
            f"- {f.feedback_content}"
            for f in feedbacks
        ])

        return f"""You are a helpful assistant.

    ## What you know about this user:
    {profile_context if profile_context else "No profile information yet."}

    ## Guidelines from past interactions:
    {feedback_context if feedback_context else "No feedback yet."}

    ## User message:
    {user_message}
    """

    user_message = "What products would you recommend for me?"
    prompt = build_prompt_with_memory(
        profiles_response.user_profiles,
        feedbacks_response.feedbacks,
        user_message
    )

    # Step 4: Call your LLM (example with OpenAI)
    # response = openai.chat.completions.create(
    #     model="gpt-5",
    #     messages=[{"role": "user", "content": prompt}]
    # )
    # agent_response = response.choices[0].message.content
    agent_response = "Based on your preferences, I recommend..."  # placeholder

    # Step 5: Publish the interaction (fire-and-forget by default)
    client.publish_interaction(
        user_id=user_id,
        interactions=[
            InteractionData(
                role="User",
                content=user_message,
                user_action=UserActionType.NONE
            ),
            InteractionData(
                role="Agent",
                content=agent_response,
                user_action=UserActionType.NONE
            )
        ],
        source="chat",
        request_group="session_001"
    )

    print("Interaction published! Profiles will be extracted automatically.")
    ```

=== "cURL"

    ```bash
    # Step 1: Login and get API key
    curl -X POST "http://127.0.0.1:8081/token" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=your_email@example.com&password=your_password"
    # Save the access_token from response as YOUR_API_KEY

    # Step 2a: Search user profiles
    curl -X POST "http://127.0.0.1:8081/api/search_profiles" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "user_id": "user_123",
        "query": "preferences interests",
        "top_k": 5
      }'

    # Step 2b: Get agent feedbacks
    curl -X POST "http://127.0.0.1:8081/api/get_feedbacks" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"limit": 5}'

    # Step 3 & 4: Build prompt and call your LLM (done in your application code)

    # Step 5: Publish the interaction
    curl -X POST "http://127.0.0.1:8081/api/publish_interaction" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "user_id": "user_123",
        "interactions": [
          {
            "role": "User",
            "content": "What products would you recommend for me?",
            "user_action": "none"
          },
          {
            "role": "Agent",
            "content": "Based on your preferences, I recommend...",
            "user_action": "none"
          }
        ],
        "source": "chat",
        "request_group": "session_001"
      }'
    ```

## Key Concepts

- **Fire-and-forget**: `publish_interaction` returns immediately by default. Set `wait_for_response=True` to wait for processing.
- **Request groups**: Group related interactions (e.g., by session) for tracking and attribution.
- **Sources**: Categorize interactions (e.g., "chat", "email") for filtering during searches.
- **Semantic search**: Use natural language queries like "user preferences" rather than exact keywords.

## Next Steps

- [Configuration Guide](configuration.md) - Complete configuration reference
- [API Reference](../api-reference/client.md) - Complete method documentation
- [Examples](../examples/user-interactions.md) - Code examples for common patterns
