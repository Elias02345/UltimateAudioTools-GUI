"""Verify projects, stem actions, batch exports and support in an actual native window."""

import argparse
import hashlib
import json
import uuid
from collections import Counter
from pathlib import Path

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
    first = next(j for j in window.engine("list_jobs") if j["id"] == args.job_id)
    assert first["status"] == "Completed"
    original_paths = [first["source"]["path"], *[o["path"] for o in first["result"]["outputs"]]]
    original_hashes = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in original_paths}

    def set_input(selector, value):
        window.js(
            "const e=document.querySelector(arguments[0]);if(!e)throw new Error(arguments[0]);"
            "const p=e.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;"
            "Object.getOwnPropertyDescriptor(p,'value').set.call(e,arguments[1]);"
            "e.dispatchEvent(new Event(e.tagName==='SELECT'?'change':'input',{bubbles:true}));",
            selector,
            str(value),
        )

    suffix = uuid.uuid4().hex[:6]
    name = f"Native session {suffix}"
    window.click("Projects")
    window.wait_text("A place for every recording")
    window.set_label("New project", name)
    window.click("Create project")
    window.wait_text(name)
    project = next(p for p in window.engine("list_projects") if p["name"] == name)
    window.click("Home")
    set_input('[aria-label="New generation project"]', project["id"])
    assert (
        window.js(
            "return document.querySelector(arguments[0]).value;", '[aria-label="New generation project"]'
        )
        == (project["id"])
    )
    # Execute a second genuine separation; the first run already cached the MDX weights.
    preset = next(p for p in window.engine("initialize")["presets"] if p["id"] == "fast_instrumental")
    preset["parameters"]["device"] = "cpu"
    preset["task"] = "Both"
    preset["output"]["directory"] = str(root / "second-generation")
    second = window.engine(
        "enqueue",
        requests=[{"path": first["source"]["path"], "preset": preset}],
        project_id=project["id"],
        start=True,
    )[0]
    second = window.wait(
        lambda: next(
            (
                j
                for j in window.engine("list_jobs")
                if j["id"] == second["id"] and j["status"] in {"Completed", "Failed"}
            ),
            None,
        ),
        seconds=180,
    )
    assert second["status"] == "Completed", second["error"]
    assert second["result"]["device"] == "cpu"
    assert second["project_id"] == project["id"]

    window.click("Library")
    set_input('[aria-label="Search history"]', "")
    window.js(
        "document.querySelector(arguments[0]).click();", f'[data-job-id="{first["id"]}"] input[type=checkbox]'
    )
    set_input('[aria-label="Move selected results to project"]', project["id"])
    window.click("Move selected")
    window.wait(
        lambda: (
            next(j for j in window.engine("list_jobs") if j["id"] == first["id"]).get("project_id")
            == project["id"]
        )
    )
    window.click("Projects")
    window.click_row("data-project-id", project["id"], "Open project")
    window.wait(
        lambda: (
            window.js(
                'return document.querySelector("h1").textContent;',
            )
            == name
        )
    )
    assert window.js('return document.querySelectorAll(".job-row").length') == 2
    window.call("/refresh", {})
    window.wait(lambda: window.js('return document.querySelectorAll(".job-row").length') == 2)
    assert all(
        j.get("project_id") == project["id"]
        for j in window.engine("list_jobs")
        if j["id"] in {first["id"], second["id"]}
    )

    window.js(
        "window.__stemAudio=[];const OriginalAudio=window.Audio;"
        "window.Audio=function(...a){const el=new OriginalAudio(...a);window.__stemAudio.push(el);return el};"
        "window.Audio.prototype=OriginalAudio.prototype;return true;"
    )
    window.click_row("data-job-id", second["id"], "Open result")
    window.wait(
        lambda: window.js(
            "return window.__stemAudio.length>=3&&window.__stemAudio.every(a=>a.readyState>=2);"
        )
    )
    stem = second["result"]["outputs"][0]["stem"]
    window.js("document.querySelector(arguments[0]).click();", f'[aria-label="Mute {stem}"]')
    window.js("document.querySelector(arguments[0]).click();", f'[aria-label="Play {stem}"]')
    window.wait(lambda: window.js("return window.__stemAudio.filter(a=>!a.muted&&!a.paused).length===1;"))
    window.wait(lambda: window.js("return window.__stemAudio.some(a=>!a.muted&&a.currentTime>0.3);"))
    other = second["result"]["outputs"][1]["stem"]
    window.js("document.querySelector(arguments[0]).click();", f'[aria-label="Play {other}"]')
    window.wait(
        lambda: window.js(
            "return document.querySelector(arguments[0])!==null;", f'[aria-label="Pause {other}"]'
        )
    )
    assert window.js("return window.__stemAudio.filter(a=>!a.muted&&!a.paused).length;") == 1
    window.click("Play all stems")
    window.wait(lambda: window.js("return window.__stemAudio.filter(a=>!a.muted&&!a.paused).length===2;"))
    window.js('document.querySelector("[data-testid=play-result]").click();')
    window.wait(lambda: window.js("return window.__stemAudio.every(a=>a.paused);"))
    window.js("document.querySelector(arguments[0]).click();", f'[aria-label="Export {stem}"]')
    window.wait_text("1 of 2 selected")
    window.click("Select all stems")
    window.wait_text("2 of 2 selected")
    window.click("Clear selection")
    assert window.js(
        'return [...document.querySelectorAll("dialog button")]'
        '.find(b=>b.textContent.trim()==="Export 0 stems").disabled;'
    )
    window.click("Cancel")
    window.screenshot(root / "stem-controls.png")
    window.click("Back to Library")
    set_input('[aria-label="Filter results by project"]', project["id"])
    window.js("document.querySelector(arguments[0]).click();", '[aria-label="Select visible results"]')
    window.click("Export selected results")
    count = len(first["result"]["outputs"]) + len(second["result"]["outputs"])
    window.wait_text(f"{count} of {count} selected")
    (root / "batch-export").mkdir(exist_ok=True)
    set_input(".export-folder input", root / "batch-export")
    window.click(f"Export {count} stems")
    window.wait_text("Export complete")
    saved = window.js(
        'return [...document.querySelectorAll(".exported-files button")].map(b=>b.textContent.trim());'
    )
    expected_hashes = Counter(
        hashlib.sha256(Path(o["path"]).read_bytes()).hexdigest()
        for j in [first, second]
        for o in j["result"]["outputs"]
    )
    actual_hashes = Counter(
        hashlib.sha256((root / "batch-export" / filename).read_bytes()).hexdigest() for filename in saved
    )
    assert actual_hashes == expected_hashes, "Batch export changed original stem samples"
    window.click("Done")

    window.click("Projects")
    window.click_row("data-project-id", project["id"], f"Rename {name}")
    renamed = name + " renamed"
    set_input('[aria-label="Project name"]', renamed)
    window.click("Save name")
    window.wait_text(renamed)
    window.click_row("data-project-id", project["id"], "Archive")
    window.wait(
        lambda: (
            not window.js(
                "return Boolean(document.querySelector(arguments[0]));",
                f'[data-project-id="{project["id"]}"]',
            )
        )
    )
    window.click("Archived")
    window.wait_text(renamed)
    window.screenshot(root / "archived-projects.png")
    window.click_row("data-project-id", project["id"], "Restore")
    window.click("Active")
    window.wait_text(renamed)
    window.click_row("data-project-id", project["id"], f"Remove project {renamed}")
    window.wait_text("Its generations become unfiled")
    window.click("Remove project")
    window.wait(lambda: not any(p["id"] == project["id"] for p in window.engine("list_projects")))
    assert all(
        j.get("project_id") is None
        for j in window.engine("list_jobs")
        if j["id"] in {first["id"], second["id"]}
    )

    window.click("Support")
    window.wait_text("Donate with PayPal")
    for address in [
        "bc1qphk3h7sw6j429c62ypw6zxgmkfeevmxs437ze3",
        "0x81deF905D66fd17433003e749f1e69bCFd95664d",
        "G362aMnx7jSXp4iWtCwyw2yXy52ukRVoFgYCpw4aqrPQ",
    ]:
        assert address in window.text()
    assert "@Elias02345" in window.text()
    window.call("/window/rect", {"width": 900, "height": 640})
    window.screenshot(root / "support-minimum.png")
    assert window.js("return document.documentElement.scrollWidth <= window.innerWidth;")
    window.click("Settings")
    window.wait_text("Application updates")
    window.click("Check for signed updates")
    window.wait(
        lambda: window.js(
            'return [...document.querySelectorAll("button")]'
            '.some(b=>b.textContent.trim()==="Check for signed updates"&&!b.disabled);'
        ),
        seconds=40,
    )
    assert "Last checked:" in window.text(), "Native signed release check failed"
    window.screenshot(root / "update-settings.png")
    assert window.js("return document.documentElement.scrollWidth <= window.innerWidth;")
    for path, digest in original_hashes.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
    (root / "report.json").write_text(
        json.dumps(
            {
                "job_ids": [first["id"], second["id"]],
                "checks": [
                    "projects created/renamed/reloaded",
                    "new and existing generations grouped",
                    "archive/restore",
                    "project removal keeps results",
                    "muted stem plays audibly",
                    "stem switching",
                    "all-stem playback",
                    "individual export selection",
                    "multi-result exact batch export",
                    "support and contributor",
                    "real signed update check",
                    "minimum window",
                    "original files unchanged",
                ],
            },
            indent=2,
        )
    )
    print("REAL NATIVE PROJECT WORKFLOW PASSED", root, flush=True)


if __name__ == "__main__":
    main()
