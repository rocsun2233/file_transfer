from __future__ import annotations

import secrets
from typing import Any

from .persistence import JsonStateStore


class TrustManager:
    def __init__(self, store: JsonStateStore) -> None:
        self.store = store
        self._pending_codes: dict[str, str] = {}

    def start_pairing(self, peer_id: str, name: str) -> dict[str, Any]:
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        self._pending_codes[peer_id] = code
        return {
            "peer_id": peer_id,
            "name": name,
            "requires_confirmation": True,
            "pairing_code": code,
        }

    def validate_pairing_code(self, peer_id: str, code: str) -> bool:
        expected = self._pending_codes.get(peer_id)
        if expected != code:
            return False
        self.store.upsert_trusted_peer(peer_id, {"peer_id": peer_id, "approved": True})
        self._pending_codes.pop(peer_id, None)
        return True

    def approve(self, peer_id: str, metadata: dict[str, Any] | None = None) -> None:
        peer = {"peer_id": peer_id, "approved": True}
        if metadata:
            peer.update(metadata)
        self.store.upsert_trusted_peer(peer_id, peer)

    def is_trusted(self, peer_id: str) -> bool:
        return peer_id in self.store.state["trusted_peers"]

    def revoke(self, peer_id: str) -> None:
        self.store.remove_trusted_peer(peer_id)
