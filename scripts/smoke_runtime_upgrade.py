"""Exercise the actual transactional GPU upgrade against the built private CPU runtime."""

import os
import time
from pathlib import Path

from separator_engine.runtime import RuntimeInstaller
from separator_engine.server import terminate

root = Path(__file__).resolve().parents[1]
os.environ["SEPARATOR_RUNTIME_BASE"] = str(root / "apps/desktop/src-tauri/resources/runtime/python")
os.environ["SEPARATOR_RUNTIME_MANIFESTS"] = str(root / "runtime")
data = root / ".test-state/runtime-upgrade"
data.mkdir(parents=True, exist_ok=True)
installer = RuntimeInstaller(
    data,
    lambda event, **data: print(event, data.get("phase"), (data.get("log") or [""])[-1], flush=True),
    terminate,
)
installer.start()
try:
    while installer.thread.is_alive():
        time.sleep(1)
    assert installer.status["phase"] == "completed", installer.status
    print("PRIVATE CUDA UPGRADE PASSED", data, flush=True)
finally:
    installer.close()
