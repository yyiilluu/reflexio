from datetime import datetime, timezone
import logging
from typing import Any, Optional, TYPE_CHECKING
import uuid
import os

from reflexio.server.api_endpoints.request_context import RequestContext
from reflexio.server.llm.litellm_client import LiteLLMClient
from reflexio_commons.api_schema.service_schemas import (
    UserProfile,
    ProfileChangeLog,
)
from reflexio_commons.api_schema.internal_schema import RequestInteractionDataModel

from reflexio_commons.config_schema import ProfileExtractorConfig
from reflexio.server.services.extractor_interaction_utils import (
    get_extractor_operation_state_key,
    get_extractor_window_params,
    get_effective_source_filter,
    should_extractor_run_by_stride,
    update_extractor_operation_state,
)

if TYPE_CHECKING:
    from reflexio.server.services.profile.profile_generation_service import (
        ProfileGenerationServiceConfig,
    )
from reflexio.server.services.profile.profile_generation_service_utils import (
    ProfileGenerationServiceConstants,
    ProfileUpdates,
    ProfileUpdateOutput,
    construct_profile_extraction_messages_from_request_groups,
    calculate_expiration_timestamp,
    check_string_token_overlap,
)
from reflexio.server.services.service_utils import (
    format_messages_for_logging,
    format_request_groups_to_history_string,
    extract_interactions_from_request_interaction_data_models,
)
from reflexio.server.services.profile.profile_generation_service_utils import (
    ProfileTimeToLive,
)
from reflexio.server.site_var.site_var_manager import SiteVarManager

logger = logging.getLogger(__name__)


class ProfileExtractor:
    """
    Extract user profile information from interactions.

    This class analyzes user interactions to identify, update, and manage user profiles,
    including adding new information, removing outdated information, and tracking mentions.
    """

    def __init__(
        self,
        request_context: RequestContext,
        llm_client: LiteLLMClient,
        extractor_config: ProfileExtractorConfig,
        service_config: "ProfileGenerationServiceConfig",
        agent_context: str,
    ):
        """
        Initialize the profile extractor.

        Args:
            request_context: Request context with storage and prompt manager
            llm_client: Unified LLM client supporting both OpenAI and Claude
            extractor_config: Profile extractor configuration from YAML
            service_config: Runtime service configuration with request data
            agent_context: Context about the agent
        """
        self.request_context = request_context
        self.client = llm_client
        self.config: ProfileExtractorConfig = extractor_config
        self.service_config: "ProfileGenerationServiceConfig" = service_config
        self.agent_context = agent_context

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

    def _get_operation_state_key(self) -> str:
        """
        Get unique operation state key for this extractor.

        Returns:
            Operation state key in format: "profile_extractor::{org_id}::{user_id}::{extractor_name}"
        """
        return get_extractor_operation_state_key(
            org_id=self.request_context.org_id,
            service_name="profile_extractor",
            extractor_name=self.config.extractor_name,
            user_id=self.service_config.user_id,
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

        state_key = self._get_operation_state_key()
        storage = self.request_context.storage

        # Stride check only for auto_run=True (regular flow)
        if self.service_config.auto_run:
            # Get new interactions since last run for stride check
            (
                state,
                new_interactions,
            ) = storage.get_operation_state_with_new_request_interaction(
                state_key, self.service_config.user_id, effective_source
            )
            new_count = sum(len(ri.interactions) for ri in new_interactions)

            # Check stride
            if not should_extractor_run_by_stride(new_count, stride_size):
                logger.info(
                    "Skipping profile extraction - stride not met (new=%d, stride=%s)",
                    new_count,
                    stride_size,
                )
                return None

        # Get window interactions with time range filter
        if window_size and window_size > 0:
            request_groups, _ = storage.get_last_k_interactions_grouped(
                user_id=self.service_config.user_id,
                k=window_size,
                sources=effective_source,
                start_time=self.service_config.rerun_start_time,
                end_time=self.service_config.rerun_end_time,
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
        state_key = self._get_operation_state_key()
        update_extractor_operation_state(
            self.request_context.storage, state_key, all_interactions
        )

    def should_extract_profile(
        self, request_interaction_data_models: list[RequestInteractionDataModel]
    ) -> bool:
        """
        Determine if profile extraction should be performed on the given interactions.

        Args:
            request_interaction_data_models: List of request interaction groups to analyze

        Returns:
            bool: True if profile extraction should proceed, False otherwise
        """
        new_interactions = format_request_groups_to_history_string(
            request_interaction_data_models
        )

        if self.config.should_extract_profile_prompt_override:
            prompt = self.request_context.prompt_manager.render_prompt(
                ProfileGenerationServiceConstants.PROFILE_SHOULD_GENERATE_OVERRIDE_PROMPT_ID,
                {
                    "instruction_override": self.config.should_extract_profile_prompt_override.strip(),
                    "new_interactions": new_interactions,
                },
            )
        else:
            prompt = self.request_context.prompt_manager.render_prompt(
                ProfileGenerationServiceConstants.PROFILE_SHOULD_GENERATE_PROMPT_ID,
                {
                    "agent_context_prompt": self.agent_context,
                    "should_extract_profile_prompt": self.config.profile_content_definition_prompt.strip(),
                    "new_interactions": new_interactions,
                },
            )

        # Check if mock mode is enabled
        mock_env = os.getenv("MOCK_LLM_RESPONSE", "")
        if mock_env.lower() == "true":
            # Return mock response based on prompt analysis
            # For testing, return True if interactions contain substantial content
            return True

        try:
            content = self.client.generate_chat_response(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.should_run_model_name,
            )
            logger.info("Should extract profile response: %s", content)

            if content and "true" in content.lower():
                return True
            return False
        except Exception as exc:
            logger.error(
                "Failed to determine profile extraction need due to %s, "
                "defaulting to extract profile.",
                str(exc),
            )
            return True

    def run(self) -> Optional[ProfileUpdates]:
        """
        Extract profile updates from request interaction groups.

        This extractor handles its own data collection:
        1. Gets interactions based on its config (window size, source filtering)
        2. Checks stride to determine if extraction should run (only for auto_run=True)
        3. Applies time range filter for rerun flows
        4. Updates operation state after processing

        Returns:
            Optional[ProfileUpdates]: Profile updates/changes log, or None if no updates
        """
        # Collect interactions using extractor's own window/stride settings
        request_interaction_data_models = self._get_interactions()
        if not request_interaction_data_models:
            # No interactions or stride not met
            return None

        existing_profiles = self.service_config.existing_data

        if not self.should_extract_profile(request_interaction_data_models):
            logger.info("No profile updates to extract")
            return None

        raw_updates = self._generate_raw_updates_from_request_groups(
            request_interaction_data_models=request_interaction_data_models,
            existing_profiles=existing_profiles,
        )
        logger.info("Generated raw updates: %s", raw_updates)
        if raw_updates:
            profile_updates = self._get_profile_updates_from_existing_profiles(
                user_id=self.service_config.user_id,
                request_id=self.service_config.request_id,
                existing_profiles=existing_profiles,
                profile_updates=raw_updates,
            )

            # Update operation state after successful processing
            self._update_operation_state(request_interaction_data_models)

            return profile_updates
        return None

    def _get_profile_updates_from_existing_profiles(
        self,
        user_id: str,
        request_id: str,
        existing_profiles: list[UserProfile],
        profile_updates: dict[str, Any],
    ) -> ProfileUpdates | None:
        """get profile updates from existing profiles

        Args:
            user_id (str): user id
            request_id (str): request id
            existing_profiles (list[UserProfile]): existing profiles
            profile_updates (dict[str, Any]): profile updates

        Returns:
            ProfileUpdates | None: profile updates/changes log
        """
        new_profiles = []
        tobe_removed_profiles = []
        mention_profiles = []
        for update_type, update_content in profile_updates.items():
            if update_type == "add":
                for profile_content in update_content:
                    if (
                        not isinstance(profile_content, dict)
                        or "content" not in profile_content
                    ):
                        logger.warning("Invalid profile content: %s", profile_content)
                        continue

                    # Get all custom features by excluding content and time_to_live
                    custom_features = {
                        k: v
                        for k, v in profile_content.items()
                        if k not in ["content", "time_to_live"]
                    }

                    added_profile = UserProfile(
                        profile_id=str(uuid.uuid4()),
                        user_id=user_id,
                        profile_content=profile_content["content"],
                        last_modified_timestamp=int(
                            datetime.now(timezone.utc).timestamp()
                        ),
                        generated_from_request_id=request_id,
                        profile_time_to_live=ProfileTimeToLive(
                            profile_content.get("time_to_live", "infinity")
                        ),
                        expiration_timestamp=calculate_expiration_timestamp(
                            int(
                                datetime.now(timezone.utc).timestamp()
                            ),  # Convert float to int
                            ProfileTimeToLive(
                                profile_content.get("time_to_live", "infinity")
                            ),
                        ),
                        custom_features=custom_features,
                    )

                    new_profiles.append(added_profile)
            elif update_type == "delete":
                tobe_removed_profiles = [
                    profile
                    for profile in existing_profiles
                    if any(
                        check_string_token_overlap(profile.profile_content, content)
                        for content in update_content
                    )
                ]
            elif update_type == "mention":
                for profile in existing_profiles:
                    if any(
                        check_string_token_overlap(profile.profile_content, content)
                        for content in update_content
                    ):
                        profile.last_modified_timestamp = int(
                            datetime.now(timezone.utc).timestamp()
                        )
                        profile.generated_from_request_id = request_id
                        profile.expiration_timestamp = calculate_expiration_timestamp(
                            profile.last_modified_timestamp,
                            profile.profile_time_to_live,
                        )
                        mention_profiles.append(profile)

        if not new_profiles and not tobe_removed_profiles and not mention_profiles:
            return None

        # Rename variable to avoid confusion with parameter name
        profile_updates_result = ProfileUpdates(
            add_profiles=new_profiles,
            delete_profiles=tobe_removed_profiles,
            mention_profiles=mention_profiles,
        )

        # update profile change log to db
        profile_change_log = ProfileChangeLog(
            id=0,  # This will be auto-generated by the storage
            user_id=user_id,
            request_id=request_id,
            created_at=int(datetime.now(timezone.utc).timestamp()),
            added_profiles=new_profiles,
            removed_profiles=tobe_removed_profiles,
            mentioned_profiles=mention_profiles,
        )

        self.request_context.storage.add_profile_change_log(profile_change_log)

        return profile_updates_result

    def _generate_raw_updates_from_request_groups(
        self,
        request_interaction_data_models: list[RequestInteractionDataModel],
        existing_profiles: list[UserProfile],
    ) -> dict[str, Any]:
        """
        Generate raw profile updates from request interaction groups.

        Args:
            request_interaction_data_models: List of request interaction groups
            existing_profiles: List of existing user profiles

        Returns:
            dict[str, Any]: Raw profile updates with add/delete/mention operations
        """
        # Check if mock mode is enabled
        mock_env_for_raw = os.getenv("MOCK_LLM_RESPONSE", "")
        if mock_env_for_raw.lower() == "true":
            # Return mock profile updates based on interactions
            return self._generate_profile_updates_from_request_groups(
                request_interaction_data_models=request_interaction_data_models,
                existing_profiles=existing_profiles,
            )

        # get user profile prompt from configurator or use the default prompt
        messages = construct_profile_extraction_messages_from_request_groups(
            prompt_manager=self.request_context.prompt_manager,
            request_interaction_data_models=request_interaction_data_models,
            agent_context_prompt=self.agent_context,
            context_prompt=(
                self.config.context_prompt.strip() if self.config.context_prompt else ""
            ),
            profile_content_definition_prompt=self.config.profile_content_definition_prompt.strip(),
            metadata_definition_prompt=(
                self.config.metadata_definition_prompt.strip()
                if self.config.metadata_definition_prompt
                else None
            ),
            existing_profiles=existing_profiles,
        )
        # Messages are already in dict format from construct_messages_from_interactions
        messages_dict = messages

        logger.info(
            "Profile extraction messages: %s",
            format_messages_for_logging(messages_dict),
        )

        # Use ProfileUpdateOutput schema for structured output
        update_response = self.client.generate_chat_response(
            messages=messages_dict,
            model=self.default_generation_model_name,
            response_format=ProfileUpdateOutput,
        )
        logger.info("Profile updates model response: %s", update_response)
        if not update_response or not isinstance(update_response, ProfileUpdateOutput):
            return {}

        # Convert Pydantic model to dict for downstream processing
        update_response = update_response.model_dump()

        if self._has_profile_update_actions(update_response):
            return update_response
        else:
            logger.warning(
                "Profile extraction response could not be parsed into actions"
            )
            return {}

    def _has_profile_update_actions(self, updates: dict[str, Any]) -> bool:
        """
        Determine whether the parsed updates contain any actionable profile operations.
        """
        if not updates:
            return False

        actionable_keys = {"add", "delete", "mention"}
        for key in actionable_keys:
            if key in updates and updates.get(key):
                return True
        return False

    def _generate_profile_updates_from_request_groups(
        self,
        request_interaction_data_models: list[RequestInteractionDataModel],
        existing_profiles: list[UserProfile],
    ) -> dict[str, Any]:
        """
        Generate heuristic profile updates based on recent request interaction groups.

        This is used both in mock mode and as a fallback when LLM responses are not
        parseable. The content mirrors the expected structure from the prompt.

        Args:
            request_interaction_data_models: List of request interaction groups
            existing_profiles: List of existing user profiles

        Returns:
            dict[str, Any]: Mock profile updates in the expected format
        """
        # Extract flat interactions from request groups
        interactions = extract_interactions_from_request_interaction_data_models(
            request_interaction_data_models
        )

        # Analyze interactions to generate realistic mock updates
        mock_updates = {}

        # Extract some sample content from interactions for realistic mocks
        if interactions:
            sample_content = (
                interactions[-1].content[:50]
                if interactions[-1].content
                else "sample interaction"
            )

            # Capture additional context that contains helpful keywords (e.g. product mentions)
            highlight_keywords = {
                "software",
                "solution",
                "product",
                "company",
                "service",
            }
            highlighted_snippet = next(
                (
                    interaction.content[:80]
                    for interaction in reversed(interactions)
                    if interaction.content
                    and any(
                        keyword in interaction.content.lower()
                        for keyword in highlight_keywords
                    )
                ),
                "",
            )

            summary_parts = [f"User mentioned: {sample_content}"]
            if highlighted_snippet and highlighted_snippet not in sample_content:
                summary_parts.append(f"Key context: {highlighted_snippet}")

            # Add a new profile based on the interaction
            mock_updates["add"] = [
                {
                    "content": " ".join(summary_parts),
                    "time_to_live": "one_month",
                }
            ]

            # If metadata definition exists, add mock metadata
            if self.config.metadata_definition_prompt:
                mock_updates["add"][0]["metadata"] = "mock_metadata_value"

        # Check for profile mentions (if existing profiles exist)
        if existing_profiles and len(existing_profiles) > 0:
            # Mock a mention of an existing profile
            mock_updates["mention"] = [existing_profiles[0].profile_content]

        return mock_updates
