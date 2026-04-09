from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonStateStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _default_state(self) -> dict[str, Any]:
        return {
            "trusted_peers": {},
            "tasks": {},
            "history": [],
            "resume_index": {},
            "settings": {
                "shared_dir": "shared",
                "default_conflict_policy": "overwrite",
                "auto_accept_trusted": True,
                "manual_port": 9102,
            },
            "selected_device_id": None,
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default_state()
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        state = self._default_state()
        state.update(data)
        return state

    def _flush(self) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self.state, handle, indent=2, sort_keys=True)

    def upsert_trusted_peer(self, peer_id: str, peer: dict[str, Any]) -> None:
        self.state["trusted_peers"][peer_id] = peer
        self._flush()

    def remove_trusted_peer(self, peer_id: str) -> None:
        self.state["trusted_peers"].pop(peer_id, None)
        self._flush()

    def save_task(self, task: dict[str, Any]) -> None:
        self.state["tasks"][task["id"]] = task
        self._flush()

    def append_history(self, entry: dict[str, Any]) -> None:
        self.state["history"].append(entry)
        self._flush()

    def save_resume_index(self, task_id: str, resume_data: dict[str, Any]) -> None:
        self.state["resume_index"][task_id] = resume_data
        self._flush()

    def delete_resume_index(self, task_id: str) -> None:
        self.state["resume_index"].pop(task_id, None)
        self._flush()

    def save_settings(self, settings: dict[str, Any]) -> None:
        self.state["settings"] = settings
        self._flush()

    def save_selected_device(self, device_id: str | None) -> None:
        self.state["selected_device_id"] = device_id
        self._flush()
