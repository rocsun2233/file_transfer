from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DiscoveryAdapter(ABC):
    @abstractmethod
    def build_announcement(self) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def parse_announcement(self, payload: bytes, address: tuple[str, int]) -> dict[str, Any]:
        raise NotImplementedError


class TransferAdapter(ABC):
    @abstractmethod
    def start_transfer(self, task: dict[str, Any]) -> None:
        raise NotImplementedError


class WebGateway(ABC):
    @abstractmethod
    def serve_forever(self) -> None:
        raise NotImplementedError
