from dataclasses import dataclass
import logging
from typing import Optional

from reflexio_commons.api_schema.internal_schema import RequestInteractionDataModel

from reflexio_commons.config_schema import AgentSuccessConfig
from reflexio.server.services.agent_success_evaluation.agent_success_evaluator import (
    AgentSuccessEvaluator,
)
from reflexio.server.services.agent_success_evaluation.agent_success_evaluation_utils import (
    AgentSuccessEvaluationRequest,
)
from reflexio.server.services.base_generation_service import BaseGenerationService

logger = logging.getLogger(__name__)


@dataclass
class AgentSuccessGenerationServiceConfig:
    """Runtime configuration for agent success evaluation service shared across all extractors.

    Attributes:
        request_id: The request ID
        agent_version: The agent version
        request_interaction_data_models: The interactions to evaluate
        source: Source of the interactions
    """

    request_id: str
    agent_version: str
    request_interaction_data_models: list[RequestInteractionDataModel]
    source: Optional[str] = None


class AgentSuccessEvaluationService(
    BaseGenerationService[
        AgentSuccessConfig,
        AgentSuccessEvaluator,
        AgentSuccessGenerationServiceConfig,
        AgentSuccessEvaluationRequest,
    ]
):
    """
    Service for evaluating agent success across multiple evaluation criteria.
    Runs multiple AgentSuccessEvaluator instances sequentially.
    """

    def _load_generation_service_config(
        self, request: AgentSuccessEvaluationRequest
    ) -> AgentSuccessGenerationServiceConfig:
        """
        Extract request parameters from AgentSuccessEvaluationRequest.

        Args:
            request: AgentSuccessEvaluationRequest containing evaluation parameters

        Returns:
            AgentSuccessGenerationServiceConfig object
        """
        return AgentSuccessGenerationServiceConfig(
            request_id=request.request_id,
            agent_version=request.agent_version,
            request_interaction_data_models=request.request_interaction_data_models,
            source=request.source,
        )

    def _load_extractor_configs(self) -> list[AgentSuccessConfig]:
        """
        Load agent success configs from configurator.

        Returns:
            list[AgentSuccessConfig]: List of agent success configuration objects from YAML
        """
        return self.configurator.get_config().agent_success_configs

    def _create_extractor(
        self,
        extractor_config: AgentSuccessConfig,
        service_config: AgentSuccessGenerationServiceConfig,
    ) -> AgentSuccessEvaluator:
        """
        Create an AgentSuccessEvaluator instance from configuration.

        Args:
            extractor_config: AgentSuccessConfig configuration object from YAML
            service_config: AgentSuccessGenerationServiceConfig containing runtime parameters

        Returns:
            AgentSuccessEvaluator instance
        """
        return AgentSuccessEvaluator(
            request_context=self.request_context,
            llm_client=self.client,
            extractor_config=extractor_config,
            service_config=service_config,
            agent_context=self.configurator.get_agent_context(),
        )

    def _process_results(self, results: list) -> None:
        """
        Process and save agent success evaluation results.

        Args:
            results: List of AgentSuccessEvaluationResult results from extractors
        """
        # Flatten results (each extractor returns list[AgentSuccessEvaluationResult])
        all_results = []
        for result in results:
            if isinstance(result, list):
                all_results.extend(result)

        # Deduplicate by request_id (keep first result for each request_id)
        # This handles the case where multiple extractors evaluate the same request
        seen_request_ids: set[str] = set()
        deduplicated_results = []
        for result in all_results:
            if result.request_id not in seen_request_ids:
                deduplicated_results.append(result)
                seen_request_ids.add(result.request_id)

        logger.info(
            "Successfully completed %d %s evaluations (deduplicated from %d) for request id: %s",
            len(deduplicated_results),
            self._get_service_name(),
            len(all_results),
            self.service_config.request_id,
        )

        # Save results
        if deduplicated_results:
            try:
                self.storage.save_agent_success_evaluation_results(deduplicated_results)
                logger.info(
                    "Saved %d agent success evaluation results for request id: %s",
                    len(deduplicated_results),
                    self.service_config.request_id,
                )
            except Exception as e:
                logger.error(
                    "Failed to save %s results for request id: %s due to %s, exception type: %s",
                    self._get_service_name(),
                    self.service_config.request_id,
                    str(e),
                    type(e).__name__,
                )

    def _get_service_name(self) -> str:
        """
        Get the name of the service for logging.

        Returns:
            Service name string
        """
        return "agent_success_evaluation"

    def _get_base_service_name(self) -> str:
        """
        Get the base service name for OperationStateManager keys.

        Returns:
            str: "agent_success_evaluation"
        """
        return "agent_success_evaluation"

    def _should_track_in_progress(self) -> bool:
        """
        Agent success evaluation does NOT track in-progress state.

        Agent success evaluation is tied to specific requests and doesn't have
        the sliding window duplication issue that profile/feedback have.

        Returns:
            bool: False - agent success evaluation does not track in-progress state
        """
        return False

    def _get_lock_scope_id(
        self, request: AgentSuccessEvaluationRequest
    ) -> Optional[str]:
        """
        Not used since _should_track_in_progress returns False.

        Args:
            request: The AgentSuccessEvaluationRequest

        Raises:
            NotImplementedError: This method is not used for this service
        """
        raise NotImplementedError(
            "AgentSuccessEvaluationService does not track in-progress state"
        )
