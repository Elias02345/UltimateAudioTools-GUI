"""Real native-window acceptance. Requires a running tauri-driver session and cached models."""

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf
from native_ui import NativeWindow

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--session-file", type=Path, default=ROOT / ".test-output/webdriver-session.json")
parser.add_argument("--models", type=Path, default=ROOT / ".test-state/models")
args = parser.parse_args()
window = NativeWindow(json.loads(args.session_file.read_text())["value"]["sessionId"])
name = f"Acceptance {uuid.uuid4().hex[:8]}"
source = ROOT / ".test-data" / f"{name} 音楽 café.wav"
source.parent.mkdir(exist_ok=True)
rate = 44100
t = np.arange(rate * 30) / rate
samples = 0.1 * np.sin(2 * np.pi * 220 * t) + 0.04 * np.sin(2 * np.pi * 110 * t)
sf.write(source, np.stack([samples, samples * 0.8], axis=1), rate, subtype="FLOAT")
original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
if "Recommended setup" in window.text():
    window.click("Recommended setup")
window.call("/refresh", {})
window.wait_text("Audio stays on this computer")
window.click("Home")
window.wait_text("Drop your audio here")
initial = window.engine("initialize")
settings = initial["settings"]
settings["model_directory"] = str(args.models.resolve())
settings["output"]["directory"] = str(ROOT / ".test-output/native-acceptance")
settings["parameters"]["device"] = "cuda" if window.engine("get_capabilities")["cuda"] else "cpu"
window.engine("save_settings", settings=settings)
window.call("/refresh", {})
window.wait_text("Audio stays on this computer")
window.click("Home")
window.wait_text("Drop your audio here")
window.drop(source)
window.wait_text(source.name)
window.click("Presets")
window.click("Create preset")
window.set_label("Name", name, ".preset-editor")
window.click("Save preset")
window.wait_text(name)
preset = next(p for p in window.engine("initialize")["presets"] if p["name"] == name)
# Edit via UI to select a cached RoFormer and a real inference setting.
window.click_row("data-preset-id", preset["id"], "Edit")
window.set_label("Name", name + " edited", ".preset-editor")
window.click("Save preset")
window.wait_text(name + " edited")
window.invoke("restart_runtime", {})
window.call("/refresh", {})
window.wait_text("Audio stays on this computer")
window.click("Home")
window.wait_text("Drop your audio here")
presets = window.engine("initialize")["presets"]
assert next(p for p in presets if p["id"] == preset["id"])["name"] == name + " edited"
window.click("Presets")
window.wait_text(name + " edited")
# Keep both desired Ultra defaults intact; use a single RoFormer for the repeated acceptance passes.
preset = next(p for p in presets if p["id"] == preset["id"])
preset["models"] = ["bs_roformer_vocals_resurrection_unwa.ckpt"]
preset["parameters"]["device"] = settings["parameters"]["device"]
preset["parameters"]["overlap"] = 2
preset["output"] = settings["output"]
window.engine("save_preset", preset=preset)
window.call("/refresh", {})
window.wait_text("Audio stays on this computer")
window.click("Home")
window.wait_text("Drop your audio here")
window.drop(source)
window.wait_text(source.name)
window.click("Presets")
window.click_row("data-preset-id", preset["id"], "Use")
window.click("Separate audio")
window.wait_text("Queue")
job = window.wait(
    lambda: next(
        (
            j
            for j in window.engine("list_jobs")
            if j["source"]["name"] == source.name and j["status"] == "Processing"
        ),
        None,
    ),
    seconds=180,
)
window.click_row("data-job-id", job["id"], f"Cancel {source.name}")
window.wait(
    lambda: next(j for j in window.engine("list_jobs") if j["id"] == job["id"])["status"] == "Cancelled"
)
time.sleep(1)
window.click_row("data-job-id", job["id"], "Retry")
window.wait_text("Pending")
window.click("Process next")
completed = window.wait(
    lambda: next(
        (
            j
            for j in window.engine("list_jobs")
            if j["id"] == job["id"] and j["status"] in {"Completed", "Failed"}
        ),
        None,
    ),
    seconds=240,
)
assert completed["status"] == "Completed", completed["error"]
assert completed["request"]["preset"]["parameters"]["overlap"] == 2
for output in completed["result"]["outputs"]:
    audio, sr = sf.read(output["path"], always_2d=True)
    assert sr == rate and len(audio) == 30 * rate and np.isfinite(audio).all()
window.js(
    "window.__testAudio=[];const OriginalAudio=window.Audio;"
    "window.Audio=function(...a){const el=new OriginalAudio(...a);window.__testAudio.push(el);return el};"
    "window.Audio.prototype=OriginalAudio.prototype;"
)
window.click_row("data-job-id", job["id"], "Listen")
window.wait(
    lambda: window.js("return window.__testAudio.length>=2 && window.__testAudio.every(a=>a.readyState>=2);")
)
window.js("document.querySelector('[data-testid=play-result]').click()")
window.wait(lambda: window.js("return window.__testAudio.every(a=>a.currentTime>0.2&&!a.paused);"))
window.js("document.querySelectorAll('.track-select')[1].click()")
time.sleep(0.5)
assert window.js(
    "return Math.max(...window.__testAudio.map(a=>a.currentTime))"
    "-Math.min(...window.__testAudio.map(a=>a.currentTime))<0.12;"
)
window.js("document.querySelector('[data-testid=play-result]').click()")
window.screenshot(ROOT / ".test-output/native-acceptance-result.png")
window.click("Models")
window.js(
    "const el=document.querySelector('[aria-label=\"Search models\"]');"
    "Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'resurrection');"
    "el.dispatchEvent(new Event('input',{bubbles:true}));"
)
window.wait_text(preset["models"][0])
assert next(m for m in window.engine("list_models") if m["id"] == preset["models"][0])["downloaded"]
assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
window.click("Presets")
window.click_row("data-preset-id", preset["id"], f"Delete preset {preset['name']}")
window.click("Delete preset")
window.wait(lambda: all(p["id"] != preset["id"] for p in window.engine("initialize")["presets"]))
(ROOT / ".test-output/native-acceptance.json").write_text(
    json.dumps(
        {
            "job": completed,
            "source_sha256": original_hash,
            "checks": [
                "native drag-drop",
                "preset create/edit/restart/delete",
                "real RoFormer CUDA or CPU",
                "cancel/retry",
                "output integrity",
                "native audio playback/switch synchronization",
                "model catalogue",
            ],
        },
        indent=2,
    )
)
print("NATIVE ACCEPTANCE PASSED", flush=True)
