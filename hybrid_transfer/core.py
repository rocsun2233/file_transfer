from __future__ import annotations

import threading
import socket
from pathlib import Path
from typing import Any

from .discovery import DiscoveryRegistry, DiscoveryService, UdpDiscoveryAdapter
from .persistence import JsonStateStore
from .tasks import ConflictPolicy, TaskManager, TaskState
from .transfer import TransferCoordinator, TcpTransferServer
from .trust import TrustManager
from .web import GuestAccessController, LocalWebGatewayServer


def resolve_access_hosts() -> list[str]:
    hosts: list[str] = []
    seen: set[str] = set()

    def add_host(candidate: str | None) -> None:
        if not candidate or candidate.startswith("127.") or ":" in candidate:
            return
        if candidate not in seen:
            seen.add(candidate)
            hosts.append(candidate)

    try:
        _, _, addresses = socket.gethostbyname_ex(socket.gethostname())
        for address in addresses:
            add_host(address)
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 1))
            add_host(probe.getsockname()[0])
    except OSError:
        pass

    if not hosts:
        hosts.append("127.0.0.1")
    return hosts


class CoreService:
    def __init__(
        self,
        state_path: str | Path,
        device_name: str = "Hybrid Transfer",
        port: int = 9100,
        bind_host: str = "0.0.0.0",
    ) -> None:
        self.state_path = Path(state_path)
        self.bind_host = bind_host
        self.discovery_port = port
        self.web_port = port + 1
        self.transfer_port = port + 2
        self.store = JsonStateStore(self.state_path)
        self.discovery = UdpDiscoveryAdapter(name=device_name, port=self.transfer_port, web_port=self.web_port)
        self.registry = DiscoveryRegistry()
        self.trust = TrustManager(self.store)
        self.tasks = TaskManager(self.store)
        self.guest_access = GuestAccessController(self.trust)
        self.discovery_service = DiscoveryService(self.discovery, self.registry)
        self._incoming_offers: dict[str, dict[str, Any]] = {}
        self.transfer_server = TcpTransferServer(
            host=self.bind_host,
            port=self.transfer_port,
            peer_id=device_name,
            trust_manager=self.trust,
            task_manager=self.tasks,
            shared_dir=self.shared_dir,
            default_conflict_policy=ConflictPolicy(self.get_settings()["default_conflict_policy"]),
            auto_accept=self.get_settings()["auto_accept_trusted"],
            offer_handler=self._handle_incoming_offer,
        )
        self.transfer_server.start()
        self.transfer_coordinator = TransferCoordinator(
            peer_id=device_name,
            task_manager=self.tasks,
            trust_manager=self.trust,
            state_store=self.store,
            destination_resolver=self.resolve_peer_endpoint,
        )
        self.web_gateway = LocalWebGatewayServer(
            self.bind_host,
            self.web_port,
            self.guest_access,
            self.tasks,
            shared_dir=self.shared_dir,
        )

    @property
    def shared_dir(self) -> Path:
        return self.state_path.parent / self.get_settings()["shared_dir"]

    def list_devices(self) -> list[dict[str, Any]]:
        return self.registry.list_devices()

    def get_access_endpoints(self) -> dict[str, Any]:
        addresses = []
        for host in resolve_access_hosts():
            label = "LAN" if not host.startswith("127.") else "Local"
            addresses.append(
                {
                    "label": label,
                    "host": host,
                    "web_url": f"http://{host}:{self.web_port}/",
                    "transfer_target": f"{host}:{self.transfer_port}",
                }
            )
        return {
            "bind_host": self.bind_host,
            "web_port": self.web_port,
            "transfer_port": self.transfer_port,
            "addresses": addresses,
        }

    def list_active_tasks(self) -> list[dict[str, Any]]:
        return sorted(self.store.state["tasks"].values(), key=lambda task: task.get("created_at", 0), reverse=True)

    def list_history(self) -> list[dict[str, Any]]:
        return list(reversed(self.tasks.list_history()))

    def get_settings(self) -> dict[str, Any]:
        return dict(self.store.state["settings"])

    def update_settings(self, settings: dict[str, Any]) -> None:
        self.store.save_settings(settings)
        self.transfer_server.default_conflict_policy = ConflictPolicy(settings["default_conflict_policy"])
        self.transfer_server.auto_accept = bool(settings["auto_accept_trusted"])

    def select_device(self, device_id: str) -> None:
        self.store.save_selected_device(device_id)

    def get_selected_device_id(self) -> str | None:
        return self.store.state.get("selected_device_id")

    def manual_connect(self, name: str, address: str, port: int, platform: str = "unknown") -> dict[str, Any]:
        peer = self.registry.add_manual(name=name, address=address, port=port, platform=platform)
        peer["web_port"] = max(port - 1, 1)
        return peer

    def resolve_peer_endpoint(self, peer_id: str) -> tuple[str, int]:
        device = self.registry.get_device(peer_id)
        if not device:
            raise ValueError(f"unknown target device: {peer_id}")
        return (device["address"], int(device["port"]))

    def start_pairing(self, peer_id: str, name: str) -> dict[str, Any]:
        return self.trust.start_pairing(peer_id, name)

    def list_pending_guest_sessions(self) -> list[dict[str, Any]]:
        return self.guest_access.list_pending_sessions()

    def approve_guest_session(self, token: str) -> None:
        self.guest_access.approve(token)

    def approve_pairing_code(self, peer_id: str, code: str) -> bool:
        return self.trust.validate_pairing_code(peer_id, code)

    def create_transfer_task(self, peer_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        return self.tasks.create_task(peer_id, items)

    def send_paths_to_selected(self, paths: list[Path]) -> dict[str, Any]:
        selected = self.get_selected_device_id()
        if not selected:
            raise ValueError("missing target device")
        return self.transfer_coordinator.send_paths(selected, paths)

    def retry_task(self, task_id: str) -> dict[str, Any]:
        return self.transfer_coordinator.retry_task(task_id)

    def mark_task_progress(self, task_id: str, bytes_done: int) -> dict[str, Any]:
        return self.tasks.update_progress(task_id, bytes_done, TaskState.IN_PROGRESS)

    def finish_task(self, task_id: str) -> dict[str, Any]:
        return self.tasks.complete_task(task_id)

    def resolve_conflict(self, filename: str, policy: str) -> str | None:
        return self.tasks.resolve_conflict(filename, ConflictPolicy(policy))

    def list_pending_incoming_offers(self) -> list[dict[str, Any]]:
        return [
            {
                "offer_id": offer_id,
                "task_id": offer["task_id"],
                "peer_id": offer["peer_id"],
                "file_count": len(offer["files"]),
                "conflict_policy": offer["conflict_policy"],
            }
            for offer_id, offer in self._incoming_offers.items()
        ]

    def resolve_incoming_offer(self, offer_id: str, accept: bool, conflict_policy: str | None = None) -> None:
        offer = self._incoming_offers[offer_id]
        offer["decision"] = {
            "accepted": accept,
            "conflict_policy": conflict_policy or offer["conflict_policy"],
            "reason": "receiver rejected task",
        }
        offer["event"].set()

    def _handle_incoming_offer(self, request: dict[str, Any]) -> dict[str, Any]:
        settings = self.get_settings()
        if settings["auto_accept_trusted"]:
            return {
                "accepted": True,
                "conflict_policy": settings["default_conflict_policy"],
            }
        offer_id = request["task_id"]
        event = threading.Event()
        self._incoming_offers[offer_id] = {
            "task_id": request["task_id"],
            "peer_id": request["peer_id"],
            "files": request["files"],
            "conflict_policy": settings["default_conflict_policy"],
            "event": event,
            "decision": None,
        }
        event.wait(timeout=30)
        offer = self._incoming_offers.pop(offer_id, None)
        if not offer or not offer["decision"]:
            return {
                "accepted": False,
                "conflict_policy": settings["default_conflict_policy"],
                "reason": "receiver rejected task",
            }
        return offer["decision"]
