"""
Profile deduplication service that merges duplicate profiles from multiple extractors using LLM.
"""

from datetime import datetime, timezone
import logging
from typing import Optional
import uuid

from pydantic import BaseModel, Field, ConfigDict

from reflexio.server.api_endpoints.request_context import RequestContext
from reflexio.server.llm.litellm_client import LiteLLMClient
from reflexio.server.services.deduplication_utils import (
    BaseDeduplicator,
)
from reflexio.server.services.profile.profile_generation_service_utils import (
    ProfileUpdates,
    ProfileTimeToLive,
    calculate_expiration_timestamp,
)
from reflexio_commons.api_schema.service_schemas import UserProfile

logger = logging.getLogger(__name__)


# ===============================
# Profile-specific Pydantic Output Schemas for LLM
# ===============================


class ProfileDuplicateGroup(BaseModel):
    """
    Represents a group of profiles that are duplicates of each other.

    Attributes:
        item_indices: List of indices (0-based) from the input profiles list that are duplicates
        merged_content: The consolidated profile content combining information from all duplicates
        merged_time_to_live: The chosen time_to_live for the merged profile
        reasoning: Brief explanation of why these profiles are duplicates and how they were merged
    """

    item_indices: list[int] = Field(
        description="Indices of profiles in the input list that are duplicates of each other"
    )
    merged_content: str = Field(
        description="Consolidated profile content combining all duplicate information"
    )
    merged_time_to_live: str = Field(
        description="Time to live for merged profile: one_day, one_week, one_month, one_quarter, one_year, infinity"
    )
    reasoning: str = Field(description="Brief explanation of the merge decision")

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"additionalProperties": False},
    )


class ProfileDeduplicationOutput(BaseModel):
    """
    Output schema for profile deduplication.

    Attributes:
        duplicate_groups: List of duplicate groups to merge
        unique_indices: List of indices of profiles that have no duplicates
    """

    duplicate_groups: list[ProfileDuplicateGroup] = Field(
        default=[], description="Groups of duplicate profiles that should be merged"
    )
    unique_indices: list[int] = Field(
        default=[],
        description="Indices of profiles that are unique (no duplicates found)",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"additionalProperties": False},
    )


class ProfileDeduplicator(BaseDeduplicator):
    """
    Deduplicates profiles from multiple extractors using LLM-based semantic matching.

    This class identifies duplicate profiles (e.g., profiles about the same topic from
    different extractors) and merges them into a single consolidated profile.
    """

    DEDUPLICATION_PROMPT_ID = "profile_deduplication"

    def __init__(
        self,
        request_context: RequestContext,
        llm_client: LiteLLMClient,
    ):
        """
        Initialize the profile deduplicator.

        Args:
            request_context: Request context with storage and prompt manager
            llm_client: Unified LLM client for LLM calls
        """
        super().__init__(request_context, llm_client)

    def _get_prompt_id(self) -> str:
        """Get the prompt ID for profile deduplication."""
        return self.DEDUPLICATION_PROMPT_ID

    def _get_item_count_key(self) -> str:
        """Get the key name for item count in prompt variables."""
        return "profile_count"

    def _get_items_key(self) -> str:
        """Get the key name for items in prompt variables."""
        return "profiles"

    def _get_output_schema_class(self) -> type[BaseModel]:
        """Get the profile-specific output schema with merged_time_to_live."""
        return ProfileDeduplicationOutput

    def _format_items_for_prompt(self, profiles: list[UserProfile]) -> str:
        """
        Format profiles list for LLM prompt.

        Args:
            profiles: List of profiles

        Returns:
            Formatted string representation
        """
        lines = []
        for idx, profile in enumerate(profiles):
            ttl = (
                profile.profile_time_to_live.value
                if profile.profile_time_to_live
                else "unknown"
            )
            source = profile.source or "unknown"
            lines.append(
                f'[{idx}] Content: "{profile.profile_content}" | TTL: {ttl} | Source: {source}'
            )
        return "\n".join(lines)

    def deduplicate(
        self,
        results: list[ProfileUpdates],
        user_id: str,
        request_id: str,
    ) -> list[ProfileUpdates]:
        """
        Deduplicate profiles across multiple ProfileUpdates from different extractors.

        Args:
            results: List of ProfileUpdates from extractors
            user_id: User ID for context
            request_id: Request ID for context

        Returns:
            list[ProfileUpdates]: Deduplicated ProfileUpdates (single consolidated entry)
        """
        # Collect all add_profiles with their source extractor info
        all_add_profiles: list[UserProfile] = []
        profile_to_result_index: list[
            int
        ] = []  # Track which result each profile came from

        for idx, result in enumerate(results):
            if result and result.add_profiles:
                for profile in result.add_profiles:
                    all_add_profiles.append(profile)
                    profile_to_result_index.append(idx)

        if len(all_add_profiles) < 2:
            # Not enough profiles to deduplicate
            return results

        # Call LLM to identify duplicates
        dedup_output = self._identify_duplicates(all_add_profiles)

        if not dedup_output or not dedup_output.duplicate_groups:
            # No duplicates found, return original results
            logger.info(
                "No duplicates found for user %s, request %s", user_id, request_id
            )
            return results

        logger.info(
            "Found %d duplicate groups for user %s, request %s",
            len(dedup_output.duplicate_groups),
            user_id,
            request_id,
        )

        # Build deduplicated result
        return self._build_deduplicated_results(
            results=results,
            all_add_profiles=all_add_profiles,
            dedup_output=dedup_output,
            user_id=user_id,
            request_id=request_id,
        )

    def _build_deduplicated_results(
        self,
        results: list[ProfileUpdates],
        all_add_profiles: list[UserProfile],
        dedup_output: ProfileDeduplicationOutput,
        user_id: str,
        request_id: str,
    ) -> list[ProfileUpdates]:
        """
        Build the deduplicated ProfileUpdates list.

        Args:
            results: Original results from extractors
            all_add_profiles: Flattened list of all add_profiles
            dedup_output: LLM deduplication output
            user_id: User ID
            request_id: Request ID

        Returns:
            Deduplicated ProfileUpdates list (single consolidated entry)
        """
        # Track which profiles have been handled
        handled_indices = set()

        # Create a single merged ProfileUpdates for all deduplicated profiles
        merged_add_profiles: list[UserProfile] = []

        # Process duplicate groups - create merged profiles
        for group in dedup_output.duplicate_groups:
            handled_indices.update(group.item_indices)

            # Get the first profile as template for metadata
            template_profile = all_add_profiles[group.item_indices[0]]

            # Merge custom_features from all profiles in group
            merged_custom_features = self._merge_custom_features(
                [all_add_profiles[i] for i in group.item_indices]
            )

            # Create merged profile
            try:
                ttl = ProfileTimeToLive(group.merged_time_to_live)
            except ValueError:
                # Fallback to template's TTL if LLM returns invalid value
                ttl = template_profile.profile_time_to_live
                logger.warning(
                    "Invalid TTL '%s' from LLM, using template TTL '%s'",
                    group.merged_time_to_live,
                    ttl.value,
                )

            now_ts = int(datetime.now(timezone.utc).timestamp())

            merged_profile = UserProfile(
                profile_id=str(uuid.uuid4()),
                user_id=user_id,
                profile_content=group.merged_content,
                last_modified_timestamp=now_ts,
                generated_from_request_id=request_id,
                profile_time_to_live=ttl,
                expiration_timestamp=calculate_expiration_timestamp(now_ts, ttl),
                custom_features=merged_custom_features,
                source=template_profile.source,  # Use first profile's source
                status=template_profile.status,
            )
            merged_add_profiles.append(merged_profile)

        # Add unique (non-duplicate) profiles
        for idx in dedup_output.unique_indices:
            if idx not in handled_indices:
                merged_add_profiles.append(all_add_profiles[idx])
                handled_indices.add(idx)

        # Add any profiles not mentioned by LLM (safety fallback)
        for idx, profile in enumerate(all_add_profiles):
            if idx not in handled_indices:
                logger.warning(
                    "Profile at index %d was not handled by LLM, adding as-is", idx
                )
                merged_add_profiles.append(profile)

        # Collect all delete and mention profiles from original results
        # Deduplicate by profile_id (multiple extractors may reference the same profile)
        delete_profiles_by_id: dict[str, UserProfile] = {}
        mention_profiles_by_id: dict[str, UserProfile] = {}

        for result in results:
            if result:
                for profile in result.delete_profiles:
                    delete_profiles_by_id[profile.profile_id] = profile
                for profile in result.mention_profiles:
                    mention_profiles_by_id[profile.profile_id] = profile

        # Return single consolidated ProfileUpdates
        return [
            ProfileUpdates(
                add_profiles=merged_add_profiles,
                delete_profiles=list(delete_profiles_by_id.values()),
                mention_profiles=list(mention_profiles_by_id.values()),
            )
        ]

    def _merge_custom_features(self, profiles: list[UserProfile]) -> Optional[dict]:
        """
        Merge custom_features from multiple profiles.

        Uses a strategy of combining all keys, with later values overwriting earlier ones
        for conflicts.

        Args:
            profiles: List of profiles to merge custom_features from

        Returns:
            Merged custom_features dict or None if no custom_features
        """
        merged = {}
        for profile in profiles:
            if profile.custom_features:
                merged.update(profile.custom_features)

        return merged if merged else None
