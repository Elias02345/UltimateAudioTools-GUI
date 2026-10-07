"""WebDriver harness for the actual Tauri WebKit window, with no mock engine."""

import base64
import json
import time
import urllib.request
from pathlib import Path


class NativeWindow:
    def __init__(self, session, server="http://127.0.0.1:4444"):
        self.base = f"{server}/session/{session}"

    def call(self, endpoint, data=None):
        req = urllib.request.Request(
            self.base + endpoint,
            data=None if data is None else json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        value = json.loads(urllib.request.urlopen(req, timeout=120).read())["value"]
        if isinstance(value, dict) and "error" in value:
            raise RuntimeError(value)
        return value

    def js(self, script, *args):
        return self.call("/execute/sync", {"script": script, "args": list(args)})

    def invoke(self, command, params):
        return self.call(
            "/execute/async",
            {
                "script": (
                    "const done=arguments[arguments.length-1]; "
                    "window.__TAURI_INTERNALS__.invoke(arguments[0],arguments[1])"
                    ".then(x=>done({ok:x})).catch(e=>done({error:String(e)}));"
                ),
                "args": [command, params],
            },
        )

    def click(self, text):
        self.js(
            (
                "const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===arguments[0]); "
                "if(!b) throw new Error('Missing button '+arguments[0]); b.click();"
            ),
            text,
        )

    def text(self):
        return self.js("return document.body.innerText;")

    def wait_text(self, text, seconds=60):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if text in self.text():
                return
            time.sleep(0.2)
        raise AssertionError(f"Missing {text}: {self.text()}")

    def screenshot(self, path):
        Path(path).write_bytes(base64.b64decode(self.call("/screenshot")))


if __name__ == "__main__":
    session = json.loads(Path(".test-output/webdriver-session.json").read_text())["value"]["sessionId"]
    window = NativeWindow(session)
    if "Recommended setup" in window.text():
        window.click("Recommended setup")
    window.wait_text("Drop your audio here")
    dropped = window.invoke(
        "plugin:event|emit",
        {
            "event": "tauri://drag-drop",
            "payload": {
                "paths": [str(Path(".test-data/Test 🎵 café.wav").resolve())],
                "position": {"x": 600, "y": 300},
            },
        },
    )
    print("drop", dropped)
    window.wait_text("Test 🎵 café.wav")
    window.screenshot(".test-output/native-home.png")
    print(window.text())
