from __future__ import annotations

import json
import platform
import socket
import time
import uuid
from threading import Event, Thread
from typing import Any

from .adapters import DiscoveryAdapter


def _normalize_platform() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system


class UdpDiscoveryAdapter(DiscoveryAdapter):
    def __init__(
        self,
        device_id: str | None = None,
        name: str | None = None,
        port: int = 9100,
        web_port: int | None = None,
    ) -> None:
        self.device_id = device_id or str(uuid.uuid4())
        self.name = name or platform.node() or "unknown-device"
        self.port = port
        self.web_port = web_port
        self.platform = _normalize_platform()

    def build_announcement(self) -> bytes:
        payload = {
            "device_id": self.device_id,
            "name": self.name,
            "port": self.port,
            "platform": self.platform,
            "timestamp": int(time.time()),
            "source": "lan",
        }
        if self.web_port is not None:
            payload["web_port"] = self.web_port
        return json.dumps(payload).encode("utf-8")

    def parse_announcement(self, payload: bytes, address: tuple[str, int]) -> dict[str, Any]:
        decoded = json.loads(payload.decode("utf-8"))
        decoded["address"] = address[0]
        decoded.setdefault("source", "lan")
        return decoded

    def open_broadcast_socket(self, broadcast_port: int) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.2)
        sock.bind(("", broadcast_port))
        return sock


class DiscoveryRegistry:
    def __init__(self) -> None:
        self._devices: dict[str, dict[str, Any]] = {}

    def record_discovered(self, peer: dict[str, Any]) -> None:
        self._devices[peer["device_id"]] = peer

    def add_manual(self, name: str, address: str, port: int, platform: str = "unknown") -> dict[str, Any]:
        peer_id = f"manual-{address}:{port}"
        peer = {
            "device_id": peer_id,
            "name": name,
            "address": address,
            "port": port,
            "platform": platform,
            "source": "manual",
        }
        self._devices[peer_id] = peer
        return peer

    def list_devices(self) -> list[dict[str, Any]]:
        return sorted(self._devices.values(), key=lambda item: (item["source"], item["name"]))

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        return self._devices.get(device_id)


class DiscoveryService:
    def __init__(self, adapter: UdpDiscoveryAdapter, registry: DiscoveryRegistry, broadcast_port: int = 54545) -> None:
        self.adapter = adapter
        self.registry = registry
        self.broadcast_port = broadcast_port
        self._stop_event = Event()
        self._thread: Thread | None = None

    def handle_packet(self, payload: bytes, address: tuple[str, int]) -> dict[str, Any]:
        peer = self.adapter.parse_announcement(payload, address)
        self.registry.record_discovered(peer)
        return peer

    def announce_once(self) -> None:
        payload = self.adapter.build_announcement()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(payload, ("255.255.255.255", self.broadcast_port))
        finally:
            sock.close()

    def listen_once(self) -> None:
        sock = self.adapter.open_broadcast_socket(self.broadcast_port)
        try:
            payload, address = sock.recvfrom(65535)
            self.handle_packet(payload, address)
        finally:
            sock.close()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def loop() -> None:
            while not self._stop_event.is_set():
                try:
                    self.announce_once()
                    self.listen_once()
                except OSError:
                    time.sleep(0.2)

        self._stop_event.clear()
        self._thread = Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
