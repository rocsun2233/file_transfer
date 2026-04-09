import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from hybrid_transfer.desktop import DesktopShell
from hybrid_transfer.desktop_state import DesktopAppState, DesktopController
from hybrid_transfer.persistence import JsonStateStore
from hybrid_transfer.tasks import TaskManager, TaskState


class FakeCore:
    def __init__(self) -> None:
        self.devices = [
            {"device_id": "peer-1", "name": "Peer 1", "address": "127.0.0.1", "port": 9100},
            {"device_id": "peer-2", "name": "Peer 2", "address": "127.0.0.2", "port": 9100},
        ]
        self.active_tasks = [
            {"id": "task-1", "peer_id": "peer-1", "state": "in_progress", "bytes_done": 10, "total_bytes": 100, "items": [1]},
            {"id": "task-2", "peer_id": "peer-2", "state": "retryable", "bytes_done": 20, "total_bytes": 100, "items": [1, 2]},
        ]
        self.history = [
            {"task_id": "task-old", "state": "completed"},
            {"task_id": "task-fail", "state": "failed"},
        ]
        self.settings = {"shared_dir": "shared", "default_conflict_policy": "overwrite", "auto_accept_trusted": True, "manual_port": 9100}
        self.selected_device_id = None
        self.pending_offers = [{"offer_id": "offer-1", "task_id": "task-9", "peer_id": "sender", "file_count": 2, "conflict_policy": "rename"}]
        self.sent_paths = None
        self.retried = None
        self.resolved_offer = None
        self.access_endpoints = {
            "bind_host": "0.0.0.0",
            "web_port": 9101,
            "transfer_port": 9102,
            "addresses": [
                {"label": "LAN", "host": "192.168.1.20", "web_url": "http://192.168.1.20:9101/", "transfer_target": "192.168.1.20:9102"},
            ],
        }
        self.approved_guest_token = None

    def list_devices(self):
        return self.devices

    def list_active_tasks(self):
        return self.active_tasks

    def list_history(self):
        return self.history

    def get_settings(self):
        return dict(self.settings)

    def update_settings(self, settings):
        self.settings = dict(settings)

    def get_selected_device_id(self):
        return self.selected_device_id

    def select_device(self, device_id):
        self.selected_device_id = device_id

    def manual_connect(self, name, address, port):
        peer = {"device_id": f"manual-{address}", "name": name, "address": address, "port": port}
        self.devices.append(peer)
        return peer

    def send_paths_to_selected(self, paths):
        self.sent_paths = paths
        return {"id": "task-send"}

    def retry_task(self, task_id):
        self.retried = task_id
        return {"id": task_id}

    def list_pending_incoming_offers(self):
        return list(self.pending_offers)

    def resolve_incoming_offer(self, offer_id, accept, conflict_policy=None):
        self.resolved_offer = {"offer_id": offer_id, "accept": accept, "conflict_policy": conflict_policy}

    def get_access_endpoints(self):
        return self.access_endpoints

    def list_pending_guest_sessions(self):
        return [{"guest_id": "android-browser", "token": "token-1"}]

    def approve_guest_session(self, token):
        self.approved_guest_token = token


class FakeListbox:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.selected: tuple[int, ...] = ()

    def curselection(self):
        return self.selected

    def get(self, index):
        return self.items[index]

    def delete(self, start, end=None):
        self.items = []
        self.selected = ()

    def insert(self, index, value):
        self.items.append(value)

    def selection_set(self, index):
        self.selected = (index,)


class DesktopStateTests(unittest.TestCase):
    def test_snapshot_maps_devices_tasks_history_and_settings(self) -> None:
        state = DesktopAppState(FakeCore()).snapshot()

        self.assertEqual(len(state.devices), 2)
        self.assertEqual(state.active_tasks[0]["progress"], "10/100")
        self.assertTrue(state.active_tasks[1]["retryable"])
        self.assertEqual(state.history[0]["task_id"], "task-old")
        self.assertEqual(state.settings["default_conflict_policy"], "overwrite")
        self.assertEqual(state.access_endpoints["bind_host"], "0.0.0.0")
        self.assertEqual(state.access_endpoints["addresses"][0]["web_url"], "http://192.168.1.20:9101/")

    def test_settings_update_persists_new_defaults(self) -> None:
        core = FakeCore()
        controller = DesktopController(core)

        updated = controller.update_settings(default_conflict_policy="rename", auto_accept_trusted=False)

        self.assertEqual(updated["default_conflict_policy"], "rename")
        self.assertFalse(updated["auto_accept_trusted"])


class DesktopInteractionTests(unittest.TestCase):
    def test_send_requires_selected_device(self) -> None:
        controller = DesktopController(FakeCore())

        with self.assertRaisesRegex(ValueError, "missing target device"):
            controller.send_paths([Path("/tmp/a.txt")])

    def test_send_uses_selected_device(self) -> None:
        core = FakeCore()
        controller = DesktopController(core)
        controller.select_device("peer-2")

        controller.send_paths([Path("/tmp/a.txt")])

        self.assertEqual(core.selected_device_id, "peer-2")
        self.assertEqual(core.sent_paths, [Path("/tmp/a.txt")])

    def test_handle_drop_sends_newline_separated_paths(self) -> None:
        core = FakeCore()
        controller = DesktopController(core)
        controller.select_device("peer-1")

        controller.handle_drop("/tmp/a.txt\n/tmp/b.txt\n")

        self.assertEqual(core.sent_paths, [Path("/tmp/a.txt"), Path("/tmp/b.txt")])

    def test_retryable_task_action_reuses_task_id(self) -> None:
        core = FakeCore()
        controller = DesktopController(core)

        controller.retry_task("task-2")

        self.assertEqual(core.retried, "task-2")

    def test_incoming_confirmation_accepts_with_conflict_override(self) -> None:
        core = FakeCore()
        controller = DesktopController(core)

        controller.accept_incoming("offer-1", conflict_policy="skip")

        self.assertEqual(core.resolved_offer, {"offer_id": "offer-1", "accept": True, "conflict_policy": "skip"})

    def test_manual_device_requires_non_empty_address(self) -> None:
        controller = DesktopController(FakeCore())

        with self.assertRaisesRegex(ValueError, "invalid manual address"):
            controller.add_manual_device("peer", "   ", 9100)


class DesktopRegressionTests(unittest.TestCase):
    def test_pending_browser_selection_survives_refresh_for_same_session(self) -> None:
        shell = DesktopShell.__new__(DesktopShell)
        shell.pending_guest_list = FakeListbox()
        shell._pending_guest_token = "token-1"
        shell.pending_guest_list.items = ["android-browser [token-1]"]
        shell.pending_guest_list.selected = (0,)

        snapshot = SimpleNamespace(
            pending_guest_sessions=[{"guest_id": "android-browser", "token": "token-1"}]
        )

        shell._refresh_pending_guest_list(snapshot)

        self.assertEqual(shell.pending_guest_list.selected, (0,))

    def test_approve_pending_browser_uses_stable_token_when_refresh_clears_widget_selection(self) -> None:
        core = FakeCore()
        shell = DesktopShell.__new__(DesktopShell)
        shell.controller = DesktopController(core)
        shell.state = DesktopAppState(core)
        shell.pending_guest_list = FakeListbox()
        shell.pending_guest_list.items = ["android-browser [token-1]"]
        shell.pending_guest_list.selected = ()
        shell._pending_guest_token = "token-1"
        shell.status_var = SimpleNamespace(set=lambda value: setattr(shell, "_last_status", value))
        shell._last_status = ""
        shell._refresh_all = lambda: None

        shell._approve_selected_guest()

        self.assertEqual(core.approved_guest_token, "token-1")
        self.assertIn("android-browser", shell._last_status)

    def test_history_ordering_and_retryable_task_state_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonStateStore(Path(tmpdir) / "state.json")
            tasks = TaskManager(store)
            t1 = tasks.create_task(peer_id="peer-1", items=[{"path": "/tmp/a", "kind": "file", "size": 10}])
            t2 = tasks.create_task(peer_id="peer-2", items=[{"path": "/tmp/b", "kind": "file", "size": 10}])
            tasks.complete_task(t1["id"])
            tasks.mark_retryable(t2["id"], "offline")

            self.assertEqual(store.state["tasks"][t2["id"]]["state"], TaskState.RETRYABLE.value)
            self.assertEqual(len(store.state["history"]), 1)


if __name__ == "__main__":
    unittest.main()
