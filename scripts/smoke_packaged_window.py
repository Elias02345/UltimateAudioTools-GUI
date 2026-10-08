"""Launch the real Linux installer in a fresh profile and verify production UI/readiness."""

import argparse
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from native_ui import NativeWindow


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


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
                window.click("Recommended setup")
                window.wait_text("Drop your audio here")
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
                            "checks": [
                                "fresh profile",
                                "production CSP",
                                "private CPU runtime",
                                "readiness",
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
                print(log.read()[-6000:], flush=True)
                raise
            finally:
                if session:
                    try:
                        urllib.request.urlopen(
                            urllib.request.Request(server + "/session/" + session, method="DELETE"),
                            timeout=15,
                        ).close()
                    except OSError:
                        pass
                proc.terminate()
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
