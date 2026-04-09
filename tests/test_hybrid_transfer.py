import json
from http.cookies import SimpleCookie
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from hybrid_transfer.core import CoreService
from hybrid_transfer.desktop_state import DesktopAppState
from hybrid_transfer.discovery import DiscoveryRegistry, DiscoveryService, UdpDiscoveryAdapter
from hybrid_transfer.persistence import JsonStateStore
from hybrid_transfer.tasks import ConflictPolicy, TaskManager, TaskState
from hybrid_transfer.trust import TrustManager
from hybrid_transfer.web import GuestAccessController, LocalWebGatewayServer, WebViewModel


class JsonStateStoreTests(unittest.TestCase):
    def test_store_persists_trusted_peers_tasks_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            store.upsert_trusted_peer("peer-a", {"name": "Peer A"})
            store.save_task({"id": "task-1", "state": "pending"})
            store.append_history({"task_id": "task-1", "state": "completed"})

            reloaded = JsonStateStore(Path(tmpdir) / "state.json")

            self.assertEqual(reloaded.state["trusted_peers"]["peer-a"]["name"], "Peer A")
            self.assertEqual(reloaded.state["tasks"]["task-1"]["state"], "pending")
            self.assertEqual(reloaded.state["history"][0]["task_id"], "task-1")


class DiscoveryTests(unittest.TestCase):
    def test_discovery_packet_round_trip_preserves_peer_metadata(self) -> None:
        adapter = UdpDiscoveryAdapter(device_id="dev-1", name="Laptop", port=9100)

        packet = adapter.build_announcement()
        decoded = adapter.parse_announcement(packet, address=("192.168.1.9", 9100))

        self.assertEqual(decoded["device_id"], "dev-1")
        self.assertEqual(decoded["name"], "Laptop")
        self.assertEqual(decoded["platform"], adapter.platform)
        self.assertEqual(decoded["address"], "192.168.1.9")

    def test_registry_keeps_discovered_and_manual_devices(self) -> None:
        registry = DiscoveryRegistry()
        registry.record_discovered(
            {
                "device_id": "peer-1",
                "name": "Office Mac",
                "address": "192.168.1.10",
                "port": 9100,
                "platform": "macos",
                "source": "lan",
            }
        )
        registry.add_manual(
            name="Fallback Host",
            address="10.0.0.22",
            port=9200,
            platform="linux",
        )

        devices = registry.list_devices()

        self.assertEqual(len(devices), 2)
        self.assertEqual({item["source"] for item in devices}, {"lan", "manual"})

    def test_discovery_service_emits_live_updates_from_packets(self) -> None:
        registry = DiscoveryRegistry()
        adapter = UdpDiscoveryAdapter(device_id="dev-1", name="Laptop", port=9100)
        service = DiscoveryService(adapter, registry)

        service.handle_packet(adapter.build_announcement(), ("192.168.1.9", 9100))

        devices = registry.list_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["address"], "192.168.1.9")


class TrustManagerTests(unittest.TestCase):
    def test_first_time_peer_requires_approval_or_pairing_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            manager = TrustManager(store)

            request = manager.start_pairing("peer-1", "Office PC")

            self.assertTrue(request["requires_confirmation"])
            self.assertEqual(manager.validate_pairing_code("peer-1", request["pairing_code"]), True)
            self.assertTrue(manager.is_trusted("peer-1"))

    def test_revoked_peer_returns_to_untrusted_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            manager = TrustManager(store)
            request = manager.start_pairing("peer-1", "Office PC")
            manager.validate_pairing_code("peer-1", request["pairing_code"])

            manager.revoke("peer-1")

            self.assertFalse(manager.is_trusted("peer-1"))


class TaskManagerTests(unittest.TestCase):
    def test_task_creation_records_files_and_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            manager = TaskManager(store)

            task = manager.create_task(
                peer_id="peer-1",
                items=[
                    {"path": "/tmp/report.pdf", "kind": "file", "size": 100},
                    {"path": "/tmp/photos", "kind": "folder", "size": 0},
                ],
            )

            self.assertEqual(task["peer_id"], "peer-1")
            self.assertEqual(len(task["items"]), 2)
            self.assertEqual(store.state["tasks"][task["id"]]["state"], TaskState.PENDING.value)

    def test_task_progress_and_resume_state_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            manager = TaskManager(store)
            task = manager.create_task(peer_id="peer-1", items=[{"path": "/tmp/a", "kind": "file", "size": 100}])

            manager.update_progress(task["id"], bytes_done=40, state=TaskState.IN_PROGRESS)

            reloaded = JsonStateStore(Path(tmpdir) / "state.json")
            self.assertEqual(reloaded.state["tasks"][task["id"]]["bytes_done"], 40)
            self.assertEqual(reloaded.state["tasks"][task["id"]]["state"], TaskState.IN_PROGRESS.value)

    def test_conflict_resolution_supports_supported_policies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            manager = TaskManager(store)

            self.assertEqual(manager.resolve_conflict("name.txt", ConflictPolicy.OVERWRITE), "name.txt")
            self.assertEqual(manager.resolve_conflict("name.txt", ConflictPolicy.SKIP), None)
            self.assertEqual(manager.resolve_conflict("name.txt", ConflictPolicy.RENAME), "name (copy).txt")

    def test_completed_tasks_are_added_to_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            manager = TaskManager(store)
            task = manager.create_task(peer_id="peer-1", items=[{"path": "/tmp/a", "kind": "file", "size": 100}])

            manager.complete_task(task["id"])

            self.assertEqual(store.state["history"][0]["task_id"], task["id"])
            self.assertEqual(store.state["history"][0]["state"], TaskState.COMPLETED.value)


class WebAccessTests(unittest.TestCase):
    def test_untrusted_guest_must_be_approved_before_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            trust = TrustManager(store)
            guest_access = GuestAccessController(trust)

            token = guest_access.create_guest_session("browser-1")

            self.assertFalse(guest_access.can_transfer(token))
            guest_access.approve(token)
            self.assertTrue(guest_access.can_transfer(token))

    def test_web_view_model_exposes_limited_browser_operations(self) -> None:
        model = WebViewModel(
            can_upload=True,
            can_download=True,
            can_manage_trust=False,
            recent_tasks=[{"task_id": "task-1", "state": "completed"}],
        )

        payload = json.loads(model.to_json())

        self.assertTrue(payload["can_upload"])
        self.assertTrue(payload["can_download"])
        self.assertFalse(payload["can_manage_trust"])
        self.assertEqual(payload["recent_tasks"][0]["task_id"], "task-1")

    def test_local_web_gateway_serves_recent_tasks_for_approved_guest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            trust = TrustManager(store)
            tasks = TaskManager(store)
            task = tasks.create_task(peer_id="peer-1", items=[{"path": "/tmp/a", "kind": "file", "size": 100}])
            tasks.complete_task(task["id"])

            guest_access = GuestAccessController(trust)
            token = guest_access.create_guest_session("browser-1")
            guest_access.approve(token)
            gateway = LocalWebGatewayServer("127.0.0.1", 0, guest_access, tasks, shared_dir=Path(tmpdir))
            server = gateway.server
            port = server.server_address[1]
            try:
                response = urllib.request.urlopen(
                    urllib.request.Request(
                        f"http://127.0.0.1:{port}/",
                        headers={"X-Guest-Token": token},
                    ),
                    timeout=1,
                )
                payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.server_close()

            self.assertTrue(payload["can_upload"])
            self.assertEqual(payload["recent_tasks"][0]["task_id"], task["id"])

    def test_mobile_browser_without_token_gets_pending_guest_session_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            trust = TrustManager(store)
            tasks = TaskManager(store)
            guest_access = GuestAccessController(trust)
            gateway = LocalWebGatewayServer("127.0.0.1", 0, guest_access, tasks, shared_dir=Path(tmpdir))
            server = gateway.server
            port = server.server_address[1]
            try:
                response = urllib.request.urlopen(
                    urllib.request.Request(
                        f"http://127.0.0.1:{port}/?mobile=1",
                        headers={"User-Agent": "Android"},
                    ),
                    timeout=1,
                )
                payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.server_close()

            self.assertEqual(payload["access_state"], "pending")
            self.assertIsNotNone(payload["guest_token"])
            self.assertEqual(len(guest_access.list_pending_sessions()), 1)

    def test_mobile_browser_session_uses_cookie_and_becomes_authorized_after_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            trust = TrustManager(store)
            tasks = TaskManager(store)
            guest_access = GuestAccessController(trust)
            gateway = LocalWebGatewayServer("127.0.0.1", 0, guest_access, tasks, shared_dir=Path(tmpdir))
            server = gateway.server
            port = server.server_address[1]
            try:
                first = urllib.request.urlopen(
                    urllib.request.Request(
                        f"http://127.0.0.1:{port}/?mobile=1",
                        headers={"User-Agent": "Android"},
                    ),
                    timeout=1,
                )
                first_payload = json.loads(first.read().decode("utf-8"))
                cookie = SimpleCookie()
                cookie.load(first.headers["Set-Cookie"])
                guest_access.approve(first_payload["guest_token"])

                second = urllib.request.urlopen(
                    urllib.request.Request(
                        f"http://127.0.0.1:{port}/?mobile=1",
                        headers={
                            "User-Agent": "Android",
                            "Cookie": f"guest_token={cookie['guest_token'].value}",
                        },
                    ),
                    timeout=1,
                )
                second_payload = json.loads(second.read().decode("utf-8"))
            finally:
                server.server_close()

            self.assertEqual(second_payload["access_state"], "authorized")
            self.assertTrue(second_payload["can_upload"])

    def test_plain_root_browser_visit_creates_pending_guest_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            trust = TrustManager(store)
            tasks = TaskManager(store)
            guest_access = GuestAccessController(trust)
            gateway = LocalWebGatewayServer("127.0.0.1", 0, guest_access, tasks, shared_dir=Path(tmpdir))
            server = gateway.server
            port = server.server_address[1]
            try:
                response = urllib.request.urlopen(
                    urllib.request.Request(f"http://127.0.0.1:{port}/"),
                    timeout=1,
                )
                body = response.read().decode("utf-8")
            finally:
                server.server_close()

            self.assertIn("Waiting for approval", body)
            self.assertEqual(len(guest_access.list_pending_sessions()), 1)

    def test_invalid_cookie_token_creates_fresh_pending_guest_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            trust = TrustManager(store)
            tasks = TaskManager(store)
            guest_access = GuestAccessController(trust)
            gateway = LocalWebGatewayServer("127.0.0.1", 0, guest_access, tasks, shared_dir=Path(tmpdir))
            server = gateway.server
            port = server.server_address[1]
            try:
                response = urllib.request.urlopen(
                    urllib.request.Request(
                        f"http://127.0.0.1:{port}/",
                        headers={"Cookie": "guest_token=stale-token"},
                    ),
                    timeout=1,
                )
                payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.server_close()

            self.assertFalse(payload["can_upload"])
            self.assertEqual(len(guest_access.list_pending_sessions()), 1)

    def test_local_web_gateway_uploads_and_downloads_files_for_approved_guest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            store = JsonStateStore(base / "state.json")
            trust = TrustManager(store)
            tasks = TaskManager(store)
            guest_access = GuestAccessController(trust)
            token = guest_access.create_guest_session("browser-1")
            guest_access.approve(token)
            gateway = LocalWebGatewayServer("127.0.0.1", 0, guest_access, tasks, shared_dir=base)
            server = gateway.server
            port = server.server_address[1]
            try:
                upload = urllib.request.urlopen(
                    urllib.request.Request(
                        f"http://127.0.0.1:{port}/upload?name=hello.txt",
                        data=b"hello world",
                        method="POST",
                        headers={"X-Guest-Token": token},
                    ),
                    timeout=1,
                )
                self.assertEqual(upload.status, 201)

                download = urllib.request.urlopen(
                    urllib.request.Request(
                        f"http://127.0.0.1:{port}/download?name=hello.txt",
                        headers={"X-Guest-Token": token},
                    ),
                    timeout=1,
                )
                body = download.read()
            finally:
                server.server_close()

            self.assertEqual(body, b"hello world")


class CoreServiceNetworkTests(unittest.TestCase):
    def test_core_service_defaults_to_lan_bind_and_exposes_access_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("hybrid_transfer.core.resolve_access_hosts", return_value=["192.168.1.20"]):
                core = CoreService(Path(tmpdir) / "state.json", port=9200)
                try:
                    endpoints = core.get_access_endpoints()
                finally:
                    core.transfer_server.close()
                    core.web_gateway.close()

        self.assertEqual(core.transfer_server.host, "0.0.0.0")
        self.assertEqual(core.web_gateway.host, "0.0.0.0")
        self.assertEqual(endpoints["bind_host"], "0.0.0.0")
        self.assertEqual(endpoints["web_port"], 9201)
        self.assertEqual(endpoints["transfer_port"], 9202)
        self.assertEqual(
            endpoints["addresses"],
            [
                {
                    "label": "LAN",
                    "host": "192.168.1.20",
                    "web_url": "http://192.168.1.20:9201/",
                    "transfer_target": "192.168.1.20:9202",
                }
            ],
        )

    def test_core_service_resolves_peer_transfer_endpoint_from_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("hybrid_transfer.core.resolve_access_hosts", return_value=["192.168.1.20"]):
                core = CoreService(Path(tmpdir) / "state.json", port=9200)
                try:
                    core.registry.record_discovered(
                        {
                            "device_id": "peer-1",
                            "name": "Peer 1",
                            "address": "192.168.1.33",
                            "port": 9302,
                            "web_port": 9301,
                            "platform": "linux",
                            "source": "lan",
                        }
                    )
                    endpoint = core.resolve_peer_endpoint("peer-1")
                finally:
                    core.transfer_server.close()
                    core.web_gateway.close()

        self.assertEqual(endpoint, ("192.168.1.33", 9302))

    def test_core_service_exposes_pending_guest_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("hybrid_transfer.core.resolve_access_hosts", return_value=["192.168.1.20"]):
                core = CoreService(Path(tmpdir) / "state.json", port=9200)
                try:
                    token = core.guest_access.create_guest_session("android-browser")
                    pending = core.list_pending_guest_sessions()
                finally:
                    core.transfer_server.close()
                    core.web_gateway.close()

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["token"], token)
        self.assertEqual(pending[0]["guest_id"], "android-browser")

    def test_desktop_state_includes_pending_guest_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("hybrid_transfer.core.resolve_access_hosts", return_value=["192.168.1.20"]):
                core = CoreService(Path(tmpdir) / "state.json", port=9200)
                try:
                    token = core.guest_access.create_guest_session("android-browser")
                    snapshot = DesktopAppState(core).snapshot()
                finally:
                    core.transfer_server.close()
                    core.web_gateway.close()

        self.assertEqual(len(snapshot.pending_guest_sessions), 1)
        self.assertEqual(snapshot.pending_guest_sessions[0]["token"], token)


class IntegrationFlowTests(unittest.TestCase):
    def test_platform_labeled_peers_follow_same_pair_and_transfer_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            trust = TrustManager(store)
            tasks = TaskManager(store)
            registry = DiscoveryRegistry()

            for device_id, platform in [
                ("windows-peer", "windows"),
                ("linux-peer", "linux"),
                ("macos-peer", "macos"),
            ]:
                registry.record_discovered(
                    {
                        "device_id": device_id,
                        "name": device_id,
                        "address": "127.0.0.1",
                        "port": 9100,
                        "platform": platform,
                        "source": "lan",
                    }
                )
                request = trust.start_pairing(device_id, device_id)
                self.assertTrue(trust.validate_pairing_code(device_id, request["pairing_code"]))
                task = tasks.create_task(
                    peer_id=device_id,
                    items=[{"path": f"/tmp/{platform}.txt", "kind": "file", "size": 10}],
                )
                tasks.update_progress(task["id"], bytes_done=10, state=TaskState.IN_PROGRESS)
                tasks.complete_task(task["id"])

            self.assertEqual(len(registry.list_devices()), 3)
            self.assertEqual(len(store.state["history"]), 3)


class EntrypointTests(unittest.TestCase):
    def test_main_script_runs_as_a_script_without_relative_import_failure(self) -> None:
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, str(root / "hybrid_transfer" / "__main__.py"), "--help"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Hybrid LAN file transfer prototype", result.stdout)


if __name__ == "__main__":
    unittest.main()
