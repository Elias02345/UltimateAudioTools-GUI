"""Runtime publication and cross-thread lock regressions; no dependency installation."""

import json
from types import SimpleNamespace

import pytest
from filelock import FileLock
from separator_engine.runtime import RuntimeInstaller


@pytest.fixture
def installer(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir()
    base = tmp_path / "bundled"
    base.mkdir()
    (base / "runtime.bin").write_bytes(b"bundled CPU stays intact")
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "linux-cuda.txt").write_text("verified test requirements")
    (manifests / "windows-cuda.txt").write_text("verified test requirements")
    monkeypatch.setenv("SEPARATOR_RUNTIME_BASE", str(base))
    monkeypatch.setenv("SEPARATOR_RUNTIME_MANIFESTS", str(manifests))
    monkeypatch.setattr("separator_engine.runtime.platform.system", lambda: "Linux")
    monkeypatch.setattr("separator_engine.runtime.platform.machine", lambda: "x86_64")
    monkeypatch.setattr(
        "separator_engine.runtime.shutil.disk_usage", lambda path: SimpleNamespace(free=100 * 1024**3)
    )
    instance = RuntimeInstaller(root, lambda *args, **kwargs: None, lambda proc: None)
    monkeypatch.setattr(instance, "command", lambda *args: None)
    yield instance
    instance.close()
    assert (base / "runtime.bin").read_bytes() == b"bundled CPU stays intact"


def finish(installer):
    installer.thread.join(timeout=10)
    assert not installer.thread.is_alive()
    # A different FileLock instance verifies that the background thread released the OS lock.
    with FileLock(installer.root / "runtime-install.lock").acquire(timeout=0):
        pass


def test_runtime_can_be_installed_again_after_background_completion(installer):
    for _ in range(2):
        installer.start()
        finish(installer)
        assert installer.status["phase"] == "completed"
    pointer = json.loads((installer.root / "active-runtime.json").read_text())
    manifest = json.loads(
        (installer.root / "runtimes" / pointer["directory"] / "separator-runtime.json").read_text()
    )
    assert manifest["complete"] and manifest["architecture"] == "x86_64"


def test_pointer_failure_preserves_active_runtime_and_removes_orphan(installer, monkeypatch):
    pointer = installer.root / "active-runtime.json"
    pointer.write_text('{"directory":"previous"}')

    def fail_replace(*args):
        raise OSError("Test publication failure")

    monkeypatch.setattr("separator_engine.runtime.os.replace", fail_replace)
    installer.start()
    finish(installer)
    assert installer.status["phase"] == "failed"
    assert json.loads(pointer.read_text())["directory"] == "previous"
    assert list((installer.root / "runtimes").iterdir()) == []


def test_cancel_before_activation_leaves_no_runtime(installer, monkeypatch):
    monkeypatch.setattr(installer, "command", lambda *args: installer.cancelled.set())
    installer.start()
    finish(installer)
    assert installer.status["phase"] == "cancelled"
    assert not (installer.root / "active-runtime.json").exists()
    assert list((installer.root / "runtimes").iterdir()) == []
