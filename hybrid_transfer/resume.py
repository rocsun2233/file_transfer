from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .persistence import JsonStateStore


class ResumeIndex:
    def __init__(self, store: JsonStateStore) -> None:
        self.store = store

    def prepare_task(self, task_id: str, files: list[dict[str, Any]]) -> dict[str, Any]:
        current = self.store.state["resume_index"].get(task_id, {"files": {}})
        file_map = current.get("files", {})
        for item in files:
            relative_path = item["relative_path"]
            file_map.setdefault(
                relative_path,
                {
                    "bytes_received": 0,
                    "size": item["size"],
                    "temp_path": None,
                    "final_path": None,
                    "completed": False,
                    "updated_at": int(time.time()),
                },
            )
        payload = {"files": file_map, "updated_at": int(time.time())}
        self.store.save_resume_index(task_id, payload)
        return payload

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.store.state["resume_index"].get(task_id, {"files": {}})

    def get_offset(self, task_id: str, relative_path: str) -> int:
        return int(self.get_task(task_id)["files"].get(relative_path, {}).get("bytes_received", 0))

    def record_chunk(
        self,
        task_id: str,
        relative_path: str,
        bytes_received: int,
        temp_path: Path,
        final_path: Path,
    ) -> None:
        task = self.get_task(task_id)
        files = task.setdefault("files", {})
        entry = files.setdefault(relative_path, {})
        entry.update(
            {
                "bytes_received": bytes_received,
                "temp_path": str(temp_path),
                "final_path": str(final_path),
                "updated_at": int(time.time()),
            }
        )
        self.store.save_resume_index(task_id, task)

    def mark_complete(self, task_id: str, relative_path: str) -> None:
        task = self.get_task(task_id)
        entry = task.setdefault("files", {}).setdefault(relative_path, {})
        entry["completed"] = True
        entry["updated_at"] = int(time.time())
        self.store.save_resume_index(task_id, task)

    def clear_task(self, task_id: str) -> None:
        self.store.delete_resume_index(task_id)
