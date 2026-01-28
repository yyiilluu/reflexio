"""Tests for feedback service utility functions."""

import pytest
from datetime import datetime, timezone

from reflexio_commons.api_schema.service_schemas import Interaction, Request
from reflexio_commons.api_schema.internal_schema import RequestInteractionDataModel
from reflexio.server.prompt.prompt_manager import PromptManager
from reflexio.server.services.feedback.feedback_service_utils import (
    construct_feedback_extraction_messages_from_request_groups,
)


def test_construct_feedback_extraction_messages_with_request_groups():
    """Test that construct_feedback_extraction_messages_from_request_groups formats interactions correctly in the rendered prompt."""
    # Create test interactions
    interactions = [
        Interaction(
            interaction_id=1,
            user_id="user_123",
            request_id="req_1",
            content="I need help with my account",
            role="user",
            created_at=int(datetime.now(timezone.utc).timestamp()),
            user_action="none",
            user_action_description="",
        ),
        Interaction(
            interaction_id=2,
            user_id="user_123",
            request_id="req_1",
            content="Here is how to access your account",
            role="assistant",
            created_at=int(datetime.now(timezone.utc).timestamp()),
            user_action="none",
            user_action_description="",
        ),
        Interaction(
            interaction_id=3,
            user_id="user_123",
            request_id="req_1",
            content="Thank you!",
            role="user",
            created_at=int(datetime.now(timezone.utc).timestamp()),
            user_action="click",
            user_action_description="help button",
        ),
    ]

    # Create request and request interaction data model
    request = Request(
        request_id="req_1",
        user_id="user_123",
        source="test",
        agent_version="1.0.0",
        request_group="session_1",
    )

    request_interaction_data_models = [
        RequestInteractionDataModel(
            request_group="session_1",
            request=request,
            interactions=interactions,
        )
    ]

    # Create prompt manager
    prompt_manager = PromptManager()

    # Call the function
    messages = construct_feedback_extraction_messages_from_request_groups(
        prompt_manager=prompt_manager,
        request_interaction_data_models=request_interaction_data_models,
        feedback_definition_prompt="Evaluate the quality of the agent's response",
        agent_context_prompt="Customer support agent",
    )

    # Validate that messages were created
    assert len(messages) > 0, "No messages were created"

    # Find the user message that contains the interactions
    found_interactions = False
    for message in messages:
        # Messages are dicts with 'role' and 'content' keys
        if isinstance(message, dict) and "content" in message:
            # Content can be a string or a list of content blocks
            content = message.get("content", "")
            if isinstance(content, list):
                # Extract text from content blocks
                extracted_text = ""
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        extracted_text += item.get("text", "")
                content = extracted_text
            else:
                content = str(content)

            # Check if this message contains the interaction section
            if (
                "[Intearctions start]" in content
                or "[Interactions end]" in content
                or "User and agent interactions:" in content
                or "Request Group:" in content
                or "user: ```I need help with my account```"
                in content  # Check directly for content
            ):
                # Validate the interactions are formatted correctly in the rendered prompt
                # Note: Content is wrapped in backticks in the prompt template
                assert (
                    "user: ```I need help with my account```" in content
                ), f"Expected 'user: ```I need help with my account```' in prompt"
                assert (
                    "assistant: ```Here is how to access your account```" in content
                ), f"Expected 'assistant: ```Here is how to access your account```' in prompt"
                assert (
                    "user: ```Thank you!```" in content
                ), f"Expected 'user: ```Thank you!```' in prompt"
                assert (
                    "user: ```click help button```" in content
                ), f"Expected 'user: ```click help button```' in prompt"

                # Also verify feedback definition prompt is in the content
                assert (
                    "Evaluate the quality of the agent's response" in content
                ), f"Expected feedback definition in prompt"

                found_interactions = True
                break

    assert found_interactions, "Did not find interactions in the rendered prompt"


def test_construct_feedback_extraction_messages_with_empty_request_groups():
    """Test that construct_feedback_extraction_messages_from_request_groups handles empty request groups."""
    # Empty request groups list
    request_interaction_data_models = []

    # Create prompt manager
    prompt_manager = PromptManager()

    # Call the function
    messages = construct_feedback_extraction_messages_from_request_groups(
        prompt_manager=prompt_manager,
        request_interaction_data_models=request_interaction_data_models,
        feedback_definition_prompt="Evaluate the quality of the agent's response",
        agent_context_prompt="Customer support agent",
    )

    # Should still create messages (system message + user message with prompt)
    assert len(messages) > 0, "No messages were created for empty request groups"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
