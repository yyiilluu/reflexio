from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from reflexio_commons.api_schema.service_schemas import (
    Interaction,
    Request,
    UserProfile,
    RawFeedback,
    Feedback,
    Skill,
    AgentSuccessEvaluationResult,
    FeedbackStatus,
    SkillStatus,
    Status,
)


class SearchInteractionRequest(BaseModel):
    user_id: str
    request_id: Optional[str] = None
    query: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    top_k: Optional[int] = None
    most_recent_k: Optional[int] = None


class SearchUserProfileRequest(BaseModel):
    user_id: str
    generated_from_request_id: Optional[str] = None
    query: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    top_k: Optional[int] = 10
    source: Optional[str] = None
    custom_feature: Optional[str] = None
    extractor_name: Optional[str] = None
    threshold: Optional[float] = 0.5
    query_rewrite: Optional[bool] = False


class SearchInteractionResponse(BaseModel):
    success: bool
    interactions: list[Interaction]
    msg: Optional[str] = None


class SearchUserProfileResponse(BaseModel):
    success: bool
    user_profiles: list[UserProfile]
    msg: Optional[str] = None


class GetInteractionsRequest(BaseModel):
    user_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    top_k: Optional[int] = 30


class GetInteractionsResponse(BaseModel):
    success: bool
    interactions: list[Interaction]
    msg: Optional[str] = None


class GetUserProfilesRequest(BaseModel):
    user_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    top_k: Optional[int] = 30
    status_filter: Optional[list[Optional[Status]]] = None


class GetUserProfilesResponse(BaseModel):
    success: bool
    user_profiles: list[UserProfile]
    msg: Optional[str] = None


class GetProfileStatisticsResponse(BaseModel):
    success: bool
    current_count: int = 0
    pending_count: int = 0
    archived_count: int = 0
    expiring_soon_count: int = 0
    msg: Optional[str] = None


class SetConfigResponse(BaseModel):
    success: bool
    msg: Optional[str] = None


class GetRawFeedbacksRequest(BaseModel):
    limit: Optional[int] = 100
    feedback_name: Optional[str] = None
    status_filter: Optional[list[Optional[Status]]] = None


class GetRawFeedbacksResponse(BaseModel):
    success: bool
    raw_feedbacks: list[RawFeedback]
    msg: Optional[str] = None


class GetFeedbacksRequest(BaseModel):
    limit: Optional[int] = 100
    feedback_name: Optional[str] = None
    status_filter: Optional[list[Optional[Status]]] = None
    feedback_status_filter: Optional[FeedbackStatus] = None


class GetFeedbacksResponse(BaseModel):
    success: bool
    feedbacks: list[Feedback]
    msg: Optional[str] = None


class SearchRawFeedbackRequest(BaseModel):
    """Request for searching raw feedbacks with semantic/text search and filtering.

    Args:
        query (str, optional): Query for semantic/text search
        user_id (str, optional): Filter by user (via request_id linkage to requests table)
        agent_version (str, optional): Filter by agent version
        feedback_name (str, optional): Filter by feedback name
        start_time (datetime, optional): Start time for created_at filter
        end_time (datetime, optional): End time for created_at filter
        status_filter (list[Optional[Status]], optional): Filter by status (None for CURRENT, PENDING, ARCHIVED)
        top_k (int, optional): Maximum number of results to return. Defaults to 10
        threshold (float, optional): Similarity threshold for vector search. Defaults to 0.5
    """

    query: Optional[str] = None
    user_id: Optional[str] = None
    agent_version: Optional[str] = None
    feedback_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status_filter: Optional[list[Optional[Status]]] = None
    top_k: Optional[int] = 10
    threshold: Optional[float] = 0.5
    query_rewrite: Optional[bool] = False


class SearchRawFeedbackResponse(BaseModel):
    """Response for searching raw feedbacks.

    Args:
        success (bool): Whether the search was successful
        raw_feedbacks (list[RawFeedback]): List of matching raw feedbacks
        msg (str, optional): Additional message
    """

    success: bool
    raw_feedbacks: list[RawFeedback]
    msg: Optional[str] = None


class SearchFeedbackRequest(BaseModel):
    """Request for searching aggregated feedbacks with semantic/text search and filtering.

    Args:
        query (str, optional): Query for semantic/text search
        agent_version (str, optional): Filter by agent version
        feedback_name (str, optional): Filter by feedback name
        start_time (datetime, optional): Start time for created_at filter
        end_time (datetime, optional): End time for created_at filter
        status_filter (list[Optional[Status]], optional): Filter by status (None for CURRENT, PENDING, ARCHIVED)
        feedback_status_filter (FeedbackStatus, optional): Filter by feedback status (PENDING, APPROVED, REJECTED)
        top_k (int, optional): Maximum number of results to return. Defaults to 10
        threshold (float, optional): Similarity threshold for vector search. Defaults to 0.5
    """

    query: Optional[str] = None
    agent_version: Optional[str] = None
    feedback_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status_filter: Optional[list[Optional[Status]]] = None
    feedback_status_filter: Optional[FeedbackStatus] = None
    top_k: Optional[int] = 10
    threshold: Optional[float] = 0.5
    query_rewrite: Optional[bool] = False


class SearchFeedbackResponse(BaseModel):
    """Response for searching aggregated feedbacks.

    Args:
        success (bool): Whether the search was successful
        feedbacks (list[Feedback]): List of matching feedbacks
        msg (str, optional): Additional message
    """

    success: bool
    feedbacks: list[Feedback]
    msg: Optional[str] = None


class GetAgentSuccessEvaluationResultsRequest(BaseModel):
    limit: Optional[int] = 100
    agent_version: Optional[str] = None


class GetAgentSuccessEvaluationResultsResponse(BaseModel):
    success: bool
    agent_success_evaluation_results: list[AgentSuccessEvaluationResult]
    msg: Optional[str] = None


class GetRequestsRequest(BaseModel):
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    top_k: Optional[int] = 30


class RequestData(BaseModel):
    request: Request
    interactions: list[Interaction]


class RequestGroup(BaseModel):
    request_group: str
    requests: list[RequestData]


class GetRequestsResponse(BaseModel):
    success: bool
    request_groups: list[RequestGroup]
    msg: Optional[str] = None


class UpdateFeedbackStatusRequest(BaseModel):
    feedback_id: int
    feedback_status: FeedbackStatus


class UpdateFeedbackStatusResponse(BaseModel):
    success: bool
    msg: Optional[str] = None


class TimeSeriesDataPoint(BaseModel):
    """A single data point in a time series."""

    timestamp: int  # Unix timestamp
    value: int  # Count or metric value


class PeriodStats(BaseModel):
    """Statistics for a specific time period."""

    total_profiles: int
    total_interactions: int
    total_feedbacks: int
    success_rate: float  # Percentage (0-100)


class DashboardStats(BaseModel):
    """Comprehensive dashboard statistics including current and previous periods."""

    current_period: PeriodStats
    previous_period: PeriodStats
    interactions_time_series: list[TimeSeriesDataPoint]
    profiles_time_series: list[TimeSeriesDataPoint]
    feedbacks_time_series: list[TimeSeriesDataPoint]
    evaluations_time_series: list[TimeSeriesDataPoint]  # Success rate over time


class GetDashboardStatsRequest(BaseModel):
    """Request for dashboard statistics.

    Args:
        days_back (int): Number of days to include in time series data. Defaults to 30.
    """

    days_back: Optional[int] = 30


class GetDashboardStatsResponse(BaseModel):
    """Response containing dashboard statistics."""

    success: bool
    stats: Optional[DashboardStats] = None
    msg: Optional[str] = None


# ===============================
# Skill Retriever Models
# ===============================


class GetSkillsRequest(BaseModel):
    limit: Optional[int] = 100
    feedback_name: Optional[str] = None
    agent_version: Optional[str] = None
    skill_status: Optional[SkillStatus] = None


class GetSkillsResponse(BaseModel):
    success: bool
    skills: list[Skill] = []
    msg: Optional[str] = None


class SearchSkillsRequest(BaseModel):
    query: Optional[str] = None
    feedback_name: Optional[str] = None
    agent_version: Optional[str] = None
    skill_status: Optional[SkillStatus] = None
    threshold: Optional[float] = 0.5
    top_k: Optional[int] = 10


class SearchSkillsResponse(BaseModel):
    success: bool
    skills: list[Skill] = []
    msg: Optional[str] = None


# ===============================
# Query Rewrite Models
# ===============================


class ConversationTurn(BaseModel):
    """A single turn in a conversation history.

    Args:
        role (str): The role of the speaker (e.g., "user", "agent")
        content (str): The message content
    """

    role: str
    content: str


class RewrittenQuery(BaseModel):
    """LLM structured output for query rewriting.

    Args:
        fts_query (str): Expanded FTS query using websearch_to_tsquery syntax (supports OR, phrases, negation)
    """

    fts_query: str


# ===============================
# Unified Search Models
# ===============================


class UnifiedSearchRequest(BaseModel):
    """Request for unified search across all entity types.

    Args:
        query (str): Search query text
        top_k (int, optional): Maximum results per entity type. Defaults to 5
        threshold (float, optional): Similarity threshold for vector search. Defaults to 0.3
        agent_version (str, optional): Filter by agent version (feedbacks, raw_feedbacks, skills)
        feedback_name (str, optional): Filter by feedback name (feedbacks, raw_feedbacks, skills)
        user_id (str, optional): Filter by user ID (profiles, raw_feedbacks)
        conversation_history (list[ConversationTurn], optional): Prior conversation turns for context-aware query rewriting
    """

    query: str
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.3
    agent_version: Optional[str] = None
    feedback_name: Optional[str] = None
    user_id: Optional[str] = None
    conversation_history: Optional[list[ConversationTurn]] = None
    query_rewrite: Optional[bool] = False


class UnifiedSearchResponse(BaseModel):
    """Response containing search results from all entity types.

    Args:
        success (bool): Whether the search was successful
        profiles (list[UserProfile]): Matching user profiles
        feedbacks (list[Feedback]): Matching aggregated feedbacks
        raw_feedbacks (list[RawFeedback]): Matching raw feedbacks
        skills (list[Skill]): Matching skills (empty if skill_generation disabled)
        rewritten_query (str, optional): The FTS query used after rewriting (None if rewrite disabled)
        msg (str, optional): Additional message
    """

    success: bool
    profiles: list[UserProfile] = []
    feedbacks: list[Feedback] = []
    raw_feedbacks: list[RawFeedback] = []
    skills: list[Skill] = []
    rewritten_query: Optional[str] = None
    msg: Optional[str] = None
