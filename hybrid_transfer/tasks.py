from __future__ import annotations

import os
import time
import uuid
from enum import Enum
from typing import Any

from .persistence import JsonStateStore


class TaskState(str, Enum):
    PENDING = "pending"
    AWAITING_ACCEPT = "awaiting_accept"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYABLE = "retryable"


class ConflictPolicy(str, Enum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    RENAME = "rename"


class TaskManager:
    def __init__(self, store: JsonStateStore) -> None:
        self.store = store

    def create_task(
        self,
        peer_id: str,
        items: list[dict[str, Any]],
        task_id: str | None = None,
        state: TaskState = TaskState.PENDING,
        **extra: Any,
    ) -> dict[str, Any]:
        total_bytes = sum(int(item.get("size", 0)) for item in items)
        task = {
            "id": task_id or str(uuid.uuid4()),
            "peer_id": peer_id,
            "items": items,
            "total_bytes": total_bytes,
            "bytes_done": 0,
            "state": state.value,
            "created_at": int(time.time()),
        }
        task.update(extra)
        self.store.save_task(task)
        return task

    def update_progress(self, task_id: str, bytes_done: int, state: TaskState) -> dict[str, Any]:
        task = self.store.state["tasks"][task_id]
        task["bytes_done"] = bytes_done
        task["state"] = state.value
        task["updated_at"] = int(time.time())
        self.store.save_task(task)
        return task

    def set_state(self, task_id: str, state: TaskState, **updates: Any) -> dict[str, Any]:
        task = self.store.state["tasks"][task_id]
        task["state"] = state.value
        task["updated_at"] = int(time.time())
        task.update(updates)
        self.store.save_task(task)
        return task

    def complete_task(self, task_id: str) -> dict[str, Any]:
        task = self.store.state["tasks"][task_id]
        task["bytes_done"] = task["total_bytes"]
        task["state"] = TaskState.COMPLETED.value
        task["completed_at"] = int(time.time())
        self.store.save_task(task)
        self.store.append_history(
            {
                "task_id": task_id,
                "peer_id": task["peer_id"],
                "state": TaskState.COMPLETED.value,
                "completed_at": task["completed_at"],
            }
        )
        return task

    def fail_task(self, task_id: str, reason: str) -> dict[str, Any]:
        task = self.store.state["tasks"][task_id]
        task["state"] = TaskState.FAILED.value
        task["error"] = reason
        task["updated_at"] = int(time.time())
        self.store.save_task(task)
        return task

    def mark_retryable(self, task_id: str, reason: str) -> dict[str, Any]:
        return self.set_state(task_id, TaskState.RETRYABLE, error=reason)

    def resolve_conflict(self, filename: str, policy: ConflictPolicy) -> str | None:
        if policy == ConflictPolicy.OVERWRITE:
            return filename
        if policy == ConflictPolicy.SKIP:
            return None
        stem, suffix = os.path.splitext(filename)
        return f"{stem} (copy){suffix}"

    def list_history(self) -> list[dict[str, Any]]:
        return list(self.store.state["history"])
