"""Shared utility for managing operation state across rerun services."""

from datetime import datetime, timezone
from typing import Any, Optional

from reflexio_commons.api_schema.service_schemas import OperationStatus


class OperationStateManager:
    """Utility class for managing operation state during rerun operations.

    Provides methods to check, initialize, update, and finalize operation states
    for long-running batch operations like profile/feedback reruns.

    Args:
        storage: Storage instance with operation state methods
        service_name: Name of the service operation (e.g., "rerun_profile_generation")
    """

    def __init__(self, storage: Any, service_name: str):
        self.storage = storage
        self.service_name = service_name

    def check_in_progress(self) -> Optional[str]:
        """Check if there's an existing in-progress operation.

        Returns:
            Error message if operation is in progress, None otherwise
        """
        existing_state_entry = self.storage.get_operation_state(self.service_name)
        if existing_state_entry:
            existing_state = existing_state_entry.get(
                "operation_state", existing_state_entry
            )
            if existing_state.get("status") == OperationStatus.IN_PROGRESS.value:
                return f"A {self.service_name} operation is already in progress. Please wait for it to complete."
        return None

    def initialize(
        self, total_users: int, request_params: dict, extra_stats: Optional[dict] = None
    ) -> None:
        """Initialize operation state with IN_PROGRESS status.

        Args:
            total_users: Total number of users to process
            request_params: Original request parameters for reference
            extra_stats: Optional additional stats fields to include
        """
        stats = {
            "total_interactions_processed": 0,
            "total_generated": 0,
        }
        if extra_stats:
            stats.update(extra_stats)

        initial_state = {
            "service_name": self.service_name,
            "status": OperationStatus.IN_PROGRESS.value,
            "started_at": int(datetime.now(timezone.utc).timestamp()),
            "completed_at": None,
            "total_users": total_users,
            "processed_users": 0,
            "failed_users": 0,
            "current_user_id": None,
            "processed_user_ids": [],
            "failed_user_ids": [],
            "request_params": request_params,
            "stats": stats,
            "error_message": None,
            "progress_percentage": 0.0,
        }
        self.storage.upsert_operation_state(self.service_name, initial_state)

    def set_current_user(self, user_id: str) -> None:
        """Set the current user being processed.

        Args:
            user_id: User ID currently being processed
        """
        state_entry = self.storage.get_operation_state(self.service_name)
        current_state = (
            state_entry.get("operation_state", state_entry) if state_entry else {}
        )
        current_state["current_user_id"] = user_id
        self.storage.update_operation_state(self.service_name, current_state)

    def update_progress(
        self,
        user_id: str,
        interaction_count: int,
        success: bool,
        total_users: int,
        error: Optional[str] = None,
    ) -> None:
        """Update operation state after processing a user.

        Args:
            user_id: User ID that was processed
            interaction_count: Number of interactions processed for this user
            success: Whether processing succeeded
            total_users: Total users being processed (for percentage calculation)
            error: Error message if processing failed
        """
        state_entry = self.storage.get_operation_state(self.service_name)
        current_state = (
            state_entry.get("operation_state", state_entry) if state_entry else {}
        )

        if success:
            current_state["processed_users"] += 1
            current_state["processed_user_ids"].append(user_id)
            current_state["stats"]["total_interactions_processed"] += interaction_count
        else:
            current_state["failed_users"] += 1
            current_state["failed_user_ids"].append(
                {"user_id": user_id, "error": error}
            )

        current_state["current_user_id"] = None
        current_state["progress_percentage"] = (
            current_state["processed_users"] / total_users
        ) * 100

        self.storage.update_operation_state(self.service_name, current_state)

    def finalize(
        self, total_interactions_processed: int, total_generated: int = 0
    ) -> None:
        """Mark operation as COMPLETED and finalize state.

        Args:
            total_interactions_processed: Total number of interactions processed
            total_generated: Total number of profiles or feedbacks generated
        """
        state_entry = self.storage.get_operation_state(self.service_name)
        final_state = (
            state_entry.get("operation_state", state_entry) if state_entry else {}
        )
        final_state["status"] = OperationStatus.COMPLETED.value
        final_state["completed_at"] = int(datetime.now(timezone.utc).timestamp())
        final_state["progress_percentage"] = 100.0
        final_state["stats"][
            "total_interactions_processed"
        ] = total_interactions_processed
        final_state["stats"]["total_generated"] = total_generated
        self.storage.update_operation_state(self.service_name, final_state)

    def mark_failed(self, error_message: str) -> None:
        """Mark operation as FAILED with error message.

        Args:
            error_message: Error description
        """
        try:
            state_entry = self.storage.get_operation_state(self.service_name)
            if state_entry:
                failed_state = state_entry.get("operation_state", state_entry)
                failed_state["status"] = OperationStatus.FAILED.value
                failed_state["completed_at"] = int(
                    datetime.now(timezone.utc).timestamp()
                )
                failed_state["error_message"] = error_message
                self.storage.update_operation_state(self.service_name, failed_state)
        except Exception:
            pass  # Ignore errors updating state during exception handling
