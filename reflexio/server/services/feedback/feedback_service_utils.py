from typing import Any, Optional

from reflexio_commons.api_schema.internal_schema import RequestInteractionDataModel
from reflexio_commons.api_schema.service_schemas import RawFeedback
from pydantic import BaseModel, Field, ConfigDict, model_validator

from reflexio.server.services.feedback.feedback_service_constants import (
    FeedbackServiceConstants,
)
from reflexio.server.prompt.prompt_manager import PromptManager
from reflexio.server.services.service_utils import (
    PromptConfig,
    MessageConstructionConfig,
    construct_messages_from_interactions,
    format_request_groups_to_history_string,
    extract_interactions_from_request_interaction_data_models,
)


# ===============================
# Pydantic classes for raw_feedback_extraction_main prompt output schema
# ===============================


class StructuredFeedbackContent(BaseModel):
    """
    Structured representation of feedback content.

    Handles two formats:
    1. Feedback present: {"do_action": "...", "do_not_action": "...", "when_condition": "..."}
    2. No feedback: {"feedback": null}

    Represents feedback in the format: "Do [do_action] instead of [do_not_action] when [when_condition]"
    At least one of do_action or do_not_action must be provided when when_condition is set.
    """

    do_action: Optional[str] = Field(
        default=None,
        description="The preferred behavior the agent should adopt",
    )
    do_not_action: Optional[str] = Field(
        default=None,
        description="The mistaken behavior the agent should avoid",
    )
    when_condition: Optional[str] = Field(
        default=None,
        description="The condition or context when this rule applies",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"additionalProperties": False},
    )

    @model_validator(mode="before")
    @classmethod
    def handle_null_feedback_format(cls, data: Any) -> Any:
        """Handle the {"feedback": null} format by converting it to empty dict."""
        if isinstance(data, dict) and "feedback" in data and data["feedback"] is None:
            return {}
        return data

    @model_validator(mode="after")
    def validate_feedback_fields(self) -> "StructuredFeedbackContent":
        """Ensure at least one action is provided when condition is present."""
        if self.when_condition is not None:
            if self.do_action is None and self.do_not_action is None:
                raise ValueError(
                    "At least one of 'do_action' or 'do_not_action' must be provided when 'when_condition' is set"
                )
        return self

    @property
    def has_feedback(self) -> bool:
        """Check if this output contains actual feedback.

        Requires a non-empty when_condition and at least one non-empty action (do or don't).
        """
        has_condition = bool(self.when_condition and self.when_condition.strip())
        has_action = bool(
            (self.do_action and self.do_action.strip())
            or (self.do_not_action and self.do_not_action.strip())
        )
        return has_condition and has_action


# ===============================
# Pydantic classes for feedback_generation prompt output schema (v2.1.0+)
# ===============================


class FeedbackAggregationOutput(BaseModel):
    """
    Output schema for feedback_generation prompt (version >= 2.1.0).

    Contains the consolidated feedback or null if no new feedback should be generated
    (e.g., when it duplicates existing approved feedback).
    """

    feedback: Optional[StructuredFeedbackContent] = Field(
        default=None,
        description="The consolidated feedback, or null if no new feedback should be generated",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"additionalProperties": False},
    )


class FeedbackGenerationRequest(BaseModel):
    request_id: str
    agent_version: str
    user_id: Optional[str] = None  # for per-user feedback extraction
    source: Optional[str] = None
    rerun_start_time: Optional[int] = None  # Unix timestamp for rerun flows
    rerun_end_time: Optional[int] = None  # Unix timestamp for rerun flows
    feedback_name: Optional[str] = None  # Filter to run only specific extractor
    auto_run: bool = (
        True  # True for regular flow (checks stride), False for rerun/manual
    )


class FeedbackAggregatorRequest(BaseModel):
    agent_version: str
    feedback_name: str
    rerun: bool = False


def construct_feedback_extraction_messages_from_request_groups(
    prompt_manager: PromptManager,
    request_interaction_data_models: list[RequestInteractionDataModel],
    agent_context_prompt: str,
    feedback_definition_prompt: str,
    existing_raw_feedbacks: Optional[list[RawFeedback]] = None,
) -> list[dict]:
    """
    Construct LLM messages for feedback extraction from request interaction groups.

    This function uses the shared message construction interface to build messages
    with a system prompt and a final user prompt specific to feedback extraction.

    Args:
        prompt_manager: The prompt manager for rendering prompt templates
        request_interaction_data_models: List of request interaction groups to extract feedback from
        agent_context_prompt: Context about the agent for system message
        feedback_definition_prompt: Definition of what feedback should contain
        existing_raw_feedbacks: Optional list of existing raw feedbacks from past 7 days

    Returns:
        list[dict]: List of messages ready for feedback extraction
    """
    # Configure system message (before interactions)
    system_config = PromptConfig(
        prompt_id=FeedbackServiceConstants.RAW_FEEDBACK_EXTRACTION_CONTEXT_PROMPT_ID,
        variables={
            "agent_context_prompt": agent_context_prompt,
        },
    )

    # Format existing feedbacks for context
    formatted_existing_feedbacks = ""
    if existing_raw_feedbacks:
        formatted_existing_feedbacks = "\n".join(
            [f"- {feedback.feedback_content}" for feedback in existing_raw_feedbacks]
        )
    else:
        formatted_existing_feedbacks = "(No existing feedbacks)"

    # Configure final user message (after interactions)
    user_config = PromptConfig(
        prompt_id=FeedbackServiceConstants.RAW_FEEDBACK_EXTRACTION_PROMPT_ID,
        variables={
            "feedback_definition_prompt": feedback_definition_prompt,
            "existing_feedbacks": formatted_existing_feedbacks,
            "interactions": format_request_groups_to_history_string(
                request_interaction_data_models
            ),
        },
    )

    # Extract flat interactions for message construction
    interactions = extract_interactions_from_request_interaction_data_models(
        request_interaction_data_models
    )

    # Use shared message construction
    config = MessageConstructionConfig(
        prompt_manager=prompt_manager,
        system_prompt_config=system_config,
        user_prompt_config=user_config,
    )

    return construct_messages_from_interactions(interactions, config)
