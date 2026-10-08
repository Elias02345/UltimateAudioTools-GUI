"""Launch the real Linux installer in a fresh profile and verify production UI/readiness."""

import argparse
import array
import json
import math
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request
import wave
from pathlib import Path

from native_ui import NativeWindow


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def process_tree(pid):
    """Capture only this test driver's children before shutting them down."""
    processes = []
    pending = [pid]
    while pending:
        current = pending.pop()
        try:
            proc = Path(f"/proc/{current}")
            processes.append(
                {
                    "pid": current,
                    "status": (proc / "status").read_text(),
                    "command": (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(),
                }
            )
            pending.extend(int(child) for child in (proc / f"task/{current}/children").read_text().split())
        except OSError:
            processes.append({"pid": current, "exited": True})
    return processes


def smoke(application: Path, report: Path):
    driver = shutil.which("tauri-driver")
    native = shutil.which("WebKitWebDriver")
    if not driver or not native:
        raise ValueError("tauri-driver and WebKitWebDriver are required for the native package test.")
    server_port, native_port = port(), port()
    while native_port == server_port:
        native_port = port()
    server = f"http://127.0.0.1:{server_port}"
    session = None
    window = None
    with tempfile.TemporaryDirectory(prefix="Separator fresh package café ") as temp:
        profile = Path(temp)
        env = {**os.environ, "APPIMAGE_EXTRACT_AND_RUN": "1"}
        env.update({f"XDG_{name}_HOME": str(profile / name.lower()) for name in ["DATA", "CONFIG", "CACHE"]})
        # Media must come from the installer rather than a development-only plugin directory.
        env.pop("GST_PLUGIN_PATH", None)
        env.pop("GST_PLUGIN_SYSTEM_PATH", None)
        with (profile / "driver.log").open("w+") as log:
            proc = subprocess.Popen(
                [
                    driver,
                    "--native-driver",
                    native,
                    "--port",
                    str(server_port),
                    "--native-port",
                    str(native_port),
                ],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    try:
                        urllib.request.urlopen(server + "/status", timeout=1).close()
                        break
                    except OSError:
                        if proc.poll() is not None:
                            raise RuntimeError("Native driver exited before startup.") from None
                        time.sleep(0.2)
                request = urllib.request.Request(
                    server + "/session",
                    data=json.dumps(
                        {
                            "capabilities": {
                                "alwaysMatch": {"tauri:options": {"application": str(application.resolve())}}
                            }
                        }
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                )
                session = json.loads(urllib.request.urlopen(request, timeout=90).read())["value"]["sessionId"]
                window = NativeWindow(session, server)
                window.wait_text("Recommended setup", seconds=90)
                assert window.js("return location.href").startswith("tauri://localhost"), (
                    "Development URL used"
                )
                initial = window.engine("initialize")
                assert not initial["settings"]["setup_complete"], "Profile was not fresh"
                checks = window.engine("self_test")
                assert all(check["passed"] for check in checks), checks
                caps = window.engine("get_capabilities")
                assert "+cpu" in caps["torch"] and not caps["cuda"], (
                    "Baseline private CPU runtime was not used"
                )
                assert "9.0.2" in caps["ffmpeg"]
                recording = profile / "Playback café 音楽.wav"
                samples = array.array(
                    "h",
                    (
                        int(300 * math.sin(2 * math.pi * 440 * i / 44100))
                        for i in range(44100 * 6)
                        for _ in range(2)
                    ),
                )
                with wave.open(str(recording), "wb") as audio:
                    audio.setnchannels(2)
                    audio.setsampwidth(2)
                    audio.setframerate(44100)
                    audio.writeframes(samples.tobytes())
                preview = window.engine("preview", path=str(recording))
                media = window.invoke("audio_url", {"path": preview})
                assert "ok" in media, media
                window.js(
                    "window.__mediaProbe={error:null,audio:new Audio(arguments[0])};"
                    "window.__mediaProbe.audio.volume=0.05;"
                    "window.__mediaProbe.audio.addEventListener('error',"
                    "()=>window.__mediaProbe.error='Native audio failed');"
                    "window.__mediaProbe.audio.play().catch(e=>window.__mediaProbe.error=String(e));"
                    " return true;",
                    media["ok"],
                )
                window.wait(
                    lambda: window.js(
                        "return window.__mediaProbe.audio.currentTime>0.2 "
                        "|| window.__mediaProbe.error!==null;"
                    ),
                    seconds=20,
                )
                assert window.js("return window.__mediaProbe.error===null"), window.js(
                    "return String(window.__mediaProbe.error)"
                )
                assert window.js("return window.__mediaProbe.audio.duration") == 6
                window.js("window.__mediaProbe.audio.pause(); return true;")
                window.click("Recommended setup")
                window.wait_text("Drop your audio here")
                preset = next(p for p in initial["presets"] if p["id"] == "fast_instrumental")
                preset["parameters"]["device"] = "cpu"
                preset["output"]["directory"] = str(profile / "results")
                job = window.engine(
                    "enqueue",
                    requests=[{"path": str(recording), "preset": preset, "download_consent": True}],
                    start=True,
                )[0]
                completed = window.wait(
                    lambda: next(
                        (
                            item
                            for item in window.engine("list_jobs")
                            if item["id"] == job["id"] and item["status"] in {"Completed", "Failed"}
                        ),
                        None,
                    ),
                    seconds=300,
                )
                assert completed["status"] == "Completed", completed["error"]
                assert completed["result"]["device"] == "cpu", completed["result"]
                session_file = profile / "window-session.json"
                session_file.write_text(json.dumps({"value": {"sessionId": session}}))
                project = Path(__file__).resolve().parents[1]
                python = project / "apps/desktop/src-tauri/resources/runtime/python/bin/python3"
                workflows = {}
                for name, script in [("results", "native_results.py"), ("projects", "native_projects.py")]:
                    checks_directory = profile / f"{name}-checks"
                    subprocess.run(
                        [
                            str(python),
                            str(project / "scripts" / script),
                            "--session-file",
                            str(session_file),
                            "--server",
                            server,
                            "--job-id",
                            job["id"],
                            "--output",
                            str(checks_directory),
                        ],
                        check=True,
                        timeout=300,
                        env={**env, "PYTHONNOUSERSITE": "1", "PYTHONPATH": ""},
                    )
                    workflows[name] = json.loads((checks_directory / "report.json").read_text())
                window.call("/window/rect", {"width": 900, "height": 640})
                assert window.js("return document.documentElement.scrollWidth <= window.innerWidth"), (
                    "Minimum window overflows"
                )
                report.parent.mkdir(parents=True, exist_ok=True)
                window.screenshot(report.with_suffix(".png"))
                report.write_text(
                    json.dumps(
                        {
                            "application": application.name,
                            "capabilities": caps,
                            "readiness": checks,
                            "result_workflow": workflows["results"],
                            "project_workflow": workflows["projects"],
                            "checks": [
                                "fresh profile",
                                "production CSP",
                                "private CPU runtime",
                                "readiness",
                                "native preview playback advances",
                                "real Fast CPU separation",
                                "native result editing and export",
                                "projects, stem actions, batch export, support and updates",
                                "minimum window",
                            ],
                        },
                        indent=2,
                    )
                )
                print("PRODUCTION NATIVE WINDOW PASSED", report, flush=True)
            except Exception:
                log.flush()
                log.seek(0)
                diagnostics = report.with_suffix(".failure")
                diagnostics.mkdir(parents=True, exist_ok=True)
                driver_log = log.read()
                (diagnostics / "driver.log").write_text(driver_log)
                (diagnostics / "driver-status.json").write_text(
                    json.dumps(
                        {"pid": proc.pid, "exit_code": proc.poll(), "processes": process_tree(proc.pid)},
                        indent=2,
                    )
                )
                for directory in profile.rglob("logs"):
                    if directory.is_dir():
                        shutil.copytree(
                            directory,
                            diagnostics / directory.relative_to(profile),
                            dirs_exist_ok=True,
                        )
                if window:
                    try:
                        window.screenshot(diagnostics / "window.png")
                        (diagnostics / "window.txt").write_text(window.text())
                    except (OSError, RuntimeError):
                        pass
                print(driver_log[-6000:], flush=True)
                raise
            finally:
                if window:
                    try:
                        window.js(
                            "window.__TAURI_INTERNALS__.invoke('plugin:window|close',{label:'main'})"
                            ".catch(()=>{}); return true;"
                        )
                        time.sleep(0.3)
                    except RuntimeError:
                        pass
                if session:
                    try:
                        urllib.request.urlopen(
                            urllib.request.Request(server + "/session/" + session, method="DELETE"),
                            timeout=15,
                        ).close()
                    except OSError:
                        pass
                # AppImage wrappers can leave GTK children behind after a failed session.
                # This new process group contains only the driver and its test application.
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--application", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path(".test-output/package-window.json"))
    args = parser.parse_args()
    smoke(args.application, args.report)
