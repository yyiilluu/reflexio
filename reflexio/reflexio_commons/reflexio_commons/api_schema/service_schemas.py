import enum
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

# OS-agnostic "never expires" timestamp (January 1, 2100 00:00:00 UTC)
# This is well within the safe range for all systems (32-bit timestamp limit is 2038)
NEVER_EXPIRES_TIMESTAMP = 4102444800


# ===============================
# Enums
# ===============================
class UserActionType(str, enum.Enum):
    CLICK = "click"
    SCROLL = "scroll"
    TYPE = "type"
    NONE = "none"


class ProfileTimeToLive(str, enum.Enum):
    ONE_DAY = "one_day"
    ONE_WEEK = "one_week"
    ONE_MONTH = "one_month"
    ONE_QUARTER = "one_quarter"
    ONE_YEAR = "one_year"
    INFINITY = "infinity"


class FeedbackStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Status(str, enum.Enum):
    CURRENT = None  # None for current profile/feedback
    ARCHIVED = "archived"  # archived old profiles/feedbacks
    PENDING = "pending"  # new profiles/feedbacks that are not approved
    ARCHIVE_IN_PROGRESS = (
        "archive_in_progress"  # temporary status during downgrade operation
    )


class OperationStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RegularVsShadow(str, enum.Enum):
    """
    This enum is used to indicate the relative performance of the regular and shadow versions of the agent.
    """

    REGULAR_IS_BETTER = "regular_is_better"
    REGULAR_IS_SLIGHTLY_BETTER = "regular_is_slightly_better"
    SHADOW_IS_BETTER = "shadow_is_better"
    SHADOW_IS_SLIGHTLY_BETTER = "shadow_is_slightly_better"
    TIED = "tied"


class BlockingIssueKind(str, enum.Enum):
    MISSING_TOOL = "missing_tool"
    PERMISSION_DENIED = "permission_denied"
    EXTERNAL_DEPENDENCY = "external_dependency"
    POLICY_RESTRICTION = "policy_restriction"


# ===============================
# Data Models
# ===============================


class BlockingIssue(BaseModel):
    kind: BlockingIssueKind
    details: str = Field(
        description="What capability is missing and why it blocks the request"
    )


class ToolUsed(BaseModel):
    tool_name: str
    tool_input: dict = Field(default_factory=dict)  # dict of param name -> value


# information about the user interaction sent by the client
class Interaction(BaseModel):
    interaction_id: int = 0  # 0 = placeholder for DB auto-increment
    user_id: str
    request_id: str
    created_at: int = Field(
        default_factory=lambda: int(datetime.now(timezone.utc).timestamp())
    )
    role: str = "User"
    content: str = ""
    user_action: UserActionType = UserActionType.NONE
    user_action_description: str = ""
    interacted_image_url: str = ""
    image_encoding: str = ""  # base64 encoded image
    shadow_content: str = ""
    tool_used: Optional[ToolUsed] = None
    embedding: list[float] = []


class Request(BaseModel):
    request_id: str
    user_id: str
    created_at: int = Field(
        default_factory=lambda: int(datetime.now(timezone.utc).timestamp())
    )
    source: str = ""
    agent_version: str = ""
    request_group: Optional[str] = None


# information about the user profile generated from the user interaction
# output of the profile generation service send back to the client
class UserProfile(BaseModel):
    profile_id: str
    user_id: str
    profile_content: str
    last_modified_timestamp: int
    generated_from_request_id: str
    profile_time_to_live: ProfileTimeToLive = ProfileTimeToLive.INFINITY
    # this is the expiration date calculated based on last modified timestamp and profile time to live instead of generated timestamp
    expiration_timestamp: int = NEVER_EXPIRES_TIMESTAMP
    custom_features: Optional[dict] = None
    source: Optional[str] = None
    status: Optional[Status] = None  # indicates the status of the profile
    extractor_names: Optional[list[str]] = None
    embedding: list[float] = []


# raw feedback for agents
class RawFeedback(BaseModel):
    raw_feedback_id: int = 0
    user_id: Optional[str] = None  # optional for backward compatibility
    agent_version: str
    request_id: str
    feedback_name: str = ""
    created_at: int = Field(
        default_factory=lambda: int(datetime.now(timezone.utc).timestamp())
    )
    feedback_content: str = ""

    # Structured feedback fields (v1.2.0+)
    do_action: Optional[str] = None  # What the agent should do (preferred behavior)
    do_not_action: Optional[
        str
    ] = None  # What the agent should avoid (mistaken behavior)
    when_condition: Optional[str] = None  # The condition/context when this applies

    status: Optional[
        Status
    ] = None  # Status.PENDING (from rerun), None (current), Status.ARCHIVED (old)
    source: Optional[
        str
    ] = None  # source of the interaction that generated this feedback
    blocking_issue: Optional[
        BlockingIssue
    ] = None  # Root cause when agent couldn't complete action
    indexed_content: Optional[
        str
    ] = None  # Content used for embedding/indexing (extracted from feedback_content)
    embedding: list[float] = []


class ProfileChangeLog(BaseModel):
    id: int
    user_id: str
    request_id: str
    created_at: int = Field(
        default_factory=lambda: int(datetime.now(timezone.utc).timestamp())
    )
    added_profiles: list[UserProfile]
    removed_profiles: list[UserProfile]
    mentioned_profiles: list[UserProfile]


class Feedback(BaseModel):
    feedback_id: int = 0
    feedback_name: str = ""
    agent_version: str
    created_at: int = Field(
        default_factory=lambda: int(datetime.now(timezone.utc).timestamp())
    )
    feedback_content: str

    # Structured feedback fields (v1.2.0+)
    do_action: Optional[str] = None  # What the agent should do (preferred behavior)
    do_not_action: Optional[
        str
    ] = None  # What the agent should avoid (mistaken behavior)
    when_condition: Optional[str] = None  # The condition/context when this applies

    blocking_issue: Optional[
        BlockingIssue
    ] = None  # Root cause when agent couldn't complete action
    feedback_status: FeedbackStatus = FeedbackStatus.PENDING
    feedback_metadata: str = ""
    embedding: list[float] = []
    status: Optional[
        Status
    ] = None  # used for tracking intermediate states during feedback aggregation. Status.ARCHIVED for feedbacks during aggregation process, None for current feedbacks


class AgentSuccessEvaluationResult(BaseModel):
    result_id: int = 0
    agent_version: str
    request_id: str
    is_success: bool
    failure_type: str
    failure_reason: str
    agent_prompt_update: str
    evaluation_name: Optional[str] = None
    created_at: int = Field(
        default_factory=lambda: int(datetime.now(timezone.utc).timestamp())
    )
    regular_vs_shadow: Optional[RegularVsShadow] = None
    embedding: list[float] = []


# ===============================
# Request Models
# ===============================


# delete user profile request
class DeleteUserProfileRequest(BaseModel):
    user_id: str
    profile_id: str = ""
    search_query: str = ""


# delete user profile response
class DeleteUserProfileResponse(BaseModel):
    success: bool
    message: str = ""


# delete user interaction request
class DeleteUserInteractionRequest(BaseModel):
    user_id: str
    interaction_id: int


# delete user interaction response
class DeleteUserInteractionResponse(BaseModel):
    success: bool
    message: str = ""


# delete request request
class DeleteRequestRequest(BaseModel):
    request_id: str


# delete request response
class DeleteRequestResponse(BaseModel):
    success: bool
    message: str = ""


# delete request group request
class DeleteRequestGroupRequest(BaseModel):
    request_group: str


# delete request group response
class DeleteRequestGroupResponse(BaseModel):
    success: bool
    message: str = ""
    deleted_requests_count: int = 0


# delete feedback request
class DeleteFeedbackRequest(BaseModel):
    feedback_id: int


# delete feedback response
class DeleteFeedbackResponse(BaseModel):
    success: bool
    message: str = ""


# delete raw feedback request
class DeleteRawFeedbackRequest(BaseModel):
    raw_feedback_id: int


# delete raw feedback response
class DeleteRawFeedbackResponse(BaseModel):
    success: bool
    message: str = ""


# user provided interaction data from the request
class InteractionData(BaseModel):
    created_at: int = Field(
        default_factory=lambda: int(datetime.now(timezone.utc).timestamp())
    )
    role: str = "User"
    content: str = ""
    shadow_content: str = ""
    user_action: UserActionType = UserActionType.NONE
    user_action_description: str = ""
    interacted_image_url: str = ""
    image_encoding: str = ""  # base64 encoded image
    tool_used: Optional[ToolUsed] = None


# publish user interaction request
class PublishUserInteractionRequest(BaseModel):
    user_id: str
    interaction_data_list: list[InteractionData]
    source: str = ""
    agent_version: str = (
        ""  # this is used for aggregating interactions for generating agent feedback
    )
    request_group: Optional[str] = None  # used for grouping requests together


# publish user interaction response
class PublishUserInteractionResponse(BaseModel):
    success: bool
    message: str = ""


# add raw feedback request/response
class AddRawFeedbackRequest(BaseModel):
    raw_feedbacks: list[RawFeedback]


class AddRawFeedbackResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    added_count: int = 0


# add feedback request/response (for aggregated feedbacks)
class AddFeedbackRequest(BaseModel):
    feedbacks: list[Feedback]


class AddFeedbackResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    added_count: int = 0


class ProfileChangeLogResponse(BaseModel):
    success: bool
    profile_change_logs: list[ProfileChangeLog]


class RunFeedbackAggregationRequest(BaseModel):
    agent_version: str
    feedback_name: str


class RunFeedbackAggregationResponse(BaseModel):
    success: bool
    message: str = ""


class RerunProfileGenerationRequest(BaseModel):
    user_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    source: Optional[str] = None
    extractor_names: Optional[list[str]] = None


class RerunProfileGenerationResponse(BaseModel):
    success: bool
    msg: Optional[str] = None
    profiles_generated: Optional[int] = None
    operation_id: str = "rerun_profile_generation"


class ManualProfileGenerationRequest(BaseModel):
    """Request for manual trigger of regular profile generation.

    Uses window-sized interactions (from config) instead of all interactions.
    Outputs profiles with CURRENT status (not PENDING like rerun).
    """

    user_id: Optional[str] = None
    source: Optional[str] = None
    extractor_names: Optional[list[str]] = None


class ManualProfileGenerationResponse(BaseModel):
    """Response for manual profile generation."""

    success: bool
    msg: Optional[str] = None
    profiles_generated: Optional[int] = None


class ManualFeedbackGenerationRequest(BaseModel):
    """Request for manual trigger of regular feedback generation.

    Uses window-sized interactions (from config) instead of all interactions.
    Outputs feedbacks with CURRENT status (not PENDING like rerun).
    """

    agent_version: str
    source: Optional[str] = None
    feedback_name: Optional[str] = None  # Optional filter by feedback name


class ManualFeedbackGenerationResponse(BaseModel):
    """Response for manual feedback generation."""

    success: bool
    msg: Optional[str] = None
    feedbacks_generated: Optional[int] = None


class RerunFeedbackGenerationRequest(BaseModel):
    agent_version: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    feedback_name: Optional[str] = None
    source: Optional[str] = None


class RerunFeedbackGenerationResponse(BaseModel):
    success: bool
    msg: Optional[str] = None
    feedbacks_generated: Optional[int] = None
    operation_id: str = "rerun_feedback_generation"


class UpgradeProfilesRequest(BaseModel):
    user_id: str
    profile_ids: Optional[list[str]] = None
    only_affected_users: bool = (
        False  # If True, only upgrade users who have pending profiles
    )


class UpgradeProfilesResponse(BaseModel):
    success: bool
    profiles_archived: int = 0
    profiles_promoted: int = 0
    profiles_deleted: int = 0
    message: str = ""


class DowngradeProfilesRequest(BaseModel):
    user_id: str
    profile_ids: Optional[list[str]] = None
    only_affected_users: bool = (
        False  # If True, only downgrade users who have archived profiles
    )


class DowngradeProfilesResponse(BaseModel):
    success: bool
    profiles_demoted: int = 0
    profiles_restored: int = 0
    message: str = ""


class UpgradeRawFeedbacksRequest(BaseModel):
    agent_version: Optional[str] = None
    feedback_name: Optional[str] = None
    archive_current: bool = True


class UpgradeRawFeedbacksResponse(BaseModel):
    success: bool
    raw_feedbacks_deleted: int = 0
    raw_feedbacks_archived: int = 0
    raw_feedbacks_promoted: int = 0
    message: str = ""


class DowngradeRawFeedbacksRequest(BaseModel):
    agent_version: Optional[str] = None
    feedback_name: Optional[str] = None


class DowngradeRawFeedbacksResponse(BaseModel):
    success: bool
    raw_feedbacks_demoted: int = 0
    raw_feedbacks_restored: int = 0
    message: str = ""


# ===============================
# Operation Status Models
# ===============================
class OperationStatusInfo(BaseModel):
    service_name: str
    status: OperationStatus
    started_at: int
    completed_at: Optional[int] = None
    total_users: int = 0
    processed_users: int = 0
    failed_users: int = 0
    current_user_id: Optional[str] = None
    processed_user_ids: list[str] = []
    failed_user_ids: list[dict] = []  # [{"user_id": "...", "error": "..."}]
    request_params: dict = {}
    stats: dict = {}
    error_message: Optional[str] = None
    progress_percentage: float = 0.0


class GetOperationStatusRequest(BaseModel):
    service_name: str = "profile_generation"


class GetOperationStatusResponse(BaseModel):
    success: bool
    operation_status: Optional[OperationStatusInfo] = None
    msg: Optional[str] = None


class CancelOperationRequest(BaseModel):
    service_name: Optional[str] = None  # None cancels both services


class CancelOperationResponse(BaseModel):
    success: bool
    cancelled_services: list[str] = []
    msg: Optional[str] = None
