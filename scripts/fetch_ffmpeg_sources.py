"""Download verified corresponding sources used by the application's FFmpeg build."""

import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "runtime/ffmpeg-sources.json").read_text())
destination = ROOT / "runtime/ffmpeg-sources"
destination.mkdir(parents=True, exist_ok=True)
for name, entry in manifest.items():
    path = destination / entry["url"].rsplit("/", 1)[1]
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]:
        continue
    temp = path.with_suffix(path.suffix + ".part")
    try:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(entry["url"], timeout=60) as response, temp.open("wb") as output:
                    while block := response.read(1024 * 1024):
                        output.write(block)
                break
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(3)
        if hashlib.sha256(temp.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Corresponding source checksum failed: " + name)
        temp.replace(path)
        print("VERIFIED SOURCE", name, entry["version"], flush=True)
    finally:
        temp.unlink(missing_ok=True)
