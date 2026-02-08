"""
Base class for generation services
"""

import enum
import logging
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Generic, Optional, TypeVar

from reflexio_commons.api_schema.service_schemas import Status

from reflexio.server.api_endpoints.request_context import RequestContext
from reflexio.server.llm.litellm_client import LiteLLMClient
from reflexio.server.services.extractor_config_utils import filter_extractor_configs
from reflexio.server.services.operation_state_utils import OperationStateManager


class StatusChangeOperation(str, enum.Enum):
    """Operation type for upgrade/downgrade responses."""

    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"


logger = logging.getLogger(__name__)

# Timeout for individual extractor execution (safety net if LLM provider ignores its own timeout)
EXTRACTOR_TIMEOUT_SECONDS = 300

# Type variables for generic base service
TExtractorConfig = TypeVar(
    "TExtractorConfig"
)  # Extractor config type from YAML (e.g., AgentFeedbackConfig, ProfileExtractorConfig)
TExtractor = TypeVar(
    "TExtractor"
)  # Extractor type (e.g., FeedbackExtractor, AgentSuccessEvaluator, ProfileExtractor)
TResult = TypeVar("TResult")  # Result type (e.g., RawFeedback, ProfileUpdates)
TGenerationServiceConfig = TypeVar(
    "TGenerationServiceConfig"
)  # Runtime service configuration type (e.g., FeedbackGenerationServiceConfig, ProfileGenerationServiceConfig)
TRequest = TypeVar(
    "TRequest"
)  # Request type (e.g., ProfileGenerationRequest, FeedbackGenerationRequest, AgentSuccessEvaluationRequest)


# Unified base class for all generation services (evaluation, feedback, profile)
class BaseGenerationService(
    ABC, Generic[TExtractorConfig, TExtractor, TGenerationServiceConfig, TRequest]
):
    """
    Base class for generation services that run multiple extractors in parallel.

    This unified class supports two types of services:
    1. Evaluation services (feedback, agent success) - process interactions and save RawFeedback
    2. Profile services - process interactions with existing data and apply updates

    Type Parameters:
        TExtractorConfig: The extractor configuration type from YAML (e.g., AgentFeedbackConfig, ProfileExtractorConfig)
        TExtractor: The extractor type (e.g., FeedbackExtractor, ProfileExtractor, AgentSuccessEvaluator)
        TGenerationServiceConfig: The runtime service configuration type (e.g., FeedbackGenerationServiceConfig, ProfileGenerationServiceConfig)
        TRequest: The request type (e.g., ProfileGenerationRequest, FeedbackGenerationRequest, AgentSuccessEvaluationRequest)

    Child classes must implement:
    - _load_extractor_configs(): Load extractor configurations from configurator
    - _load_generation_service_config(): Extract parameters from request and return GenerationServiceConfig
    - _create_extractor(): Create extractor instances with extractor config and service config
    - _get_service_name(): Get service name for logging
    - _process_results(): Process and save results (can access self.service_config)
    """

    def __init__(
        self, llm_client: LiteLLMClient, request_context: RequestContext
    ) -> None:
        """
        Initialize the base generation service.

        Args:
            llm_client: Unified LLM client supporting both OpenAI and Claude
            request_context: Request context with storage, configurator, and org_id
        """
        self.client = llm_client
        self.storage = request_context.storage
        self.org_id = request_context.org_id
        self.configurator = request_context.configurator
        self.request_context = request_context
        self.service_config: Optional[TGenerationServiceConfig] = None
        self._is_batch_mode: bool = False

    @abstractmethod
    def _load_extractor_configs(self) -> list[TExtractorConfig]:
        """
        Load extractor configurations from the configurator.

        Returns:
            List of extractor configuration objects (from YAML)
        """

    @abstractmethod
    def _load_generation_service_config(
        self, request: TRequest
    ) -> TGenerationServiceConfig:
        """
        Extract parameters from request object and return GenerationServiceConfig.

        Args:
            request: The request object

        Returns:
            GenerationServiceConfig object (e.g., FeedbackGenerationServiceConfig, ProfileGenerationServiceConfig)
        """

    @abstractmethod
    def _create_extractor(
        self,
        extractor_config: TExtractorConfig,
        service_config: TGenerationServiceConfig,
    ) -> TExtractor:
        """
        Create an extractor instance from extractor config and service config.

        Args:
            extractor_config: The extractor configuration object from YAML (e.g., AgentFeedbackConfig, ProfileExtractorConfig)
            service_config: The runtime service configuration object (e.g., FeedbackGenerationServiceConfig, ProfileGenerationServiceConfig)

        Returns:
            An extractor instance
        """

    @abstractmethod
    def _get_service_name(self) -> str:
        """
        Get the name of the service for logging purposes.

        Returns:
            Service name string
        """

    @abstractmethod
    def _get_base_service_name(self) -> str:
        """
        Get the base service name for OperationStateManager keys.

        This is the service identity used for progress/lock key construction,
        independent of whether the operation is a rerun or regular run.

        Returns:
            Base service name (e.g., "profile_generation", "feedback_generation")
        """

    @abstractmethod
    def _process_results(self, results: list) -> None:
        """
        Process and save results. Can access self.service_config for context.

        Args:
            results: List of results from extractors
        """

    @abstractmethod
    def _should_track_in_progress(self) -> bool:
        """
        Return True if this service should track in-progress state to prevent duplicates.

        Profile and Feedback services should return True to prevent duplicate generation
        when back-to-back requests arrive. AgentSuccess services should return False
        as they process per-request and don't have the same duplication issue.

        Returns:
            bool: True if in-progress tracking should be enabled
        """

    @abstractmethod
    def _get_lock_scope_id(self, request: TRequest) -> Optional[str]:
        """
        Get the scope ID for lock key construction.

        Profile services return user_id (per-user lock), feedback services return None (per-org lock).

        Args:
            request: The generation request

        Returns:
            Optional[str]: Scope ID (e.g., user_id) or None for org-level scope
        """

    def _filter_extractor_configs_by_service_config(
        self,
        extractor_configs: list[TExtractorConfig],
        service_config: TGenerationServiceConfig,
    ) -> list[TExtractorConfig]:
        """
        Filter extractor configs based on request_sources_enabled and manual_trigger fields.

        Args:
            extractor_configs: List of extractor configuration objects from YAML
            service_config: Runtime service configuration containing the source and allow_manual_trigger flag

        Returns:
            Filtered list of extractor configs that should run for the given source and trigger mode
        """
        # Extract filtering parameters from service_config
        source = getattr(service_config, "source", None)
        allow_manual_trigger = getattr(service_config, "allow_manual_trigger", False)
        extractor_names = getattr(service_config, "extractor_names", None)

        return filter_extractor_configs(
            extractor_configs=extractor_configs,
            source=source,
            allow_manual_trigger=allow_manual_trigger,
            extractor_names=extractor_names,
        )

    def _run_extractors_in_parallel(
        self,
        extractors: list[TExtractor],
        error_context: str = "unknown",
    ) -> list:
        """
        Run extractors in parallel with error handling and timeout protection.

        Uses manual executor management instead of context manager to avoid blocking
        on shutdown(wait=True) when threads are hung on LLM calls.

        Args:
            extractors: List of extractor instances (each with parameterless run() method)
            error_context: Context string for error logging (e.g., request_id)

        Returns:
            List of results from all successful extractor executions
        """
        results = []
        executor = ThreadPoolExecutor(max_workers=5)

        try:
            futures = [executor.submit(extractor.run) for extractor in extractors]

            for future in futures:
                try:
                    result = future.result(timeout=EXTRACTOR_TIMEOUT_SECONDS)
                    if result:
                        results.append(result)
                except FuturesTimeoutError:
                    logger.error(
                        "Extractor timed out after %d seconds for %s context %s",
                        EXTRACTOR_TIMEOUT_SECONDS,
                        self._get_service_name(),
                        error_context,
                    )
                    continue
                except Exception as e:
                    logger.error(
                        "Failed to run %s for context %s due to %s, exception type: %s",
                        self._get_service_name(),
                        error_context,
                        str(e),
                        type(e).__name__,
                    )
                    continue
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        return results

    # ===============================
    # In-progress state management via OperationStateManager
    # ===============================

    def _create_state_manager(self) -> OperationStateManager:
        """Create an OperationStateManager for this service.

        Returns:
            OperationStateManager instance configured for this service
        """
        return OperationStateManager(
            self.storage, self.org_id, self._get_base_service_name()
        )

    def run(self, request: TRequest) -> None:
        """
        Run the generation service for the given request.

        This is the main entry point that:
        1. If in-progress tracking is enabled, handles lock acquisition/release
        2. Validates and extracts parameters from the request into GenerationServiceConfig
        3. Runs extractors in parallel (each extractor handles its own data collection)
        4. Processes results
        5. Re-runs if new requests came in during generation

        Args:
            request: The request object containing parameters
        """
        # Check if this service tracks in-progress state
        if not self._should_track_in_progress():
            self._run_generation(request)
            return

        # Get scope ID and request ID for in-progress tracking
        scope_id = self._get_lock_scope_id(request)
        my_request_id = getattr(request, "request_id", None) or str(uuid.uuid4())

        state_manager = self._create_state_manager()

        # Try to acquire lock
        if not state_manager.acquire_lock(my_request_id, scope_id=scope_id):
            return  # Another operation is running, we've updated pending_request_id

        # Re-run loop: keep running until no new requests come in
        try:
            while True:
                self._run_generation(request)

                # If in batch mode and cancellation was requested, clear lock
                # to prevent queued pending requests from running, then stop
                if self._is_batch_mode and state_manager.is_cancellation_requested():
                    state_manager.clear_lock(scope_id=scope_id)
                    logger.info(
                        "Cancellation detected in run() for %s, cleared lock to prevent pending re-runs",
                        self._get_service_name(),
                    )
                    break

                # Check if another request came in during our run
                pending_request_id = state_manager.release_lock(
                    my_request_id, scope_id=scope_id
                )

                logger.info(
                    "Released in-progress lock for %s: request_id=%s, pending_request_id=%s",
                    self._get_service_name(),
                    my_request_id,
                    pending_request_id,
                )

                if not pending_request_id:
                    break  # No pending request, we're done

                # Another request came in, update my_request_id and re-run
                my_request_id = pending_request_id

        except Exception:
            # Clear lock on error to prevent deadlock
            state_manager.clear_lock(scope_id=scope_id)
            raise

    def _run_generation(self, request: TRequest) -> None:
        """
        Run the actual generation logic.

        This method contains the core generation logic extracted from the original run() method.
        It handles:
        1. Validating and extracting parameters from the request
        2. Running extractors in parallel
        3. Processing results

        Args:
            request: The request object containing parameters
        """
        # Validate request
        if not request:
            logger.error("Received None request for %s", self._get_service_name())
            return

        try:
            # Extract parameters into GenerationServiceConfig
            self.service_config = self._load_generation_service_config(request)

            # Load extractor configs
            extractor_configs = self._load_extractor_configs()
            if not extractor_configs:
                logger.warning(
                    "No %s extractor configs found", self._get_service_name()
                )
                return

            # Filter configs based on source and manual trigger (if applicable)
            extractor_configs = self._filter_extractor_configs_by_service_config(
                extractor_configs, self.service_config
            )

            if not extractor_configs:
                source = getattr(self.service_config, "source", "N/A")
                source_display = source if source else "N/A"
                logger.info(
                    "No %s extractor configs enabled for source: %s",
                    self._get_service_name(),
                    source_display,
                )
                return

            # Create extractors with extractor config and service config
            # Each extractor handles its own data collection and stride checking
            extractors = [
                self._create_extractor(extractor_config, self.service_config)
                for extractor_config in extractor_configs
            ]

            # Get identifier for error context
            identifier = getattr(self.service_config, "user_id", None) or getattr(
                self.service_config, "request_id", "unknown"
            )

            # Run extractors in parallel (each extractor has parameterless run() method)
            # Extractors that don't meet stride or have no interactions will return None
            results = self._run_extractors_in_parallel(extractors, identifier)

            # Process results
            if not results:
                logger.info(
                    "No results generated for %s identifier: %s",
                    self._get_service_name(),
                    identifier,
                )
                return

            self._process_results(results)

        except Exception as e:
            logger.warning(
                "Failed to run %s due to %s, exception type: %s",
                self._get_service_name(),
                str(e),
                type(e).__name__,
            )

    # ===============================
    # Batch with progress (shared by rerun + manual)
    # ===============================

    def _run_batch_with_progress(
        self,
        user_ids: list[str],
        request: TRequest,
        request_params: dict,
        state_manager: OperationStateManager,
    ) -> tuple[int, int]:
        """Run a batch of users with progress tracking.

        Shared logic for both run_rerun() and run_manual_regular().
        Initializes progress, processes each user, and finalizes.
        Checks for cancellation before each user.

        Args:
            user_ids: List of user IDs to process
            request: The original request object
            request_params: Parameters dict for progress state
            state_manager: OperationStateManager instance

        Returns:
            Tuple of (users_processed, total_generated)
        """
        total_users = len(user_ids)
        self._is_batch_mode = True

        # Initialize progress
        state_manager.initialize_progress(
            total_users=total_users,
            request_params=request_params,
        )

        try:
            # Process each user
            users_processed = 0
            for user_id in user_ids:
                # Check for cancellation before starting next user
                if state_manager.is_cancellation_requested():
                    logger.info(
                        "Cancellation requested for %s, stopping after %d/%d users",
                        self._get_base_service_name(),
                        users_processed,
                        total_users,
                    )
                    state_manager.mark_cancelled()
                    return users_processed, self._get_generated_count(request)

                state_manager.set_current_item(user_id)

                try:
                    run_request = self._create_run_request_for_item(user_id, request)
                    self.run(run_request)
                    users_processed += 1

                    state_manager.update_progress(
                        item_id=user_id,
                        count=0,  # Extractors collect their own data
                        success=True,
                        total_users=total_users,
                    )

                except Exception as e:
                    logger.error(
                        "Failed to process user %s for %s: %s",
                        user_id,
                        self._get_base_service_name(),
                        str(e),
                    )
                    state_manager.update_progress(
                        item_id=user_id,
                        count=0,
                        success=False,
                        total_users=total_users,
                        error=str(e),
                    )
                    continue

            # Get generated count and finalize
            total_generated = self._get_generated_count(request)
            state_manager.finalize_progress(users_processed, total_generated)

            return users_processed, total_generated
        finally:
            self._is_batch_mode = False

    # ===============================
    # Rerun methods (optional - override to enable rerun functionality)
    # ===============================

    def _get_rerun_user_ids(self, request: TRequest) -> list[str]:
        """Get user IDs to process during rerun.

        Override this method to enable rerun functionality for the service.
        Returns a list of user IDs that have interactions matching the request filters.
        Each extractor collects its own data using its configured window_size.

        Args:
            request: The rerun request object

        Returns:
            List of user IDs to process
        """
        raise NotImplementedError("Rerun not supported by this service")

    def _build_rerun_request_params(self, request: TRequest) -> dict:
        """Build request params dict for operation state tracking.

        Override this method to enable rerun functionality for the service.

        Args:
            request: The rerun request object

        Returns:
            Dictionary of request parameters for state tracking
        """
        raise NotImplementedError("Rerun not supported by this service")

    def _create_run_request_for_item(self, user_id: str, request: TRequest) -> TRequest:
        """Create the request object to pass to self.run() for a single user.

        Override this method to enable rerun functionality for the service.
        Each extractor collects its own data using its configured window_size.

        Args:
            user_id: The user ID to process
            request: The original rerun request object

        Returns:
            A request object suitable for self.run()
        """
        raise NotImplementedError("Rerun not supported by this service")

    def _create_rerun_response(self, success: bool, msg: str, count: int) -> Any:
        """Create the rerun response object.

        Override this method to enable rerun functionality for the service.

        Args:
            success: Whether the operation succeeded
            msg: Status message
            count: Number of items generated

        Returns:
            A response object (e.g., RerunProfileGenerationResponse)
        """
        raise NotImplementedError("Rerun not supported by this service")

    def _get_generated_count(self, request: TRequest) -> int:
        """Get the count of generated items (profiles or feedbacks) after rerun.

        Override this method to enable rerun functionality for the service.

        Args:
            request: The rerun request object (for filtering)

        Returns:
            Number of items generated during rerun
        """
        raise NotImplementedError("Rerun not supported by this service")

    def _pre_process_rerun(self, request: TRequest) -> None:
        """Hook called before processing rerun items.

        Override in subclasses to perform cleanup or preparation before rerun.
        Default implementation does nothing.

        Args:
            request: The rerun request object
        """

    def run_rerun(self, request: TRequest) -> Any:
        """Run the rerun workflow for the service.

        This template method orchestrates the rerun process:
        1. Check for existing in-progress operations
        2. Get user IDs to process
        3. Pre-process hook
        4. Run batch with progress tracking
        5. Return response

        Child classes must implement the hook methods to enable rerun functionality:
        - _get_rerun_user_ids()
        - _build_rerun_request_params()
        - _create_run_request_for_item()
        - _create_rerun_response()

        Args:
            request: The rerun request object

        Returns:
            A response object with success status, message, and count
        """
        state_manager = self._create_state_manager()

        try:
            # 1. Check for existing in-progress operation
            error = state_manager.check_in_progress()
            if error:
                return self._create_rerun_response(False, error, 0)

            # 2. Get user IDs to process
            user_ids = self._get_rerun_user_ids(request)
            if not user_ids:
                return self._create_rerun_response(
                    False, "No interactions found matching the specified filters", 0
                )

            # 3. Pre-process hook (e.g., delete existing pending items)
            self._pre_process_rerun(request)

            # 4. Run batch with progress tracking
            users_processed, total_generated = self._run_batch_with_progress(
                user_ids=user_ids,
                request=request,
                request_params=self._build_rerun_request_params(request),
                state_manager=state_manager,
            )

            msg = f"Completed for {users_processed} user(s)"
            return self._create_rerun_response(True, msg, total_generated)

        except Exception as e:
            state_manager.mark_progress_failed(str(e))
            return self._create_rerun_response(
                False,
                f"Failed to run {self._get_base_service_name()}: {str(e)}",
                0,
            )

    # ===============================
    # Upgrade/Downgrade methods (optional - override to enable)
    # ===============================

    def _has_items_with_status(
        self, status: Optional[Status], request: TRequest
    ) -> bool:
        """Check if items exist with given status and filters from request.

        Override this method to enable upgrade/downgrade functionality for the service.

        Args:
            status: The status to check for (None for CURRENT)
            request: The upgrade/downgrade request object with filters

        Returns:
            bool: True if any matching items exist
        """
        raise NotImplementedError("Upgrade/downgrade not supported by this service")

    def _delete_items_by_status(self, status: Status, request: TRequest) -> int:
        """Delete items with given status matching request filters.

        Override this method to enable upgrade/downgrade functionality for the service.

        Args:
            status: The status of items to delete
            request: The upgrade/downgrade request object with filters

        Returns:
            int: Number of items deleted
        """
        raise NotImplementedError("Upgrade/downgrade not supported by this service")

    def _update_items_status(
        self,
        old_status: Optional[Status],
        new_status: Optional[Status],
        request: TRequest,
        user_ids: Optional[list[str]] = None,
    ) -> int:
        """Update items from old_status to new_status with request filters.

        Override this method to enable upgrade/downgrade functionality for the service.

        Args:
            old_status: The current status to match (None for CURRENT)
            new_status: The new status to set (None for CURRENT)
            request: The upgrade/downgrade request object with filters
            user_ids: Optional pre-computed list of user IDs to filter by

        Returns:
            int: Number of items updated
        """
        raise NotImplementedError("Upgrade/downgrade not supported by this service")

    def _get_affected_user_ids_for_upgrade(
        self, request: TRequest
    ) -> Optional[list[str]]:
        """Get user IDs to filter by for upgrade operations.

        Override this method to support the only_affected_users flag.
        By default returns None (no filtering).

        Args:
            request: The upgrade request object

        Returns:
            Optional[list[str]]: List of user IDs to filter by, or None for no filtering
        """
        return None

    def _get_affected_user_ids_for_downgrade(
        self, request: TRequest
    ) -> Optional[list[str]]:
        """Get user IDs to filter by for downgrade operations.

        Override this method to support the only_affected_users flag.
        By default returns None (no filtering).

        Args:
            request: The downgrade request object

        Returns:
            Optional[list[str]]: List of user IDs to filter by, or None for no filtering
        """
        return None

    def _create_status_change_response(
        self,
        operation: StatusChangeOperation,
        success: bool,
        counts: dict,
        msg: str,
    ) -> Any:
        """Create upgrade or downgrade response object based on operation type.

        Override this method to enable upgrade/downgrade functionality for the service.

        Args:
            operation: The operation type (UPGRADE or DOWNGRADE)
            success: Whether the operation succeeded
            counts: Dictionary of counts (upgrade: deleted/archived/promoted, downgrade: demoted/restored)
            msg: Status message

        Returns:
            A response object (e.g., UpgradeProfilesResponse, DowngradeRawFeedbacksResponse)
        """
        raise NotImplementedError("Upgrade/downgrade not supported by this service")

    def run_upgrade(self, request: TRequest) -> Any:
        """Run the upgrade workflow for the service.

        This template method orchestrates the upgrade process:
        1. Validate that pending items exist
        2. Delete old archived items
        3. Archive current items (None → ARCHIVED)
        4. Promote pending items (PENDING → None/CURRENT)

        Child classes must implement the hook methods to enable upgrade functionality:
        - _has_items_with_status()
        - _delete_items_by_status()
        - _update_items_status()
        - _create_status_change_response()

        Args:
            request: The upgrade request object with optional filters

        Returns:
            A response object with success status, counts, and message
        """
        try:
            # 1. Validate pending items exist
            if not self._has_items_with_status(Status.PENDING, request):
                return self._create_status_change_response(
                    StatusChangeOperation.UPGRADE,
                    False,
                    {"deleted": 0, "archived": 0, "promoted": 0},
                    "No pending items found to upgrade",
                )

            # Get affected user IDs once (child class determines the logic)
            affected_user_ids = self._get_affected_user_ids_for_upgrade(request)

            # 2. Delete old archived items (skip if archive_current=False)
            deleted = 0
            archived = 0
            if getattr(request, "archive_current", True):
                deleted = self._delete_items_by_status(Status.ARCHIVED, request)

                # 3. Archive current items (None → ARCHIVED)
                archived = self._update_items_status(
                    None, Status.ARCHIVED, request, user_ids=affected_user_ids
                )

            # 4. Promote pending items (PENDING → None)
            promoted = self._update_items_status(
                Status.PENDING, None, request, user_ids=affected_user_ids
            )

            msg = f"Upgraded: {promoted} promoted, {archived} archived, {deleted} old archived deleted"
            return self._create_status_change_response(
                StatusChangeOperation.UPGRADE,
                True,
                {"deleted": deleted, "archived": archived, "promoted": promoted},
                msg,
            )

        except Exception as e:
            return self._create_status_change_response(
                StatusChangeOperation.UPGRADE,
                False,
                {"deleted": 0, "archived": 0, "promoted": 0},
                f"Failed to upgrade: {str(e)}",
            )

    def run_downgrade(self, request: TRequest) -> Any:
        """Run the downgrade workflow for the service.

        This template method orchestrates the downgrade process:
        1. Validate that archived items exist
        2. Demote current items (None → ARCHIVE_IN_PROGRESS)
        3. Restore archived items (ARCHIVED → None/CURRENT)
        4. Complete archiving (ARCHIVE_IN_PROGRESS → ARCHIVED)

        Child classes must implement the hook methods to enable downgrade functionality:
        - _has_items_with_status()
        - _update_items_status()
        - _create_status_change_response()

        Args:
            request: The downgrade request object with optional filters

        Returns:
            A response object with success status, counts, and message
        """
        try:
            # 1. Validate archived items exist
            if not self._has_items_with_status(Status.ARCHIVED, request):
                return self._create_status_change_response(
                    StatusChangeOperation.DOWNGRADE,
                    False,
                    {"demoted": 0, "restored": 0},
                    "No archived items found to restore",
                )

            # Get affected user IDs once (child class determines the logic)
            affected_user_ids = self._get_affected_user_ids_for_downgrade(request)

            # 2. Demote current (None → ARCHIVE_IN_PROGRESS)
            demoted = self._update_items_status(
                None, Status.ARCHIVE_IN_PROGRESS, request, user_ids=affected_user_ids
            )

            # 3. Restore archived (ARCHIVED → None)
            restored = self._update_items_status(
                Status.ARCHIVED, None, request, user_ids=affected_user_ids
            )

            # 4. Complete archiving (ARCHIVE_IN_PROGRESS → ARCHIVED)
            self._update_items_status(
                Status.ARCHIVE_IN_PROGRESS,
                Status.ARCHIVED,
                request,
                user_ids=affected_user_ids,
            )

            msg = f"Downgraded: {demoted} archived, {restored} restored"
            return self._create_status_change_response(
                StatusChangeOperation.DOWNGRADE,
                True,
                {"demoted": demoted, "restored": restored},
                msg,
            )

        except Exception as e:
            return self._create_status_change_response(
                StatusChangeOperation.DOWNGRADE,
                False,
                {"demoted": 0, "restored": 0},
                f"Failed to downgrade: {str(e)}",
            )
