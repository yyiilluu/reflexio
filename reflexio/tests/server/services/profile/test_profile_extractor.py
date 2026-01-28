"""
Unit tests for ProfileExtractor.

Tests the extractor's new responsibilities for:
- Operation state key generation
- Interaction collection with window/stride
- Source filtering
- Operation state updates
- Integration of run() method
"""

import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch

from reflexio_commons.api_schema.service_schemas import Interaction, Request
from reflexio_commons.api_schema.internal_schema import RequestInteractionDataModel
from reflexio_commons.config_schema import ProfileExtractorConfig

from reflexio.server.api_endpoints.request_context import RequestContext
from reflexio.server.services.profile.profile_extractor import ProfileExtractor
from reflexio.server.services.profile.profile_generation_service import (
    ProfileGenerationServiceConfig,
)
from reflexio.server.services.profile.profile_generation_service_utils import (
    ProfileUpdateOutput,
)
from reflexio.server.llm.litellm_client import LiteLLMClient


# ===============================
# Fixtures
# ===============================


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock(spec=LiteLLMClient)
    # Return an empty ProfileUpdateOutput for profile extraction
    client.generate_chat_response.return_value = ProfileUpdateOutput()
    return client


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def request_context(temp_storage_dir):
    """Create a request context with mock storage."""
    context = RequestContext(org_id="test_org", storage_base_dir=temp_storage_dir)
    # Mock the storage
    context.storage = MagicMock()
    return context


@pytest.fixture
def extractor_config():
    """Create a profile extractor config."""
    return ProfileExtractorConfig(
        extractor_name="test_extractor",
        profile_content_definition_prompt="Extract user preferences",
    )


@pytest.fixture
def service_config():
    """Create a service config."""
    return ProfileGenerationServiceConfig(
        user_id="test_user",
        request_id="test_request",
        source="api",
    )


@pytest.fixture
def sample_interactions():
    """Create sample interactions for testing."""
    return [
        Interaction(
            interaction_id=1,
            user_id="test_user",
            content="I prefer dark mode",
            request_id="req1",
            created_at=1000,
            role="user",
        ),
        Interaction(
            interaction_id=2,
            user_id="test_user",
            content="Got it, I'll remember that preference",
            request_id="req1",
            created_at=1001,
            role="assistant",
        ),
    ]


@pytest.fixture
def sample_request_interaction_models(sample_interactions):
    """Create sample RequestInteractionDataModel objects."""
    request = Request(
        request_id="req1",
        user_id="test_user",
        created_at=1000,
        source="api",
    )
    return [
        RequestInteractionDataModel(
            request_group="req1",
            request=request,
            interactions=sample_interactions,
        )
    ]


# ===============================
# Test: Operation State Key
# ===============================


class TestOperationStateKey:
    """Tests for operation state key generation."""

    def test_key_includes_user_id(
        self, request_context, mock_llm_client, extractor_config, service_config
    ):
        """Test that profile extractor key includes user_id (user-scoped)."""
        extractor = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=extractor_config,
            service_config=service_config,
            agent_context="Test agent",
        )

        key = extractor._get_operation_state_key()

        assert "profile_extractor" in key
        assert "test_org" in key
        assert "test_user" in key
        assert "test_extractor" in key
        assert key == "profile_extractor::test_org::test_user::test_extractor"

    def test_different_users_have_different_keys(
        self, request_context, mock_llm_client, extractor_config
    ):
        """Test that different users get different operation state keys."""
        config1 = ProfileGenerationServiceConfig(
            user_id="user1", request_id="req1", source="api"
        )
        config2 = ProfileGenerationServiceConfig(
            user_id="user2", request_id="req2", source="api"
        )

        extractor1 = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=extractor_config,
            service_config=config1,
            agent_context="Test agent",
        )
        extractor2 = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=extractor_config,
            service_config=config2,
            agent_context="Test agent",
        )

        assert (
            extractor1._get_operation_state_key()
            != extractor2._get_operation_state_key()
        )


# ===============================
# Test: Get Interactions
# ===============================


class TestGetInteractions:
    """Tests for interaction collection logic."""

    def test_returns_none_when_stride_not_met(
        self,
        request_context,
        mock_llm_client,
        service_config,
        sample_request_interaction_models,
    ):
        """Test that None is returned when stride threshold is not met."""
        # Configure extractor with stride of 10
        config = ProfileExtractorConfig(
            extractor_name="test_extractor",
            profile_content_definition_prompt="Extract user preferences",
            extraction_window_stride_override=10,
        )

        # Mock storage to return only 2 interactions (below stride)
        request_context.storage.get_operation_state_with_new_request_interaction.return_value = (
            {},
            sample_request_interaction_models,  # 2 interactions
        )

        extractor = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=config,
            service_config=service_config,
            agent_context="Test agent",
        )

        result = extractor._get_interactions()

        assert result is None

    def test_returns_interactions_when_stride_met(
        self,
        request_context,
        mock_llm_client,
        service_config,
        sample_request_interaction_models,
    ):
        """Test that interactions are returned when stride is met."""
        # Configure extractor with stride of 2
        config = ProfileExtractorConfig(
            extractor_name="test_extractor",
            profile_content_definition_prompt="Extract user preferences",
            extraction_window_stride_override=2,
        )

        # Mock storage to return 2 interactions (meets stride)
        request_context.storage.get_operation_state_with_new_request_interaction.return_value = (
            {},
            sample_request_interaction_models,
        )

        extractor = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=config,
            service_config=service_config,
            agent_context="Test agent",
        )

        result = extractor._get_interactions()

        assert result is not None
        assert len(result) == 1  # One request group

    def test_uses_window_size_when_configured(
        self,
        request_context,
        mock_llm_client,
        service_config,
        sample_request_interaction_models,
    ):
        """Test that window size is used to fetch interactions."""
        # Configure extractor with window size
        config = ProfileExtractorConfig(
            extractor_name="test_extractor",
            profile_content_definition_prompt="Extract user preferences",
            extraction_window_size_override=50,
            extraction_window_stride_override=1,
        )

        # Mock storage
        request_context.storage.get_operation_state_with_new_request_interaction.return_value = (
            {},
            sample_request_interaction_models,
        )
        request_context.storage.get_last_k_interactions_grouped.return_value = (
            sample_request_interaction_models,
            [],
        )

        extractor = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=config,
            service_config=service_config,
            agent_context="Test agent",
        )

        extractor._get_interactions()

        # Verify get_last_k_interactions_grouped was called with correct window size
        request_context.storage.get_last_k_interactions_grouped.assert_called_once()
        call_kwargs = request_context.storage.get_last_k_interactions_grouped.call_args
        assert call_kwargs[1]["k"] == 50

    def test_returns_none_when_source_filter_skips(
        self,
        request_context,
        mock_llm_client,
        sample_request_interaction_models,
    ):
        """Test that None is returned when source filter causes skip."""
        # Configure extractor with specific sources
        config = ProfileExtractorConfig(
            extractor_name="test_extractor",
            profile_content_definition_prompt="Extract user preferences",
            request_sources_enabled=["mobile", "desktop"],
        )

        # Service config has source="api" which is not in enabled list
        service_config = ProfileGenerationServiceConfig(
            user_id="test_user",
            request_id="test_request",
            source="api",  # Not in enabled list
        )

        extractor = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=config,
            service_config=service_config,
            agent_context="Test agent",
        )

        result = extractor._get_interactions()

        assert result is None

    def test_passes_correct_user_id_to_storage(
        self,
        request_context,
        mock_llm_client,
        service_config,
        sample_request_interaction_models,
    ):
        """Test that user_id is passed to storage methods (user-scoped)."""
        config = ProfileExtractorConfig(
            extractor_name="test_extractor",
            profile_content_definition_prompt="Extract user preferences",
            extraction_window_stride_override=1,
        )

        request_context.storage.get_operation_state_with_new_request_interaction.return_value = (
            {},
            sample_request_interaction_models,
        )

        extractor = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=config,
            service_config=service_config,
            agent_context="Test agent",
        )

        extractor._get_interactions()

        # Verify user_id was passed to storage
        call_args = (
            request_context.storage.get_operation_state_with_new_request_interaction.call_args
        )
        assert call_args[0][1] == "test_user"  # user_id is second positional arg


# ===============================
# Test: Update Operation State
# ===============================


class TestUpdateOperationState:
    """Tests for operation state update logic."""

    def test_updates_state_after_processing(
        self,
        request_context,
        mock_llm_client,
        extractor_config,
        service_config,
        sample_request_interaction_models,
    ):
        """Test that operation state is updated with processed interactions."""
        extractor = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=extractor_config,
            service_config=service_config,
            agent_context="Test agent",
        )

        extractor._update_operation_state(sample_request_interaction_models)

        # Verify upsert was called
        request_context.storage.upsert_operation_state.assert_called_once()

        # Verify state contains interaction IDs
        call_args = request_context.storage.upsert_operation_state.call_args
        state_key = call_args[0][0]
        state = call_args[0][1]

        assert "profile_extractor" in state_key
        assert "last_processed_interaction_ids" in state
        assert 1 in state["last_processed_interaction_ids"]
        assert 2 in state["last_processed_interaction_ids"]


# ===============================
# Test: Run Integration
# ===============================


class TestRun:
    """Integration tests for the run() method."""

    def test_run_collects_own_interactions_when_not_provided(
        self,
        request_context,
        mock_llm_client,
        service_config,
        sample_request_interaction_models,
    ):
        """Test that run() collects interactions when not provided in service config."""
        config = ProfileExtractorConfig(
            extractor_name="test_extractor",
            profile_content_definition_prompt="Extract user preferences",
            extraction_window_stride_override=1,
        )

        request_context.storage.get_operation_state_with_new_request_interaction.return_value = (
            {},
            sample_request_interaction_models,
        )

        extractor = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=config,
            service_config=service_config,
            agent_context="Test agent",
        )

        # Enable mock mode for LLM responses
        with patch.dict(os.environ, {"MOCK_LLM_RESPONSE": "true"}):
            extractor.run()

        # Verify storage was queried for interactions
        request_context.storage.get_operation_state_with_new_request_interaction.assert_called()

    def test_run_returns_empty_when_no_interactions(
        self,
        request_context,
        mock_llm_client,
        service_config,
    ):
        """Test that run() returns None when no interactions available."""
        config = ProfileExtractorConfig(
            extractor_name="test_extractor",
            profile_content_definition_prompt="Extract user preferences",
            extraction_window_stride_override=10,  # High stride
        )

        # Return empty interactions
        request_context.storage.get_operation_state_with_new_request_interaction.return_value = (
            {},
            [],
        )

        extractor = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=config,
            service_config=service_config,
            agent_context="Test agent",
        )

        result = extractor.run()

        assert result is None

    def test_run_updates_operation_state_on_success(
        self,
        request_context,
        mock_llm_client,
        service_config,
        sample_request_interaction_models,
    ):
        """Test that operation state is updated after successful extraction."""
        config = ProfileExtractorConfig(
            extractor_name="test_extractor",
            profile_content_definition_prompt="Extract user preferences",
            extraction_window_stride_override=1,
        )

        request_context.storage.get_operation_state_with_new_request_interaction.return_value = (
            {},
            sample_request_interaction_models,
        )
        request_context.storage.get_user_profile.return_value = []

        extractor = ProfileExtractor(
            request_context=request_context,
            llm_client=mock_llm_client,
            extractor_config=config,
            service_config=service_config,
            agent_context="Test agent",
        )

        with patch.dict(os.environ, {"MOCK_LLM_RESPONSE": "true"}):
            result = extractor.run()

        # Verify operation state was updated
        if result is not None:
            request_context.storage.upsert_operation_state.assert_called()
