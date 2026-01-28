"""
Unit tests for BaseGenerationService class.

Tests the abstract base class by creating a concrete implementation for testing.
"""

import pytest
import tempfile
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock

from reflexio.server.api_endpoints.request_context import RequestContext
from reflexio.server.llm.litellm_client import LiteLLMClient, LiteLLMConfig
from reflexio.server.services.base_generation_service import (
    BaseGenerationService,
    StatusChangeOperation,
)
from reflexio_commons.api_schema.service_schemas import (
    Interaction,
    Status,
)


# ===============================
# Test Data Classes
# ===============================


@dataclass
class MockExtractorConfig:
    """Mock extractor config for testing."""

    extractor_name: str
    request_sources_enabled: Optional[list[str]] = None
    manual_trigger: bool = False


@dataclass
class MockServiceConfig:
    """Mock service config for testing."""

    user_id: str = "test_user"
    request_id: str = "test_request"
    request_interaction_data_models: Optional[list] = None
    source: Optional[str] = None
    allow_manual_trigger: bool = False
    extractor_names: Optional[list[str]] = None


class MockExtractor:
    """Mock extractor for testing parallel execution."""

    def __init__(self, result=None, should_raise=False, exception_message="Test error"):
        self.result = result
        self.should_raise = should_raise
        self.exception_message = exception_message
        self.run_called = False

    def run(self):
        self.run_called = True
        if self.should_raise:
            raise Exception(self.exception_message)
        return self.result


# ===============================
# Concrete Test Implementation
# ===============================


class ConcreteGenerationService(BaseGenerationService):
    """Concrete implementation of BaseGenerationService for testing."""

    def __init__(self, llm_client, request_context, extractor_configs=None):
        super().__init__(llm_client, request_context)
        self._extractor_configs = extractor_configs or []
        self._processed_results = []
        # For upgrade/downgrade testing
        self._items_by_status = {}
        self._deleted_count = 0
        self._updated_count = 0

    def _load_extractor_configs(self):
        return self._extractor_configs

    def _load_generation_service_config(self, request):
        return request

    def _create_extractor(self, extractor_config, service_config):
        # Return mock extractor that returns the config name as result
        return MockExtractor(result={"extractor_name": extractor_config.extractor_name})

    def _get_service_name(self):
        return "test_generation_service"

    def _process_results(self, results):
        self._processed_results = results

    # Rerun hooks
    def _get_rerun_user_ids(self, request):
        # Get unique user IDs from request interactions
        interactions = getattr(request, "interactions", [])
        user_ids = set()
        for interaction in interactions:
            user_ids.add(interaction.user_id)
        return list(user_ids)

    def _build_rerun_request_params(self, request):
        return {"test_param": "test_value"}

    def _create_run_request_for_item(self, user_id, request):
        return MockServiceConfig(
            user_id=user_id,
            request_id=f"rerun_{user_id}",
            source=getattr(request, "source", None),
        )

    def _create_rerun_response(self, success, msg, count):
        return {"success": success, "message": msg, "count": count}

    def _get_generated_count(self, request):
        return len(self._processed_results)

    # Upgrade/downgrade hooks
    def _has_items_with_status(self, status, request):
        return (
            status in self._items_by_status and len(self._items_by_status[status]) > 0
        )

    def _delete_items_by_status(self, status, request):
        if status in self._items_by_status:
            count = len(self._items_by_status[status])
            self._items_by_status[status] = []
            self._deleted_count = count
            return count
        return 0

    def _update_items_status(self, old_status, new_status, request, user_ids=None):
        if old_status in self._items_by_status:
            items = self._items_by_status.pop(old_status, [])
            if new_status not in self._items_by_status:
                self._items_by_status[new_status] = []
            self._items_by_status[new_status].extend(items)
            self._updated_count = len(items)
            return len(items)
        return 0

    def _create_status_change_response(self, operation, success, counts, msg):
        return {
            "operation": operation.value,
            "success": success,
            "counts": counts,
            "message": msg,
        }

    # In-progress tracking hooks
    def _should_track_in_progress(self):
        return False  # Disabled by default for tests

    def _get_in_progress_state_key(self, request):
        return f"test_in_progress::{getattr(request, 'user_id', 'unknown')}"


# ===============================
# Fixtures
# ===============================


@pytest.fixture
def temp_storage():
    """Create a temporary directory for storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def llm_client():
    """Create a mock LLM client."""
    config = LiteLLMConfig(model="gpt-4o-mini")
    return LiteLLMClient(config)


@pytest.fixture
def request_context(temp_storage):
    """Create a request context with temporary storage."""
    return RequestContext(org_id="test_org", storage_base_dir=temp_storage)


@pytest.fixture
def base_service(llm_client, request_context):
    """Create a concrete generation service for testing."""
    return ConcreteGenerationService(llm_client, request_context)


# ===============================
# Test: _filter_extractor_configs_by_service_config
# ===============================


class TestFilterExtractorConfigsByServiceConfig:
    """Tests for the _filter_extractor_configs_by_service_config method."""

    def test_no_filtering_without_source_attribute(self, base_service):
        """Test that configs are not filtered if service_config has no source attribute."""
        configs = [
            MockExtractorConfig(extractor_name="extractor1"),
            MockExtractorConfig(extractor_name="extractor2"),
        ]

        # Create service config without source attribute
        class NoSourceConfig:
            pass

        service_config = NoSourceConfig()
        result = base_service._filter_extractor_configs_by_service_config(
            configs, service_config
        )
        assert len(result) == 2

    def test_filter_by_source_enabled(self, base_service):
        """Test filtering extractors by request_sources_enabled."""
        configs = [
            MockExtractorConfig(
                extractor_name="extractor1", request_sources_enabled=["api", "web"]
            ),
            MockExtractorConfig(
                extractor_name="extractor2", request_sources_enabled=["mobile"]
            ),
            MockExtractorConfig(extractor_name="extractor3"),  # No source restriction
        ]

        service_config = MockServiceConfig(source="api")
        result = base_service._filter_extractor_configs_by_service_config(
            configs, service_config
        )

        # extractor1 (api in enabled list) and extractor3 (no restriction) should pass
        assert len(result) == 2
        extractor_names = [c.extractor_name for c in result]
        assert "extractor1" in extractor_names
        assert "extractor3" in extractor_names
        assert "extractor2" not in extractor_names

    def test_filter_by_manual_trigger(self, base_service):
        """Test filtering extractors by manual_trigger flag."""
        configs = [
            MockExtractorConfig(extractor_name="extractor1", manual_trigger=True),
            MockExtractorConfig(extractor_name="extractor2", manual_trigger=False),
            MockExtractorConfig(extractor_name="extractor3"),  # Default False
        ]

        # allow_manual_trigger=False - manual_trigger=True extractors should be skipped
        service_config = MockServiceConfig(allow_manual_trigger=False)
        result = base_service._filter_extractor_configs_by_service_config(
            configs, service_config
        )

        assert len(result) == 2
        extractor_names = [c.extractor_name for c in result]
        assert "extractor2" in extractor_names
        assert "extractor3" in extractor_names
        assert "extractor1" not in extractor_names

    def test_manual_trigger_allowed_when_allow_manual_trigger_true(self, base_service):
        """Test that manual_trigger extractors are allowed when allow_manual_trigger=True."""
        configs = [
            MockExtractorConfig(extractor_name="extractor1", manual_trigger=True),
            MockExtractorConfig(extractor_name="extractor2", manual_trigger=False),
        ]

        service_config = MockServiceConfig(allow_manual_trigger=True)
        result = base_service._filter_extractor_configs_by_service_config(
            configs, service_config
        )

        assert len(result) == 2
        extractor_names = [c.extractor_name for c in result]
        assert "extractor1" in extractor_names
        assert "extractor2" in extractor_names

    def test_filter_by_extractor_names(self, base_service):
        """Test filtering extractors by extractor_names list in service_config."""
        configs = [
            MockExtractorConfig(extractor_name="extractor1"),
            MockExtractorConfig(extractor_name="extractor2"),
            MockExtractorConfig(extractor_name="extractor3"),
        ]

        service_config = MockServiceConfig(extractor_names=["extractor1", "extractor3"])
        result = base_service._filter_extractor_configs_by_service_config(
            configs, service_config
        )

        assert len(result) == 2
        extractor_names = [c.extractor_name for c in result]
        assert "extractor1" in extractor_names
        assert "extractor3" in extractor_names
        assert "extractor2" not in extractor_names

    def test_combined_filtering(self, base_service):
        """Test that all filter conditions are applied together."""
        configs = [
            MockExtractorConfig(
                extractor_name="extractor1",
                request_sources_enabled=["api"],
                manual_trigger=False,
            ),
            MockExtractorConfig(
                extractor_name="extractor2",
                request_sources_enabled=["mobile"],
                manual_trigger=False,
            ),
            MockExtractorConfig(
                extractor_name="extractor3",
                request_sources_enabled=["api"],
                manual_trigger=True,
            ),
        ]

        # Source=api, allow_manual_trigger=False, filter by name
        service_config = MockServiceConfig(
            source="api",
            allow_manual_trigger=False,
            extractor_names=["extractor1", "extractor3"],
        )
        result = base_service._filter_extractor_configs_by_service_config(
            configs, service_config
        )

        # Only extractor1 passes all filters:
        # - extractor2: wrong source
        # - extractor3: manual_trigger=True but allow_manual_trigger=False
        assert len(result) == 1
        assert result[0].extractor_name == "extractor1"

    def test_empty_configs_list(self, base_service):
        """Test filtering with empty configs list."""
        configs = []
        service_config = MockServiceConfig(source="api")
        result = base_service._filter_extractor_configs_by_service_config(
            configs, service_config
        )
        assert len(result) == 0

    def test_none_source_in_service_config(self, base_service):
        """Test filtering when source is None in service_config."""
        configs = [
            MockExtractorConfig(
                extractor_name="extractor1", request_sources_enabled=["api"]
            ),
            MockExtractorConfig(extractor_name="extractor2"),
        ]

        service_config = MockServiceConfig(source=None)
        result = base_service._filter_extractor_configs_by_service_config(
            configs, service_config
        )

        # Both should pass since source is None (no filtering by source)
        assert len(result) == 2


# ===============================
# Test: _run_extractors_in_parallel
# ===============================


class TestRunExtractorsInParallel:
    """Tests for the _run_extractors_in_parallel method."""

    def test_successful_parallel_execution(self, base_service):
        """Test that all extractors run successfully in parallel."""
        extractors = [
            MockExtractor(result={"id": 1}),
            MockExtractor(result={"id": 2}),
            MockExtractor(result={"id": 3}),
        ]

        results = base_service._run_extractors_in_parallel(extractors, "test_context")

        assert len(results) == 3
        assert all(e.run_called for e in extractors)

    def test_handles_exceptions_gracefully(self, base_service):
        """Test that exceptions in one extractor don't stop others."""
        extractors = [
            MockExtractor(result={"id": 1}),
            MockExtractor(should_raise=True, exception_message="Failed extractor"),
            MockExtractor(result={"id": 3}),
        ]

        results = base_service._run_extractors_in_parallel(extractors, "test_context")

        # Should have 2 results (excluding failed one)
        assert len(results) == 2
        assert all(e.run_called for e in extractors)

    def test_filters_none_results(self, base_service):
        """Test that None results are filtered out."""
        extractors = [
            MockExtractor(result={"id": 1}),
            MockExtractor(result=None),
            MockExtractor(result={"id": 3}),
        ]

        results = base_service._run_extractors_in_parallel(extractors, "test_context")

        assert len(results) == 2

    def test_empty_extractors_list(self, base_service):
        """Test with empty extractors list."""
        results = base_service._run_extractors_in_parallel([], "test_context")
        assert len(results) == 0

    def test_all_extractors_fail(self, base_service):
        """Test when all extractors raise exceptions."""
        extractors = [
            MockExtractor(should_raise=True),
            MockExtractor(should_raise=True),
        ]

        results = base_service._run_extractors_in_parallel(extractors, "test_context")

        assert len(results) == 0
        assert all(e.run_called for e in extractors)


# ===============================
# Test: run()
# ===============================


class TestRun:
    """Tests for the main run() method."""

    def test_run_with_valid_request(self, llm_client, request_context):
        """Test run() with a valid request containing interactions."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[
                MockExtractorConfig(extractor_name="extractor1"),
                MockExtractorConfig(extractor_name="extractor2"),
            ],
        )

        request = MockServiceConfig(
            user_id="test_user",
            request_id="test_request",
            request_interaction_data_models=[MagicMock()],
        )

        service.run(request)

        # Results should be processed
        assert len(service._processed_results) == 2

    def test_run_with_none_request(self, base_service):
        """Test that run() handles None request gracefully."""
        base_service.run(None)
        # Should not raise, just return early
        assert len(base_service._processed_results) == 0

    def test_run_without_interaction_data(self, llm_client, request_context):
        """Test run() when request has no interaction data.

        Note: After the refactor, extractors handle their own data collection.
        When request_interaction_data_models=None, extractors will attempt to
        collect their own interactions rather than the service returning early.
        """
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        request = MockServiceConfig(
            user_id="test_user",
            request_id="test_request",
            request_interaction_data_models=None,
        )

        service.run(request)

        # After refactor: extractors run and try to get their own data
        # The mock extractor returns a result, so we expect 1 result
        assert len(service._processed_results) == 1

    def test_run_without_extractor_configs(self, llm_client, request_context):
        """Test run() when no extractor configs are available."""
        service = ConcreteGenerationService(
            llm_client, request_context, extractor_configs=[]
        )

        request = MockServiceConfig(
            request_interaction_data_models=[MagicMock()],
        )

        service.run(request)

        # Should return early without processing
        assert len(service._processed_results) == 0

    def test_run_stores_service_config(self, llm_client, request_context):
        """Test that run() stores the service_config for later access."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        request = MockServiceConfig(
            user_id="test_user",
            request_id="test_request",
            request_interaction_data_models=[MagicMock()],
        )

        service.run(request)

        assert service.service_config is not None
        assert service.service_config.user_id == "test_user"

    def test_run_filters_extractor_configs(self, llm_client, request_context):
        """Test that run() applies config filtering before creating extractors."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[
                MockExtractorConfig(
                    extractor_name="extractor1", request_sources_enabled=["api"]
                ),
                MockExtractorConfig(
                    extractor_name="extractor2", request_sources_enabled=["mobile"]
                ),
            ],
        )

        request = MockServiceConfig(
            source="api",
            request_interaction_data_models=[MagicMock()],
        )

        service.run(request)

        # Only extractor1 should run since source is "api"
        assert len(service._processed_results) == 1
        assert service._processed_results[0]["extractor_name"] == "extractor1"


# ===============================
# Test: _count_interactions()
# ===============================


# ===============================
# Helper: Mock Operation State Storage
# ===============================


def create_mock_operation_state_storage():
    """Create a mock storage that tracks operation state properly."""
    state_store = {}

    def get_operation_state(service_name):
        return state_store.get(service_name)

    def upsert_operation_state(service_name, state):
        state_store[service_name] = {"operation_state": state}

    def update_operation_state(service_name, state):
        state_store[service_name] = {"operation_state": state}

    return get_operation_state, upsert_operation_state, update_operation_state


# ===============================
# Test: run_rerun()
# ===============================


class TestRunRerun:
    """Tests for the run_rerun() method."""

    def test_rerun_with_valid_interactions(self, llm_client, request_context):
        """Test rerun with valid interactions."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Set up mock storage that tracks state properly
        get_state, upsert_state, update_state = create_mock_operation_state_storage()
        service.storage.get_operation_state = get_state
        service.storage.upsert_operation_state = upsert_state
        service.storage.update_operation_state = update_state

        request = MagicMock()
        request.interactions = [
            Interaction(user_id="user1", request_id="req1", content="test1"),
            Interaction(user_id="user1", request_id="req1", content="test2"),
        ]

        response = service.run_rerun(request)

        assert response["success"] is True
        assert "Completed" in response["message"]

    def test_rerun_blocks_if_in_progress(self, llm_client, request_context):
        """Test that rerun blocks if another operation is in progress."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Mock operation state to show in-progress
        service.storage.get_operation_state = MagicMock(
            return_value={"operation_state": {"status": "in_progress"}}
        )

        request = MagicMock()
        request.interactions = [
            Interaction(user_id="user1", request_id="req1", content="test1")
        ]

        response = service.run_rerun(request)

        assert response["success"] is False
        assert "already in progress" in response["message"]

    def test_rerun_with_no_interactions(self, llm_client, request_context):
        """Test rerun when no interactions match filters."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        service.storage.get_operation_state = MagicMock(return_value=None)

        request = MagicMock()
        request.interactions = []

        response = service.run_rerun(request)

        assert response["success"] is False
        assert "No interactions found" in response["message"]

    def test_rerun_groups_by_user(self, llm_client, request_context):
        """Test that rerun processes interactions grouped by user."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Set up mock storage that tracks state properly
        get_state, upsert_state, update_state = create_mock_operation_state_storage()
        service.storage.get_operation_state = get_state
        service.storage.upsert_operation_state = upsert_state
        service.storage.update_operation_state = update_state

        request = MagicMock()
        request.interactions = [
            Interaction(user_id="user1", request_id="req1", content="test1"),
            Interaction(user_id="user2", request_id="req2", content="test2"),
            Interaction(user_id="user1", request_id="req3", content="test3"),
        ]

        response = service.run_rerun(request)

        assert response["success"] is True
        # Should process 2 users (user1 and user2)
        assert "2 user" in response["message"]


# ===============================
# Test: run_upgrade()
# ===============================


class TestRunUpgrade:
    """Tests for the run_upgrade() method."""

    def test_upgrade_promotes_pending_items(self, llm_client, request_context):
        """Test that upgrade promotes pending items to current."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Set up items: pending items exist
        service._items_by_status = {
            Status.PENDING: ["item1", "item2"],
            None: ["old_item"],  # Current items
            Status.ARCHIVED: ["archived_item"],
        }

        request = MagicMock()
        response = service.run_upgrade(request)

        assert response["success"] is True
        assert response["operation"] == "upgrade"
        assert response["counts"]["promoted"] == 2

    def test_upgrade_fails_without_pending_items(self, llm_client, request_context):
        """Test that upgrade fails when no pending items exist."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        service._items_by_status = {
            None: ["current_item"],
        }

        request = MagicMock()
        response = service.run_upgrade(request)

        assert response["success"] is False
        assert "No pending items" in response["message"]

    def test_upgrade_archives_current_items(self, llm_client, request_context):
        """Test that upgrade archives current items."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        service._items_by_status = {
            Status.PENDING: ["new_item"],
            None: ["current1", "current2", "current3"],
        }

        request = MagicMock()
        response = service.run_upgrade(request)

        assert response["success"] is True
        assert response["counts"]["archived"] == 3

    def test_upgrade_deletes_old_archived_items(self, llm_client, request_context):
        """Test that upgrade deletes old archived items."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        service._items_by_status = {
            Status.PENDING: ["new_item"],
            Status.ARCHIVED: ["old1", "old2"],
        }

        request = MagicMock()
        response = service.run_upgrade(request)

        assert response["success"] is True
        assert response["counts"]["deleted"] == 2


# ===============================
# Test: run_downgrade()
# ===============================


class TestRunDowngrade:
    """Tests for the run_downgrade() method."""

    def test_downgrade_restores_archived_items(self, llm_client, request_context):
        """Test that downgrade restores archived items to current."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        service._items_by_status = {
            None: ["current_item"],
            Status.ARCHIVED: ["archived1", "archived2"],
        }

        request = MagicMock()
        response = service.run_downgrade(request)

        assert response["success"] is True
        assert response["operation"] == "downgrade"
        assert response["counts"]["restored"] == 2

    def test_downgrade_fails_without_archived_items(self, llm_client, request_context):
        """Test that downgrade fails when no archived items exist."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        service._items_by_status = {
            None: ["current_item"],
        }

        request = MagicMock()
        response = service.run_downgrade(request)

        assert response["success"] is False
        assert "No archived items" in response["message"]

    def test_downgrade_demotes_current_items(self, llm_client, request_context):
        """Test that downgrade demotes current items to archived."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        service._items_by_status = {
            None: ["current1", "current2"],
            Status.ARCHIVED: ["archived1"],
        }

        request = MagicMock()
        response = service.run_downgrade(request)

        assert response["success"] is True
        assert response["counts"]["demoted"] == 2


# ===============================
# Test: StatusChangeOperation Enum
# ===============================


class TestStatusChangeOperation:
    """Tests for the StatusChangeOperation enum."""

    def test_upgrade_value(self):
        """Test UPGRADE enum value."""
        assert StatusChangeOperation.UPGRADE.value == "upgrade"

    def test_downgrade_value(self):
        """Test DOWNGRADE enum value."""
        assert StatusChangeOperation.DOWNGRADE.value == "downgrade"


# ===============================
# Test: Error Handling
# ===============================


class TestErrorHandling:
    """Tests for error handling in BaseGenerationService."""

    def test_run_handles_exception_in_load_config(self, llm_client, request_context):
        """Test that run() handles exceptions during config loading."""

        class FailingService(ConcreteGenerationService):
            def _load_generation_service_config(self, request):
                raise ValueError("Config loading failed")

        service = FailingService(llm_client, request_context)
        request = MockServiceConfig(request_interaction_data_models=[MagicMock()])

        # Should not raise, just log warning
        service.run(request)
        assert len(service._processed_results) == 0

    def test_run_handles_exception_in_extractor(self, llm_client, request_context):
        """Test that run() handles exceptions from extractors."""

        class FailingExtractorService(ConcreteGenerationService):
            def _create_extractor(self, extractor_config, service_config):
                return MockExtractor(should_raise=True)

        service = FailingExtractorService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )
        request = MockServiceConfig(request_interaction_data_models=[MagicMock()])

        service.run(request)
        assert len(service._processed_results) == 0

    def test_rerun_handles_item_processing_exception(self, llm_client, request_context):
        """Test that rerun handles exceptions during item processing."""

        class FailingRunService(ConcreteGenerationService):
            def run(self, request):
                if hasattr(request, "user_id") and request.user_id == "failing_user":
                    raise Exception("Processing failed")
                super().run(request)

        service = FailingRunService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Set up mock storage that tracks state properly
        get_state, upsert_state, update_state = create_mock_operation_state_storage()
        service.storage.get_operation_state = get_state
        service.storage.upsert_operation_state = upsert_state
        service.storage.update_operation_state = update_state

        request = MagicMock()
        request.interactions = [
            Interaction(user_id="failing_user", request_id="req1", content="test1"),
            Interaction(user_id="success_user", request_id="req2", content="test2"),
        ]

        response = service.run_rerun(request)

        # Should still complete successfully for other users
        assert response["success"] is True


# ===============================
# Test: In-Progress Lock Mechanism
# ===============================


class InProgressTrackingService(ConcreteGenerationService):
    """Concrete implementation with in-progress tracking enabled."""

    def __init__(self, llm_client, request_context, extractor_configs=None):
        super().__init__(llm_client, request_context, extractor_configs)
        self._generation_count = 0  # Tracks _run_generation calls

    def _should_track_in_progress(self):
        return True  # Enable in-progress tracking

    def _get_in_progress_state_key(self, request):
        user_id = getattr(request, "user_id", "unknown")
        return f"test_in_progress::{self.org_id}::{user_id}"

    def _run_generation(self, request):
        """Override to track generation calls."""
        self._generation_count += 1
        # Don't call super() to avoid needing real extractors


class TestInProgressLockMechanism:
    """Tests for the in-progress lock acquisition and release mechanism."""

    def test_lock_acquired_when_no_existing_lock(self, llm_client, request_context):
        """Test that lock is acquired when no lock exists."""
        service = InProgressTrackingService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Mock storage to simulate no existing lock and successful lock acquisition
        service.storage.try_acquire_in_progress_lock = MagicMock(
            return_value={"acquired": True}
        )
        # Return state showing we own the lock with no pending
        service.storage.get_operation_state = MagicMock(
            return_value={
                "operation_state": {
                    "in_progress": True,
                    "current_request_id": "request_1",
                    "pending_request_id": None,
                }
            }
        )
        service.storage.upsert_operation_state = MagicMock()

        request = MockServiceConfig(user_id="test_user", request_id="request_1")
        service.run(request)

        # Verify lock acquisition was attempted and generation ran
        service.storage.try_acquire_in_progress_lock.assert_called_once()
        assert service._generation_count == 1

    def test_lock_not_acquired_when_another_operation_in_progress(
        self, llm_client, request_context
    ):
        """Test that lock is not acquired when another operation is running."""
        service = InProgressTrackingService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Mock storage to simulate existing lock (not acquired)
        service.storage.try_acquire_in_progress_lock = MagicMock(
            return_value={"acquired": False}
        )

        request = MockServiceConfig(user_id="test_user", request_id="request_2")
        service.run(request)

        # Verify generation was NOT run (lock not acquired)
        assert service._generation_count == 0

    def test_stale_lock_is_overridden(self, llm_client, request_context):
        """Test that stale locks (>5 min) are overridden."""
        service = InProgressTrackingService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Mock storage to simulate stale lock that gets acquired
        # The storage.try_acquire_in_progress_lock handles stale lock detection
        service.storage.try_acquire_in_progress_lock = MagicMock(
            return_value={"acquired": True, "was_stale": True}
        )
        service.storage.get_operation_state = MagicMock(
            return_value={
                "operation_state": {
                    "in_progress": True,
                    "current_request_id": "request_3",
                    "pending_request_id": None,
                }
            }
        )
        service.storage.upsert_operation_state = MagicMock()

        request = MockServiceConfig(user_id="test_user", request_id="request_3")
        service.run(request)

        # Verify lock was acquired (stale lock overridden)
        assert service._generation_count == 1

    def test_pending_request_triggers_rerun(self, llm_client, request_context):
        """Test that pending_request_id triggers a re-run after completion."""
        service = InProgressTrackingService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Track call count for get_operation_state (used by _release_in_progress_lock)
        release_call_count = [0]

        def mock_get_state(state_key):
            release_call_count[0] += 1
            if release_call_count[0] == 1:
                # First call: return pending request to trigger re-run
                return {
                    "operation_state": {
                        "in_progress": True,
                        "current_request_id": "request_1",
                        "pending_request_id": "request_2",
                    }
                }
            else:
                # Subsequent calls: no more pending requests
                return {
                    "operation_state": {
                        "in_progress": True,
                        "current_request_id": "request_2",
                        "pending_request_id": None,
                    }
                }

        service.storage.try_acquire_in_progress_lock = MagicMock(
            return_value={"acquired": True}
        )
        service.storage.get_operation_state = mock_get_state
        service.storage.upsert_operation_state = MagicMock()

        request = MockServiceConfig(user_id="test_user", request_id="request_1")
        service.run(request)

        # Verify _run_generation was called twice (initial + re-run for pending request)
        assert service._generation_count == 2

    def test_lock_cleared_on_exception(self, llm_client, request_context):
        """Test that lock is cleared when an exception occurs during generation."""

        class FailingInProgressService(InProgressTrackingService):
            def _run_generation(self, request):
                raise Exception("Generation failed!")

        service = FailingInProgressService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        service.storage.try_acquire_in_progress_lock = MagicMock(
            return_value={"acquired": True}
        )
        service.storage.upsert_operation_state = MagicMock()

        request = MockServiceConfig(user_id="test_user", request_id="request_1")

        # Should raise but lock should be cleared
        with pytest.raises(Exception, match="Generation failed!"):
            service.run(request)

        # Verify lock was cleared (upsert with in_progress=False)
        clear_call = service.storage.upsert_operation_state.call_args
        assert clear_call is not None
        state_arg = clear_call[0][1]
        assert state_arg["in_progress"] is False

    def test_release_lock_no_pending_clears_state(self, llm_client, request_context):
        """Test that releasing lock with no pending request clears the state."""
        service = InProgressTrackingService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Mock storage to return state with matching request_id and no pending
        service.storage.get_operation_state = MagicMock(
            return_value={
                "operation_state": {
                    "in_progress": True,
                    "current_request_id": "my_request",
                    "pending_request_id": None,
                }
            }
        )
        service.storage.upsert_operation_state = MagicMock()

        result = service._release_in_progress_lock("test_key", "my_request")

        # Should return None (no pending) and clear the lock
        assert result is None
        service.storage.upsert_operation_state.assert_called_once()
        state_arg = service.storage.upsert_operation_state.call_args[0][1]
        assert state_arg["in_progress"] is False

    def test_release_lock_with_pending_transfers_ownership(
        self, llm_client, request_context
    ):
        """Test that releasing lock with pending request transfers ownership."""
        service = InProgressTrackingService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Mock storage to return state with pending request
        service.storage.get_operation_state = MagicMock(
            return_value={
                "operation_state": {
                    "in_progress": True,
                    "current_request_id": "my_request",
                    "pending_request_id": "new_request",
                }
            }
        )
        service.storage.upsert_operation_state = MagicMock()

        result = service._release_in_progress_lock("test_key", "my_request")

        # Should return pending_request_id and transfer ownership
        assert result == "new_request"
        service.storage.upsert_operation_state.assert_called_once()
        state_arg = service.storage.upsert_operation_state.call_args[0][1]
        assert state_arg["in_progress"] is True
        assert state_arg["current_request_id"] == "new_request"
        assert state_arg["pending_request_id"] is None

    def test_release_lock_ignores_if_not_owner(self, llm_client, request_context):
        """Test that release does nothing if caller is not the current owner."""
        service = InProgressTrackingService(
            llm_client,
            request_context,
            extractor_configs=[MockExtractorConfig(extractor_name="extractor1")],
        )

        # Mock storage to return state owned by different request
        service.storage.get_operation_state = MagicMock(
            return_value={
                "operation_state": {
                    "in_progress": True,
                    "current_request_id": "other_request",
                    "pending_request_id": "another_pending",
                }
            }
        )
        service.storage.upsert_operation_state = MagicMock()

        result = service._release_in_progress_lock("test_key", "my_request")

        # Should return None and NOT update state (not the owner)
        assert result is None
        service.storage.upsert_operation_state.assert_not_called()


# ===============================
# Test: Extractor Names Filtering in Rerun
# ===============================


class TestRerunWithExtractorNamesFilter:
    """Tests for extractor_names filtering during rerun operations."""

    def test_rerun_respects_extractor_names_filter(self, llm_client, request_context):
        """Test that rerun only runs extractors specified in extractor_names."""
        service = ConcreteGenerationService(
            llm_client,
            request_context,
            extractor_configs=[
                MockExtractorConfig(extractor_name="extractor1"),
                MockExtractorConfig(extractor_name="extractor2"),
                MockExtractorConfig(extractor_name="extractor3"),
            ],
        )

        # Set up mock storage
        get_state, upsert_state, update_state = create_mock_operation_state_storage()
        service.storage.get_operation_state = get_state
        service.storage.upsert_operation_state = upsert_state
        service.storage.update_operation_state = update_state

        # Create request with extractor_names filter
        request = MagicMock()
        request.interactions = [
            Interaction(user_id="user1", request_id="req1", content="test1")
        ]
        request.extractor_names = ["extractor1", "extractor3"]

        # Override _create_run_request_for_item to pass extractor_names
        original_create = service._create_run_request_for_item

        def create_with_names(user_id, req):
            result = original_create(user_id, req)
            result.extractor_names = getattr(req, "extractor_names", None)
            return result

        service._create_run_request_for_item = create_with_names

        response = service.run_rerun(request)

        assert response["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
