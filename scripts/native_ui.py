"""WebDriver harness for the actual Tauri WebKit window, with no mock engine."""

import base64
import json
import time
import urllib.error
import urllib.request
import uuid
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
        try:
            payload = urllib.request.urlopen(req, timeout=120).read()
        except urllib.error.HTTPError as error:
            raise RuntimeError(error.read().decode()) from error
        value = json.loads(payload)["value"]
        if isinstance(value, dict) and "error" in value:
            raise RuntimeError(value)
        return value

    def js(self, script, *args):
        return self.call("/execute/sync", {"script": script, "args": list(args)})

    def invoke(self, command, params):
        # WebKit's async WebDriver endpoint can reset the connection. Launch
        # each IPC command once, then read its Promise result through sync JS.
        # Retrying the invocation itself could duplicate a mutating command.
        token = uuid.uuid4().hex
        self.js(
            "window.__webdriverReplies ??= Object.create(null);"
            "const token=arguments[0];window.__webdriverReplies[token]={pending:true};"
            "window.__TAURI_INTERNALS__.invoke(arguments[1],arguments[2])"
            ".then(x=>window.__webdriverReplies[token]={ok:x})"
            ".catch(e=>window.__webdriverReplies[token]={error:String(e)});return true;",
            token,
            command,
            params,
        )
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                reply = self.js("return window.__webdriverReplies[arguments[0]];", token)
                if reply is not None and not reply.get("pending"):
                    return reply
                time.sleep(0.1)
            raise TimeoutError(f"Native IPC command timed out: {command}")
        finally:
            try:
                self.js("delete window.__webdriverReplies[arguments[0]];return true;", token)
            except (OSError, RuntimeError):
                pass

    def click(self, text):
        self.js(
            (
                "const b=[...document.querySelectorAll('button')]"
                ".find(b=>b.textContent.trim()===arguments[0]); "
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

    def engine(self, method, **params):
        result = self.invoke("engine_request", {"method": method, "params": params})
        if "error" in result:
            raise RuntimeError(result["error"])
        return result["ok"]

    def wait(self, check, seconds=120):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = check()
            if result:
                return result
            time.sleep(0.2)
        raise AssertionError(f"Native UI condition timed out: {self.text()}")

    def set_label(self, label, value, scope="document"):
        self.js(
            "const root=arguments[2]==='document'?document:document.querySelector(arguments[2]);"
            "const label=[...root.querySelectorAll('label')]"
            ".find(l=>l.firstChild.textContent.trim()===arguments[0]);"
            "if(!label)throw new Error('Missing label '+arguments[0]);"
            "const el=label.querySelector('input,select');"
            "const proto=el.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;"
            "Object.getOwnPropertyDescriptor(proto,'value').set.call(el,arguments[1]);"
            "el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true}));",
            label,
            value,
            scope,
        )

    def click_row(self, attribute, value, button):
        self.js(
            "const row=document.querySelector('['+arguments[0]+'=\"'+arguments[1]+'\"]');"
            "if(!row)throw new Error('Missing row '+arguments[1]);"
            "const b=[...row.querySelectorAll('button')]"
            ".find(b=>b.textContent.trim()===arguments[2]||b.getAttribute('aria-label')===arguments[2]);"
            "if(!b||b.disabled)throw new Error('Missing or disabled action '+arguments[2]);b.click();",
            attribute,
            value,
            button,
        )

    def drop(self, path):
        path = Path(path).resolve()
        for _ in range(20):
            self.invoke(
                "plugin:event|emit",
                {
                    "event": "tauri://drag-drop",
                    "payload": {"paths": [str(path)], "position": {"x": 600, "y": 300}},
                },
            )
            time.sleep(0.3)
            if path.name in self.text():
                return
        raise AssertionError("Native drag-drop did not import " + str(path))


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
