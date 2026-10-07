"""Create a real custom ensemble and compare a matching excerpt in the native window."""

import copy
import hashlib
import json
import time
import uuid
from pathlib import Path

from native_ui import NativeWindow

ROOT = Path(__file__).resolve().parents[1]
window = NativeWindow(
    json.loads((ROOT / ".test-output/webdriver-session.json").read_text())["value"]["sessionId"]
)
source = Path(json.loads((ROOT / ".test-output/native-acceptance.json").read_text())["job"]["source"]["path"])
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
window.call("/refresh", {})
window.wait_text("Audio stays on this computer")
window.click("Home")
window.wait_text("Drop your audio here")
settings = window.engine("initialize")["settings"]
base = copy.deepcopy(next(p for p in window.engine("initialize")["presets"] if p["id"] == "balanced_vocals"))
base.update(
    id="comparison_" + uuid.uuid4().hex,
    name="Acceptance Solo " + uuid.uuid4().hex[:6],
    builtin=False,
    task="Both",
    algorithm="avg_fft",
)
base["parameters"]["device"] = settings["parameters"]["device"]
base["parameters"]["overlap"] = 2
window.engine("save_preset", preset=base)
ensemble = copy.deepcopy(base)
ensemble.update(id="comparison_" + uuid.uuid4().hex, name="Acceptance Ensemble " + uuid.uuid4().hex[:6])
window.engine("save_preset", preset=ensemble)
window.call("/refresh", {})
window.wait_text("Audio stays on this computer")
window.click("Presets")
window.wait_text(ensemble["name"])
window.click_row("data-preset-id", ensemble["id"], "Edit")
window.set_label("RoFormer overlap", "4", ".preset-editor")
window.js(
    "const el=document.querySelector('[aria-label=\"Search ensemble models\"]');Object.ge"
    "tOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'big_beta6x"
    "');el.dispatchEvent(new Event('input',{bubbles:true}));"
)
window.wait(
    lambda: window.js("return document.querySelector('[aria-label=\"Add model\"]')?.options.length>1;")
)
window.js(
    "const el=document.querySelector('[aria-label=\"Add model\"]');el.value='melband_rofo"
    "rmer_big_beta6x.ckpt';el.dispatchEvent(new Event('change',{bubbles:true}));"
)
window.click("Save preset")
window.wait(
    lambda: (
        len(next(p for p in window.engine("initialize")["presets"] if p["id"] == ensemble["id"])["models"])
        == 2
    )
)
window.click("Home")
window.drop(source)
window.click("Compare")
window.wait_text("Choose 2–4 presets")
window.set_label("Range start (seconds)", "5")
window.set_label("Range end (seconds)", "25")
# Uncheck existing defaults, then choose these actual saved presets.
for label in window.js(
    "return [...document.querySelectorAll('.compare-choice')].filter(l=>l.querySelector"
    "('input').checked).map(l=>l.querySelector('strong').textContent)"
):
    window.js(
        "[...document.querySelectorAll('.compare-choice')].find(l=>l.querySelector('strong'"
        ").textContent===arguments[0]).querySelector('input').click()",
        label,
    )
for label in [base["name"], ensemble["name"]]:
    window.js(
        "[...document.querySelectorAll('.compare-choice')].find(l=>l.querySelector('strong'"
        ").textContent===arguments[0]).querySelector('input').click()",
        label,
    )
window.click("Run comparison")
window.js(
    "[...document.querySelectorAll('dialog button')].find(b=>b.textContent.trim()==='Run comparison').click()"
)
jobs = window.wait(
    lambda: [
        j for j in window.engine("list_jobs") if j["request"]["preset"]["id"] in {base["id"], ensemble["id"]}
    ],
    seconds=30,
)
window.wait(
    lambda: (
        len(
            [
                j
                for j in window.engine("list_jobs")
                if j["request"]["preset"]["id"] in {base["id"], ensemble["id"]}
            ]
        )
        == 2
    )
)
jobs = window.wait(
    lambda: (
        lambda js: js if len(js) == 2 and all(j["status"] in {"Completed", "Failed"} for j in js) else None
    )(
        [
            j
            for j in window.engine("list_jobs")
            if j["request"]["preset"]["id"] in {base["id"], ensemble["id"]}
        ]
    ),
    seconds=300,
)
assert all(j["status"] == "Completed" for j in jobs), jobs
assert {j["request"]["preset"]["parameters"]["overlap"] for j in jobs} == {2, 4}
assert all(abs(o["duration"] - 20) < 0.01 for j in jobs for o in j["result"]["outputs"])
window.click("Home")
window.js(
    "window.__testAudio=[];const OriginalAudio=window.Audio;window.Audio=function(...ar"
    "gs){const el=new OriginalAudio(...args);window.__testAudio.push(el);return el};win"
    "dow.Audio.prototype=OriginalAudio.prototype"
)
window.click("Compare")
window.wait_text("Reveal models")
window.wait(
    lambda: window.js("return window.__testAudio.length===5&&window.__testAudio.every(a=>a.readyState>=2);")
)
assert window.js("return window.__testAudio.every(a=>Math.abs(a.duration-20)<0.01)")
window.js("document.querySelector('[data-testid=play-result]').click()")
window.wait(lambda: window.js("return window.__testAudio.every(a=>!a.paused&&a.currentTime>0.2)"))
for index in [1, 3, 0, 4]:
    window.js("document.querySelectorAll('.track-select')[arguments[0]].click()", index)
    time.sleep(0.2)
    assert window.js(
        "return Math.max(...window.__testAudio.map(a=>a.currentTime))-Math.min(...window.__"
        "testAudio.map(a=>a.currentTime))<0.12"
    )
window.js("document.querySelector('[data-testid=play-result]').click()")
assert "A ·" in window.text() and "B ·" in window.text()
window.click("Reveal models")
window.wait_text(ensemble["name"] + " ·")
window.screenshot(ROOT / ".test-output/native-comparison.png")
output_paths = [Path(o["path"]) for j in jobs for o in j["result"]["outputs"]]
window.click("Delete comparison data")
window.click("Delete comparison")
window.wait(lambda: not any(p.exists() for p in output_paths))
assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
for p in [base, ensemble]:
    window.engine("delete_preset", id=p["id"])
(ROOT / ".test-output/native-comparison.json").write_text(
    json.dumps(
        {
            "jobs": jobs,
            "checks": [
                "UI ensemble creation",
                "distinct stored parameters",
                "real CUDA ensemble",
                "matching 20-second original and outputs",
                "native blind A/B playback",
                "model reveal",
                "safe temporary cleanup",
            ],
        },
        indent=2,
    )
)
print("NATIVE COMPARISON ACCEPTANCE PASSED", flush=True)
