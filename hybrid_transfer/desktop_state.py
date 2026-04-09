from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DesktopViewState:
    devices: list[dict[str, Any]]
    active_tasks: list[dict[str, Any]]
    history: list[dict[str, Any]]
    settings: dict[str, Any]
    access_endpoints: dict[str, Any]
    selected_device_id: str | None
    pending_offers: list[dict[str, Any]]
    pending_guest_sessions: list[dict[str, Any]]


class DesktopAppState:
    def __init__(self, core_service) -> None:
        self.core = core_service

    def snapshot(self) -> DesktopViewState:
        return DesktopViewState(
            devices=self.core.list_devices(),
            active_tasks=self._map_tasks(self.core.list_active_tasks()),
            history=self.core.list_history(),
            settings=self.core.get_settings(),
            access_endpoints=self.core.get_access_endpoints(),
            selected_device_id=self.core.get_selected_device_id(),
            pending_offers=self.core.list_pending_incoming_offers(),
            pending_guest_sessions=self.core.list_pending_guest_sessions(),
        )

    def _map_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mapped = []
        for task in tasks:
            mapped.append(
                {
                    "id": task["id"],
                    "peer_id": task["peer_id"],
                    "state": task["state"],
                    "progress": f"{task.get('bytes_done', 0)}/{task.get('total_bytes', 0)}",
                    "item_count": len(task.get("items", [])),
                    "retryable": task["state"] == "retryable",
                }
            )
        return mapped


class DesktopController:
    def __init__(self, core_service, app_state: DesktopAppState | None = None) -> None:
        self.core = core_service
        self.app_state = app_state or DesktopAppState(core_service)

    def select_device(self, device_id: str) -> None:
        self.core.select_device(device_id)

    def add_manual_device(self, name: str, address: str, port: int) -> dict[str, Any]:
        if not address.strip():
            raise ValueError("invalid manual address")
        return self.core.manual_connect(name=name, address=address, port=port)

    def update_settings(self, **updates: Any) -> dict[str, Any]:
        settings = self.core.get_settings()
        settings.update(updates)
        if "shared_dir" in settings:
            shared_dir = Path(settings["shared_dir"])
            if shared_dir.exists() and not shared_dir.is_dir():
                raise ValueError("shared directory is not writable")
        self.core.update_settings(settings)
        return self.core.get_settings()

    def send_paths(self, paths: list[str | Path]) -> dict[str, Any]:
        if not self.core.get_selected_device_id():
            raise ValueError("missing target device")
        return self.core.send_paths_to_selected([Path(path) for path in paths])

    def handle_drop(self, payload: str) -> dict[str, Any]:
        paths = [Path(item.strip()) for item in payload.splitlines() if item.strip()]
        return self.send_paths(paths)

    def retry_task(self, task_id: str) -> dict[str, Any]:
        return self.core.retry_task(task_id)

    def accept_incoming(self, offer_id: str, conflict_policy: str) -> None:
        self.core.resolve_incoming_offer(offer_id, accept=True, conflict_policy=conflict_policy)

    def reject_incoming(self, offer_id: str) -> None:
        self.core.resolve_incoming_offer(offer_id, accept=False)

    def approve_guest_session(self, token: str) -> None:
        self.core.approve_guest_session(token)
