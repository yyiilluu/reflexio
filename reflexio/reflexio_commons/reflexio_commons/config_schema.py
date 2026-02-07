from enum import IntEnum, Enum
from pydantic import BaseModel
from typing import Optional


# Embedding vector dimensions. Changing this requires a DB migration and re-embedding,
# so it is intentionally a constant rather than a configurable setting.
EMBEDDING_DIMENSIONS = 512


class SearchMode(str, Enum):
    """Search mode for hybrid search functionality.

    Controls how search queries are processed:
    - VECTOR: Pure vector similarity search using embeddings
    - FTS: Pure full-text search using PostgreSQL tsvector
    - HYBRID: Combined search using Reciprocal Rank Fusion (RRF)
    """

    VECTOR = "vector"
    FTS = "fts"
    HYBRID = "hybrid"


class StorageConfigTest(IntEnum):
    UNKNOWN = 0
    INCOMPLETE = 1
    FAILED = 2
    SUCCEEDED = 3


class StorageConfigLocal(BaseModel):
    dir_path: str


class StorageConfigSupabase(BaseModel):
    url: str
    key: str
    db_url: str


StorageConfig = StorageConfigLocal | StorageConfigSupabase | None


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI specific configuration."""

    api_key: str
    endpoint: str  # e.g., "https://your-resource.openai.azure.com/"
    api_version: str = "2024-02-15-preview"
    deployment_name: Optional[str] = None  # Optional, can be specified per request


class OpenAIConfig(BaseModel):
    """OpenAI API configuration (direct or Azure)."""

    api_key: Optional[str] = None  # Direct OpenAI API key
    azure_config: Optional[AzureOpenAIConfig] = None  # Azure OpenAI configuration


class AnthropicConfig(BaseModel):
    """Anthropic API configuration."""

    api_key: str


class OpenRouterConfig(BaseModel):
    """OpenRouter API configuration."""

    api_key: str


class APIKeyConfig(BaseModel):
    """
    API key configuration for LLM providers.

    Supports OpenAI (direct and Azure), Anthropic, and OpenRouter API keys.
    These keys are used by the LiteLLM client for multi-provider support.
    """

    openai: Optional[OpenAIConfig] = None
    anthropic: Optional[AnthropicConfig] = None
    openrouter: Optional[OpenRouterConfig] = None


class ProfileExtractorConfig(BaseModel):
    extractor_name: str
    profile_content_definition_prompt: str
    context_prompt: Optional[str] = None
    metadata_definition_prompt: Optional[str] = None
    should_extract_profile_prompt_override: Optional[str] = None
    request_sources_enabled: Optional[
        list[str]
    ] = None  # default enabled for all sources, if set, only extract profiles from the enabled request sources
    manual_trigger: bool = False  # require manual triggering (rerun) to run extraction and skip auto extraction if set to True
    extraction_window_size_override: Optional[
        int
    ] = None  # override global extraction_window_size for this extractor
    extraction_window_stride_override: Optional[
        int
    ] = None  # override global extraction_window_stride for this extractor


class FeedbackAggregatorConfig(BaseModel):
    min_feedback_threshold: int = 2
    refresh_count: int = 2


class AgentFeedbackConfig(BaseModel):
    feedback_name: str
    # define what success looks like
    feedback_definition_prompt: str
    metadata_definition_prompt: Optional[str] = None
    feedback_aggregator_config: Optional[FeedbackAggregatorConfig] = None
    request_sources_enabled: Optional[
        list[str]
    ] = None  # default enabled for all sources, if set, only extract feedbacks from the enabled request sources
    extraction_window_size_override: Optional[
        int
    ] = None  # override global extraction_window_size for this extractor
    extraction_window_stride_override: Optional[
        int
    ] = None  # override global extraction_window_stride for this extractor


class ToolUseConfig(BaseModel):
    tool_name: str
    tool_description: str


# define what success looks like for agent
class AgentSuccessConfig(BaseModel):
    evaluation_name: str
    success_definition_prompt: str
    metadata_definition_prompt: Optional[str] = None
    sampling_rate: float = 1.0  # percentage of batch of interactions (defined by extraction_window_size and extraction_window_stride) to be sampled for success evaluation
    extraction_window_size_override: Optional[
        int
    ] = None  # override global extraction_window_size for this extractor
    extraction_window_stride_override: Optional[
        int
    ] = None  # override global extraction_window_stride for this extractor


class LLMConfig(BaseModel):
    """
    LLM model configuration overrides.

    These settings override the default model names from llm_model_setting.json site variable.
    If a field is None, the default from site variable is used.
    """

    should_run_model_name: Optional[
        str
    ] = None  # Model for "should run extraction" checks
    generation_model_name: Optional[
        str
    ] = None  # Model for generation and evaluation tasks
    embedding_model_name: Optional[str] = None  # Model for embedding generation


class Config(BaseModel):
    # define where user configuration is stored at
    storage_config: StorageConfig
    storage_config_test: Optional[StorageConfigTest] = StorageConfigTest.UNKNOWN
    # define agent working environment, tool can use and action space
    agent_context_prompt: Optional[str] = None
    # tools agent can use (shared across success evaluation and feedback extraction)
    tool_can_use: Optional[list[ToolUseConfig]] = None
    # user level memory
    profile_extractor_configs: Optional[list[ProfileExtractorConfig]] = None
    # agent level feedback
    agent_feedback_configs: Optional[list[AgentFeedbackConfig]] = None
    # agent level success
    agent_success_configs: Optional[list[AgentSuccessConfig]] = None
    # sliding window parameters for extraction
    extraction_window_size: Optional[int] = None
    extraction_window_stride: Optional[int] = None
    # API key configuration for LLM providers
    api_key_config: Optional[APIKeyConfig] = None
    # LLM model configuration overrides
    llm_config: Optional[LLMConfig] = None
