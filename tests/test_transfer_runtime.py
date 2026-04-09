import socket
import tempfile
import time
import unittest
from pathlib import Path

from hybrid_transfer.persistence import JsonStateStore
from hybrid_transfer.tasks import ConflictPolicy, TaskManager, TaskState
from hybrid_transfer.trust import TrustManager
from hybrid_transfer.transfer import TransferCoordinator, TcpTransferServer
from hybrid_transfer.transfer_protocol import MessageType, ProtocolFrame, decode_frame, encode_frame


def wait_for(predicate, timeout: float = 2.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met before timeout")


class ProtocolTests(unittest.TestCase):
    def test_protocol_frame_round_trip_preserves_message_type_and_payload(self) -> None:
        frame = ProtocolFrame(MessageType.TASK_OFFER, {"task_id": "task-1", "files": [{"path": "a.txt"}]})

        encoded = encode_frame(frame)
        decoded = decode_frame(encoded)

        self.assertEqual(decoded.message_type, MessageType.TASK_OFFER)
        self.assertEqual(decoded.payload["task_id"], "task-1")
        self.assertEqual(decoded.payload["files"][0]["path"], "a.txt")


class TransferRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)

        self.sender_store = JsonStateStore(self.base / "sender" / "state.json")
        self.receiver_store = JsonStateStore(self.base / "receiver" / "state.json")
        self.sender_tasks = TaskManager(self.sender_store)
        self.receiver_tasks = TaskManager(self.receiver_store)
        self.sender_trust = TrustManager(self.sender_store)
        self.receiver_trust = TrustManager(self.receiver_store)
        self.sender_trust.approve("receiver-peer", {"name": "Receiver"})
        self.receiver_trust.approve("sender-peer", {"name": "Sender"})

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _start_server(self, acceptance_policy=ConflictPolicy.OVERWRITE, auto_accept=True) -> TcpTransferServer:
        destination = self.base / "receiver" / "shared"
        server = TcpTransferServer(
            host="127.0.0.1",
            port=0,
            peer_id="receiver-peer",
            trust_manager=self.receiver_trust,
            task_manager=self.receiver_tasks,
            shared_dir=destination,
            default_conflict_policy=acceptance_policy,
            auto_accept=auto_accept,
        )
        server.start()
        return server

    def _make_sender(self, port: int, chunk_size: int = 8) -> TransferCoordinator:
        return TransferCoordinator(
            peer_id="sender-peer",
            task_manager=self.sender_tasks,
            trust_manager=self.sender_trust,
            state_store=self.sender_store,
            chunk_size=chunk_size,
            destination_resolver=lambda peer_id: ("127.0.0.1", port),
        )

    def test_loopback_transfer_moves_single_file_and_marks_task_complete(self) -> None:
        source = self.base / "sender" / "hello.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("hello over tcp", encoding="utf-8")

        server = self._start_server()
        sender = self._make_sender(server.port)
        try:
            task = sender.send_paths("receiver-peer", [source])
            wait_for(lambda: (self.base / "receiver" / "shared" / "hello.txt").exists())
        finally:
            server.close()

        received = (self.base / "receiver" / "shared" / "hello.txt").read_text(encoding="utf-8")
        self.assertEqual(received, "hello over tcp")
        self.assertEqual(self.sender_store.state["tasks"][task["id"]]["state"], TaskState.COMPLETED.value)

    def test_loopback_transfer_preserves_folder_structure_for_batch_task(self) -> None:
        folder = self.base / "sender" / "photos"
        nested = folder / "trip"
        nested.mkdir(parents=True, exist_ok=True)
        (folder / "cover.jpg").write_text("cover", encoding="utf-8")
        (nested / "day1.jpg").write_text("day1", encoding="utf-8")

        server = self._start_server()
        sender = self._make_sender(server.port)
        try:
            sender.send_paths("receiver-peer", [folder])
            wait_for(lambda: (self.base / "receiver" / "shared" / "photos" / "trip" / "day1.jpg").exists())
        finally:
            server.close()

        self.assertEqual(
            (self.base / "receiver" / "shared" / "photos" / "cover.jpg").read_text(encoding="utf-8"),
            "cover",
        )
        self.assertEqual(
            (self.base / "receiver" / "shared" / "photos" / "trip" / "day1.jpg").read_text(encoding="utf-8"),
            "day1",
        )

    def test_receiver_may_reject_task_before_file_bytes_are_written(self) -> None:
        source = self.base / "sender" / "deny.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("nope", encoding="utf-8")

        server = self._start_server(auto_accept=False)
        sender = self._make_sender(server.port)
        try:
            with self.assertRaisesRegex(RuntimeError, "rejected"):
                sender.send_paths("receiver-peer", [source])
        finally:
            server.close()

        self.assertFalse((self.base / "receiver" / "shared" / "deny.txt").exists())

    def test_resume_retransmits_only_missing_bytes_after_interruption(self) -> None:
        source = self.base / "sender" / "resume.bin"
        source.parent.mkdir(parents=True, exist_ok=True)
        payload = b"abcdefghijklmnopqrstuvwxyz"
        source.write_bytes(payload)

        server = self._start_server()
        sender = self._make_sender(server.port, chunk_size=5)
        try:
            task = sender.prepare_task("receiver-peer", [source])
            sender.send_task(task, simulate_disconnect_after_chunks=2)
            self.assertEqual(self.sender_store.state["tasks"][task["id"]]["state"], TaskState.RETRYABLE.value)

            sender.retry_task(task["id"])
            wait_for(lambda: (self.base / "receiver" / "shared" / "resume.bin").exists())
        finally:
            server.close()

        self.assertEqual((self.base / "receiver" / "shared" / "resume.bin").read_bytes(), payload)
        self.assertEqual(self.sender_store.state["tasks"][task["id"]]["state"], TaskState.COMPLETED.value)

    def test_conflict_policy_rename_preserves_existing_destination_file(self) -> None:
        source = self.base / "sender" / "report.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("incoming", encoding="utf-8")
        destination = self.base / "receiver" / "shared"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "report.txt").write_text("existing", encoding="utf-8")

        server = self._start_server(acceptance_policy=ConflictPolicy.RENAME)
        sender = self._make_sender(server.port)
        try:
            sender.send_paths("receiver-peer", [source])
            wait_for(lambda: (destination / "report (copy).txt").exists())
        finally:
            server.close()

        self.assertEqual((destination / "report.txt").read_text(encoding="utf-8"), "existing")
        self.assertEqual((destination / "report (copy).txt").read_text(encoding="utf-8"), "incoming")

    def test_retryable_task_can_be_replayed_after_temporary_connection_failure(self) -> None:
        source = self.base / "sender" / "retry.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("retry content", encoding="utf-8")

        free_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        free_socket.bind(("127.0.0.1", 0))
        port = free_socket.getsockname()[1]
        free_socket.close()

        sender = self._make_sender(port)
        task = sender.prepare_task("receiver-peer", [source])

        with self.assertRaises(OSError):
            sender.send_task(task)

        self.assertEqual(self.sender_store.state["tasks"][task["id"]]["state"], TaskState.RETRYABLE.value)

        server = self._start_server()
        sender = self._make_sender(server.port)
        try:
            sender.retry_task(task["id"])
            wait_for(lambda: (self.base / "receiver" / "shared" / "retry.txt").exists())
        finally:
            server.close()

        self.assertEqual((self.base / "receiver" / "shared" / "retry.txt").read_text(encoding="utf-8"), "retry content")


if __name__ == "__main__":
    unittest.main()
