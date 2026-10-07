"""Local NDJSON supervisor with durable queue and killable/reusable ML worker."""

import concurrent.futures
import importlib.metadata
import json
import logging
import logging.handlers
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from filelock import FileLock, Timeout
from platformdirs import user_data_dir

from . import PROTOCOL_VERSION, __version__
from .audio import clear_cache, directory_size, ffmpeg, input_path, metadata, preview, waveform
from .catalog import Catalog, builtin_presets
from .runtime import RuntimeInstaller
from .schema import Job, JobRequest, Preset, Request, Settings
from .state import State

ACTIVE = {"Preparing", "Downloading model", "Loading model", "Processing", "Ensembling", "Encoding"}


def terminate(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            # Only the child process tree owned by this application is terminated.
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                proc.kill()
            else:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
    except ProcessLookupError:
        pass


class Supervisor:
    def __init__(self, root: Path, emit):
        self.root, self.emit = root.resolve(), emit
        self.root.mkdir(parents=True, exist_ok=True)
        self.instance_lock = FileLock(self.root / "engine.lock")
        try:
            self.instance_lock.acquire(timeout=0)
        except Timeout as error:
            raise RuntimeError(
                "Another Separator instance is using this data folder. Close it before restarting."
            ) from error
        self.state = State(self.root)
        raw_settings = self.state.get("settings", {})
        self.settings = Settings.model_validate(raw_settings)
        if not self.settings.output.directory:
            self.settings.output.directory = str(Path.home() / "Music" / "Separator")
        self.model_dir = Path(self.settings.model_directory or root / "models").expanduser().resolve()
        self.catalog = Catalog(self.model_dir, self.root)
        self.cache = self.root / "cache"
        self.work_root = self.cache / "jobs"
        # Only application-owned stale temporary inference directories are removed.
        clear_cache(self.work_root)
        self.jobs = self.state.jobs()
        for job in self.jobs:
            if job["status"] in ACTIVE:
                job.update(
                    status="Interrupted", error="Processing was interrupted. Retry to run this job again."
                )
                self.state.save_job(job)
        self.lock = threading.RLock()
        self.cache_lock = threading.RLock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.running = False
        self.single = False
        self.worker = None
        self.worker_log = None
        self.current = None
        self.downloads = {}
        self.capability_cache = None
        self.runtime_installer = RuntimeInstaller(self.root, self.emit, terminate)
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.queue_thread = threading.Thread(target=self.queue_loop, daemon=True)
        self.queue_thread.start()

    def notify_job(self, job: dict) -> None:
        self.state.save_job(job)
        self.emit("job_updated", job=Job.model_validate(job).model_dump())

    def presets(self) -> list[dict]:
        return builtin_presets() + self.state.get("user_presets", [])

    def get_job(self, job_id: str) -> dict:
        return next((j for j in self.jobs if j["id"] == job_id), None) or self.missing("Job")

    @staticmethod
    def missing(what: str):
        raise ValueError(f"{what} not found.")

    def spawn_worker(self, settings: Settings | None = None, active_request: dict | None = None):
        settings = settings or self.settings
        args = [
            sys.executable,
            "-u",
            "-m",
            "separator_engine.worker",
            "serve",
            str(self.model_dir),
            str(self.root),
        ]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        if settings.engine == "container":
            runtime = shutil.which(settings.container_command)
            if not runtime:
                raise ValueError("The selected container runtime is not installed. Choose Native Runtime.")
            mounts = {str(self.root), str(self.model_dir)}
            for job in self.jobs:
                if job["status"] == "Pending" or job["request"] == active_request:
                    request = job["request"]
                    mounts.add(str(Path(request["path"]).parent))
                    mounts.add(str(Path(request["preset"]["output"]["directory"]).expanduser().resolve()))
            options = [runtime, "run", "--rm", "-i", "--network", "none"]
            if settings.parameters.device in {"cuda", "auto"} and settings.container_command == "docker":
                options += ["--gpus", "all"]
            for mount in mounts:
                Path(mount).mkdir(parents=True, exist_ok=True)
                options += ["--mount", f"type=bind,source={mount},target={mount}"]
            args = [
                *options,
                settings.container_image,
                "python",
                "-u",
                "-m",
                "separator_engine.worker",
                "serve",
                str(self.model_dir),
                str(self.root),
            ]
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
            start_new_session=os.name != "nt",
        )
        threading.Thread(target=self.collect_log, args=(proc,), daemon=True).start()
        return proc

    @staticmethod
    def collect_log(proc):
        for line in proc.stderr:
            logging.getLogger("engine.worker").info(line.rstrip())

    def worker_request(self, proc, message: dict, on_event):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                logging.warning("Non-protocol worker output discarded")
                continue
            if event.get("kind") == "result":
                return event["result"]
            if event.get("kind") == "error":
                raise ValueError(event["error"])
            on_event(event)
        raise RuntimeError(
            "The processing engine stopped unexpectedly. Retry this job; the application is still running."
        )

    def queue_loop(self):
        while not self.stop.is_set():
            self.wake.wait(0.5)
            self.wake.clear()
            with self.lock:
                if not self.running:
                    continue
                job = next((j for j in self.jobs if j["status"] == "Pending"), None)
                if not job:
                    self.running = False
                    self.emit("queue_state", running=False)
                    continue
                self.current = job["id"]
                job.update(status="Preparing", started_at=time.time(), error=None)
                self.notify_job(job)
            work = self.work_root / job["id"]
            try:
                request = JobRequest.model_validate(job["request"])
                self.catalog.validate_selection(request.preset)
                if not self.settings.auto_download and not request.download_consent:
                    lookup = {m["id"]: m for m in self.catalog.list()}
                    missing = [m for m in request.preset.models if not lookup[m]["downloaded"]]
                    if missing:
                        raise ValueError(
                            "Required models are missing. Download them in Models or enable "
                            "automatic model downloads in Settings."
                        )
                with self.lock:
                    if job["status"] == "Cancelled" or self.stop.is_set():
                        continue
                    if self.worker is None or self.worker.poll() is not None:
                        self.worker = self.spawn_worker(active_request=job["request"])
                    proc = self.worker

                def update(event, job=job):
                    with self.lock:
                        if job["status"] == "Cancelled":
                            return
                        if event["kind"] == "stage":
                            job.update(
                                status=event["stage"],
                                stage=event["stage"],
                                model=event.get("model"),
                                device=event.get("device", job.get("device")),
                                pass_index=event.get("pass_index"),
                                pass_count=event.get("pass_count"),
                            )
                            self.notify_job(job)
                        elif event["kind"] == "download_progress":
                            job.update(status="Downloading model", download=event)
                            self.notify_job(job)

                result = self.worker_request(
                    proc,
                    {"method": "run", "id": job["id"], "request": job["request"], "work": str(work)},
                    update,
                )
                with self.lock:
                    if job["status"] != "Cancelled":
                        job.update(status="Completed", result=result, completed_at=time.time(), download=None)
                        self.notify_job(job)
            except Exception as error:
                logging.exception("Job failed: %s", job["id"])
                with self.lock:
                    if job["status"] != "Cancelled":
                        job.update(status="Failed", error=str(error)[:1800], completed_at=time.time())
                        self.notify_job(job)
                if self.worker is not None and self.worker.poll() is not None:
                    self.worker = None
            finally:
                if job["status"] in {"Cancelled", "Failed"}:
                    self.cleanup_download_parts(job["request"]["preset"]["models"])
                shutil.rmtree(work, ignore_errors=True)
                output_dir = Path(job["request"]["preset"]["output"]["directory"])
                for temp in output_dir.glob(f"**/.separator-{job['id']}-*.part"):
                    temp.unlink(missing_ok=True)
                with self.lock:
                    self.current = None
                    if self.single:
                        self.running, self.single = False, False
                        self.emit("queue_state", running=False)
                self.wake.set()

    def capabilities(self, refresh: bool = False):
        if self.capability_cache is not None and not refresh:
            return self.capability_cache
        import torch

        gpus = []
        for i in range(torch.cuda.device_count()):
            prop = torch.cuda.get_device_properties(i)
            gpus.append({"index": i, "name": prop.name, "vram": prop.total_memory})
        if not gpus and shutil.which("nvidia-smi"):
            try:
                detected = subprocess.run(
                    ["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for line in detected.stdout.splitlines():
                    index, name, memory = [part.strip() for part in line.split(",", 2)]
                    gpus.append({"index": int(index), "name": name, "vram": int(memory) * 1024**2})
            except (ValueError, subprocess.TimeoutExpired):
                pass
        mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        ram = None
        try:
            import psutil

            ram = psutil.virtual_memory().total
        except ImportError:
            if hasattr(os, "sysconf"):
                ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        command = subprocess.run([ffmpeg(), "-version"], capture_output=True, text=True, timeout=15)
        info = {
            "platform": platform.system(),
            "architecture": platform.machine(),
            "cpu": platform.processor() or self.cpu_name(),
            "ram": ram,
            "gpus": gpus,
            "cuda": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
            "mps": mps,
            "mlx": False,
            "directml": False,
            "cuda_installable": bool(gpus)
            and not torch.cuda.is_available()
            and bool(os.environ.get("SEPARATOR_RUNTIME_BASE")),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "engine_version": importlib.metadata.version("audio-separator"),
            "ffmpeg": command.stdout.splitlines()[0] if command.returncode == 0 else None,
            "disk_free": shutil.disk_usage(self.root).free,
            "backends": ["cpu"] + (["cuda"] if torch.cuda.is_available() else []) + (["mps"] if mps else []),
            "recommended_device": "cuda" if torch.cuda.is_available() else "mps" if mps else "cpu",
            "containers": [c for c in ["docker", "podman"] if shutil.which(c)],
        }
        self.capability_cache = info
        return info

    @staticmethod
    def cpu_name():
        if platform.system() == "Linux":
            try:
                return next(
                    line.split(":", 1)[1].strip()
                    for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name")
                )
            except (OSError, StopIteration):
                pass
        return platform.machine()

    def self_test(self):
        import numpy as np
        import soundfile as sf
        import torch

        from .audio import run_ffmpeg

        checks = []
        checks.append({"name": "Engine protocol", "passed": True, "detail": f"v{PROTOCOL_VERSION}"})
        for name, path in [
            ("Model folder", self.model_dir),
            ("Output folder", Path(self.settings.output.directory)),
        ]:
            try:
                path.mkdir(parents=True, exist_ok=True)
                probe = path / f".separator-write-{uuid.uuid4().hex}"
                with probe.open("xb") as stream:
                    stream.write(b"test")
                probe.unlink()
                checks.append({"name": name, "passed": True, "detail": "Writable"})
            except OSError as error:
                checks.append({"name": name, "passed": False, "detail": str(error)})
        tmp = self.cache / f"self-test-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True)
        try:
            src, dest = tmp / "source.wav", tmp / "encoded.flac"
            sf.write(src, np.zeros((4410, 2), dtype=np.float32), 44100)
            run_ffmpeg(["-y", "-i", str(src), str(dest)], timeout=30)
            checks.append(
                {"name": "FFmpeg decode/encode", "passed": sf.info(dest).frames == 4410, "detail": "FLAC"}
            )
            device = self.capabilities()["recommended_device"]
            x = torch.ones((8, 8), device=device)
            valid = bool(torch.isfinite(x @ x).all().item())
            checks.append({"name": "Hardware initialization", "passed": valid, "detail": device})
        except Exception as error:
            checks.append({"name": "Runtime self-test", "passed": False, "detail": str(error)[:500]})
        finally:
            shutil.rmtree(tmp)
        return checks

    def download_model(self, model: str):
        if model not in {m["id"] for m in self.catalog.list()}:
            raise ValueError("Model not found in upstream catalogue.")
        with self.lock:
            if self.stop.is_set():
                raise ValueError("The application is shutting down.")
            if model in self.downloads:
                raise ValueError("This model is already downloading.")
            if self.current:
                raise ValueError("Wait for processing to finish before starting a separate download.")
            native_settings = self.settings.model_copy(update={"engine": "native"})
            proc = self.spawn_worker(native_settings)
            self.downloads[model] = proc

        def task():
            try:
                self.worker_request(
                    proc,
                    {"method": "download", "model": model},
                    lambda e: self.emit("model_download", model=model, **e),
                )
                self.emit("model_download", model=model, kind="completed")
            except Exception as error:
                self.emit(
                    "model_download",
                    model=model,
                    kind="cancelled" if self.downloads.get(model) is not proc else "failed",
                    error=str(error),
                )
            finally:
                terminate(proc)
                self.cleanup_download_parts([model])
                with self.lock:
                    if self.downloads.get(model) is proc:
                        self.downloads.pop(model, None)

        self.pool.submit(task)
        return {"model": model}

    def cleanup_download_parts(self, models):
        from filelock import FileLock, Timeout

        entries = {entry["id"]: entry for entry in self.catalog.list()}
        for model in models:
            for filename in entries.get(model, {}).get("physical_files", []):
                path = self.model_dir / filename
                try:
                    with FileLock(str(path) + ".lock", timeout=0):
                        path.with_suffix(path.suffix + ".part").unlink(missing_ok=True)
                except Timeout:
                    # Another worker now owns this asset; never remove its partial.
                    pass

    def dispatch(self, method: str, params: dict):
        if self.stop.is_set() and method != "shutdown":
            raise ValueError("The application is shutting down.")
        if method == "initialize":
            return {
                "v": PROTOCOL_VERSION,
                "engine_version": __version__,
                "settings": self.settings.model_dump(),
                "jobs": [Job.model_validate(j).model_dump() for j in self.jobs],
                "presets": self.presets(),
                "running": self.running,
                "runtime_install": self.runtime_installer.status,
            }
        if method == "install_acceleration":
            with self.lock:
                if self.current or self.downloads:
                    raise ValueError("Finish or cancel processing and downloads before changing the runtime.")
                return self.runtime_installer.start()
        if method == "cancel_runtime_install":
            self.runtime_installer.cancel()
            return True
        if method == "runtime_install_status":
            return self.runtime_installer.status
        if method == "get_capabilities":
            return self.capabilities(params.get("refresh", False))
        if method == "self_test":
            with self.cache_lock:
                return self.self_test()
        if method == "list_models":
            return self.catalog.list(params.get("refresh", False))
        if method == "verify_models":
            return self.catalog.verify()
        if method == "download_model":
            return self.download_model(params["model"])
        if method == "cancel_download":
            with self.lock:
                proc = self.downloads.pop(params["model"], None)
            terminate(proc)
            self.cleanup_download_parts([params["model"]])
            return True
        if method == "remove_model":
            with self.lock:
                if self.current or self.downloads:
                    raise ValueError("Finish or cancel processing/downloads before deleting a model.")
                entry = next((m for m in self.catalog.list() if m["id"] == params["model"]), None)
                if not entry:
                    raise ValueError("Model not found.")
                # Remove only this checkpoint. Shared configs and auxiliary weights are retained.
                path = Path(entry["path"])
                if not path.resolve().is_relative_to(self.model_dir):
                    raise ValueError("Model path is outside the model cache.")
                path.unlink(missing_ok=True)
            return True
        if method == "inspect_audio":
            return metadata(params["path"])
        if method == "import_folder":
            from .audio import SUPPORTED

            folder = Path(params["path"]).resolve(strict=True)
            if not folder.is_dir():
                raise ValueError("Choose a folder.")
            return [str(p) for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED][
                :10000
            ]
        if method == "waveform":
            with self.cache_lock:
                return waveform(params["path"], self.cache / "waveforms")
        if method == "preview":
            with self.cache_lock:
                return preview(
                    params["path"],
                    self.cache / "previews",
                    params.get("range_start"),
                    params.get("range_end"),
                )
        if (
            method in {"enqueue", "process_queue"}
            and self.runtime_installer.thread
            and self.runtime_installer.thread.is_alive()
        ):
            raise ValueError("Finish or cancel runtime installation before starting processing.")
        if method == "enqueue":
            requests = [JobRequest.model_validate(r) for r in params["requests"]]
            if not requests or len(requests) > 10000:
                raise ValueError("Choose between one and 10,000 recordings.")
            added = []
            for request in requests:
                request.path = str(input_path(request.path))
                self.catalog.validate_selection(request.preset)
                if not request.preset.output.directory:
                    request.preset.output = self.settings.output.model_copy(deep=True)
                job = {
                    "id": uuid.uuid4().hex,
                    "status": "Pending",
                    "created_at": time.time(),
                    "request": request.model_dump(),
                    "source": metadata(request.path),
                    "error": None,
                    "result": None,
                }
                with self.lock:
                    self.jobs.append(job)
                    self.notify_job(job)
                added.append(job)
            if params.get("start", False):
                self.running = True
                self.wake.set()
            return added
        if method == "list_jobs":
            return [Job.model_validate(j).model_dump() for j in self.jobs]
        if method == "process_queue":
            self.running, self.single = True, params.get("single", False)
            self.wake.set()
            self.emit("queue_state", running=True)
            return True
        if method == "pause_queue":
            self.running = False
            self.emit("queue_state", running=False)
            return True
        if method == "cancel_job":
            with self.lock:
                job = self.get_job(params["id"])
                if job["status"] in {"Completed", "Failed", "Cancelled", "Interrupted"}:
                    return True
                job.update(status="Cancelled", completed_at=time.time())
                self.notify_job(job)
                proc = self.worker if self.current == job["id"] else None
                if proc:
                    self.worker = None
            terminate(proc)
            return True
        if method == "retry_job":
            with self.lock:
                job = self.get_job(params["id"])
                if self.current == job["id"]:
                    raise ValueError("Cancellation is finishing. Wait a moment before retrying.")
                if job["status"] not in {"Failed", "Cancelled", "Interrupted"}:
                    raise ValueError("Only failed, cancelled or interrupted jobs can be retried.")
                job.update(status="Pending", error=None, result=None, started_at=None)
                self.notify_job(job)
            return True
        if method == "remove_job":
            with self.lock:
                job = self.get_job(params["id"])
                if job["status"] in ACTIVE:
                    raise ValueError("Cancel this job before removing it.")
                self.jobs.remove(job)
                self.state.remove_job(job["id"])
            return True
        if method == "clear_completed":
            with self.lock:
                for job in list(self.jobs):
                    if job["status"] == "Completed":
                        self.jobs.remove(job)
                        self.state.remove_job(job["id"])
            return True
        if method == "reorder_queue":
            ids = params["ids"]
            with self.lock:
                old = {j["id"]: j for j in self.jobs}
                self.state.reorder(ids)
                self.jobs = [old[i] for i in ids]
            return True
        if method == "save_preset":
            preset = Preset.model_validate(params["preset"])
            if preset.builtin or preset.id in {p["id"] for p in builtin_presets()}:
                raise ValueError("Duplicate a built-in preset before editing it.")
            self.catalog.validate_selection(preset)
            with self.lock:
                users = [p for p in self.state.get("user_presets", []) if p["id"] != preset.id]
                self.state.put("user_presets", users + [preset.model_dump()])
            return self.presets()
        if method == "delete_preset":
            self.state.put(
                "user_presets", [p for p in self.state.get("user_presets", []) if p["id"] != params["id"]]
            )
            return self.presets()
        if method == "save_settings":
            settings = Settings.model_validate(params["settings"])
            with self.lock:
                if self.current or self.downloads:
                    raise ValueError("Finish or cancel processing before changing runtime settings.")
                self.settings = settings
                self.state.put("settings", settings.model_dump())
                terminate(self.worker)
                self.worker = None
                self.model_dir = Path(settings.model_directory or self.root / "models").expanduser().resolve()
                self.catalog = Catalog(self.model_dir, self.root)
            return settings.model_dump()
        if method == "storage":
            return {
                "models": directory_size(self.model_dir),
                "cache": directory_size(self.cache),
                "runtime": directory_size(Path(sys.prefix)),
                "disk_free": shutil.disk_usage(self.root).free,
            }
        if method == "clear_cache":
            with self.cache_lock, self.lock:
                if self.current:
                    raise ValueError("Wait for processing to finish before clearing caches.")
                clear_cache(self.cache)
            return True
        if method == "diagnostics":
            caps = self.capabilities()
            return {
                "app": __version__,
                "protocol": PROTOCOL_VERSION,
                **caps,
                "model_directory": str(self.model_dir).replace(str(Path.home()), "~"),
                "logs": "~/[application-data]/Separator/logs",
                "loaded_model": None,
                "privacy": "Audio stays on this computer. No telemetry.",
            }
        if method == "shutdown":
            self.close()
            return True
        raise ValueError(f"Unknown engine method: {method}")

    def close(self):
        self.runtime_installer.close()
        with self.lock:
            self.stop.set()
            self.running = False
            workers = [self.worker, *self.downloads.values()]
        self.wake.set()
        for proc in workers:
            terminate(proc)

        self.queue_thread.join(timeout=6)
        self.instance_lock.release()


def main():
    root = Path(os.environ.get("SEPARATOR_DATA_DIR") or user_data_dir("Separator", "EliasKanakidis"))
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(logs / "engine.log", maxBytes=2_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    wire = sys.stdout
    sys.stdout = sys.stderr
    write_lock = threading.Lock()

    def write(data):
        with write_lock:
            wire.write(json.dumps(data, allow_nan=False) + "\n")
            wire.flush()

    def emit(event, **data):
        write({"v": PROTOCOL_VERSION, "event": event, "data": data})

    supervisor = Supervisor(root, emit)

    def stopped(_signal, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stopped)

    def handle(request):
        try:
            result = supervisor.dispatch(request.method, request.params)
            write({"v": PROTOCOL_VERSION, "id": request.id, "result": result})
        except Exception as error:
            logging.exception("Request failed: %s", request.method)
            write(
                {
                    "v": PROTOCOL_VERSION,
                    "id": request.id,
                    "error": {"code": type(error).__name__, "message": str(error)[:2000]},
                }
            )

    try:
        for line in sys.stdin:
            try:
                request = Request.model_validate_json(line)
            except Exception:
                write(
                    {
                        "v": PROTOCOL_VERSION,
                        "id": "invalid",
                        "error": {"code": "InvalidRequest", "message": "Invalid protocol request."},
                    }
                )
                continue
            if request.method == "shutdown":
                handle(request)
                break
            supervisor.pool.submit(handle, request)
    finally:
        supervisor.close()
        supervisor.pool.shutdown(wait=True, cancel_futures=True)
        supervisor.queue_thread.join(timeout=6)
        supervisor.state.close()


if __name__ == "__main__":
    main()
