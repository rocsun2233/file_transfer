from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    TASK_OFFER = "TASK_OFFER"
    TASK_ACCEPT = "TASK_ACCEPT"
    TASK_REJECT = "TASK_REJECT"
    CHUNK = "CHUNK"
    CHUNK_ACK = "CHUNK_ACK"
    RESUME_REQUEST = "RESUME_REQUEST"
    RESUME_STATE = "RESUME_STATE"
    TASK_COMPLETE = "TASK_COMPLETE"
    TASK_ERROR = "TASK_ERROR"


@dataclass
class ProtocolFrame:
    message_type: MessageType
    payload: dict[str, Any]


def encode_frame(frame: ProtocolFrame) -> bytes:
    body = json.dumps({"type": frame.message_type.value, "payload": frame.payload}).encode("utf-8")
    return struct.pack("!I", len(body)) + body


def decode_frame(encoded: bytes) -> ProtocolFrame:
    if len(encoded) < 4:
        raise ValueError("encoded frame too short")
    (size,) = struct.unpack("!I", encoded[:4])
    body = encoded[4 : 4 + size]
    data = json.loads(body.decode("utf-8"))
    return ProtocolFrame(MessageType(data["type"]), data["payload"])


class FrameSocket:
    def __init__(self, sock) -> None:
        self.sock = sock

    def send_frame(self, frame: ProtocolFrame) -> None:
        self.sock.sendall(encode_frame(frame))

    def recv_frame(self) -> ProtocolFrame:
        header = self._recv_exact(4)
        (size,) = struct.unpack("!I", header)
        body = self._recv_exact(size)
        return decode_frame(header + body)

    def _recv_exact(self, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            data = self.sock.recv(size - len(chunks))
            if not data:
                raise ConnectionError("socket closed during frame receive")
            chunks.extend(data)
        return bytes(chunks)
