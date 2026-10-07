"""Genuine end-to-end integration check; uses the same supervisor and inference worker as the desktop."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from separator_engine.schema import JobRequest, OutputSettings, Preset
from separator_engine.server import Supervisor

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="bs_roformer_vocals_resurrection_unwa.ckpt")
parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
parser.add_argument("--precision", default="float32", choices=["float32", "autocast", "float16"])
parser.add_argument("--preset")
parser.add_argument("--task", default="Both")
parser.add_argument("--chunk", type=int)
parser.add_argument("--duration", type=int, default=20)
parser.add_argument("--engine", choices=["native", "container"], default="native")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
data = root / ".test-data"
data.mkdir(exist_ok=True)
rate = 44100
t = np.arange(rate * args.duration, dtype=np.float32) / rate
rng = np.random.default_rng(42)
voice = np.sin(2 * np.pi * (220 * t + 6 * np.sin(2 * np.pi * 3 * t))) * (
    0.08 + 0.03 * np.sin(2 * np.pi * 4 * t)
)
music = 0.1 * np.sin(2 * np.pi * 110 * t) + 0.06 * np.sin(2 * np.pi * 440 * t)
beat = rng.standard_normal(len(t)).astype(np.float32) * np.exp(-np.mod(t, 0.5) * 40) * 0.04
mix = np.stack([voice + music + beat, voice * 0.9 + music * 0.7 + beat], axis=1)
source = data / f"Test 🎵 café {args.duration}s.wav"
sf.write(source, mix, rate, subtype="FLOAT")


def event(name, **payload):
    if name == "job_updated":
        job = payload["job"]
        detail = job.get("download")
        if not detail or detail.get("bytes", 0) % (10 * 1024 * 1024) < 1024 * 1024:
            print(
                json.dumps({"status": job["status"], "model": job.get("model"), "download": detail}),
                flush=True,
            )


supervisor = Supervisor(
    root / ".test-state" / "container-smoke" if args.engine == "container" else root / ".test-state", event
)
try:
    if args.engine == "container":
        settings = supervisor.settings.model_copy(deep=True)
        settings.model_directory = str(root / ".test-state/models")
        supervisor.dispatch("save_settings", {"settings": settings.model_dump()})
    capabilities = supervisor.capabilities()
    if args.device == "cuda" and not capabilities["cuda"]:
        raise RuntimeError("This CUDA test requires a working NVIDIA backend.")
    if args.preset:
        preset = Preset.model_validate(next(p for p in supervisor.presets() if p["id"] == args.preset))
        preset.task = "Both"
    else:
        preset = Preset(id="integration", name="Integration", task="Both", models=[args.model])
    preset.task = args.task
    preset.engine = args.engine
    preset.parameters.chunk_duration = args.chunk
    preset.parameters.device = args.device
    preset.parameters.precision = args.precision
    preset.output = OutputSettings(directory=str(root / ".test-output"), format="FLAC")
    request = JobRequest(path=str(source), preset=preset, download_consent=True)
    job = supervisor.dispatch("enqueue", {"requests": [request.model_dump()], "start": True})[0]
    while job["status"] not in {"Completed", "Failed", "Cancelled"}:
        time.sleep(1)
    if job["status"] != "Completed":
        raise RuntimeError(job["error"] or job["status"])
    for output in job["result"]["outputs"]:
        samples, sr = sf.read(output["path"], always_2d=True)
        assert sr == rate
        assert len(samples) == rate * args.duration
        assert samples.shape[1] == 2
        assert np.isfinite(samples).all()
        assert Path(output["path"]).stat().st_size > 100
    if args.device == "cuda":
        assert all(m["device"].startswith("cuda") for m in job["result"]["models"])
    report_name = (
        f"{args.preset or args.model}-{args.precision}-{args.device}-"
        f"{args.duration}s-chunk{args.chunk}-{args.engine}.json"
    )
    report = root / ".test-output" / report_name
    report.write_text(json.dumps({"capabilities": capabilities, "job": job}, indent=2))
    print("REAL SEPARATION PASSED", report, flush=True)
finally:
    supervisor.close()
    supervisor.queue_thread.join(timeout=10)
