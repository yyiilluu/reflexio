import logging
import os
from typing import Optional, TYPE_CHECKING

from reflexio.server.api_endpoints.request_context import RequestContext
from reflexio.server.llm.litellm_client import LiteLLMClient
from reflexio_commons.config_schema import AgentFeedbackConfig
from reflexio_commons.api_schema.service_schemas import RawFeedback
from reflexio_commons.api_schema.internal_schema import RequestInteractionDataModel

from reflexio.server.services.extractor_interaction_utils import (
    get_extractor_window_params,
    get_effective_source_filter,
    should_extractor_run_by_stride,
)
from reflexio.server.services.operation_state_utils import OperationStateManager
from reflexio.server.services.feedback.feedback_service_constants import (
    FeedbackServiceConstants,
)
from reflexio.server.services.feedback.feedback_service_utils import (
    construct_feedback_extraction_messages_from_request_groups,
    StructuredFeedbackContent,
)
from reflexio.server.services.service_utils import (
    format_messages_for_logging,
    format_request_groups_to_history_string,
    extract_interactions_from_request_interaction_data_models,
    log_model_response,
)
from reflexio.server.site_var.site_var_manager import SiteVarManager

if TYPE_CHECKING:
    from reflexio.server.services.feedback.feedback_generation_service import (
        FeedbackGenerationServiceConfig,
    )

logger = logging.getLogger(__name__)

"""
Extract agent evolvement feedback from agent to improve its performance through self evolvement.
Make better decisions on what to improve next time.
"""


class FeedbackExtractor:
    """
    Extract agent evolvement feedback from agent interactions to improve its performance.

    This class analyzes agent-user interactions and generates structured feedback
    to help the agent make better decisions.
    """

    def __init__(
        self,
        request_context: RequestContext,
        llm_client: LiteLLMClient,
        extractor_config: AgentFeedbackConfig,
        service_config: "FeedbackGenerationServiceConfig",
        agent_context: str,
    ):
        """
        Initialize the feedback extractor.

        Args:
            request_context: Request context with storage and prompt manager
            llm_client: Unified LLM client supporting both OpenAI and Claude
            extractor_config: Feedback configuration from YAML
            service_config: Runtime service configuration with request data
            agent_context: Context about the agent
        """
        self.request_context: RequestContext = request_context
        self.client: LiteLLMClient = llm_client
        self.config: AgentFeedbackConfig = extractor_config
        self.service_config: "FeedbackGenerationServiceConfig" = service_config
        self.agent_context: str = agent_context

        # Get LLM config overrides from configuration
        config = self.request_context.configurator.get_config()
        llm_config = config.llm_config if config else None

        # Get site var as fallback
        self.model_setting = SiteVarManager().get_site_var("llm_model_setting")
        assert isinstance(self.model_setting, dict), "llm_model_setting must be a dict"

        # Use override if present, otherwise fallback to site var
        self.should_run_model_name = (
            llm_config.should_run_model_name
            if llm_config and llm_config.should_run_model_name
            else self.model_setting.get("should_run_model_name", "gpt-5-mini")
        )
        self.default_generation_model_name = (
            llm_config.generation_model_name
            if llm_config and llm_config.generation_model_name
            else self.model_setting.get("default_generation_model_name", "gpt-5-mini")
        )

    def _create_state_manager(self) -> OperationStateManager:
        """
        Create an OperationStateManager for this extractor.

        Returns:
            OperationStateManager configured for feedback_extractor
        """
        return OperationStateManager(
            self.request_context.storage,
            self.request_context.org_id,
            "feedback_extractor",
        )

    def _get_interactions(self) -> Optional[list[RequestInteractionDataModel]]:
        """
        Get interactions for this extractor based on its config.

        Handles:
        - Getting window/stride parameters (extractor override or global fallback)
        - Source filtering based on extractor config
        - Stride checking to determine if extractor should run (only for auto_run=True)
        - Time range filtering for rerun flows

        Returns:
            List of request interaction data models if stride is met (or auto_run=False), None otherwise
        """
        # Get global config values
        config = self.request_context.configurator.get_config()
        global_window_size = (
            getattr(config, "extraction_window_size", None) if config else None
        )
        global_stride = (
            getattr(config, "extraction_window_stride", None) if config else None
        )

        # Get effective window/stride for this extractor
        window_size, stride_size = get_extractor_window_params(
            self.config,
            global_window_size,
            global_stride,
        )

        # Get effective source filter (None = get ALL sources)
        should_skip, effective_source = get_effective_source_filter(
            self.config,
            self.service_config.source,
        )
        if should_skip:
            return None

        mgr = self._create_state_manager()
        storage = self.request_context.storage

        # Stride check only for auto_run=True (regular flow)
        if self.service_config.auto_run:
            # Get new interactions since last run for stride check
            # Use user_id from service_config for per-user feedback extraction
            (
                state,
                new_interactions,
            ) = mgr.get_extractor_state_with_new_interactions(
                extractor_name=self.config.feedback_name,
                user_id=self.service_config.user_id,
                sources=effective_source,
            )
            new_count = sum(len(ri.interactions) for ri in new_interactions)

            # Check stride
            if not should_extractor_run_by_stride(new_count, stride_size):
                logger.info(
                    "Skipping feedback extraction - stride not met (new=%d, stride=%s)",
                    new_count,
                    stride_size,
                )
                return None

        # Only filter by agent_version during rerun (non-auto_run) mode
        rerun_agent_version = (
            self.service_config.agent_version
            if not self.service_config.auto_run
            else None
        )

        # Get window interactions with time range filter
        if window_size and window_size > 0:
            request_groups, _ = storage.get_last_k_interactions_grouped(
                user_id=self.service_config.user_id,  # Per-user feedback extraction
                k=window_size,
                sources=effective_source,
                start_time=self.service_config.rerun_start_time,
                end_time=self.service_config.rerun_end_time,
                agent_version=rerun_agent_version,
            )
            return request_groups
        else:
            # No window configured - for auto_run, return new interactions from stride check
            if self.service_config.auto_run:
                # new_interactions was set earlier during stride check
                return new_interactions
            # For non-auto_run without window, we still need to fetch interactions
            # Use a large limit to get all relevant interactions within time range
            request_groups, _ = storage.get_last_k_interactions_grouped(
                user_id=self.service_config.user_id,
                k=1000,  # Reasonable limit for non-windowed rerun
                sources=effective_source,
                start_time=self.service_config.rerun_start_time,
                end_time=self.service_config.rerun_end_time,
                agent_version=rerun_agent_version,
            )
            return request_groups

    def _update_operation_state(
        self, request_interaction_data_models: list[RequestInteractionDataModel]
    ) -> None:
        """
        Update operation state after processing interactions.

        Args:
            request_interaction_data_models: The interactions that were processed
        """
        all_interactions = extract_interactions_from_request_interaction_data_models(
            request_interaction_data_models
        )
        mgr = self._create_state_manager()
        mgr.update_extractor_bookmark(
            extractor_name=self.config.feedback_name,
            processed_interactions=all_interactions,
            user_id=self.service_config.user_id,
        )

    # ===============================
    # public methods
    # ===============================

    def run(self) -> list[RawFeedback]:
        """
        Run feedback extraction on request interaction groups.

        This extractor handles its own data collection:
        1. Gets interactions based on its config (window size, source filtering)
        2. Checks stride to determine if extraction should run (only for auto_run=True)
        3. Applies time range filter for rerun flows
        4. Updates operation state after processing

        Returns:
            list[RawFeedback]: List of extracted feedback
        """
        # Collect interactions using extractor's own window/stride settings
        request_interaction_data_models = self._get_interactions()
        if not request_interaction_data_models:
            # No interactions or stride not met
            return []

        if not self.should_generate_feedback(request_interaction_data_models):
            logger.info("No feedback should be generated for the given interactions")
            return []

        feedbacks = self.extract_feedbacks(request_interaction_data_models)

        # Update operation state after successful processing
        if feedbacks:
            self._update_operation_state(request_interaction_data_models)

        return feedbacks

    def should_generate_feedback(
        self, request_interaction_data_models: list[RequestInteractionDataModel]
    ) -> bool:
        """
        Determine if feedback should be generated from the given request interaction groups.

        Args:
            request_interaction_data_models: List of request interaction groups to analyze

        Returns:
            bool: True if feedback should be generated, False otherwise
        """
        # Check if mock mode is enabled
        if os.getenv("MOCK_LLM_RESPONSE", "").lower() == "true":
            # Return True for testing if interactions contain substantial content
            logger.info(
                "Mock mode: should_generate_feedback returning True for testing"
            )
            return True

        new_interactions = format_request_groups_to_history_string(
            request_interaction_data_models
        )

        # Get tool_can_use from root config (same pattern as extract_feedbacks)
        root_config = self.request_context.configurator.get_config()
        tool_can_use_str = ""
        if root_config and root_config.tool_can_use:
            tool_can_use_str = "\n".join(
                [
                    f"{tool.tool_name}: {tool.tool_description}"
                    for tool in root_config.tool_can_use
                ]
            )

        prompt_manager = self.request_context.prompt_manager
        should_generate_feedback_prompt = prompt_manager.render_prompt(
            FeedbackServiceConstants.RAW_FEEDBACK_SHOULD_GENERATE_PROMPT_ID,
            {
                "agent_context_prompt": self.agent_context,
                "feedback_definition_prompt": self.config.feedback_definition_prompt.strip(),
                "new_interactions": new_interactions,
                "tool_can_use": tool_can_use_str,
            },
        )

        try:
            content = self.client.generate_chat_response(
                messages=[
                    {
                        "role": "user",
                        "content": should_generate_feedback_prompt,
                    }
                ],
                model=self.should_run_model_name,
            )
            logger.info("should run prompt %s", should_generate_feedback_prompt)
            log_model_response(logger, "Should generate feedback response", content)
            if content and "true" in content.lower():
                return True
            return False
        except Exception as exc:
            logger.error(
                "Failed to determine feedback generation need due to %s, "
                "defaulting to generate feedback.",
                str(exc),
            )
            return True

    def extract_feedbacks(
        self, request_interaction_data_models: list[RequestInteractionDataModel]
    ) -> list[RawFeedback]:
        """
        Extract feedbacks from the given request interaction groups using structured output.

        Args:
            request_interaction_data_models: List of request interaction groups

        Returns:
            list[RawFeedback]: List of extracted feedback
        """
        # Get existing feedbacks from service config (past 7 days)
        existing_feedbacks = self.service_config.existing_data or []

        # Check if mock mode is enabled
        if os.getenv("MOCK_LLM_RESPONSE", "").lower() == "true":
            logger.info("Mock mode: generating mock feedback")
            structured = self._generate_mock_feedback(request_interaction_data_models)
            feedback_content = self._format_structured_feedback_content(structured)
            logger.info("Mock feedback: %s", feedback_content)

            return [
                RawFeedback(
                    feedback_name=self.config.feedback_name,
                    user_id=self.service_config.user_id,
                    agent_version=self.service_config.agent_version,
                    request_id=self.service_config.request_id,
                    feedback_content=feedback_content,
                    do_action=structured.do_action,
                    do_not_action=structured.do_not_action,
                    when_condition=structured.when_condition,
                    blocking_issue=structured.blocking_issue,
                    indexed_content=structured.when_condition,
                )
            ]

        # Get tool_can_use from root config
        root_config = self.request_context.configurator.get_config()
        tool_can_use_str = ""
        if root_config and root_config.tool_can_use:
            tool_can_use_str = "\n".join(
                [
                    f"{tool.tool_name}: {tool.tool_description}"
                    for tool in root_config.tool_can_use
                ]
            )

        messages = construct_feedback_extraction_messages_from_request_groups(
            prompt_manager=self.request_context.prompt_manager,
            request_interaction_data_models=request_interaction_data_models,
            agent_context_prompt=self.agent_context,
            feedback_definition_prompt=(
                self.config.feedback_definition_prompt.strip()
                if self.config.feedback_definition_prompt
                else ""
            ),
            existing_raw_feedbacks=existing_feedbacks,
            tool_can_use=tool_can_use_str,
        )
        logger.info(
            "Feedback extraction messages: %s",
            format_messages_for_logging(messages),
        )

        try:
            response = self.client.generate_chat_response(
                messages=messages,
                model=self.default_generation_model_name,
                response_format=StructuredFeedbackContent,
                parse_structured_output=True,
            )
            log_model_response(logger, "Feedback structured response", response)

            raw_feedback = self._process_structured_response(response)
            if raw_feedback is None:
                logger.info("No feedback can be generated for the given interactions")
                return []
            return [raw_feedback]
        except Exception as exc:
            logger.error(
                "Feedback extraction failed due to %s, returning empty.",
                str(exc),
            )
            return []

    def _generate_mock_feedback(
        self, request_interaction_data_models: list[RequestInteractionDataModel]
    ) -> StructuredFeedbackContent:
        """
        Generate mock structured feedback for testing purposes.

        Args:
            request_interaction_data_models: List of request interaction groups

        Returns:
            StructuredFeedbackContent: Mock structured feedback
        """
        # Extract flat interactions from request groups
        interactions = extract_interactions_from_request_interaction_data_models(
            request_interaction_data_models
        )

        # Generate concise feedback based on feedback definition
        feedback_definition = (
            self.config.feedback_definition_prompt.strip()
            if self.config.feedback_definition_prompt
            else "agent behavior"
        )

        # Build when_condition from interaction context
        when_condition = "similar interactions occur"
        if interactions:
            last_interaction = interactions[-1]
            if last_interaction.content:
                content_preview = last_interaction.content[:50]
                when_condition = f"user says something like '{content_preview}'"

        return StructuredFeedbackContent(
            do_action=f"improve on {feedback_definition}",
            do_not_action="continue current approach without adjustment",
            when_condition=when_condition,
        )

    def _format_structured_feedback_content(
        self, structured: StructuredFeedbackContent
    ) -> str:
        """
        Format structured feedback content to prompt instruction format.

        Converts structured fields to bullet format:
        - When: "condition."
        - Do: "action."
        - Don't: "avoid action."

        Args:
            structured (StructuredFeedbackContent): The structured feedback content

        Returns:
            str: Formatted feedback content string for prompts
        """
        lines = []

        # When condition always comes first
        lines.append(f'When: "{structured.when_condition}"')

        # Add Do if present
        if structured.do_action:
            lines.append(f'Do: "{structured.do_action}"')

        # Add Don't if present
        if structured.do_not_action:
            lines.append(f'Don\'t: "{structured.do_not_action}"')

        # Add blocking issue if present
        if structured.blocking_issue:
            lines.append(
                f"Blocked by: [{structured.blocking_issue.kind.value}] {structured.blocking_issue.details}"
            )

        return "\n".join(lines)

    def _process_structured_response(
        self, response: StructuredFeedbackContent
    ) -> Optional[RawFeedback]:
        """
        Process structured response from LLM into RawFeedback.

        Args:
            response (StructuredFeedbackContent): Parsed Pydantic model from structured output

        Returns:
            RawFeedback or None if no feedback should be generated
        """
        if not response or not response.has_feedback:
            return None

        # Format to canonical string
        feedback_content = self._format_structured_feedback_content(response)

        return RawFeedback(
            feedback_name=self.config.feedback_name,
            user_id=self.service_config.user_id,
            agent_version=self.service_config.agent_version,
            request_id=self.service_config.request_id,
            feedback_content=feedback_content,
            do_action=response.do_action,
            do_not_action=response.do_not_action,
            when_condition=response.when_condition,
            blocking_issue=response.blocking_issue,
            indexed_content=response.when_condition,  # Use when_condition for indexing
        )
