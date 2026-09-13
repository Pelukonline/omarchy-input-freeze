import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("storage", ROOT / "state.py")
storage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(storage)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.directory = self.base / "omarchy-input-freeze"
        self.directory.mkdir(mode=0o700)
        self.victim = self.base / "victim"
        self.victim.write_text("DO NOT CHANGE\n")
        self.bin = self.base / "bin"
        self.bin.mkdir()
        mock = self.bin / "hyprctl"
        mock.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
p = pathlib.Path(os.environ["MOCK_SESSION"])
s = json.loads(p.read_text()) if p.exists() else {"submap":"", "disabled":[]}
a = sys.argv[1:]
if a == ["-j", "submap"]: print(json.dumps(s["submap"]))
elif a == ["devices", "-j"]: print(json.dumps({"mice":[{"name":"test-mouse"}]}))
elif a[0] == "dispatch":
    if os.environ.get("MOCK_FAIL_DISPATCH") and '"reset"' not in a[1]: sys.exit(1)
    s["submap"] = "" if '"reset"' in a[1] else "input-freeze"
elif a[0] == "eval":
    s["disabled"] = [] if "true" in a[1] else ["test-mouse"]
else: sys.exit(1)
p.write_text(json.dumps(s))
''')
        mock.chmod(0o700)
        self.env = dict(os.environ, XDG_STATE_HOME=str(self.base),
                        PATH=str(self.bin) + ":" + os.environ["PATH"],
                        MOCK_SESSION=str(self.base / "session"), INPUT_FREEZE_NOTIFY="0")

    def helper(self, action):
        return subprocess.run([str(ROOT / "input-freeze"), action], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_symlinks_rejected_without_touching_target(self):
        for name in (storage.LOCK, storage.DEVICES):
            for action in ("status", "enable", "ensure", "disable"):
                with self.subTest(name=name, action=action):
                    path = self.directory / name
                    path.unlink(missing_ok=True)
                    path.symlink_to(self.victim)
                    before = self.victim.stat()
                    self.assertNotEqual(self.helper(action).returncode, 0)
                    self.assertEqual(self.victim.read_text(), "DO NOT CHANGE\n")
                    self.assertEqual(self.victim.stat().st_mtime_ns, before.st_mtime_ns)
                    path.unlink()

    def test_hardlinks_rejected(self):
        for name in (storage.LOCK, storage.DEVICES):
            path = self.directory / name
            path.unlink(missing_ok=True)
            os.link(self.victim, path)
            self.assertNotEqual(self.helper("status").returncode, 0)
            self.assertEqual(self.victim.read_text(), "DO NOT CHANGE\n")
            path.unlink()

    def test_special_files_rejected_without_hanging(self):
        for name in (storage.LOCK, storage.DEVICES):
            path = self.directory / name
            path.unlink(missing_ok=True)
            os.mkfifo(path)
            self.assertNotEqual(self.helper("status").returncode, 0)
            path.unlink()
            path.mkdir()
            self.assertNotEqual(self.helper("status").returncode, 0)
            path.rmdir()

    def test_directory_symlink_rejected(self):
        self.directory.rmdir()
        self.directory.symlink_to(self.bin, target_is_directory=True)
        self.assertNotEqual(self.helper("status").returncode, 0)
        self.assertFalse((self.bin / storage.LOCK).exists())

    def test_legacy_permissions_and_normal_lifecycle(self):
        self.directory.chmod(0o755)
        for name in (storage.LOCK, storage.DEVICES):
            (self.directory / name).write_text("")
            (self.directory / name).chmod(0o644)
        for action in ("status", "enable", "ensure", "disable", "recover", "status"):
            result = self.helper(action)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        for name in (storage.LOCK, storage.DEVICES):
            self.assertEqual((self.directory / name).stat().st_mode & 0o777, 0o600)

    def test_emergency_recovery_ignores_unsafe_state(self):
        self.assertEqual(self.helper("enable").returncode, 0)
        (self.directory / storage.DEVICES).unlink()
        (self.directory / storage.DEVICES).symlink_to(self.victim)
        self.assertEqual(self.helper("recover").returncode, 0)
        import json
        session = json.loads((self.base / "session").read_text())
        self.assertEqual(session, {"submap": "", "disabled": []})
        self.assertEqual(self.victim.read_text(), "DO NOT CHANGE\n")

    def test_concurrent_toggles_are_serialized(self):
        workers = [subprocess.Popen([str(ROOT / "input-freeze"), "toggle"],
                   env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
        for worker in workers:
            _, error = worker.communicate(timeout=15)
            self.assertEqual(worker.returncode, 0, error)
        self.assertIn('"active":false', self.helper("status").stdout)

    def test_failed_activation_restores_pointer(self):
        import json
        self.env["MOCK_FAIL_DISPATCH"] = "1"
        self.assertNotEqual(self.helper("enable").returncode, 0)
        session = json.loads((self.base / "session").read_text())
        self.assertEqual(session["disabled"], [])
        self.assertEqual((self.directory / storage.DEVICES).read_text(), "")

    def test_status_does_not_truncate_lock_or_rewrite_state(self):
        lock = self.directory / storage.LOCK
        lock.write_text("lock sentinel")
        lock.chmod(0o600)
        devices = self.directory / storage.DEVICES
        devices.write_text("test-mouse\n")
        devices.chmod(0o600)
        before = devices.stat().st_mtime_ns
        self.assertEqual(self.helper("status").returncode, 0)
        self.assertEqual(lock.read_text(), "lock sentinel")
        self.assertEqual(devices.stat().st_mtime_ns, before)

    def test_atomic_write_failure_preserves_previous_state(self):
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        storage.write_state(fd, ["original"])
        with patch.object(storage.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                storage.write_state(fd, ["replacement"])
        self.assertEqual(storage.read_state(fd), ["original"])
        self.assertEqual(list(self.directory.glob(".devices-*")), [])

    def test_directory_descriptor_survives_path_replacement(self):
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        self.directory.rename(self.base / "original-directory")
        self.directory.symlink_to(self.bin, target_is_directory=True)
        storage.write_state(fd, ["test-mouse"])
        self.assertFalse((self.bin / storage.DEVICES).exists())
        self.assertEqual(storage.read_state(fd), ["test-mouse"])
