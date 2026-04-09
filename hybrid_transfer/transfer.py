from __future__ import annotations

import base64
import hashlib
import os
import socket
import threading
from pathlib import Path
from typing import Any, Callable

from .resume import ResumeIndex
from .tasks import ConflictPolicy, TaskManager, TaskState
from .transfer_protocol import FrameSocket, MessageType, ProtocolFrame
from .trust import TrustManager


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class TcpTransferServer:
    def __init__(
        self,
        host: str,
        port: int,
        peer_id: str,
        trust_manager: TrustManager,
        task_manager: TaskManager,
        shared_dir: Path,
        default_conflict_policy: ConflictPolicy = ConflictPolicy.OVERWRITE,
        auto_accept: bool = True,
        offer_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.peer_id = peer_id
        self.trust_manager = trust_manager
        self.task_manager = task_manager
        self.shared_dir = Path(shared_dir)
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        self.resume_index = ResumeIndex(task_manager.store)
        self.default_conflict_policy = default_conflict_policy
        self.auto_accept = auto_accept
        self.offer_handler = offer_handler
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = threading.Event()
        self._plans: dict[str, dict[str, Any]] = {}

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind((self.host, self.port))
        self._sock.listen()
        self._sock.settimeout(0.2)
        self.port = self._sock.getsockname()[1]
        self._running.set()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        assert self._sock is not None
        while self._running.is_set():
            try:
                conn, _ = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()

    def _handle_client(self, conn: socket.socket) -> None:
        with conn:
            frame_socket = FrameSocket(conn)
            try:
                offer = frame_socket.recv_frame()
                if offer.message_type != MessageType.TASK_OFFER:
                    frame_socket.send_frame(ProtocolFrame(MessageType.TASK_ERROR, {"reason": "expected offer"}))
                    return
                self._handle_offer(frame_socket, offer.payload)
                while True:
                    frame = frame_socket.recv_frame()
                    if frame.message_type == MessageType.CHUNK:
                        self._handle_chunk(frame_socket, frame.payload)
                    elif frame.message_type == MessageType.TASK_COMPLETE:
                        self._handle_complete(frame_socket, frame.payload)
                        return
                    else:
                        frame_socket.send_frame(ProtocolFrame(MessageType.TASK_ERROR, {"reason": "unexpected message"}))
                        return
            except ConnectionError:
                return

    def _handle_offer(self, frame_socket: FrameSocket, payload: dict[str, Any]) -> None:
        peer_id = payload["peer_id"]
        task_id = payload["task_id"]
        files = payload["files"]
        if not self.trust_manager.is_trusted(peer_id):
            frame_socket.send_frame(ProtocolFrame(MessageType.TASK_REJECT, {"reason": "untrusted peer"}))
            return
        decision = {
            "accepted": self.auto_accept,
            "conflict_policy": self.default_conflict_policy.value,
            "reason": "receiver rejected task",
        }
        if self.offer_handler is not None:
            decision.update(self.offer_handler({"task_id": task_id, "peer_id": peer_id, "files": files}))
        if not decision["accepted"]:
            frame_socket.send_frame(ProtocolFrame(MessageType.TASK_REJECT, {"reason": decision.get("reason", "receiver rejected task")}))
            return
        conflict_policy = ConflictPolicy(decision.get("conflict_policy", self.default_conflict_policy.value))
        plan = []
        self.resume_index.prepare_task(task_id, files)
        for item in files:
            relative_path = item["relative_path"]
            target_relative_path = self._resolve_conflict(relative_path, conflict_policy)
            if target_relative_path is None:
                plan.append({"relative_path": relative_path, "status": "skip", "offset": 0, "target_relative_path": relative_path})
                continue
            final_path = self.shared_dir / target_relative_path
            temp_path = self.shared_dir / ".incoming" / task_id / f"{target_relative_path}.part"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            current_offset = 0
            if temp_path.exists():
                current_offset = temp_path.stat().st_size
            elif final_path.exists() and self.default_conflict_policy == ConflictPolicy.OVERWRITE:
                current_offset = 0
            self.resume_index.record_chunk(task_id, relative_path, current_offset, temp_path, final_path)
            plan.append(
                {
                    "relative_path": relative_path,
                    "target_relative_path": target_relative_path,
                    "status": "accept",
                    "offset": current_offset,
                }
            )
        self._plans[task_id] = {entry["relative_path"]: entry for entry in plan}
        frame_socket.send_frame(ProtocolFrame(MessageType.TASK_ACCEPT, {"task_id": task_id, "files": plan}))

    def _resolve_conflict(self, relative_path: str, policy: ConflictPolicy) -> str | None:
        target = self.shared_dir / relative_path
        if not target.exists():
            return relative_path
        return self.task_manager.resolve_conflict(relative_path, policy)

    def _handle_chunk(self, frame_socket: FrameSocket, payload: dict[str, Any]) -> None:
        task_id = payload["task_id"]
        relative_path = payload["relative_path"]
        plan = self._plans[task_id][relative_path]
        if plan["status"] == "skip":
            frame_socket.send_frame(ProtocolFrame(MessageType.CHUNK_ACK, {"task_id": task_id, "relative_path": relative_path, "bytes_received": 0}))
            return
        target_relative_path = plan["target_relative_path"]
        temp_path = self.shared_dir / ".incoming" / task_id / f"{target_relative_path}.part"
        final_path = self.shared_dir / target_relative_path
        chunk_data = base64.b64decode(payload["data"].encode("ascii"))
        offset = int(payload["offset"])
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "r+b" if temp_path.exists() else "wb"
        with temp_path.open(mode) as handle:
            handle.seek(offset)
            handle.write(chunk_data)
        bytes_received = max(temp_path.stat().st_size, offset + len(chunk_data))
        self.resume_index.record_chunk(task_id, relative_path, bytes_received, temp_path, final_path)
        frame_socket.send_frame(
            ProtocolFrame(
                MessageType.CHUNK_ACK,
                {"task_id": task_id, "relative_path": relative_path, "bytes_received": bytes_received},
            )
        )

    def _handle_complete(self, frame_socket: FrameSocket, payload: dict[str, Any]) -> None:
        task_id = payload["task_id"]
        files = payload["files"]
        for item in files:
            relative_path = item["relative_path"]
            plan = self._plans[task_id][relative_path]
            if plan["status"] == "skip":
                continue
            target_relative_path = plan["target_relative_path"]
            temp_path = self.shared_dir / ".incoming" / task_id / f"{target_relative_path}.part"
            final_path = self.shared_dir / target_relative_path
            final_path.parent.mkdir(parents=True, exist_ok=True)
            if final_path.exists():
                final_path.unlink()
            os.replace(temp_path, final_path)
            self.resume_index.mark_complete(task_id, relative_path)
        self.resume_index.clear_task(task_id)
        frame_socket.send_frame(ProtocolFrame(MessageType.TASK_COMPLETE, {"task_id": task_id, "status": "ok"}))

    def close(self) -> None:
        self._running.clear()
        if self._sock is not None:
            self._sock.close()
        if self._thread is not None:
            self._thread.join(timeout=1)


class TransferCoordinator:
    def __init__(
        self,
        peer_id: str,
        task_manager: TaskManager,
        trust_manager: TrustManager,
        state_store,
        destination_resolver: Callable[[str], tuple[str, int]],
        chunk_size: int = 65536,
    ) -> None:
        self.peer_id = peer_id
        self.task_manager = task_manager
        self.trust_manager = trust_manager
        self.state_store = state_store
        self.destination_resolver = destination_resolver
        self.chunk_size = chunk_size
        self.resume_index = ResumeIndex(state_store)

    def prepare_task(self, peer_id: str, source_paths: list[Path]) -> dict[str, Any]:
        items = self._expand_paths(source_paths)
        task = self.task_manager.create_task(
            peer_id=peer_id,
            items=items,
            state=TaskState.PENDING,
            retry_count=0,
        )
        return task

    def send_paths(self, peer_id: str, source_paths: list[Path]) -> dict[str, Any]:
        task = self.prepare_task(peer_id, source_paths)
        return self.send_task(task)

    def retry_task(self, task_id: str) -> dict[str, Any]:
        task = self.state_store.state["tasks"][task_id]
        task["retry_count"] = int(task.get("retry_count", 0)) + 1
        self.state_store.save_task(task)
        return self.send_task(task)

    def send_task(self, task: dict[str, Any], simulate_disconnect_after_chunks: int | None = None) -> dict[str, Any]:
        host, port = self.destination_resolver(task["peer_id"])
        self.task_manager.set_state(task["id"], TaskState.AWAITING_ACCEPT)
        try:
            with socket.create_connection((host, port), timeout=2) as conn:
                frame_socket = FrameSocket(conn)
                files = [
                    {
                        "relative_path": item["relative_path"],
                        "size": item["size"],
                        "sha256": item["sha256"],
                    }
                    for item in task["items"]
                    if item["kind"] == "file"
                ]
                frame_socket.send_frame(
                    ProtocolFrame(
                        MessageType.TASK_OFFER,
                        {
                            "task_id": task["id"],
                            "peer_id": self.peer_id,
                            "files": files,
                        },
                    )
                )
                response = frame_socket.recv_frame()
                if response.message_type == MessageType.TASK_REJECT:
                    self.task_manager.fail_task(task["id"], response.payload["reason"])
                    raise RuntimeError(f"rejected: {response.payload['reason']}")
                if response.message_type != MessageType.TASK_ACCEPT:
                    raise RuntimeError("unexpected accept response")
                plans = {entry["relative_path"]: entry for entry in response.payload["files"]}
                self.task_manager.set_state(task["id"], TaskState.IN_PROGRESS)
                chunks_sent = 0
                bytes_done = 0
                for item in task["items"]:
                    if item["kind"] != "file":
                        continue
                    plan = plans[item["relative_path"]]
                    if plan["status"] == "skip":
                        continue
                    offset = int(plan.get("offset", 0))
                    with Path(item["source_path"]).open("rb") as handle:
                        handle.seek(offset)
                        position = offset
                        while True:
                            data = handle.read(self.chunk_size)
                            if not data:
                                break
                            frame_socket.send_frame(
                                ProtocolFrame(
                                    MessageType.CHUNK,
                                    {
                                        "task_id": task["id"],
                                        "relative_path": item["relative_path"],
                                        "offset": position,
                                        "data": base64.b64encode(data).decode("ascii"),
                                    },
                                )
                            )
                            ack = frame_socket.recv_frame()
                            if ack.message_type != MessageType.CHUNK_ACK:
                                raise RuntimeError("expected chunk acknowledgement")
                            position += len(data)
                            bytes_done += len(data)
                            chunks_sent += 1
                            self.task_manager.update_progress(task["id"], bytes_done, TaskState.IN_PROGRESS)
                            if simulate_disconnect_after_chunks and chunks_sent >= simulate_disconnect_after_chunks:
                                raise ConnectionError("simulated disconnect")
                frame_socket.send_frame(
                    ProtocolFrame(
                        MessageType.TASK_COMPLETE,
                        {"task_id": task["id"], "files": files},
                    )
                )
                done = frame_socket.recv_frame()
                if done.message_type != MessageType.TASK_COMPLETE:
                    raise RuntimeError("expected completion acknowledgement")
                return self.task_manager.complete_task(task["id"])
        except ConnectionError as exc:
            self.task_manager.mark_retryable(task["id"], str(exc))
            if "simulated disconnect" in str(exc):
                return self.state_store.state["tasks"][task["id"]]
            raise
        except OSError as exc:
            self.task_manager.mark_retryable(task["id"], str(exc))
            raise

    def _expand_paths(self, source_paths: list[Path]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for source in [Path(path) for path in source_paths]:
            if source.is_dir():
                for child in sorted(source.rglob("*")):
                    if child.is_file():
                        relative_path = str(Path(source.name) / child.relative_to(source))
                        items.append(self._file_item(child, relative_path))
            else:
                items.append(self._file_item(source, source.name))
        return items

    def _file_item(self, source: Path, relative_path: str) -> dict[str, Any]:
        stat = source.stat()
        return {
            "kind": "file",
            "path": str(source),
            "source_path": str(source),
            "relative_path": relative_path.replace("\\", "/"),
            "size": stat.st_size,
            "modified_at": int(stat.st_mtime),
            "sha256": _sha256(source),
        }
