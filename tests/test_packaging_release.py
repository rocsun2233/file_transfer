import json
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hybrid_transfer.release import (
    RELEASE_VERSION,
    build_release_manifest,
    ensure_distribution_layout,
    resolve_pyinstaller_invocation,
    validate_build_environment,
    validate_release_outputs,
)


BUILD_RELEASE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "build_release.py"
BUILD_RELEASE_SPEC = importlib.util.spec_from_file_location("build_release_script", BUILD_RELEASE_PATH)
assert BUILD_RELEASE_SPEC and BUILD_RELEASE_SPEC.loader is not None
build_release_script = importlib.util.module_from_spec(BUILD_RELEASE_SPEC)
BUILD_RELEASE_SPEC.loader.exec_module(build_release_script)


class PackagingReleaseTests(unittest.TestCase):
    def test_release_version_is_semver_like(self) -> None:
        parts = RELEASE_VERSION.split(".")

        self.assertEqual(len(parts), 3)
        self.assertTrue(all(part.isdigit() for part in parts))

    def test_release_manifest_declares_desktop_platforms_and_android_boundary(self) -> None:
        manifest = build_release_manifest(build_date="2026-03-28")

        self.assertEqual(manifest["version"], RELEASE_VERSION)
        self.assertEqual(manifest["platforms"], ["windows", "linux", "macos"])
        self.assertEqual(manifest["android"]["mode"], "browser-only")
        self.assertIn("not packaged", manifest["android"]["note"])

    def test_distribution_layout_creates_platform_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            ensure_distribution_layout(root)

            self.assertTrue((root / "dist" / "windows" / "HybridTransfer").is_dir())
            self.assertTrue((root / "dist" / "linux" / "HybridTransfer").is_dir())
            self.assertTrue((root / "dist" / "macos" / "HybridTransfer").is_dir())
            self.assertTrue((root / "release").is_dir())

    def test_validate_build_environment_requires_pyinstaller_and_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            entrypoint = root / "hybrid_transfer" / "__main__.py"
            entrypoint.parent.mkdir(parents=True)
            entrypoint.write_text("print('ok')\n", encoding="utf-8")

            with mock.patch("hybrid_transfer.release.resolve_pyinstaller_invocation", return_value=None):
                errors = validate_build_environment(root, entrypoint=entrypoint)
            self.assertIn("PyInstaller is not installed", errors[0])

            with mock.patch(
                "hybrid_transfer.release.resolve_pyinstaller_invocation",
                return_value=(["pyinstaller"], None),
            ):
                errors = validate_build_environment(root, entrypoint=entrypoint)
            self.assertEqual(errors, [])

    def test_resolve_pyinstaller_invocation_uses_local_site_packages_when_path_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            site_packages = root / "myenv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
            pyinstaller_main = site_packages / "PyInstaller" / "__main__.py"
            pyinstaller_main.parent.mkdir(parents=True, exist_ok=True)
            pyinstaller_main.write_text("print('ok')\n", encoding="utf-8")

            with mock.patch("hybrid_transfer.release.importlib.util.find_spec", return_value=None):
                with mock.patch("hybrid_transfer.release.shutil.which", return_value=None):
                    cmd, env = resolve_pyinstaller_invocation(root)

        self.assertEqual(cmd, [sys.executable, "-m", "PyInstaller"])
        self.assertIsNotNone(env)
        assert env is not None
        self.assertTrue(env["PYTHONPATH"].startswith(str(site_packages)))

    def test_build_uses_resolved_pyinstaller_environment(self) -> None:
        fake_env = {"PYTHONPATH": "/tmp/site-packages"}

        with mock.patch.object(build_release_script, "ensure_distribution_layout"):
            with mock.patch.object(build_release_script, "validate_build_environment", return_value=[]):
                with mock.patch.object(build_release_script, "write_release_files"):
                    with mock.patch.object(build_release_script, "write_quick_start"):
                        with mock.patch.object(
                            build_release_script,
                            "resolve_pyinstaller_invocation",
                            return_value=([sys.executable, "-m", "PyInstaller"], fake_env),
                        ):
                            with mock.patch.object(build_release_script.subprocess, "call", return_value=0) as call_mock:
                                result = build_release_script.build("linux")

        self.assertEqual(result, 0)
        call_mock.assert_called_once()
        args, kwargs = call_mock.call_args
        self.assertEqual(args[0][:3], [sys.executable, "-m", "PyInstaller"])
        self.assertEqual(kwargs["env"], fake_env)

    def test_validate_release_outputs_requires_manifest_readme_and_changelog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ensure_distribution_layout(root)
            release = root / "release"
            (release / "manifest.json").write_text(json.dumps(build_release_manifest("2026-03-28")), encoding="utf-8")
            (release / "README.md").write_text("# Release\n", encoding="utf-8")
            (release / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
            for platform in ("windows", "linux", "macos"):
                platform_dir = root / "dist" / platform / "HybridTransfer"
                (platform_dir / "README.txt").write_text("Run me\n", encoding="utf-8")

            errors = validate_release_outputs(root)

            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
