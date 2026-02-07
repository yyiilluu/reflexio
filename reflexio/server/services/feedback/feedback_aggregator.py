import logging
import os

import hdbscan
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_distances

# Threshold for switching between clustering algorithms
# Below this, use Agglomerative (works better with small datasets)
# Above this, use HDBSCAN (scales better, handles noise)
CLUSTERING_ALGORITHM_THRESHOLD = 50

from reflexio_commons.api_schema.service_schemas import (
    Feedback,
    FeedbackStatus,
    RawFeedback,
)
from reflexio.server.api_endpoints.request_context import RequestContext
from reflexio.server.services.operation_state_utils import OperationStateManager
from reflexio_commons.config_schema import (
    FeedbackAggregatorConfig,
)
from reflexio.server.llm.litellm_client import LiteLLMClient
from reflexio.server.services.feedback.feedback_service_constants import (
    FeedbackServiceConstants,
)
from reflexio.server.services.feedback.feedback_service_utils import (
    FeedbackAggregatorRequest,
    FeedbackAggregationOutput,
    StructuredFeedbackContent,
)


logger = logging.getLogger(__name__)


class FeedbackAggregator:
    def __init__(
        self,
        llm_client: LiteLLMClient,
        request_context: RequestContext,
        agent_version: str,
    ) -> None:
        self.client = llm_client
        self.storage = request_context.storage
        self.configurator = request_context.configurator
        self.request_context = request_context
        self.agent_version = agent_version

    # ===============================
    # private methods - operation state
    # ===============================

    def _create_state_manager(self) -> OperationStateManager:
        """
        Create an OperationStateManager for the feedback aggregator.

        Returns:
            OperationStateManager configured for feedback_aggregator
        """
        return OperationStateManager(
            self.storage,
            self.request_context.org_id,
            "feedback_aggregator",
        )

    def _get_new_raw_feedbacks_count(
        self, feedback_name: str, rerun: bool = False
    ) -> int:
        """
        Count how many new raw feedbacks exist since last aggregation.
        Uses efficient SQL COUNT query instead of fetching all feedbacks.

        Args:
            feedback_name: Name of the feedback type
            rerun: If True, count all raw feedbacks (use last_processed_id=0)

        Returns:
            int: Count of new raw feedbacks
        """
        # For rerun, use 0 to process all raw feedbacks
        if rerun:
            last_processed_id = 0
        else:
            mgr = self._create_state_manager()
            bookmark = mgr.get_aggregator_bookmark(
                name=feedback_name, version=self.agent_version
            )
            last_processed_id = bookmark if bookmark is not None else 0

        # Count feedbacks with ID greater than last processed using efficient count query
        # Only count current raw feedbacks (status=None), not archived or pending ones
        new_count = self.storage.count_raw_feedbacks(
            feedback_name=feedback_name,
            min_raw_feedback_id=last_processed_id,
            agent_version=self.agent_version,
            status_filter=[None],
        )

        logger.info(
            "Found %d new raw feedbacks for '%s' (last processed ID: %d)",
            new_count,
            feedback_name,
            last_processed_id,
        )

        return new_count

    def _should_run_aggregation(
        self,
        feedback_name: str,
        feedback_aggregator_config: FeedbackAggregatorConfig,
        rerun: bool = False,
    ) -> bool:
        """
        Check if aggregation should run based on new feedbacks count.

        Args:
            feedback_name: Name of the feedback type
            feedback_aggregator_config: Configuration for feedback aggregator
            rerun: If True, count all raw feedbacks to determine if aggregation is needed

        Returns:
            bool: True if aggregation should run, False otherwise
        """
        # Get refresh_count, default to 2 if not set or 0
        refresh_count = feedback_aggregator_config.refresh_count
        if refresh_count <= 0:
            refresh_count = 2

        # Check new feedbacks count (uses all feedbacks if rerun=True)
        new_count = self._get_new_raw_feedbacks_count(feedback_name, rerun=rerun)

        return new_count >= refresh_count

    def _update_operation_state(
        self, feedback_name: str, raw_feedbacks: list[RawFeedback]
    ) -> None:
        """
        Update operation state with the highest raw_feedback_id processed.

        Args:
            feedback_name: Name of the feedback type
            raw_feedbacks: List of raw feedbacks that were processed
        """
        if not raw_feedbacks:
            return

        # Find max raw_feedback_id
        max_id = max(feedback.raw_feedback_id for feedback in raw_feedbacks)

        mgr = self._create_state_manager()
        mgr.update_aggregator_bookmark(
            name=feedback_name,
            version=self.agent_version,
            last_processed_id=max_id,
        )

    def _format_structured_cluster_input(
        self, cluster_feedbacks: list[RawFeedback]
    ) -> str:
        """
        Format a cluster of feedbacks for structured aggregation prompt.

        Collects all do_action, do_not_action, and when_condition values
        from the cluster. Since clustering may not be perfect, all when_conditions
        are passed to the LLM to generate a consolidated condition.

        Args:
            cluster_feedbacks: List of raw feedbacks in this cluster

        Returns:
            str: Formatted input for the aggregation prompt
        """
        # Collect all values (including duplicates to show frequency)
        do_actions = []
        do_not_actions = []
        when_conditions = []

        for fb in cluster_feedbacks:
            if fb.do_action:
                do_actions.append(fb.do_action)
            if fb.do_not_action:
                do_not_actions.append(fb.do_not_action)
            if fb.when_condition:
                when_conditions.append(fb.when_condition)

        # Format the output - pass all when_conditions for LLM to consolidate
        lines = []

        # List all when_conditions for LLM to generate a consolidated one
        if when_conditions:
            lines.append("WHEN conditions (to be consolidated):")
            for condition in when_conditions:
                lines.append(f"- {condition}")
        else:
            lines.append("WHEN conditions: (none specified)")

        if do_actions:
            lines.append("DO actions:")
            for action in do_actions:
                lines.append(f"- {action}")

        if do_not_actions:
            lines.append("DON'T actions:")
            for action in do_not_actions:
                lines.append(f"- {action}")

        # Collect blocking issues from cluster feedbacks
        blocking_issues = []
        for fb in cluster_feedbacks:
            if fb.blocking_issue:
                blocking_issues.append(
                    f"[{fb.blocking_issue.kind.value}] {fb.blocking_issue.details}"
                )
        if blocking_issues:
            lines.append("BLOCKED BY issues:")
            for issue in blocking_issues:
                lines.append(f"- {issue}")

        return "\n".join(lines)

    # ===============================
    # public methods
    # ===============================

    def run(self, feedback_aggregator_request: FeedbackAggregatorRequest) -> None:
        # get feedback aggregator config
        feedback_aggregator_config = self._get_feedback_aggregator_config(
            feedback_aggregator_request.feedback_name
        )
        if (
            not feedback_aggregator_config
            or feedback_aggregator_config.min_feedback_threshold < 2
        ):
            logger.info(
                "No feedback aggregator config found or min feedback threshold is less than 2, skipping feedback aggregation, config: %s",
                feedback_aggregator_config,
            )
            return

        # Check if we should run aggregation based on new feedbacks count
        # For rerun, use all raw feedbacks (last_processed_id=0) to determine if aggregation is needed
        if not self._should_run_aggregation(
            feedback_aggregator_request.feedback_name,
            feedback_aggregator_config,
            rerun=feedback_aggregator_request.rerun,
        ):
            new_count = self._get_new_raw_feedbacks_count(
                feedback_aggregator_request.feedback_name,
                rerun=feedback_aggregator_request.rerun,
            )
            refresh_count = (
                feedback_aggregator_config.refresh_count
                if feedback_aggregator_config.refresh_count > 0
                else 2
            )
            logger.info(
                "Skipping aggregation for '%s' - only %d new feedbacks (need %d)",
                feedback_aggregator_request.feedback_name,
                new_count,
                refresh_count,
            )
            return

        logger.info(
            f"Running aggregation for '{feedback_aggregator_request.feedback_name}'"
        )

        # Get existing APPROVED and PENDING feedbacks before archiving (to pass to LLM for deduplication)
        existing_feedbacks = self.storage.get_feedbacks(
            feedback_name=feedback_aggregator_request.feedback_name,
            status_filter=[None],  # Current feedbacks only
            feedback_status_filter=[FeedbackStatus.APPROVED, FeedbackStatus.PENDING],
        )
        logger.info(
            f"Found {len(existing_feedbacks)} existing feedbacks (approved + pending) to preserve"
        )

        # Archive existing non-APPROVED feedbacks (APPROVED feedbacks are untouched)
        self.storage.archive_feedbacks_by_feedback_name(
            feedback_aggregator_request.feedback_name, agent_version=self.agent_version
        )

        try:
            # get all raw feedbacks
            raw_feedbacks = self.storage.get_raw_feedbacks(
                feedback_name=feedback_aggregator_request.feedback_name,
                agent_version=self.agent_version,
            )

            # generate clusters from raw feedbacks
            clusters = self.get_clusters(raw_feedbacks, feedback_aggregator_config)
            # Generate new feedbacks, passing existing feedbacks for deduplication
            feedbacks = self._generate_feedback_from_clusters(
                clusters, existing_feedbacks
            )

            # save feedbacks
            self.storage.save_feedbacks(feedbacks)

            # Update operation state with the highest raw_feedback_id processed
            self._update_operation_state(
                feedback_aggregator_request.feedback_name, raw_feedbacks
            )

            # Delete archived feedbacks after successful aggregation
            self.storage.delete_archived_feedbacks_by_feedback_name(
                feedback_aggregator_request.feedback_name,
                agent_version=self.agent_version,
            )

        except Exception as e:
            # Restore archived feedbacks if any error occurs during aggregation
            logger.error(
                "Error during feedback aggregation for '%s': %s. Restoring archived feedbacks.",
                feedback_aggregator_request.feedback_name,
                str(e),
            )
            self.storage.restore_archived_feedbacks_by_feedback_name(
                feedback_aggregator_request.feedback_name,
                agent_version=self.agent_version,
            )
            # Re-raise the exception after restoring
            raise

    def get_clusters(
        self,
        raw_feedbacks: list[RawFeedback],
        feedback_aggregator_config: FeedbackAggregatorConfig,
    ) -> dict[int, list[RawFeedback]]:
        """
        Cluster raw feedbacks based on their embeddings (when_condition indexed).

        Args:
            raw_feedbacks: Contains raw feedbacks to cluster
            feedback_aggregator_config: Feedback aggregator config

        Returns:
            dict[int, list[RawFeedback]]: Dictionary mapping cluster IDs to lists of raw feedbacks
        """
        if not feedback_aggregator_config:
            logger.info(
                "No feedback aggregator config found, skipping feedback aggregation"
            )
            return {}

        min_cluster_size = feedback_aggregator_config.min_feedback_threshold

        if not raw_feedbacks:
            logger.info("No raw feedbacks to cluster")
            return {}

        # Mock mode: cluster by when_condition
        if os.getenv("MOCK_LLM_RESPONSE", "").lower() == "true":
            logger.info("Mock mode: clustering by when_condition")
            return self._cluster_by_when_condition_mock(raw_feedbacks, min_cluster_size)

        # Extract embeddings from raw feedbacks
        embeddings = np.array([feedback.embedding for feedback in raw_feedbacks])

        if len(embeddings) < min_cluster_size:
            logger.info(
                "Not enough feedbacks to cluster (got %d, need %d)",
                len(embeddings),
                min_cluster_size,
            )
            return {}

        # Compute cosine distance matrix for better text embedding clustering
        distance_matrix = cosine_distances(embeddings)

        # Choose algorithm based on dataset size
        if len(embeddings) < CLUSTERING_ALGORITHM_THRESHOLD:
            cluster_labels = self._cluster_with_agglomerative(
                distance_matrix, min_cluster_size
            )
        else:
            cluster_labels = self._cluster_with_hdbscan(
                distance_matrix, min_cluster_size
            )

        # Group feedbacks by cluster
        clusters: dict[int, list[RawFeedback]] = {}
        for idx, label in enumerate(cluster_labels):
            if label == -1:  # Skip noise points from HDBSCAN
                continue
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(raw_feedbacks[idx])

        # Filter out clusters smaller than min_cluster_size
        clusters = {
            label: feedbacks
            for label, feedbacks in clusters.items()
            if len(feedbacks) >= min_cluster_size
        }

        logger.info(
            "Found %d clusters from %d feedbacks", len(clusters), len(raw_feedbacks)
        )
        for cluster_id, cluster_feedbacks in clusters.items():
            logger.info("Cluster %d: %d feedbacks", cluster_id, len(cluster_feedbacks))

        return clusters

    def _cluster_by_when_condition_mock(
        self, raw_feedbacks: list[RawFeedback], min_cluster_size: int
    ) -> dict[int, list[RawFeedback]]:
        """
        Simple mock clustering by exact when_condition match.

        Args:
            raw_feedbacks: List of raw feedbacks with when_condition
            min_cluster_size: Minimum number of feedbacks per cluster

        Returns:
            dict[int, list[RawFeedback]]: Clusters grouped by when_condition
        """
        # Group by when_condition
        condition_groups: dict[str, list[RawFeedback]] = {}
        for fb in raw_feedbacks:
            condition = fb.when_condition or ""
            if condition not in condition_groups:
                condition_groups[condition] = []
            condition_groups[condition].append(fb)

        # Convert to cluster format, filtering by min_cluster_size
        clusters: dict[int, list[RawFeedback]] = {}
        cluster_id = 0
        for feedbacks in condition_groups.values():
            if len(feedbacks) >= min_cluster_size:
                clusters[cluster_id] = feedbacks
                cluster_id += 1

        logger.info(
            "Mock mode: created %d when_condition clusters from %d feedbacks",
            len(clusters),
            len(raw_feedbacks),
        )
        return clusters

    def _cluster_with_agglomerative(
        self, distance_matrix: np.ndarray, min_cluster_size: int
    ) -> np.ndarray:
        """
        Cluster using Agglomerative Clustering - best for small datasets.

        Args:
            distance_matrix: Precomputed cosine distance matrix
            min_cluster_size: Minimum cluster size (used for logging only,
                              filtering happens in get_clusters)

        Returns:
            np.ndarray: Cluster labels for each point
        """
        logger.info(
            "Using Agglomerative Clustering for %d feedbacks (< %d threshold)",
            len(distance_matrix),
            CLUSTERING_ALGORITHM_THRESHOLD,
        )

        clusterer = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=0.3,  # ~70% cosine similarity
            metric="precomputed",
            linkage="average",
        )

        return clusterer.fit_predict(distance_matrix)

    def _cluster_with_hdbscan(
        self, distance_matrix: np.ndarray, min_cluster_size: int
    ) -> np.ndarray:
        """
        Cluster using HDBSCAN - best for large datasets with potential noise.

        Args:
            distance_matrix: Precomputed cosine distance matrix
            min_cluster_size: Minimum number of points to form a cluster

        Returns:
            np.ndarray: Cluster labels for each point (-1 indicates noise)
        """
        logger.info(
            "Using HDBSCAN for %d feedbacks (>= %d threshold)",
            len(distance_matrix),
            CLUSTERING_ALGORITHM_THRESHOLD,
        )

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=1,
            metric="precomputed",
            cluster_selection_epsilon=0.3,  # ~70% cosine similarity
        )

        return clusterer.fit_predict(distance_matrix)

    def _generate_feedback_from_clusters(
        self,
        clusters: dict[int, list[RawFeedback]],
        existing_approved_feedbacks: list[Feedback],
    ) -> list[Feedback]:
        """
        Generate feedback from clusters, considering existing approved feedbacks.

        Args:
            clusters: Dictionary mapping cluster IDs to lists of raw feedbacks
            existing_approved_feedbacks: List of existing approved feedbacks to avoid duplication

        Returns:
            list[Feedback]: List of newly generated feedbacks (excludes duplicates)
        """
        # Format existing approved feedbacks for the prompt
        approved_feedbacks_str = (
            "\n".join(
                [f"- {fb.feedback_content}" for fb in existing_approved_feedbacks]
            )
            if existing_approved_feedbacks
            else "None"
        )

        feedbacks = []
        for _, cluster_feedbacks in clusters.items():
            feedback = self._generate_feedback_from_cluster(
                cluster_feedbacks, approved_feedbacks_str
            )
            if feedback is not None:
                feedbacks.append(feedback)
        return feedbacks

    def _generate_feedback_from_cluster(
        self,
        cluster_feedbacks: list[RawFeedback],
        existing_approved_feedbacks_str: str,
    ) -> Feedback | None:
        """
        Generate feedback from a cluster using structured JSON output.

        Args:
            cluster_feedbacks: List of raw feedbacks in this cluster
            existing_approved_feedbacks_str: Formatted string of existing approved feedbacks

        Returns:
            Feedback | None: Generated feedback, or None if no new feedback needed
        """
        if not cluster_feedbacks:
            return None

        if os.getenv("MOCK_LLM_RESPONSE", "").lower() == "true":
            # Extract structured fields directly from cluster
            do_actions = [fb.do_action for fb in cluster_feedbacks if fb.do_action]
            do_not_actions = [
                fb.do_not_action for fb in cluster_feedbacks if fb.do_not_action
            ]
            when_conditions = [
                fb.when_condition for fb in cluster_feedbacks if fb.when_condition
            ]

            do_action = do_actions[0] if do_actions else None
            do_not_action = do_not_actions[0] if do_not_actions else None
            when_condition = when_conditions[0] if when_conditions else "in general"

            # At least one of do_action or do_not_action is required for valid feedback
            if do_action is None and do_not_action is None:
                # Fall back to using feedback_content from first feedback if available
                first_content = cluster_feedbacks[0].feedback_content
                if first_content:
                    do_action = first_content
                else:
                    logger.info("No valid structured fields in cluster, skipping")
                    return None

            # Create structured content and format to string
            structured = StructuredFeedbackContent(
                do_action=do_action,
                do_not_action=do_not_action,
                when_condition=when_condition,
            )
            feedback_content = self._format_structured_feedback_content(structured)

            return Feedback(
                feedback_name=cluster_feedbacks[0].feedback_name,
                agent_version=cluster_feedbacks[0].agent_version,
                feedback_content=feedback_content,
                do_action=do_action,
                do_not_action=do_not_action,
                when_condition=when_condition,
                feedback_status=FeedbackStatus.PENDING,
                feedback_metadata="mock_generated",
            )

        # Format raw feedbacks for prompt using structured format
        raw_feedbacks_str = self._format_structured_cluster_input(cluster_feedbacks)

        messages = [
            {
                "role": "user",
                "content": self.request_context.prompt_manager.render_prompt(
                    FeedbackServiceConstants.FEEDBACK_GENERATION_PROMPT_ID,
                    {
                        "raw_feedbacks": raw_feedbacks_str,
                        "existing_approved_feedbacks": existing_approved_feedbacks_str,
                    },
                ),
            }
        ]

        try:
            response = self.client.generate_chat_response(
                messages=messages,
                model=self.client.config.model,
                response_format=FeedbackAggregationOutput,
                parse_structured_output=True,
            )
            logger.info("Aggregation structured response: %s", response)

            return self._process_aggregation_response(response, cluster_feedbacks)
        except Exception as exc:
            logger.error(
                "Feedback aggregation failed due to %s, returning None.",
                str(exc),
            )
            return None

    def _process_aggregation_response(
        self, response: FeedbackAggregationOutput, cluster_feedbacks: list[RawFeedback]
    ) -> Feedback | None:
        """
        Process structured response from LLM into Feedback.

        Args:
            response: Parsed FeedbackAggregationOutput from LLM
            cluster_feedbacks: Original cluster feedbacks for metadata

        Returns:
            Feedback or None if no feedback should be generated
        """
        if not response:
            return None

        structured = response.feedback
        if structured is None:
            logger.info("LLM returned null feedback (duplicate of existing)")
            return None

        # Format to canonical string
        feedback_content = self._format_structured_feedback_content(structured)

        return Feedback(
            feedback_name=cluster_feedbacks[0].feedback_name,
            agent_version=cluster_feedbacks[0].agent_version,
            feedback_content=feedback_content,
            do_action=structured.do_action,
            do_not_action=structured.do_not_action,
            when_condition=structured.when_condition,
            blocking_issue=structured.blocking_issue,
            feedback_status=FeedbackStatus.PENDING,
            feedback_metadata="",
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
            structured: The structured feedback content

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

        # Add Blocked by if present
        if structured.blocking_issue:
            lines.append(
                f"Blocked by: [{structured.blocking_issue.kind.value}] {structured.blocking_issue.details}"
            )

        return "\n".join(lines)

    def _get_feedback_aggregator_config(
        self, feedback_name: str
    ) -> FeedbackAggregatorConfig | None:
        agent_feedback_configs = self.configurator.get_config().agent_feedback_configs
        if not agent_feedback_configs:
            return None
        for agent_feedback_config in agent_feedback_configs:
            if agent_feedback_config.feedback_name == feedback_name:
                return agent_feedback_config.feedback_aggregator_config
        return None
