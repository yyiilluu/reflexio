---
title: API Schemas
---

# API Schemas

This page documents the data models and enumerations used in the Reflexio API.

## Enums

### UserActionType

Represents different types of user actions that can be tracked.

- `CLICK`: Click interaction
- `SCROLL`: Scroll interaction
- `TYPE`: Type interaction
- `NONE`: No specific interaction

### ProfileTimeToLive

Defines the time-to-live options for user profiles.

- `ONE_DAY`: Profile expires after one day
- `ONE_WEEK`: Profile expires after one week
- `ONE_MONTH`: Profile expires after one month
- `ONE_QUARTER`: Profile expires after one quarter
- `ONE_YEAR`: Profile expires after one year
- `INFINITY`: Profile never expires

### Status

Represents the current status of a user profile.

- `CURRENT`: Active profile currently in use
- `ARCHIVED`: Profile has been archived
- `PENDING`: Profile is pending approval or processing
- `ARCHIVE_IN_PROGRESS`: Profile is being archived

### FeedbackStatus

Represents the approval status of feedback.

- `PENDING`: Feedback is pending review
- `APPROVED`: Feedback has been approved
- `REJECTED`: Feedback has been rejected

### BlockingIssueKind

Represents the type of capability gap that prevented the agent from completing a request.

- `MISSING_TOOL`: Tool doesn't exist in the agent's toolset
- `PERMISSION_DENIED`: Agent lacks authorization to perform the action
- `EXTERNAL_DEPENDENCY`: External service is unavailable
- `POLICY_RESTRICTION`: Policy prevents the action

### Status

Represents the processing status for profiles and feedbacks.

- `CURRENT` (None): Active profile/feedback currently in use
- `ARCHIVED`: Profile/feedback has been archived (old versions)
- `PENDING`: New profile/feedback that is pending approval or processing (from rerun operations)
- `ARCHIVE_IN_PROGRESS`: Temporary status during downgrade operation

### OperationStatus

Represents the status of long-running operations.

- `IN_PROGRESS`: Operation is currently running
- `COMPLETED`: Operation has completed successfully
- `FAILED`: Operation has failed

## Models

### BlockingIssue

Represents a capability gap that blocked the agent from completing a user request.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `kind` | BlockingIssueKind | Type of blocking issue | Required |
| `details` | string | What capability is missing and why it blocks the request | Required |

### ToolUsed

Tracks a tool the agent used during an interaction. Multiple tools can be used per interaction.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `tool_name` | string | Name of the tool used | Required |
| `tool_input` | object | Parameter name to value mapping | Empty object |

### Interaction

Represents information about a user interaction stored in the system.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `interaction_id` | string | Unique identifier for the interaction | Required |
| `user_id` | string | Identifier of the user | Required |
| `request_id` | string | Identifier of the request | Required |
| `created_at` | integer | Unix timestamp when interaction was created | Required |
| `role` | string | Role of the interaction participant | Required |
| `content` | string | Text content of the interaction | Empty string |
| `shadow_content` | string | Alternative agent response for A/B testing (see [Shadow Content](#shadow-content)) | Empty string |
| `user_action` | UserActionType | Type of user action | `NONE` |
| `user_action_description` | string | Description of the user action | Empty string |
| `interacted_image_url` | string | URL of any associated image | Empty string |
| `image_encoding` | string | Base64 encoded image data | Empty string |
| `tools_used` | list[ToolUsed] | Tools used during this interaction | Empty list |
| `embedding` | array[float] | Vector embedding of the interaction | Empty array |

### Request

Represents a container for one or more interactions with metadata.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `request_id` | string | Unique identifier for the request | Required |
| `user_id` | string | Identifier of the user | Required |
| `created_at` | integer | Unix timestamp when request was created | Required |
| `source` | string | Source of the request (e.g., "web_app", "mobile_app") | Empty string |
| `agent_version` | string | Version of the agent that generated this request | Empty string |
| `request_group` | string | Group identifier for related requests | Empty string |

### RequestData

Contains a request with its associated interactions.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `request` | Request | The request object | Required |
| `interactions` | array[Interaction] | List of interactions in this request | Required |

### RequestGroup

Groups multiple requests by request_group identifier.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `request_group` | string | The request group identifier | Required |
| `requests` | array[RequestData] | List of requests in this group | Required |

### UserProfile

Represents a user profile generated from user interactions.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `profile_id` | string | Unique identifier for the profile | Required |
| `user_id` | string | Identifier of the user | Required |
| `profile_content` | string | Content of the user profile | Required |
| `last_modified_timestamp` | integer | Unix timestamp of last modification | Required |
| `generated_from_request_id` | string | Request ID that generated this profile | Required |
| `profile_time_to_live` | ProfileTimeToLive | Time-to-live setting for the profile | `INFINITY` |
| `expiration_timestamp` | integer | Unix timestamp when profile expires | Maximum timestamp |
| `custom_features` | object | Custom feature metadata | None |
| `source` | string | Source of the interaction that generated this profile | None |
| `status` | Status | Processing status of the profile (None for current, ARCHIVED, PENDING) | None |
| `embedding` | array[float] | Vector embedding of the profile | Empty array |

### InteractionData

Model for user-provided interaction information (also called InteractionRequest).

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `created_at` | integer | Unix timestamp when interaction was created | Current time |
| `role` | string | Role of the interaction participant (e.g., "User", "Agent") | "User" |
| `content` | string | Text content of the interaction | Empty string |
| `shadow_content` | string | Alternative agent response for A/B testing (see [Shadow Content](#shadow-content)) | Empty string |
| `user_action` | UserActionType | Type of user action | `NONE` |
| `user_action_description` | string | Description of the user action | Empty string |
| `interacted_image_url` | string | URL of any associated image | Empty string |
| `image_encoding` | string | Base64 encoded image data | Empty string |
| `tools_used` | list[ToolUsed] | Tools used during this interaction | Empty list |

### PublishUserInteractionRequest

Request model for publishing user interactions.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `user_id` | string | Identifier of the user | Required |
| `interaction_data_list` | array[InteractionData] | List of interaction data | Required |
| `source` | string | Source of the interactions | Empty string |
| `agent_version` | string | Version of the agent generating interactions | Empty string |
| `request_group` | string | Group identifier for related requests | None |

### PublishUserInteractionResponse

Response model for interaction publication requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the publication was successful | Required |
| `message` | string | Additional information about the operation | Empty string |

### SearchInteractionRequest

Request model for searching user interactions.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `user_id` | string | Identifier of the user | Required |
| `query` | string | Semantic search query | Required |
| `top_k` | integer | Number of results to return | 5 |
| `threshold` | float | Similarity threshold for results | 0.7 |

### SearchInteractionResponse

Response model for interaction search requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the search was successful | Required |
| `interactions` | array[Interaction] | List of matching interactions | Required |
| `msg` | string | Additional message | Optional |

### SearchUserProfileRequest

Request model for searching user profiles.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `user_id` | string | Identifier of the user | Required |
| `query` | string | Semantic search query | Required |
| `source` | string | Filter by interaction source | Optional |
| `custom_feature` | string | Filter by custom features | Optional |
| `extractor_name` | string | Filter by extractor name | Optional |
| `threshold` | float | Similarity threshold for results | 0.7 |
| `top_k` | integer | Number of results to return | 5 |

### SearchUserProfileResponse

Response model for profile search requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the search was successful | Required |
| `user_profiles` | array[UserProfile] | List of matching profiles | Required |
| `msg` | string | Additional message | Optional |

### DeleteUserProfileRequest

Request model for deleting a user profile.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `user_id` | string | Identifier of the user | Required |
| `profile_id` | string | Identifier of the profile to delete | Empty string |
| `search_query` | string | Search query to find profiles to delete | Empty string |

### DeleteUserProfileResponse

Response model for profile deletion requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the deletion was successful | Required |
| `message` | string | Additional information about the operation | Empty string |

### DeleteUserInteractionRequest

Request model for deleting a user interaction.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `user_id` | string | Identifier of the user | Required |
| `interaction_id` | string | Identifier of the interaction to delete | Required |

### DeleteUserInteractionResponse

Response model for interaction deletion requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the deletion was successful | Required |
| `message` | string | Additional information about the operation | Empty string |

### DeleteRequestRequest

Request model for deleting a request and all its associated interactions.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `request_id` | string | Identifier of the request to delete | Required |

### DeleteRequestResponse

Response model for request deletion requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the deletion was successful | Required |
| `message` | string | Additional information about the operation | Empty string |

### DeleteRequestGroupRequest

Request model for deleting all requests in a request group.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `request_group` | string | Request group identifier | Required |

### DeleteRequestGroupResponse

Response model for request group deletion requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the deletion was successful | Required |
| `message` | string | Additional information about the operation | Empty string |
| `deleted_requests_count` | integer | Number of requests deleted | 0 |

### DeleteFeedbackRequest

Request model for deleting a feedback.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `feedback_id` | integer | Identifier of the feedback to delete | Required |

### DeleteFeedbackResponse

Response model for feedback deletion requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the deletion was successful | Required |
| `message` | string | Additional information about the operation | Empty string |

### DeleteRawFeedbackRequest

Request model for deleting a raw feedback.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `raw_feedback_id` | integer | Identifier of the raw feedback to delete | Required |

### DeleteRawFeedbackResponse

Response model for raw feedback deletion requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the deletion was successful | Required |
| `message` | string | Additional information about the operation | Empty string |

### Config

Configuration object for Reflexio system.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `storage_config` | StorageConfig | Database storage configuration | Required |
| `agent_context_prompt` | string | Global agent context prompt | Optional |
| `profile_extractor_configs` | array[ProfileExtractorConfig] | Profile extraction configurations | Empty array |
| `agent_feedback_configs` | array[AgentFeedbackConfig] | Agent feedback configurations | Empty array |

### ProfileExtractorConfig

Configuration for profile extraction from interactions.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `profile_content_definition_prompt` | string | Prompt defining what to extract | Required |
| `context_prompt` | string | Context for profile extraction | Empty string |
| `metadata_definition_prompt` | string | Prompt for metadata extraction | Optional |
| `should_extract_profile_prompt_override` | string | Override for extraction conditions | Optional |

### AgentFeedbackConfig

Configuration for agent feedback generation.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `feedback_name` | string | Name of the feedback type | Required |
| `feedback_definition_prompt` | string | Prompt defining feedback extraction | Required |
| `metadata_definition_prompt` | string | Prompt for metadata extraction | Optional |
| `feedback_aggregator_config` | FeedbackAggregatorConfig | Configuration for aggregation | Required |

### FeedbackAggregatorConfig

Configuration for feedback aggregation.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `min_feedback_threshold` | integer | Minimum feedbacks required for aggregation | 2 |

### RawFeedback

Represents raw feedback generated from user interactions.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `raw_feedback_id` | integer | Unique identifier for the feedback | 0 |
| `agent_version` | string | Version of the agent | Required |
| `request_id` | string | Request ID that generated this feedback | Required |
| `feedback_name` | string | Name of the feedback type | Empty string |
| `created_at` | integer | Unix timestamp when feedback was created | Current time |
| `feedback_content` | string | Content of the feedback | Empty string |
| `do_action` | string | The preferred behavior the agent should adopt (structured feedback v1.2.0+) | None |
| `do_not_action` | string | The mistaken behavior the agent should avoid (structured feedback v1.2.0+) | None |
| `when_condition` | string | The condition/context when this rule applies (structured feedback v1.2.0+) | None |
| `source` | string | Source of the interaction that generated this feedback | None |
| `blocking_issue` | BlockingIssue | Root cause when agent couldn't complete action | None |
| `indexed_content` | string | Content used for embedding/indexing (extracted from feedback_content) | None |
| `status` | Status | Processing status (None=current, PENDING=from rerun, ARCHIVED=old) | None |
| `embedding` | array[float] | Vector embedding of the feedback | Empty array |

### Feedback

Represents aggregated feedback consolidated from multiple raw feedbacks.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `feedback_id` | integer | Unique identifier for the aggregated feedback | 0 |
| `feedback_name` | string | Name of the feedback type | Empty string |
| `agent_version` | string | Version of the agent | Required |
| `created_at` | integer | Unix timestamp when feedback was created | Current time |
| `feedback_content` | string | Aggregated content of the feedback | Required |
| `do_action` | string | The preferred behavior the agent should adopt (structured feedback v1.2.0+) | None |
| `do_not_action` | string | The mistaken behavior the agent should avoid (structured feedback v1.2.0+) | None |
| `when_condition` | string | The condition/context when this rule applies (structured feedback v1.2.0+) | None |
| `blocking_issue` | BlockingIssue | Root cause when agent couldn't complete action | None |
| `feedback_status` | FeedbackStatus | Approval status (PENDING, APPROVED, REJECTED) | Required |
| `feedback_metadata` | string | Additional metadata about the feedback | Required |
| `status` | Status | Processing status for aggregation tracking | None |
| `embedding` | array[float] | Vector embedding of the feedback | Empty array |

### ProfileChangeLog

Represents a log entry tracking changes to user profiles.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `id` | integer | Unique identifier for the change log | Required |
| `user_id` | string | Identifier of the user whose profile changed | Required |
| `request_id` | string | Request ID that triggered the change | Required |
| `created_at` | integer | Unix timestamp when the change occurred | Current time |
| `added_profiles` | array[UserProfile] | Profiles that were added | Required |
| `removed_profiles` | array[UserProfile] | Profiles that were removed | Required |
| `mentioned_profiles` | array[UserProfile] | Profiles that were referenced but not changed | Required |

### ProfileChangeLogResponse

Response model for profile change log requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the request was successful | Required |
| `profile_change_logs` | array[ProfileChangeLog] | List of profile change logs | Required |

### GetInteractionsRequest

Request model for getting user interactions.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `user_id` | string | Identifier of the user | Required |
| `start_time` | datetime | Filter by start time | Optional |
| `end_time` | datetime | Filter by end time | Optional |
| `top_k` | integer | Maximum number of results to return | 30 |

### GetInteractionsResponse

Response model for getting user interactions.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the request was successful | Required |
| `interactions` | array[Interaction] | List of interactions | Required |
| `msg` | string | Additional message | Optional |

### GetUserProfilesRequest

Request model for getting user profiles.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `user_id` | string | Identifier of the user | Required |
| `start_time` | datetime | Filter by start time | Optional |
| `end_time` | datetime | Filter by end time | Optional |
| `top_k` | integer | Maximum number of results to return | 30 |
| `status_filter` | array[Status] | Filter by profile status | Optional |

### GetUserProfilesResponse

Response model for getting user profiles.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the request was successful | Required |
| `user_profiles` | array[UserProfile] | List of profiles | Required |
| `msg` | string | Additional message | Optional |

### GetRawFeedbacksRequest

Request model for getting raw feedbacks.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `limit` | integer | Maximum number of results to return | 100 |
| `feedback_name` | string | Filter by feedback name | Optional |
| `status_filter` | array[Status] | Filter by status | Optional |

### GetRawFeedbacksResponse

Response model for getting raw feedbacks.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the request was successful | Required |
| `raw_feedbacks` | array[RawFeedback] | List of raw feedbacks | Required |
| `msg` | string | Additional message | Optional |

### AddRawFeedbackRequest

Request model for adding raw feedbacks directly to storage.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `raw_feedbacks` | array[RawFeedback] | List of raw feedbacks to add | Required |

### AddRawFeedbackResponse

Response model for adding raw feedbacks.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the operation was successful | Required |
| `message` | string | Additional information about the operation | Empty string |
| `added_count` | integer | Number of feedbacks added | 0 |

### GetFeedbacksRequest

Request model for getting aggregated feedbacks.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `limit` | integer | Maximum number of results to return | 100 |
| `feedback_name` | string | Filter by feedback name | Optional |
| `status_filter` | array[Status] | Filter by status | Optional |
| `feedback_status_filter` | FeedbackStatus | Filter by feedback status | APPROVED |

### GetFeedbacksResponse

Response model for getting aggregated feedbacks.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the request was successful | Required |
| `feedbacks` | array[Feedback] | List of aggregated feedbacks | Required |
| `msg` | string | Additional message | Optional |

### RunFeedbackAggregationRequest

Request model for running feedback aggregation.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `agent_version` | string | Agent version to aggregate feedbacks for | Required |
| `feedback_name` | string | Name of the feedback type to aggregate | Required |

### RunFeedbackAggregationResponse

Response model for feedback aggregation requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the aggregation was successful | Required |
| `message` | string | Additional information about the operation | Empty string |

### GetRequestsRequest

Request model for getting requests grouped by request_group.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `user_id` | string | Filter by user ID | Optional |
| `request_id` | string | Filter by specific request ID | Optional |
| `start_time` | datetime | Filter by start time | Optional |
| `end_time` | datetime | Filter by end time | Optional |
| `top_k` | integer | Maximum number of results to return | 30 |

### GetRequestsResponse

Response model for getting requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the request was successful | Required |
| `request_groups` | array[RequestGroup] | List of request groups with their requests | Required |
| `msg` | string | Additional message | Optional |

### AgentSuccessEvaluationResult

Represents an agent performance evaluation result.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `result_id` | integer | Unique identifier for the evaluation result | 0 |
| `agent_version` | string | Version of the agent being evaluated | Required |
| `request_id` | string | Request ID that was evaluated | Required |
| `is_success` | boolean | Whether the agent was successful | Required |
| `failure_type` | string | Type of failure if unsuccessful | Required |
| `failure_reason` | string | Detailed reason for failure | Required |
| `agent_prompt_update` | string | Suggested improvement for the agent | Required |
| `created_at` | integer | Unix timestamp when evaluation was created | Current time |
| `embedding` | array[float] | Vector embedding of the evaluation result | Empty array |

### GetAgentSuccessEvaluationResultsRequest

Request model for getting agent success evaluation results.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `agent_version` | string | Filter by specific agent version | Optional |
| `limit` | integer | Maximum number of results to return | 100 |

### GetAgentSuccessEvaluationResultsResponse

Response model for getting agent success evaluation results.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the request was successful | Required |
| `results` | array[AgentSuccessEvaluationResult] | List of evaluation results | Required |
| `msg` | string | Additional message | Optional |

### RerunProfileGenerationRequest

Request model for rerunning profile generation.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `user_id` | string | Specific user ID to rerun for (if None, runs for all users) | Optional |
| `start_time` | datetime | Filter interactions from this time | Optional |
| `end_time` | datetime | Filter interactions until this time | Optional |
| `source` | string | Filter interactions by source | Optional |

### RerunProfileGenerationResponse

Response model for profile generation rerun requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the operation was successful | Required |
| `msg` | string | Additional information | Optional |
| `profiles_generated` | integer | Number of profiles generated | Optional |
| `operation_id` | string | Operation identifier for tracking | Optional |

### RerunFeedbackGenerationRequest

Request model for rerunning feedback generation.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `agent_version` | string | Agent version to evaluate | Required |
| `start_time` | datetime | Filter interactions from this time | Optional |
| `end_time` | datetime | Filter interactions until this time | Optional |
| `feedback_name` | string | Specific feedback type to generate | Optional |

### RerunFeedbackGenerationResponse

Response model for feedback generation rerun requests.

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `success` | boolean | Whether the operation was successful | Required |
| `msg` | string | Additional information | Optional |
| `feedbacks_generated` | integer | Number of feedbacks generated | Optional |
| `operation_id` | string | Operation identifier for tracking | Optional |

## Concepts

### Shadow Content

The `shadow_content` field allows you to capture an alternative agent response alongside the production response, enabling A/B testing and comparison of different agent behaviors.

**How it works:**

| Field | Purpose |
|-------|---------|
| `content` | The actual production interaction between user and agent. Used for storage, semantic search, and retrieval. |
| `shadow_content` | An alternative response (e.g., from a different agent version or with different user profiles). Used for profile extraction, feedback generation, and evaluation when provided. |

This separation allows you to:

- **Compare agent versions**: Test how a new agent version would respond without affecting production
- **Evaluate profile effectiveness**: See how different user profile configurations affect agent responses
- **A/B test feedback integration**: Compare responses with and without specific agent feedback applied

**When to use shadow_content:**

- Testing a new agent version's responses against the current production version
- Evaluating how different user profile configurations affect agent behavior
- Comparing responses with different feedback/prompt improvements applied
- Running shadow evaluations without impacting the user experience

**Example: Comparing Agent Responses**

```python
# Agent v1.0 is in production, testing v2.0 response in shadow
client.publish_interaction(
    user_id="user_123",
    interactions=[
        {
            "role": "User",
            "content": "I would like to get a refund"
        },
        {
            "role": "Agent",
            # Production response (v1.0) - generic, asks for info
            "content": "Happy to help you with that. What is your email or phone number?",
            # Shadow response (v2.0) - personalized, uses known user data
            "shadow_content": "Happy to assist you with that. I can see your phone number is 123-456-7890. Is that the right number to send the refund confirmation to?"
        }
    ],
    request_group="support_session_001",
    agent_version="v1.0"
)
```

In this example:
- `content` stores the production response from agent v1.0
- `shadow_content` captures how agent v2.0 (with access to user profiles) would have responded
- Profile extraction and evaluation use `shadow_content` to assess the v2.0 approach
- You can compare evaluation results to decide whether to promote v2.0 to production
