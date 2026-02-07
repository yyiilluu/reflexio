"""
Shared utilities for deduplication services.

This module contains base classes and Pydantic schemas used by both
ProfileDeduplicator and FeedbackDeduplicator.
"""

from abc import ABC, abstractmethod
import logging
import os
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict

from reflexio.server.api_endpoints.request_context import RequestContext
from reflexio.server.llm.litellm_client import LiteLLMClient
from reflexio.server.services.service_utils import log_model_response
from reflexio.server.site_var.site_var_manager import SiteVarManager

logger = logging.getLogger(__name__)


# ===============================
# Shared Pydantic Output Schemas for LLM
# ===============================


class DuplicateGroup(BaseModel):
    """
    Represents a group of items that are duplicates of each other.

    Attributes:
        item_indices: List of indices (0-based) from the input list that are duplicates
        merged_content: The consolidated content combining information from all duplicates
        reasoning: Brief explanation of why these items are duplicates and how they were merged
    """

    item_indices: list[int] = Field(
        description="Indices of items in the input list that are duplicates of each other"
    )
    merged_content: str = Field(
        description="Consolidated content combining all duplicate information"
    )
    reasoning: str = Field(description="Brief explanation of the merge decision")

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"additionalProperties": False},
    )


class DeduplicationOutput(BaseModel):
    """
    Output schema for deduplication.

    Attributes:
        duplicate_groups: List of duplicate groups to merge
        unique_indices: List of indices of items that have no duplicates
    """

    duplicate_groups: list[DuplicateGroup] = Field(
        default=[], description="Groups of duplicate items that should be merged"
    )
    unique_indices: list[int] = Field(
        default=[], description="Indices of items that are unique (no duplicates found)"
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"additionalProperties": False},
    )


# ===============================
# Base Deduplicator ABC
# ===============================


class BaseDeduplicator(ABC):
    """
    Abstract base class for deduplicators that use LLM-based semantic matching.

    This class provides shared functionality for identifying and merging duplicates:
    - LLM client initialization
    - Common LLM call pattern for identifying duplicates
    - Logging

    Subclasses must implement:
    - _get_prompt_id(): Return the prompt ID for this deduplicator
    - _format_items_for_prompt(): Format items for the LLM prompt
    - _get_item_count_key(): Return the key for item count in prompt variables
    """

    def __init__(
        self,
        request_context: RequestContext,
        llm_client: LiteLLMClient,
    ):
        """
        Initialize the deduplicator.

        Args:
            request_context: Request context with storage and prompt manager
            llm_client: Unified LLM client for LLM calls
        """
        self.request_context = request_context
        self.client = llm_client

        # Get model name from site var
        model_setting = SiteVarManager().get_site_var("llm_model_setting")
        assert isinstance(model_setting, dict), "llm_model_setting must be a dict"
        self.model_name = model_setting.get(
            "default_generation_model_name", "gpt-5-mini"
        )

    @abstractmethod
    def _get_prompt_id(self) -> str:
        """
        Get the prompt ID for this deduplicator.

        Returns:
            Prompt ID string (e.g., "profile_deduplication", "feedback_deduplication")
        """

    @abstractmethod
    def _format_items_for_prompt(self, items: list[Any]) -> str:
        """
        Format items list for LLM prompt.

        Args:
            items: List of items to format

        Returns:
            Formatted string representation for the prompt
        """

    @abstractmethod
    def _get_item_count_key(self) -> str:
        """
        Get the key name for item count in prompt variables.

        Returns:
            Key string (e.g., "profile_count", "feedback_count")
        """

    def _get_output_schema_class(self) -> type[BaseModel]:
        """
        Get the Pydantic output schema class for LLM response.

        Override this method to use a custom schema (e.g., ProfileDeduplicationOutput
        with merged_time_to_live).

        Returns:
            Pydantic model class for parsing LLM output. Default: DeduplicationOutput
        """
        return DeduplicationOutput

    def _identify_duplicates(self, items: list[Any]) -> Optional[BaseModel]:
        """
        Use LLM to identify duplicate items.

        Args:
            items: List of items to analyze for duplicates

        Returns:
            Output schema instance with identified duplicate groups, or None on error
        """
        # Check if mock mode is enabled
        if os.getenv("MOCK_LLM_RESPONSE", "").lower() == "true":
            # In mock mode, return None to indicate no duplicates found
            # This skips deduplication and keeps all items as-is
            logger.info("Mock mode: skipping deduplication, returning no duplicates")
            return None

        # Format items for the prompt
        items_text = self._format_items_for_prompt(items)

        # Build prompt
        prompt = self.request_context.prompt_manager.render_prompt(
            self._get_prompt_id(),
            {
                self._get_item_count_key(): len(items),
                self._get_items_key(): items_text,
            },
        )

        # Get the output schema class for this deduplicator
        output_schema_class = self._get_output_schema_class()

        try:
            response = self.client.generate_chat_response(
                messages=[{"role": "user", "content": prompt}],
                model=self.model_name,
                response_format=output_schema_class,
            )

            logger.info("Deduplication prompt: %s", prompt)
            log_model_response(logger, "Deduplication response", response)

            if isinstance(response, output_schema_class):
                return response
            else:
                logger.warning(
                    "Unexpected response type from deduplication LLM: %s",
                    type(response),
                )
                return None

        except Exception as e:
            logger.error("Failed to identify duplicates: %s", str(e))
            return None

    def _get_items_key(self) -> str:
        """
        Get the key name for items in prompt variables.

        Returns:
            Key string (e.g., "profiles", "feedbacks")
        """
        # Default implementation derives from item_count_key
        # e.g., "profile_count" -> "profiles", "feedback_count" -> "feedbacks"
        count_key = self._get_item_count_key()
        return count_key.replace("_count", "s")
