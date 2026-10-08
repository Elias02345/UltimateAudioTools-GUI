"""Exercise result editing and exports in a real Tauri window with completed audio."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from native_ui import NativeWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-file", type=Path, required=True)
    parser.add_argument("--server", default="http://127.0.0.1:4444")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    window = NativeWindow(json.loads(args.session_file.read_text())["value"]["sessionId"], args.server)
    window.call("/refresh", {})
    window.wait(lambda: window.js('return Boolean(document.querySelector(".app-shell"));'))
    job = next(j for j in window.engine("list_jobs") if j["id"] == args.job_id)
    assert job["status"] == "Completed"
    paths = [job["source"]["path"], *[o["path"] for o in job["result"]["outputs"]]]
    hashes = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths}

    def set_input(selector, value):
        window.js(
            "const e=document.querySelector(arguments[0]); if(!e)throw new Error(arguments[0]);"
            "const p=e.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;"
            "Object.getOwnPropertyDescriptor(p,'value').set.call(e,arguments[1]);"
            "e.dispatchEvent(new Event(e.tagName==='SELECT'?'change':'input',{bubbles:true}));",
            selector,
            str(value),
        )

    window.click("Library")
    window.wait_text("Made from your music")
    set_input('[aria-label="Search history"]', job["source"]["name"])
    window.wait(
        lambda: window.js(
            "return document.querySelector(arguments[1]).value===arguments[0];",
            job["source"]["name"],
            '[aria-label="Search history"]',
        )
    )
    window.js(
        "window.__testAudio=[];const OriginalAudio=window.Audio;"
        "window.Audio=function(...a){const el=new OriginalAudio(...a);"
        "window.__testAudio.push(el);return el};window.Audio.prototype=OriginalAudio.prototype;return true;"
    )
    window.click_row("data-job-id", job["id"], "Open result")
    window.wait(
        lambda: window.js(
            "return window.__testAudio.length>=2&&window.__testAudio.every(a=>a.readyState>=2);"
        )
    )
    window.click("Edit audio")
    window.click("Reset edits")
    set_input('[aria-label="Trim start"]', "")
    set_input('[aria-label="Trim end"]', 5)
    assert window.js(
        "return [...document.querySelectorAll('button')]"
        ".find(b=>b.textContent.trim()==='Export stems').disabled;"
    )
    set_input('[aria-label="Trim end"]', "")
    window.click("Set start here")
    assert window.js(
        "return [...document.querySelectorAll('button')]"
        ".find(b=>b.textContent.trim()==='Export stems').disabled;"
    )
    set_input('[aria-label="Trim start"]', 2.25)
    set_input('[aria-label="Trim end"]', 4.75)
    stem = job["result"]["outputs"][0]
    set_input(f'[aria-label="{stem["stem"]} gain"]', 0.5)
    window.wait_text("Edits saved locally")
    window.js(
        "[...document.querySelectorAll('.track-select')].find(b=>b.textContent.includes(arguments[0])).click();",
        stem["stem"],
    )
    window.js('document.querySelector("[data-testid=play-result]").click();')
    window.wait(lambda: window.js("return window.__testAudio.every(a=>a.currentTime>2.4&&!a.paused);"))
    window.wait(lambda: window.js("return window.__testAudio.every(a=>a.paused);"), seconds=10)
    assert abs(window.js("return window.__testAudio[1].volume;") - 0.425) < 1e-5
    window.screenshot(root / "editor.png")
    window.click("Back to Library")
    assert (
        window.js("return document.querySelector(arguments[0]).value;", '[aria-label="Search history"]')
        == job["source"]["name"]
    )
    window.click_row("data-job-id", job["id"], "Open result")
    window.click("Edit audio")
    assert (
        window.js("return document.querySelector(arguments[0]).value;", '[aria-label="Trim start"]') == "2.25"
    )
    assert (
        window.js("return document.querySelector(arguments[0]).value;", '[aria-label="Trim end"]') == "4.75"
    )
    assert (
        window.js("return document.querySelector(arguments[0]).value;", f'[aria-label="{stem["stem"]} gain"]')
        == "0.5"
    )
    window.click("Export stems")
    window.wait_text("Choose the stems to save")
    window.screenshot(root / "export.png")
    # Keep only one selected stem, regardless of the result's stem count.
    window.js(
        "const inputs=[...document.querySelectorAll('.export-stem input')];"
        "inputs.slice(1).forEach(e=>e.click());"
    )
    set_input(".export-folder input", root)
    set_input(".export-options input", "My edit 音楽")
    window.click("Export 1 stem")
    window.wait_text("Export complete")
    first = next(root.glob("My edit*.flac"))
    edited, rate = sf.read(first, always_2d=True)
    original, source_rate = sf.read(stem["path"], always_2d=True)
    assert rate == source_rate
    expected = original[round(2.25 * rate) : round(4.75 * rate)] * 0.5
    np.testing.assert_allclose(edited, expected, atol=2e-7)
    window.js("document.querySelector('.exported-files button').click();")
    window.wait(lambda: window.js("return document.querySelector('.export-preview audio')?.readyState>=2;"))
    window.js("document.querySelector('.export-preview audio').play();")
    window.wait(lambda: window.js("return document.querySelector('.export-preview audio').currentTime>0.2;"))
    window.js("document.querySelector('.export-preview audio').pause();")
    window.screenshot(root / "success.png")
    window.click("Done")
    window.click("Export stems")
    window.js("[...document.querySelectorAll('.export-stem input')].slice(1).forEach(e=>e.click());")
    set_input(".export-folder input", root)
    set_input(".export-options input", "My edit 音楽")
    window.click("Export 1 stem")
    window.wait_text("Export complete")
    assert len(list(root.glob("My edit*.flac"))) == 2
    window.click("Done")
    window.click("Export stems")
    window.click("Cancel")
    assert not window.js('return Boolean(document.querySelector("dialog"));')
    window.click("Reset edits")
    window.click("Back to Library")
    window.click_row("data-job-id", job["id"], "Export")
    window.wait_text("Copies the created files exactly")
    set_input(".export-folder input", root)
    window.click(
        f"Export {len(job['result']['outputs'])} {'stem' if len(job['result']['outputs']) == 1 else 'stems'}"
    )
    window.wait_text("Export complete")
    for output in job["result"]["outputs"]:
        assert (
            hashlib.sha256((root / Path(output["path"]).name).read_bytes()).hexdigest()
            == hashes[output["path"]]
        )
    window.click("Done")
    window.click_row("data-job-id", job["id"], f"Remove {job['source']['name']} from history")
    window.wait_text("Remove this result from history?")
    window.click("Cancel")
    assert any(j["id"] == job["id"] for j in window.engine("list_jobs"))
    assert all(
        hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in hashes.items()
    )
    window.call("/window/rect", {"width": 900, "height": 640})
    assert window.js("return document.documentElement.scrollWidth<=innerWidth;")
    window.screenshot(root / "library-minimum.png")
    (root / "report.json").write_text(
        json.dumps(
            {
                "job_id": job["id"],
                "source_hashes": hashes,
                "checks": [
                    "native aligned range playback and gain",
                    "blank time fields keep export disabled",
                    "range end stops playback",
                    "persistent edit draft",
                    "return preserves library search",
                    "selected edited FLAC sample parity",
                    "exported audio plays within the app",
                    "repeat export unique names",
                    "cancel preserves result",
                    "byte-identical original copies",
                    "history removal cancellation",
                    "original audio hashes preserved",
                    "minimum window no horizontal overflow",
                ],
            },
            indent=2,
        )
    )
    print("REAL NATIVE RESULT WORKFLOW PASSED", flush=True)


if __name__ == "__main__":
    main()
