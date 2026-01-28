"""
Utility functions for filtering extractor configurations.
"""

import logging
from typing import Optional, TypeVar

logger = logging.getLogger(__name__)

TExtractorConfig = TypeVar("TExtractorConfig")


def filter_extractor_configs(
    extractor_configs: list[TExtractorConfig],
    source: Optional[str] = None,
    allow_manual_trigger: bool = False,
    extractor_names: Optional[list[str]] = None,
) -> list[TExtractorConfig]:
    """
    Filter extractor configs based on source, manual_trigger, and extractor names.

    This is a standalone utility function that can be used by both BaseGenerationService
    and GenerationService to filter extractor configurations consistently.

    Args:
        extractor_configs: List of extractor configuration objects (e.g., ProfileExtractorConfig,
            AgentFeedbackConfig, AgentSuccessConfig)
        source: Request source for filtering by request_sources_enabled. If None, source
            filtering is skipped.
        allow_manual_trigger: Whether to allow extractors with manual_trigger=True.
            If False, extractors with manual_trigger=True will be skipped.
        extractor_names: Optional list of extractor names to filter by. If provided,
            only extractors with names in this list will be included.

    Returns:
        Filtered list of extractor configs that should run for the given parameters
    """
    filtered_configs = []

    for config in extractor_configs:
        # Check if config has request_sources_enabled attribute
        if hasattr(config, "request_sources_enabled"):
            sources_enabled = config.request_sources_enabled
            # Skip if source filtering applies and source is not in enabled list
            if sources_enabled and source and source not in sources_enabled:
                extractor_name = getattr(
                    config,
                    "extractor_name",
                    getattr(
                        config,
                        "feedback_name",
                        getattr(config, "evaluation_name", "unknown"),
                    ),
                )
                logger.debug(
                    "Skipping extractor '%s' - source '%s' not in enabled sources %s",
                    extractor_name,
                    source,
                    sources_enabled,
                )
                continue

        # Check manual_trigger: skip if manual_trigger=True and allow_manual_trigger=False
        manual_trigger = getattr(config, "manual_trigger", False)
        if manual_trigger and not allow_manual_trigger:
            extractor_name = getattr(
                config,
                "extractor_name",
                getattr(
                    config,
                    "feedback_name",
                    getattr(config, "evaluation_name", "unknown"),
                ),
            )
            logger.debug(
                "Skipping extractor '%s' - manual_trigger=True and allow_manual_trigger=False",
                extractor_name,
            )
            continue

        # Filter by extractor_names if specified
        if extractor_names:
            extractor_name = getattr(
                config,
                "extractor_name",
                getattr(
                    config, "feedback_name", getattr(config, "evaluation_name", None)
                ),
            )
            if extractor_name and extractor_name not in extractor_names:
                logger.debug(
                    "Skipping extractor '%s' - not in specified extractor_names %s",
                    extractor_name,
                    extractor_names,
                )
                continue

        filtered_configs.append(config)

    return filtered_configs
