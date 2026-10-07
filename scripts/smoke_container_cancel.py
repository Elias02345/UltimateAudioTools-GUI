"""Cancel an actual container inference and prove only its owned container is removed."""

import json
import subprocess
import time
from pathlib import Path

from separator_engine.schema import JobRequest, Preset
from separator_engine.server import Supervisor

ROOT = Path(__file__).resolve().parents[1]
supervisor = Supervisor(ROOT / ".test-state/container-cancel", lambda *a, **kw: None)
try:
    settings = supervisor.settings.model_copy(deep=True)
    settings.model_directory = str(ROOT / ".test-state/models")
    settings.output.directory = str(ROOT / ".test-output/container-cancel")
    supervisor.dispatch("save_settings", {"settings": settings.model_dump()})
    preset = Preset(
        id="container-test",
        name="Container cancellation",
        models=["bs_roformer_vocals_resurrection_unwa.ckpt"],
        engine="container",
    )
    preset.parameters.device = "cpu"
    job = supervisor.dispatch(
        "enqueue",
        {
            "requests": [
                JobRequest(
                    path=str(ROOT / ".test-data/Test 🎵 café.wav"), preset=preset, download_consent=True
                ).model_dump()
            ],
            "start": True,
        },
    )[0]
    deadline = time.monotonic() + 120
    while job["status"] != "Processing":
        if job["status"] == "Failed" or time.monotonic() > deadline:
            raise RuntimeError(job["error"] or "Container did not begin inference")
        time.sleep(0.1)
    name = supervisor.worker.separator_container[1]
    supervisor.dispatch("cancel_job", {"id": job["id"]})
    while supervisor.current is not None and time.monotonic() < deadline:
        time.sleep(0.1)
    assert job["status"] == "Cancelled"
    assert subprocess.run(["docker", "container", "inspect", name], capture_output=True).returncode != 0
    assert not list(supervisor.work_root.iterdir())
    (ROOT / ".test-output/container-cancel.json").write_text(
        json.dumps({"container": name, "status": job["status"]})
    )
    print("REAL CONTAINER CANCELLATION PASSED", flush=True)
finally:
    supervisor.close()
