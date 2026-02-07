"""
Utils for service layer
"""

import logging
import re
import json
import ast
from typing import Any, Optional
from dataclasses import dataclass

from reflexio_commons.api_schema.service_schemas import (
    Interaction,
    UserActionType,
)
from reflexio_commons.api_schema.internal_schema import RequestInteractionDataModel
from reflexio.server.prompt.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

_CYAN = "\033[96m"
_RESET = "\033[0m"


def log_model_response(
    target_logger: logging.Logger, label: str, response: Any
) -> None:
    """
    Log an LLM model response in bright cyan for terminal visibility.

    Args:
        target_logger (logging.Logger): The logger instance to use
        label (str): Descriptive label for the response (e.g. "Profile updates model response")
        response (Any): The model response to log
    """
    target_logger.info("%s%s: %s%s", _CYAN, label, response, _RESET)


@dataclass
class PromptConfig:
    """Configuration for a prompt to be rendered.

    Attributes:
        prompt_id: The ID of the prompt template to render
        variables: Dictionary of variables to pass to the prompt template
    """

    prompt_id: str
    variables: dict[str, any]


@dataclass
class MessageConstructionConfig:
    """Configuration for constructing LLM messages from interactions.

    Attributes:
        prompt_manager: The prompt manager to use for rendering prompts
        system_prompt_config: Configuration for the system message (before interactions)
        user_prompt_config: Configuration for the user message (after interactions)
    """

    prompt_manager: PromptManager
    system_prompt_config: Optional[PromptConfig] = None
    user_prompt_config: Optional[PromptConfig] = None


def format_interactions_to_history_string(interactions: list[Interaction]) -> str:
    """
    Format a list of interactions into a single string representing the interaction history.

    Each interaction is formatted as:
    - Text content: "{role}: {content}"
    - User actions: "{role}: {action} {action_description}"

    Args:
        interactions (list[Interaction]): List of interactions to format

    Returns:
        str: A formatted string representing the interaction history, with interactions separated by newlines.
             Returns empty string if no interactions are provided.

    Example:
        >>> interactions = [
        ...     Interaction(role="user", content="I love sushi", user_action=UserActionType.NONE),
        ...     Interaction(role="user", content="", user_action=UserActionType.CLICK, user_action_description="menu item")
        ... ]
        >>> result = format_interactions_to_history_string(interactions)
        >>> print(result)
        user: I love sushi
        user: click menu item
    """
    formatted_interactions = []
    for interaction in interactions:
        # Add text content with tool_used prefix if present
        if interaction.content:
            if interaction.tool_used:
                tool_input_str = json.dumps(interaction.tool_used.tool_input)
                tool_prefix = (
                    f"[used tool: {interaction.tool_used.tool_name}({tool_input_str})] "
                )
                formatted_interactions.append(
                    f"{interaction.role}: ```{tool_prefix}{interaction.content}```"
                )
            else:
                formatted_interactions.append(
                    f"{interaction.role}: ```{interaction.content}```"
                )

        # Add user action
        if interaction.user_action != UserActionType.NONE:
            formatted_interactions.append(
                f"{interaction.role}: ```{interaction.user_action.value} {interaction.user_action_description}```"
            )

    return "\n".join(formatted_interactions)


def format_request_groups_to_history_string(
    request_groups: list[RequestInteractionDataModel],
) -> str:
    """
    Format interactions grouped by request group into a string.

    All RequestInteractionDataModel objects with the same request_group name are consolidated
    under a single header. Within each consolidated group, interactions are ordered by
    their id in ascending order (smaller to bigger).

    Args:
        request_groups (list[RequestInteractionDataModel]): List of request interaction groups to format

    Returns:
        str: A formatted string with interactions grouped by request group.
             Returns empty string if no groups are provided.

    Example:
        >>> # Given request groups with interactions (multiple requests in same group)
        >>> result = format_request_groups_to_history_string(request_groups)
        >>> print(result)
        === Request Group: session_1 ===
        user: Hello, I need help
        assistant: How can I assist you?
        user: Thanks for the help
        assistant: You're welcome!

        === Request Group: session_2 ===
        user: I love sushi
        assistant: That's great!
    """
    if not request_groups:
        return ""

    # Group all RequestInteractionDataModel objects by their request_group name
    grouped_by_name: dict[str, list[RequestInteractionDataModel]] = {}
    for request_interaction in request_groups:
        if request_interaction.request_group not in grouped_by_name:
            grouped_by_name[request_interaction.request_group] = []
        grouped_by_name[request_interaction.request_group].append(request_interaction)

    # Sort each group's requests by created_at timestamp
    for group_name in grouped_by_name:
        grouped_by_name[group_name] = sorted(
            grouped_by_name[group_name], key=lambda g: g.request.created_at
        )

    # Sort group names by the earliest request timestamp in each group
    sorted_group_names = sorted(
        grouped_by_name.keys(),
        key=lambda name: grouped_by_name[name][0].request.created_at,
    )

    formatted_groups = []
    for group_name in sorted_group_names:
        # Format header with request group name
        group_header = f"=== Request Group: {group_name} ==="

        # Combine all interactions from all requests in this group
        all_interactions = []
        for request_interaction in grouped_by_name[group_name]:
            all_interactions.extend(request_interaction.interactions)

        # Sort interactions by id ascending (smaller to bigger)
        all_interactions = sorted(all_interactions, key=lambda i: i.interaction_id)

        # Format combined interactions
        group_interactions = format_interactions_to_history_string(all_interactions)

        # Combine header and interactions
        formatted_groups.append(f"{group_header}\n{group_interactions}")

    return "\n\n".join(formatted_groups)


def extract_interactions_from_request_interaction_data_models(
    request_interaction_data_models: list[RequestInteractionDataModel],
) -> list[Interaction]:
    """
    Extract a flat list of interactions from request interaction groups.

    This is useful for backward compatibility with services that still expect
    a flat list of interactions.

    Args:
        request_interaction_data_models (list[RequestInteractionDataModel]): List of request interaction data models

    Returns:
        list[Interaction]: Flat list of all interactions from all groups
    """
    interactions = []
    for request_interaction_data_model in request_interaction_data_models:
        interactions.extend(request_interaction_data_model.interactions)
    return interactions


def construct_messages_from_interactions(
    interactions: list[Interaction],
    config: MessageConstructionConfig,
) -> list[dict]:
    """
    Construct a list of LLM messages from interactions with custom prompts.

    This function creates a structured message sequence:
    1. Optional system message (using system_prompt_config)
    2. Single user message containing:
       - Formatted interactions (text content and user actions)
       - User prompt (if configured)
       - Last interaction's image (if present)

    Args:
        interactions: List of interactions to convert into messages
        config: Configuration for message construction including prompt configs

    Returns:
        list[dict]: List of messages ready to be sent to the LLM API.
            Each message is a dict with 'role' and 'content' keys.

    Example:
        >>> system_config = PromptConfig(
        ...     prompt_id="profile_update_instruction_start",
        ...     variables={"agent_context_prompt": "...", "context_prompt": "..."}
        ... )
        >>> user_config = PromptConfig(
        ...     prompt_id="profile_update_main",
        ...     variables={"profile_content_definition_prompt": "...", "existing_profiles": "..."}
        ... )
        >>> config = MessageConstructionConfig(
        ...     prompt_manager=prompt_manager,
        ...     system_prompt_config=system_config,
        ...     user_prompt_config=user_config
        ... )
        >>> messages = construct_messages_from_interactions(interactions, config)
    """
    messages = []

    # Add system message if configured
    if config.system_prompt_config:
        system_content = config.prompt_manager.render_prompt(
            config.system_prompt_config.prompt_id,
            config.system_prompt_config.variables,
        )
        messages.append({"role": "system", "content": system_content})

    # Build combined user message content
    combined_content = []

    # Add user prompt if configured
    if config.user_prompt_config:
        user_prompt_content = config.prompt_manager.render_prompt(
            config.user_prompt_config.prompt_id,
            config.user_prompt_config.variables,
        )
        combined_content.append({"type": "text", "text": user_prompt_content})

    # Add last interaction's image (if present)
    if interactions:
        last_interaction = interactions[-1]

        # Add image URL (priority over base64)
        if last_interaction.interacted_image_url:
            combined_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": last_interaction.interacted_image_url},
                }
            )
        # Add base64-encoded image if no URL
        elif last_interaction.image_encoding:
            combined_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{last_interaction.image_encoding}"
                    },
                }
            )

    # Add combined user message if there's any content
    if combined_content:
        messages.append({"role": "user", "content": combined_content})

    return messages


def extract_json_from_string(text: str) -> dict:
    """
    Extract JSON from a string, handling both JSON-style and Python-style booleans.

    This function attempts to extract JSON from text in the following order:
    1. From code blocks (```json...```)
    2. From content between first { and last }

    It also handles Python-style boolean values (True/False/None) by converting
    them to JSON-style (true/false/null) before parsing, and falls back to
    Python literal parsing for dict-like responses that use single quotes.

    Args:
        text (str): string to extract JSON from

    Returns:
        dict: JSON object, or empty dict if parsing fails
    """

    def normalize_json_string(json_str: str) -> str:
        """Convert Python-style syntax to JSON-friendly syntax.

        Handles:
        - Python booleans (True/False/None) -> JSON (true/false/null)
        """
        # Replace Python boolean/null values with JSON equivalents
        # Use word boundaries to avoid replacing parts of strings
        json_str = re.sub(r"\bTrue\b", "true", json_str)
        json_str = re.sub(r"\bFalse\b", "false", json_str)
        json_str = re.sub(r"\bNone\b", "null", json_str)

        return json_str

    def fix_unescaped_inner_quotes(json_str: str) -> str:
        """
        Attempt to fix common cases where apostrophes are returned as double quotes.

        Many LLMs occasionally substitute `customer's` with `customer"s`, leaving the JSON
        invalid because the double quote isn't escaped. We treat double quotes that sit
        between two word characters as apostrophes.
        """
        return re.sub(r"(?<=\w)\"(?=\w)", "'", json_str)

    def parse_json_candidate(json_str: str) -> tuple[Optional[dict], Optional[str]]:
        """
        Try to parse a JSON candidate string using multiple strategies.

        Strategies:
        1. Direct json.loads
        2. json.loads after normalizing Python syntax
        3. ast.literal_eval as a fallback for Python-style dicts
        """
        candidates = [json_str]
        last_error: Optional[str] = None

        normalized_json_str = normalize_json_string(json_str)
        if normalized_json_str != json_str:
            candidates.append(normalized_json_str)

        repaired_json_str = fix_unescaped_inner_quotes(normalized_json_str)
        if repaired_json_str not in candidates:
            candidates.append(repaired_json_str)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed, None
            except json.JSONDecodeError as err:
                last_error = str(err)
                continue

        for candidate in candidates:
            try:
                parsed = ast.literal_eval(candidate)
                if isinstance(parsed, dict):
                    return parsed, None
            except (ValueError, SyntaxError) as err:
                last_error = str(err)
                continue

        return None, last_error

    # Pattern to match content between triple backticks and json keyword
    # Allow optional whitespace around json keyword and content
    pattern = r"```json\s*(.*?)\s*```"

    # Find the match using regex
    match = re.search(pattern, text, re.DOTALL)

    if match:
        json_str = match.group(1)
        parsed_json, error_message = parse_json_candidate(json_str)
        if parsed_json is not None:
            return parsed_json
        if error_message:
            logger.warning("Failed to parse JSON from code block: %s", error_message)

    # Try to find JSON content between first { and last }
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1:
        json_str = text[start_idx : end_idx + 1]
        parsed_json, error_message = parse_json_candidate(json_str)
        if parsed_json is not None:
            return parsed_json
        if error_message:
            logger.warning("Failed to parse JSON from braces: %s", error_message)

    return {}


def try_parse_json(text: str) -> dict:
    try:
        return ast.literal_eval(text)
    except Exception:
        logger.error("Error in try_parse_json: %s", text)
        return {}


def format_messages_for_logging(messages: list[dict[str, Any]]) -> str:
    """
    Format messages for logging with proper newlines in text content.

    Args:
        messages: List of message dictionaries with role and content

    Returns:
        str: Formatted string representation of messages with newlines preserved
    """
    formatted_parts = []
    for i, msg in enumerate(messages):
        formatted_parts.append(f"Message {i + 1}:")
        formatted_parts.append(f"  role: {msg.get('role', 'unknown')}")
        content = msg.get("content", "")

        if isinstance(content, str):
            # Simple string content - preserve newlines
            formatted_parts.append("  content:")
            # Indent each line of content
            for line in content.split("\n"):
                formatted_parts.append(f"    {line}")
        elif isinstance(content, list):
            # Multimodal content (list of objects)
            formatted_parts.append("  content:")
            for item in content:
                if isinstance(item, dict):
                    item_type = item.get("type", "unknown")
                    if item_type == "text":
                        text_content = item.get("text", "")
                        formatted_parts.append(f"    type: {item_type}")
                        formatted_parts.append("    text:")
                        # Indent each line of text
                        for line in text_content.split("\n"):
                            formatted_parts.append(f"      {line}")
                    else:
                        # For non-text content, use JSON representation
                        formatted_parts.append(f"    {json.dumps(item, indent=4)}")
                else:
                    formatted_parts.append(f"    {json.dumps(item, indent=4)}")
        else:
            # Fallback to JSON for other types
            formatted_parts.append(f"  content: {json.dumps(content, indent=4)}")

        formatted_parts.append("")  # Empty line between messages

    return "\n".join(formatted_parts)


# Example usage
if __name__ == "__main__":
    test_string = """'Based on the existing profiles (which are currently empty) and the new interaction indicating a preference for sushi, the update would involve adding a new profile that reflects this preference. Here's the JSON format for the updates:\n\n```json\n{\n    "add_profile": ["I like sushi"],\n    "delete_profile": []\n}\n```'"""

    result = extract_json_from_string(test_string)
    print("Extracted JSON:", result)
