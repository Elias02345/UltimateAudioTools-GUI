"""Transactional, application-owned NVIDIA runtime upgrade. No system Python or drivers change."""

import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from filelock import FileLock, Timeout

from . import __version__


class RuntimeInstaller:
    def __init__(self, root: Path, emit, terminate):
        self.root, self.emit, self.terminate = root, emit, terminate
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.proc = None
        self.thread = None
        self.file_lock = FileLock(root / "runtime-install.lock", thread_local=False)
        self.last_progress = 0.0
        try:
            with self.file_lock.acquire(timeout=0):
                for pattern in [".staging-cuda-*", ".wheels-cuda-*"]:
                    for stale in (self.root / "runtimes").glob(pattern):
                        shutil.rmtree(stale, ignore_errors=True)
        except Timeout:
            pass
        self.status = {"phase": "idle", "log": [], "error": None}

    def event(self, phase=None, line=None, error=None):
        with self.lock:
            if phase:
                self.status["phase"] = phase
            progress = re.fullmatch(r"Progress (\d+) of (\d+)", line or "")
            if progress:
                self.status["download"] = {"bytes": int(progress[1]), "total": int(progress[2])}
                now = time.monotonic()
                if now - self.last_progress < 0.2:
                    return
                self.last_progress = now
            elif line:
                self.status["log"] = [*self.status["log"], line[-1500:]][-100:]
            self.status["error"] = error
            snapshot = dict(self.status)
        self.emit("runtime_install", **snapshot)

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError("A runtime installation is already active.")
            base = Path(os.environ.get("SEPARATOR_RUNTIME_BASE", ""))
            manifests = Path(os.environ.get("SEPARATOR_RUNTIME_MANIFESTS", ""))
            target = "windows" if os.name == "nt" else "linux"
            requirements = manifests / f"{target}-cuda.txt"
            if platform.machine().lower() not in {"x86_64", "amd64"} or platform.system() not in {
                "Linux",
                "Windows",
            }:
                raise ValueError("NVIDIA runtime upgrades support Windows and Linux x64.")
            if not base.is_dir() or (base / "pyvenv.cfg").exists() or not requirements.is_file():
                raise ValueError("Install the complete release package before upgrading its private runtime.")
            if shutil.disk_usage(self.root).free < 20 * 1024**3:
                raise ValueError("At least 20 GB free space is needed for an NVIDIA runtime upgrade.")
            self.file_lock.acquire(timeout=0)
            self.cancelled.clear()
            self.status = {"phase": "copying", "log": [], "error": None}
            self.thread = threading.Thread(target=self.install, args=(base, requirements), daemon=True)
            try:
                self.thread.start()
            except Exception:
                self.file_lock.release()
                self.status = {"phase": "failed", "log": [], "error": "Could not start installation."}
                raise
        return self.status

    def command(self, python, *args):
        if self.cancelled.is_set():
            raise InterruptedError("Runtime installation cancelled.")
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("PYTHON", "PIP_", "UV_")) and k != "VIRTUAL_ENV"
        }
        env["PIP_CONFIG_FILE"] = os.devnull
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        with self.lock:
            if self.cancelled.is_set():
                raise InterruptedError("Runtime installation cancelled.")
            self.proc = subprocess.Popen(
                [str(python), "-I", *args],
                cwd=python.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                start_new_session=os.name != "nt",
            )
            proc = self.proc
        for line in proc.stdout:
            self.event(line=line.strip())
        code = proc.wait()
        with self.lock:
            if self.proc is proc:
                self.proc = None
        if self.cancelled.is_set():
            raise InterruptedError("Runtime installation cancelled.")
        if code:
            raise RuntimeError(f"Runtime installer exited with code {code}. Review the installation log.")

    def install(self, base, requirements):
        name = f"cuda-{__version__}-{uuid.uuid4().hex}"
        directory = self.root / "runtimes"
        staged = directory / (".staging-" + name)
        final = directory / name
        wheels = directory / (".wheels-" + name)
        activated = False
        try:
            directory.mkdir(exist_ok=True)
            self.event("copying", "Creating an independent copy of the bundled CPU runtime.")
            shutil.copytree(base, staged, symlinks=True, copy_function=self.copy_file)
            python = staged / ("python.exe" if os.name == "nt" else "bin/python3")
            wheels.mkdir()
            self.event("downloading", "Downloading publisher wheels with SHA256 verification.")
            self.command(
                python,
                "-m",
                "pip",
                "--isolated",
                "download",
                "--require-hashes",
                "--only-binary=:all:",
                "--no-cache-dir",
                "--progress-bar",
                "raw",
                "--dest",
                str(wheels),
                "-r",
                str(requirements),
            )
            self.event("installing", "Installing only into the staged private runtime.")
            self.command(python, "-m", "pip", "--isolated", "uninstall", "-y", "onnxruntime")
            self.command(
                python,
                "-m",
                "pip",
                "--isolated",
                "install",
                "--no-index",
                "--find-links",
                str(wheels),
                "--require-hashes",
                "--only-binary=:all:",
                "--no-cache-dir",
                "-r",
                str(requirements),
            )
            self.event("testing", "Checking native imports and an actual CUDA matrix operation.")
            probe = str(Path(__file__).with_name("runtime_probe.py"))
            self.command(python, str(Path(__file__).with_name("license_inventory.py")))
            self.command(python, probe, "--cuda")
            with self.lock:
                if self.cancelled.is_set():
                    raise InterruptedError("Runtime installation cancelled.")
                (staged / "separator-runtime.json").write_text(
                    json.dumps(
                        {
                            "complete": True,
                            "version": __version__,
                            "backend": "cuda",
                            "platform": platform.system(),
                            "architecture": platform.machine().lower(),
                        }
                    )
                )
                staged.rename(final)
                pointer = self.root / "active-runtime.json"
                temp = pointer.with_name(f".active-runtime-{uuid.uuid4().hex}.part")
                try:
                    with temp.open("w") as stream:
                        json.dump({"directory": name, "version": __version__}, stream)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temp, pointer)
                    activated = True
                finally:
                    temp.unlink(missing_ok=True)
                self.event("completed", "NVIDIA acceleration is ready. Restart the engine to use it.")
        except Exception as error:
            self.event("cancelled" if self.cancelled.is_set() else "failed", error=str(error))
        finally:
            shutil.rmtree(staged, ignore_errors=True)
            shutil.rmtree(wheels, ignore_errors=True)
            if not activated:
                shutil.rmtree(final, ignore_errors=True)
            self.file_lock.release()

    def copy_file(self, source, destination):
        if self.cancelled.is_set():
            raise InterruptedError("Runtime installation cancelled.")
        return shutil.copy2(source, destination)

    def cancel(self):
        with self.lock:
            if self.status["phase"] == "completed":
                return
            self.cancelled.set()
            proc = self.proc
        self.terminate(proc)

    def close(self):
        self.cancel()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=6)
