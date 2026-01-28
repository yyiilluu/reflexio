"""
Unit tests for ProfileDeduplicator.

Tests the deduplicator's responsibilities for:
- Pydantic output schema validation
- Profile deduplication with LLM
- Profile formatting for prompts
- Building deduplicated results
- Merging custom features
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import uuid


# Disable mock mode for deduplicator tests so LLM mocks are actually used
@pytest.fixture(autouse=True)
def disable_mock_llm_response(monkeypatch):
    """Disable MOCK_LLM_RESPONSE env var so deduplicator tests use their own mocks."""
    monkeypatch.delenv("MOCK_LLM_RESPONSE", raising=False)


from reflexio_commons.api_schema.service_schemas import (
    UserProfile,
    ProfileTimeToLive,
)
from reflexio.server.api_endpoints.request_context import RequestContext
from reflexio.server.llm.litellm_client import LiteLLMClient
from reflexio.server.services.profile.profile_deduplicator import (
    ProfileDeduplicator,
    ProfileDuplicateGroup,
    ProfileDeduplicationOutput,
)
from reflexio.server.services.profile.profile_generation_service_utils import (
    ProfileUpdates,
)


# ===============================
# Fixtures
# ===============================


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock(spec=LiteLLMClient)
    return client


@pytest.fixture
def mock_request_context():
    """Create a mock request context with prompt manager."""
    context = MagicMock(spec=RequestContext)
    context.prompt_manager = MagicMock()
    context.prompt_manager.render_prompt.return_value = "test prompt"
    return context


@pytest.fixture
def mock_site_var_manager():
    """Mock the SiteVarManager to return model settings."""
    with patch("reflexio.server.services.deduplication_utils.SiteVarManager") as mock:
        instance = mock.return_value
        instance.get_site_var.return_value = {"default_generation_model_name": "gpt-4"}
        yield mock


@pytest.fixture
def sample_profiles():
    """Create sample UserProfile objects for testing."""
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return [
        UserProfile(
            profile_id=str(uuid.uuid4()),
            user_id="test_user",
            profile_content="User prefers dark mode for coding",
            last_modified_timestamp=timestamp,
            generated_from_request_id="req_1",
            profile_time_to_live=ProfileTimeToLive.ONE_MONTH,
            source="extractor_a",
        ),
        UserProfile(
            profile_id=str(uuid.uuid4()),
            user_id="test_user",
            profile_content="User likes dark theme in their IDE",
            last_modified_timestamp=timestamp,
            generated_from_request_id="req_2",
            profile_time_to_live=ProfileTimeToLive.ONE_WEEK,
            source="extractor_b",
        ),
        UserProfile(
            profile_id=str(uuid.uuid4()),
            user_id="test_user",
            profile_content="User is a Python developer",
            last_modified_timestamp=timestamp,
            generated_from_request_id="req_3",
            profile_time_to_live=ProfileTimeToLive.ONE_YEAR,
            source="extractor_a",
        ),
    ]


@pytest.fixture
def sample_profile_updates(sample_profiles):
    """Create sample ProfileUpdates from different extractors."""
    return [
        ProfileUpdates(
            add_profiles=[sample_profiles[0]],
            delete_profiles=[],
            mention_profiles=[],
        ),
        ProfileUpdates(
            add_profiles=[sample_profiles[1]],
            delete_profiles=[],
            mention_profiles=[],
        ),
        ProfileUpdates(
            add_profiles=[sample_profiles[2]],
            delete_profiles=[],
            mention_profiles=[],
        ),
    ]


# ===============================
# Test: Pydantic Models
# ===============================


class TestPydanticModels:
    """Tests for the Pydantic output schema models."""

    def test_duplicate_group_creation(self):
        """Test that ProfileDuplicateGroup can be created with valid data."""
        group = ProfileDuplicateGroup(
            item_indices=[0, 1],
            merged_content="User prefers dark mode",
            merged_time_to_live="one_month",
            reasoning="Both profiles are about dark mode preferences",
        )
        assert group.item_indices == [0, 1]
        assert group.merged_content == "User prefers dark mode"
        assert group.merged_time_to_live == "one_month"

    def test_duplicate_group_forbids_extra_fields(self):
        """Test that ProfileDuplicateGroup forbids extra fields."""
        with pytest.raises(Exception):
            ProfileDuplicateGroup(
                item_indices=[0],
                merged_content="test",
                merged_time_to_live="one_day",
                reasoning="test",
                extra_field="not allowed",
            )

    def test_deduplication_output_creation(self):
        """Test that ProfileDeduplicationOutput can be created."""
        output = ProfileDeduplicationOutput(
            duplicate_groups=[
                ProfileDuplicateGroup(
                    item_indices=[0, 1],
                    merged_content="merged",
                    merged_time_to_live="one_week",
                    reasoning="duplicates",
                )
            ],
            unique_indices=[2, 3],
        )
        assert len(output.duplicate_groups) == 1
        assert output.unique_indices == [2, 3]

    def test_deduplication_output_empty_defaults(self):
        """Test that ProfileDeduplicationOutput has empty list defaults."""
        output = ProfileDeduplicationOutput()
        assert output.duplicate_groups == []
        assert output.unique_indices == []

    def test_deduplication_output_from_dict(self):
        """Test that ProfileDeduplicationOutput can be validated from dict."""
        data = {
            "duplicate_groups": [
                {
                    "item_indices": [0, 1],
                    "merged_content": "test",
                    "merged_time_to_live": "one_day",
                    "reasoning": "reason",
                }
            ],
            "unique_indices": [2],
        }
        output = ProfileDeduplicationOutput.model_validate(data)
        assert len(output.duplicate_groups) == 1
        assert output.unique_indices == [2]


# ===============================
# Test: ProfileDeduplicator Init
# ===============================


class TestProfileDeduplicatorInit:
    """Tests for ProfileDeduplicator initialization."""

    def test_init_sets_attributes(
        self, mock_request_context, mock_llm_client, mock_site_var_manager
    ):
        """Test that __init__ sets all required attributes."""
        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        assert deduplicator.request_context == mock_request_context
        assert deduplicator.client == mock_llm_client
        assert deduplicator.model_name == "gpt-4"

    def test_init_uses_default_model_when_not_specified(
        self, mock_request_context, mock_llm_client
    ):
        """Test that init falls back to default model if not in site var."""
        with patch(
            "reflexio.server.services.deduplication_utils.SiteVarManager"
        ) as mock:
            instance = mock.return_value
            instance.get_site_var.return_value = {}
            deduplicator = ProfileDeduplicator(
                request_context=mock_request_context,
                llm_client=mock_llm_client,
            )
            assert deduplicator.model_name == "gpt-5-mini"


# ===============================
# Test: Format Profiles For Prompt
# ===============================


class TestFormatProfilesForPrompt:
    """Tests for profile formatting for LLM prompt."""

    def test_format_profiles_basic(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
    ):
        """Test that profiles are formatted correctly."""
        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._format_items_for_prompt(sample_profiles)

        assert "[0]" in result
        assert "[1]" in result
        assert "[2]" in result
        assert "User prefers dark mode for coding" in result
        assert "User likes dark theme in their IDE" in result
        assert "one_month" in result
        assert "one_week" in result
        assert "extractor_a" in result
        assert "extractor_b" in result

    def test_format_profiles_uses_ttl_value(
        self, mock_request_context, mock_llm_client, mock_site_var_manager
    ):
        """Test formatting shows TTL value from profile."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        profiles = [
            UserProfile(
                profile_id="1",
                user_id="user",
                profile_content="test content",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req",
                profile_time_to_live=ProfileTimeToLive.ONE_QUARTER,
            )
        ]
        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._format_items_for_prompt(profiles)
        assert "TTL: one_quarter" in result

    def test_format_profiles_with_missing_source(
        self, mock_request_context, mock_llm_client, mock_site_var_manager
    ):
        """Test formatting with profiles that have no source."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        profiles = [
            UserProfile(
                profile_id="1",
                user_id="user",
                profile_content="test content",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req",
                source=None,
            )
        ]
        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._format_items_for_prompt(profiles)
        assert "Source: unknown" in result


# ===============================
# Test: Merge Custom Features
# ===============================


class TestMergeCustomFeatures:
    """Tests for custom features merging."""

    def test_merge_custom_features_empty(
        self, mock_request_context, mock_llm_client, mock_site_var_manager
    ):
        """Test merging when no profiles have custom features."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        profiles = [
            UserProfile(
                profile_id="1",
                user_id="user",
                profile_content="test",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req",
                custom_features=None,
            ),
            UserProfile(
                profile_id="2",
                user_id="user",
                profile_content="test2",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req",
                custom_features=None,
            ),
        ]
        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._merge_custom_features(profiles)
        assert result is None

    def test_merge_custom_features_single(
        self, mock_request_context, mock_llm_client, mock_site_var_manager
    ):
        """Test merging when only one profile has custom features."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        profiles = [
            UserProfile(
                profile_id="1",
                user_id="user",
                profile_content="test",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req",
                custom_features={"key1": "value1"},
            ),
            UserProfile(
                profile_id="2",
                user_id="user",
                profile_content="test2",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req",
                custom_features=None,
            ),
        ]
        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._merge_custom_features(profiles)
        assert result == {"key1": "value1"}

    def test_merge_custom_features_multiple(
        self, mock_request_context, mock_llm_client, mock_site_var_manager
    ):
        """Test merging custom features from multiple profiles."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        profiles = [
            UserProfile(
                profile_id="1",
                user_id="user",
                profile_content="test",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req",
                custom_features={"key1": "value1", "key2": "old_value"},
            ),
            UserProfile(
                profile_id="2",
                user_id="user",
                profile_content="test2",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req",
                custom_features={"key2": "new_value", "key3": "value3"},
            ),
        ]
        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._merge_custom_features(profiles)
        assert result == {"key1": "value1", "key2": "new_value", "key3": "value3"}


# ===============================
# Test: Identify Duplicates
# ===============================


class TestIdentifyDuplicates:
    """Tests for LLM-based duplicate identification."""

    def test_identify_duplicates_returns_output(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
    ):
        """Test that identify_duplicates returns ProfileDeduplicationOutput."""
        mock_llm_client.generate_chat_response.return_value = (
            ProfileDeduplicationOutput(
                duplicate_groups=[
                    ProfileDuplicateGroup(
                        item_indices=[0, 1],
                        merged_content="User prefers dark mode",
                        merged_time_to_live="one_month",
                        reasoning="Both about dark mode",
                    )
                ],
                unique_indices=[2],
            )
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._identify_duplicates(sample_profiles)

        assert result is not None
        assert isinstance(result, ProfileDeduplicationOutput)
        assert len(result.duplicate_groups) == 1
        assert result.unique_indices == [2]

    def test_identify_duplicates_handles_pydantic_response(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
    ):
        """Test that identify_duplicates handles ProfileDeduplicationOutput directly."""
        expected_output = ProfileDeduplicationOutput(
            duplicate_groups=[
                ProfileDuplicateGroup(
                    item_indices=[0, 1],
                    merged_content="merged",
                    merged_time_to_live="one_week",
                    reasoning="duplicate",
                )
            ],
            unique_indices=[2],
        )
        mock_llm_client.generate_chat_response.return_value = expected_output

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._identify_duplicates(sample_profiles)

        assert result == expected_output

    def test_identify_duplicates_returns_none_on_error(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
    ):
        """Test that identify_duplicates returns None on LLM error."""
        mock_llm_client.generate_chat_response.side_effect = Exception("LLM Error")

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._identify_duplicates(sample_profiles)

        assert result is None

    def test_identify_duplicates_returns_none_on_unexpected_type(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
    ):
        """Test that identify_duplicates returns None on unexpected response type."""
        mock_llm_client.generate_chat_response.return_value = "unexpected string"

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._identify_duplicates(sample_profiles)

        assert result is None


# ===============================
# Test: Build Deduplicated Results
# ===============================


class TestBuildDeduplicatedResults:
    """Tests for building deduplicated ProfileUpdates."""

    def test_build_deduplicated_results_merges_duplicates(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
        sample_profile_updates,
    ):
        """Test that duplicates are merged into a single profile."""
        dedup_output = ProfileDeduplicationOutput(
            duplicate_groups=[
                ProfileDuplicateGroup(
                    item_indices=[0, 1],
                    merged_content="User prefers dark mode in their IDE",
                    merged_time_to_live="one_month",
                    reasoning="Both about dark mode preferences",
                )
            ],
            unique_indices=[2],
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._build_deduplicated_results(
            results=sample_profile_updates,
            all_add_profiles=sample_profiles,
            dedup_output=dedup_output,
            user_id="test_user",
            request_id="test_request",
        )

        assert len(result) == 1
        assert len(result[0].add_profiles) == 2  # 1 merged + 1 unique

        # Find the merged profile
        merged_profile = next(
            (
                p
                for p in result[0].add_profiles
                if p.profile_content == "User prefers dark mode in their IDE"
            ),
            None,
        )
        assert merged_profile is not None
        assert merged_profile.profile_time_to_live == ProfileTimeToLive.ONE_MONTH

    def test_build_deduplicated_results_preserves_unique(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
        sample_profile_updates,
    ):
        """Test that unique profiles are preserved."""
        dedup_output = ProfileDeduplicationOutput(
            duplicate_groups=[],
            unique_indices=[0, 1, 2],
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._build_deduplicated_results(
            results=sample_profile_updates,
            all_add_profiles=sample_profiles,
            dedup_output=dedup_output,
            user_id="test_user",
            request_id="test_request",
        )

        assert len(result) == 1
        assert len(result[0].add_profiles) == 3

    def test_build_deduplicated_results_handles_invalid_ttl(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
        sample_profile_updates,
    ):
        """Test that invalid TTL from LLM falls back to template TTL."""
        dedup_output = ProfileDeduplicationOutput(
            duplicate_groups=[
                ProfileDuplicateGroup(
                    item_indices=[0, 1],
                    merged_content="merged content",
                    merged_time_to_live="invalid_ttl",
                    reasoning="test",
                )
            ],
            unique_indices=[2],
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._build_deduplicated_results(
            results=sample_profile_updates,
            all_add_profiles=sample_profiles,
            dedup_output=dedup_output,
            user_id="test_user",
            request_id="test_request",
        )

        merged_profile = next(
            (
                p
                for p in result[0].add_profiles
                if p.profile_content == "merged content"
            ),
            None,
        )
        assert merged_profile is not None
        # Should fall back to template profile's TTL (first profile in group)
        assert merged_profile.profile_time_to_live == ProfileTimeToLive.ONE_MONTH

    def test_build_deduplicated_results_handles_unmentioned_profiles(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
        sample_profile_updates,
    ):
        """Test that profiles not mentioned by LLM are added as-is."""
        # LLM only mentions indices 0 and 1, not 2
        dedup_output = ProfileDeduplicationOutput(
            duplicate_groups=[
                ProfileDuplicateGroup(
                    item_indices=[0, 1],
                    merged_content="merged",
                    merged_time_to_live="one_week",
                    reasoning="test",
                )
            ],
            unique_indices=[],  # LLM forgot to mention index 2
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._build_deduplicated_results(
            results=sample_profile_updates,
            all_add_profiles=sample_profiles,
            dedup_output=dedup_output,
            user_id="test_user",
            request_id="test_request",
        )

        # Should still include all 3 profiles (1 merged + 1 unmentioned)
        assert len(result[0].add_profiles) == 2

    def test_build_deduplicated_results_collects_delete_profiles(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
    ):
        """Test that delete_profiles are collected from all results."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        delete_profile = UserProfile(
            profile_id="delete_1",
            user_id="test_user",
            profile_content="to delete",
            last_modified_timestamp=timestamp,
            generated_from_request_id="req",
        )

        results = [
            ProfileUpdates(
                add_profiles=[sample_profiles[0]],
                delete_profiles=[delete_profile],
                mention_profiles=[],
            ),
            ProfileUpdates(
                add_profiles=[sample_profiles[1]],
                delete_profiles=[],
                mention_profiles=[],
            ),
        ]

        dedup_output = ProfileDeduplicationOutput(
            duplicate_groups=[],
            unique_indices=[0, 1],
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._build_deduplicated_results(
            results=results,
            all_add_profiles=sample_profiles[:2],
            dedup_output=dedup_output,
            user_id="test_user",
            request_id="test_request",
        )

        assert len(result[0].delete_profiles) == 1
        assert result[0].delete_profiles[0].profile_id == "delete_1"

    def test_build_deduplicated_results_deduplicates_delete_profiles(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
    ):
        """Test that duplicate delete_profiles are deduplicated by profile_id."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        delete_profile = UserProfile(
            profile_id="delete_1",
            user_id="test_user",
            profile_content="to delete",
            last_modified_timestamp=timestamp,
            generated_from_request_id="req",
        )

        results = [
            ProfileUpdates(
                add_profiles=[sample_profiles[0]],
                delete_profiles=[delete_profile],
                mention_profiles=[],
            ),
            ProfileUpdates(
                add_profiles=[sample_profiles[1]],
                delete_profiles=[delete_profile],  # Same profile referenced again
                mention_profiles=[],
            ),
        ]

        dedup_output = ProfileDeduplicationOutput(
            duplicate_groups=[],
            unique_indices=[0, 1],
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator._build_deduplicated_results(
            results=results,
            all_add_profiles=sample_profiles[:2],
            dedup_output=dedup_output,
            user_id="test_user",
            request_id="test_request",
        )

        # Should only have one delete_profile despite being mentioned twice
        assert len(result[0].delete_profiles) == 1


# ===============================
# Test: Deduplicate Main Method
# ===============================


class TestDeduplicate:
    """Tests for the main deduplicate() method."""

    def test_deduplicate_returns_original_when_single_profile(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
    ):
        """Test that original results are returned when there's only one profile."""
        results = [
            ProfileUpdates(
                add_profiles=[sample_profiles[0]],
                delete_profiles=[],
                mention_profiles=[],
            )
        ]

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator.deduplicate(
            results=results,
            user_id="test_user",
            request_id="test_request",
        )

        # Should return original results without calling LLM
        assert result == results
        mock_llm_client.generate_chat_response.assert_not_called()

    def test_deduplicate_returns_original_when_no_add_profiles(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
    ):
        """Test that original results are returned when no add_profiles exist."""
        results = [
            ProfileUpdates(
                add_profiles=[],
                delete_profiles=[],
                mention_profiles=[],
            ),
            ProfileUpdates(
                add_profiles=[],
                delete_profiles=[],
                mention_profiles=[],
            ),
        ]

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator.deduplicate(
            results=results,
            user_id="test_user",
            request_id="test_request",
        )

        assert result == results
        mock_llm_client.generate_chat_response.assert_not_called()

    def test_deduplicate_returns_original_when_no_duplicates_found(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
        sample_profile_updates,
    ):
        """Test that original results are returned when LLM finds no duplicates."""
        mock_llm_client.generate_chat_response.return_value = (
            ProfileDeduplicationOutput(
                duplicate_groups=[],
                unique_indices=[0, 1, 2],
            )
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator.deduplicate(
            results=sample_profile_updates,
            user_id="test_user",
            request_id="test_request",
        )

        assert result == sample_profile_updates

    def test_deduplicate_returns_original_when_llm_fails(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
        sample_profile_updates,
    ):
        """Test that original results are returned when LLM call fails."""
        mock_llm_client.generate_chat_response.side_effect = Exception("LLM Error")

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator.deduplicate(
            results=sample_profile_updates,
            user_id="test_user",
            request_id="test_request",
        )

        assert result == sample_profile_updates

    def test_deduplicate_merges_duplicates(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
        sample_profile_updates,
    ):
        """Test that duplicates are properly merged."""
        mock_llm_client.generate_chat_response.return_value = (
            ProfileDeduplicationOutput(
                duplicate_groups=[
                    ProfileDuplicateGroup(
                        item_indices=[0, 1],
                        merged_content="User prefers dark mode",
                        merged_time_to_live="one_month",
                        reasoning="Both about dark mode",
                    )
                ],
                unique_indices=[2],
            )
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator.deduplicate(
            results=sample_profile_updates,
            user_id="test_user",
            request_id="test_request",
        )

        assert len(result) == 1
        # Should have 2 profiles: 1 merged + 1 unique
        assert len(result[0].add_profiles) == 2

    def test_deduplicate_handles_none_results(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
        sample_profiles,
    ):
        """Test that None results in the list are handled."""
        results = [
            ProfileUpdates(
                add_profiles=[sample_profiles[0]],
                delete_profiles=[],
                mention_profiles=[],
            ),
            None,
            ProfileUpdates(
                add_profiles=[sample_profiles[1]],
                delete_profiles=[],
                mention_profiles=[],
            ),
        ]

        mock_llm_client.generate_chat_response.return_value = (
            ProfileDeduplicationOutput(
                duplicate_groups=[
                    ProfileDuplicateGroup(
                        item_indices=[0, 1],
                        merged_content="merged",
                        merged_time_to_live="one_week",
                        reasoning="duplicates",
                    )
                ],
                unique_indices=[],
            )
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator.deduplicate(
            results=results,
            user_id="test_user",
            request_id="test_request",
        )

        assert len(result) == 1
        assert len(result[0].add_profiles) == 1


# ===============================
# Test: Integration
# ===============================


class TestIntegration:
    """Integration tests for the complete deduplication flow."""

    def test_full_deduplication_flow(
        self,
        mock_request_context,
        mock_llm_client,
        mock_site_var_manager,
    ):
        """Test a complete deduplication flow with realistic data."""
        timestamp = int(datetime.now(timezone.utc).timestamp())

        # Create profiles from different extractors with duplicates
        profiles = [
            UserProfile(
                profile_id="p1",
                user_id="user",
                profile_content="User works in finance industry",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req1",
                profile_time_to_live=ProfileTimeToLive.ONE_YEAR,
                source="industry_extractor",
                custom_features={"sector": "finance"},
            ),
            UserProfile(
                profile_id="p2",
                user_id="user",
                profile_content="User is in the financial services sector",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req2",
                profile_time_to_live=ProfileTimeToLive.ONE_MONTH,
                source="job_extractor",
                custom_features={"job_type": "analyst"},
            ),
            UserProfile(
                profile_id="p3",
                user_id="user",
                profile_content="User prefers Python programming",
                last_modified_timestamp=timestamp,
                generated_from_request_id="req3",
                profile_time_to_live=ProfileTimeToLive.INFINITY,
                source="tech_extractor",
            ),
        ]

        results = [
            ProfileUpdates(
                add_profiles=[profiles[0]], delete_profiles=[], mention_profiles=[]
            ),
            ProfileUpdates(
                add_profiles=[profiles[1]], delete_profiles=[], mention_profiles=[]
            ),
            ProfileUpdates(
                add_profiles=[profiles[2]], delete_profiles=[], mention_profiles=[]
            ),
        ]

        mock_llm_client.generate_chat_response.return_value = ProfileDeduplicationOutput(
            duplicate_groups=[
                ProfileDuplicateGroup(
                    item_indices=[0, 1],
                    merged_content="User works in the financial services industry",
                    merged_time_to_live="one_year",
                    reasoning="Both profiles describe the user's industry as finance/financial services",
                )
            ],
            unique_indices=[2],
        )

        deduplicator = ProfileDeduplicator(
            request_context=mock_request_context,
            llm_client=mock_llm_client,
        )
        result = deduplicator.deduplicate(
            results=results,
            user_id="user",
            request_id="test_request",
        )

        # Verify structure
        assert len(result) == 1
        assert len(result[0].add_profiles) == 2

        # Find merged profile
        merged = next(
            (
                p
                for p in result[0].add_profiles
                if "financial services industry" in p.profile_content
            ),
            None,
        )
        assert merged is not None
        assert merged.user_id == "user"
        assert merged.profile_time_to_live == ProfileTimeToLive.ONE_YEAR
        # Custom features should be merged
        assert merged.custom_features == {"sector": "finance", "job_type": "analyst"}

        # Find unique profile
        unique = next(
            (p for p in result[0].add_profiles if "Python" in p.profile_content), None
        )
        assert unique is not None
        assert unique.profile_content == "User prefers Python programming"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
