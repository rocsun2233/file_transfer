import json
import tempfile
import unittest
import urllib.error
import urllib.request
from http.cookies import SimpleCookie
from pathlib import Path

from hybrid_transfer.persistence import JsonStateStore
from hybrid_transfer.tasks import TaskManager
from hybrid_transfer.trust import TrustManager
from hybrid_transfer.web import GuestAccessController, LocalWebGatewayServer, MobileWebViewModel


class MobileWebViewModelTests(unittest.TestCase):
    def test_mobile_view_model_marks_pending_state(self) -> None:
        model = MobileWebViewModel.from_state(
            access_state="pending",
            can_upload=False,
            can_download=False,
            guest_token=None,
            recent_tasks=[],
            device_label="Office Host",
            support_note="Android uses browser access",
            error_message=None,
        )

        payload = json.loads(model.to_json())

        self.assertEqual(payload["access_state"], "pending")
        self.assertFalse(payload["can_upload"])
        self.assertIn("Office Host", payload["connection_hint"])

    def test_mobile_view_model_marks_authorized_state(self) -> None:
        model = MobileWebViewModel.from_state(
            access_state="authorized",
            can_upload=True,
            can_download=True,
            guest_token=None,
            recent_tasks=[{"task_id": "task-1", "state": "completed"}],
            device_label="Office Host",
            support_note="Android uses browser access",
            error_message=None,
        )

        payload = json.loads(model.to_json())

        self.assertEqual(payload["access_state"], "authorized")
        self.assertTrue(payload["can_upload"])
        self.assertEqual(payload["recent_tasks"][0]["task_id"], "task-1")


class MobileBrowserInterfaceTests(unittest.TestCase):
    def _make_server(self):
        tmpdir = tempfile.TemporaryDirectory()
        base = Path(tmpdir.name)
        store = JsonStateStore(base / "state.json")
        trust = TrustManager(store)
        tasks = TaskManager(store)
        task = tasks.create_task(peer_id="peer-1", items=[{"path": "/tmp/a", "kind": "file", "size": 100}])
        tasks.complete_task(task["id"])
        guest_access = GuestAccessController(trust)
        gateway = LocalWebGatewayServer("127.0.0.1", 0, guest_access, tasks, shared_dir=base)
        port = gateway.server.server_address[1]
        return tmpdir, guest_access, gateway, port

    def test_android_browser_sees_pending_state_without_token(self) -> None:
        tmpdir, guest_access, gateway, port = self._make_server()
        try:
            request = urllib.request.Request(f"http://127.0.0.1:{port}/", headers={"User-Agent": "Android"})
            response = urllib.request.urlopen(request, timeout=1)
            body = response.read().decode("utf-8")
        finally:
            gateway.server.server_close()
            tmpdir.cleanup()

        self.assertEqual(response.headers.get_content_type(), "text/html")
        self.assertIn("Waiting for approval", body)
        self.assertIn("Android currently uses browser access", body)

    def test_android_browser_html_can_upload_download_and_view_recent_tasks_when_authorized(self) -> None:
        tmpdir, guest_access, gateway, port = self._make_server()
        try:
            first = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/",
                    headers={"User-Agent": "Android"},
                ),
                timeout=1,
            )
            cookie = SimpleCookie()
            cookie.load(first.headers["Set-Cookie"])
            token = cookie["guest_token"].value
            guest_access.approve(token)

            page = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/",
                    headers={"User-Agent": "Android", "Cookie": f"guest_token={token}"},
                ),
                timeout=1,
            )
            body = page.read().decode("utf-8")
            upload = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/upload?name=mobile.txt",
                    data=b"android upload",
                    method="POST",
                    headers={"User-Agent": "Android", "Cookie": f"guest_token={token}"},
                ),
                timeout=1,
            )

            download = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/download?name=mobile.txt",
                    headers={"User-Agent": "Android", "Cookie": f"guest_token={token}"},
                ),
                timeout=1,
            )
            download_body = download.read()
        finally:
            gateway.server.server_close()
            tmpdir.cleanup()

        self.assertEqual(page.headers.get_content_type(), "text/html")
        self.assertIn("authorized", body)
        self.assertIn("Upload Files", body)
        self.assertIn("Available Downloads", body)
        self.assertIn("completed", body)
        self.assertEqual(upload.status, 201)
        self.assertEqual(download_body, b"android upload")

    def test_android_browser_shows_denied_state_for_invalid_token_download(self) -> None:
        tmpdir, guest_access, gateway, port = self._make_server()
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(
                    urllib.request.Request(
                        f"http://127.0.0.1:{port}/download?name=nope.txt",
                        headers={"User-Agent": "Android", "X-Guest-Token": "bad-token"},
                    ),
                    timeout=1,
                )
        finally:
            gateway.server.server_close()
            tmpdir.cleanup()

        self.assertEqual(ctx.exception.code, 403)

    def test_android_browser_download_sets_attachment_filename_for_utf8_name(self) -> None:
        tmpdir, guest_access, gateway, port = self._make_server()
        try:
            (Path(tmpdir.name) / "报告.txt").write_bytes(b"report")
            first = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/",
                    headers={"User-Agent": "Android"},
                ),
                timeout=1,
            )
            cookie = SimpleCookie()
            cookie.load(first.headers["Set-Cookie"])
            token = cookie["guest_token"].value
            guest_access.approve(token)

            download = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/download?name=%E6%8A%A5%E5%91%8A.txt",
                    headers={"User-Agent": "Android", "Cookie": f"guest_token={token}"},
                ),
                timeout=1,
            )
            body = download.read()
        finally:
            gateway.server.server_close()
            tmpdir.cleanup()

        self.assertEqual(body, b"report")
        self.assertIn("attachment", download.headers["Content-Disposition"])
        self.assertIn("filename*", download.headers["Content-Disposition"])

    def test_android_browser_download_link_works_with_token_query_without_cookie(self) -> None:
        tmpdir, guest_access, gateway, port = self._make_server()
        try:
            (Path(tmpdir.name) / "mobile.txt").write_bytes(b"android download")
            first = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/",
                    headers={"User-Agent": "Android"},
                ),
                timeout=1,
            )
            cookie = SimpleCookie()
            cookie.load(first.headers["Set-Cookie"])
            token = cookie["guest_token"].value
            guest_access.approve(token)

            page = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/",
                    headers={"User-Agent": "Android", "Cookie": f"guest_token={token}"},
                ),
                timeout=1,
            )
            body = page.read().decode("utf-8")

            download = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/download?name=mobile.txt&token={token}",
                    headers={"User-Agent": "Android"},
                ),
                timeout=1,
            )
            download_body = download.read()
        finally:
            gateway.server.server_close()
            tmpdir.cleanup()

        self.assertIn(f"/download?name=mobile.txt&amp;token={token}", body)
        self.assertEqual(download_body, b"android download")

    def test_android_browser_download_link_marks_anchor_as_download(self) -> None:
        tmpdir, guest_access, gateway, port = self._make_server()
        try:
            (Path(tmpdir.name) / "mobile.txt").write_bytes(b"android download")
            first = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/",
                    headers={"User-Agent": "Android"},
                ),
                timeout=1,
            )
            cookie = SimpleCookie()
            cookie.load(first.headers["Set-Cookie"])
            token = cookie["guest_token"].value
            guest_access.approve(token)

            page = urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/",
                    headers={"User-Agent": "Android", "Cookie": f"guest_token={token}"},
                ),
                timeout=1,
            )
            body = page.read().decode("utf-8")
        finally:
            gateway.server.server_close()
            tmpdir.cleanup()

        self.assertIn('download="mobile.txt"', body)


if __name__ == "__main__":
    unittest.main()
