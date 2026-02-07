import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from reflexio_commons.api_schema.service_schemas import (
    Interaction,
    PublishUserInteractionRequest,
    Request,
)
from reflexio_commons.api_schema.internal_schema import RequestInteractionDataModel
from reflexio.server.api_endpoints.request_context import RequestContext
from reflexio.server.llm.litellm_client import LiteLLMClient
from reflexio.server.services.feedback.feedback_generation_service import (
    FeedbackGenerationService,
)
from reflexio.server.services.feedback.feedback_service_utils import (
    FeedbackGenerationRequest,
)
from reflexio.server.services.profile.profile_generation_service import (
    ProfileGenerationService,
)
from reflexio.server.services.profile.profile_generation_service_utils import (
    ProfileGenerationRequest,
)
from reflexio.server.services.agent_success_evaluation.agent_success_evaluation_service import (
    AgentSuccessEvaluationService,
)
from reflexio.server.services.agent_success_evaluation.agent_success_evaluation_utils import (
    AgentSuccessEvaluationRequest,
)


from reflexio.server.services.operation_state_utils import OperationStateManager

logger = logging.getLogger(__name__)
# Stale lock timeout - if cleanup started > 10 min ago and still "in_progress", assume it crashed
CLEANUP_STALE_LOCK_SECONDS = 600


class GenerationService:
    """
    Main service for orchestrating profile, feedback, and agent success evaluation generation.

    This service coordinates multiple generation services (profile, feedback, agent success)
    and manages the overall interaction processing workflow.
    """

    def __init__(
        self,
        llm_client: LiteLLMClient,
        request_context: RequestContext,
    ) -> None:
        """
        Initialize the generation service.

        Args:
            llm_client: Pre-configured LLM client for making API calls.
            request_context: Request context with storage and configurator.
        """
        self.client = llm_client
        self.storage = request_context.storage
        self.org_id = request_context.org_id
        self.configurator = request_context.configurator
        self.request_context = request_context

    # ===============================
    # public methods
    # ===============================

    def run(
        self, publish_user_interaction_request: PublishUserInteractionRequest
    ) -> None:
        """
        Process a user interaction request by storing interactions and triggering generation services.

        Each generation service (profile, feedback, agent_success) handles its own:
        - Data collection based on extractor-specific configs
        - Stride checking based on extractor-specific settings
        - Operation state tracking per extractor

        Args:
            publish_user_interaction_request: The incoming user interaction request
        """
        if not publish_user_interaction_request:
            logger.error("Received None publish_user_interaction_request")
            return

        user_id = publish_user_interaction_request.user_id
        if not user_id:
            logger.error("Received None user_id in publish_user_interaction_request")
            return

        # Check if cleanup is needed before adding new interactions
        self._cleanup_old_interactions_if_needed()

        try:
            # Always generate a new UUID for request_id
            request_id = str(uuid.uuid4())

            new_interactions: list[
                Interaction
            ] = GenerationService.get_interaction_from_publish_user_interaction_request(
                publish_user_interaction_request, request_id
            )

            if not new_interactions:
                logger.info(
                    "No interactions from the publish user interaction request: %s, get all interactions for the user: %s",
                    request_id,
                    user_id,
                )
                return

            # Store Request
            new_request = Request(
                request_id=request_id,
                user_id=user_id,
                source=publish_user_interaction_request.source,
                agent_version=publish_user_interaction_request.agent_version,
                request_group=publish_user_interaction_request.request_group or None,
            )
            self.storage.add_request(new_request)

            # Add interactions to storage (bulk insert with batched embedding generation)
            self.storage.add_user_interactions_bulk(
                user_id=user_id, interactions=new_interactions
            )

            # Extract source (empty string treated as None)
            source = publish_user_interaction_request.source or None

            # Create generation services and requests
            # Each service writes to separate storage tables and has no dependencies on others
            profile_generation_service = ProfileGenerationService(
                llm_client=self.client, request_context=self.request_context
            )
            profile_generation_request = ProfileGenerationRequest(
                user_id=user_id,
                request_id=request_id,
                source=source,
            )

            feedback_generation_service = FeedbackGenerationService(
                llm_client=self.client, request_context=self.request_context
            )
            feedback_generation_request = FeedbackGenerationRequest(
                request_id=request_id,
                agent_version=publish_user_interaction_request.agent_version,
                user_id=user_id,
                source=source,
            )

            request_interaction_data_model = RequestInteractionDataModel(
                request_group=new_request.request_group or "",
                request=new_request,
                interactions=new_interactions,
            )
            agent_success_evaluation_service = AgentSuccessEvaluationService(
                llm_client=self.client, request_context=self.request_context
            )
            agent_success_evaluation_request = AgentSuccessEvaluationRequest(
                request_id=request_id,
                agent_version=publish_user_interaction_request.agent_version,
                source=source,
                request_interaction_data_models=[request_interaction_data_model],
            )

            # Run all generation services in parallel
            # Each service creates its own internal ThreadPoolExecutor for extractors
            # This is safe because we create separate, independent pool instances
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(
                        profile_generation_service.run, profile_generation_request
                    ),
                    executor.submit(
                        feedback_generation_service.run, feedback_generation_request
                    ),
                    executor.submit(
                        agent_success_evaluation_service.run,
                        agent_success_evaluation_request,
                    ),
                ]

                # Collect results and handle any exceptions
                # Each service failure is logged but doesn't block others
                for future in futures:
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(
                            "Generation service failed for request %s: %s, exception type: %s",
                            request_id,
                            str(e),
                            type(e).__name__,
                        )

        except Exception as e:
            # log exception
            logger.error(
                "Failed to refresh user profile for user id: %s due to %s, exception type: %s",
                user_id,
                e,
                type(e).__name__,
            )
            raise e

    # ===============================
    # private methods
    # ===============================

    def _cleanup_old_interactions_if_needed(self) -> None:
        """
        Check total interaction count and cleanup oldest interactions if threshold exceeded.
        Uses OperationStateManager simple lock to prevent race conditions.
        """
        from reflexio.server import (
            INTERACTION_CLEANUP_THRESHOLD,
            INTERACTION_CLEANUP_DELETE_COUNT,
        )

        if INTERACTION_CLEANUP_THRESHOLD <= 0:
            return  # Cleanup disabled

        try:
            total_count = self.storage.count_all_interactions()
            if total_count < INTERACTION_CLEANUP_THRESHOLD:
                return  # No cleanup needed

            mgr = OperationStateManager(
                self.storage, self.org_id, "interaction_cleanup"
            )
            if not mgr.acquire_simple_lock(stale_seconds=CLEANUP_STALE_LOCK_SECONDS):
                return

            try:
                # Perform cleanup
                deleted = self.storage.delete_oldest_interactions(
                    INTERACTION_CLEANUP_DELETE_COUNT
                )
                logger.info(
                    "Cleaned up %d oldest interactions (total was %d, threshold %d)",
                    deleted,
                    total_count,
                    INTERACTION_CLEANUP_THRESHOLD,
                )
            finally:
                mgr.release_simple_lock()

        except Exception as e:
            logger.error("Failed to cleanup old interactions: %s", e)
            # Don't raise - cleanup failure shouldn't block normal operation

    # ===============================
    # static methods
    # ===============================

    @staticmethod
    def get_interaction_from_publish_user_interaction_request(
        publish_user_interaction_request: PublishUserInteractionRequest,
        request_id: str,
    ) -> list[Interaction]:
        """get interaction from publish user interaction request

        Args:
            publish_user_interaction_request (PublishUserInteractionRequest): The publish user interaction request
            request_id (str): The request ID generated by the service

        Returns:
            list[Interaction]: List of interactions created from the request
        """
        interaction_data_list = publish_user_interaction_request.interaction_data_list

        user_id = publish_user_interaction_request.user_id
        # Always use server-side UTC timestamp to ensure consistency
        server_timestamp = int(datetime.now(timezone.utc).timestamp())
        return [
            Interaction(
                # interaction_id is auto-generated by DB
                user_id=user_id,
                request_id=request_id,
                created_at=server_timestamp,  # Use server UTC timestamp
                content=interaction_data.content,
                role=interaction_data.role,
                user_action=interaction_data.user_action,
                user_action_description=interaction_data.user_action_description,
                interacted_image_url=interaction_data.interacted_image_url,
                image_encoding=interaction_data.image_encoding,
                shadow_content=interaction_data.shadow_content,
                tool_used=interaction_data.tool_used,
            )
            for interaction_data in interaction_data_list
        ]
