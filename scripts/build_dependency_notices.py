"""Preserve original npm/Cargo license texts alongside the packaged desktop resources."""

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "apps/desktop/src-tauri/resources/dependency-notices"
NOTICE = re.compile(r"^(licen[cs]e|copying|notice|copyright)([._-].*)?$", re.IGNORECASE)


def preserve(name: str, version: str, directory: Path, kind: str):
    copied = []
    for path in directory.rglob("*"):
        if (
            path.is_file()
            and NOTICE.match(path.name)
            and "node_modules" not in path.relative_to(directory).parts
        ):
            destination = DESTINATION / kind / name.replace("/", "_") / version / path.relative_to(directory)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            copied.append(str(destination.relative_to(DESTINATION)))
    return copied


def build():
    shutil.rmtree(DESTINATION, ignore_errors=True)
    DESTINATION.mkdir(parents=True)
    packages = []
    for manifest in (ROOT / "node_modules").glob("**/package.json"):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not data.get("name") or not data.get("version"):
            continue
        # Only package roots, not nested test/example manifests.
        directory = manifest.parent
        if directory.parent.name != "node_modules" and directory.parent.parent.name != "node_modules":
            continue
        packages.append(
            {
                "kind": "npm",
                "name": data["name"],
                "version": data["version"],
                "license": data.get("license"),
                "repository": data.get("repository"),
                "notices": preserve(data["name"], data["version"], directory, "npm"),
            }
        )
    metadata = json.loads(
        subprocess.check_output(
            [
                "cargo",
                "metadata",
                "--locked",
                "--format-version",
                "1",
                "--manifest-path",
                str(ROOT / "apps/desktop/src-tauri/Cargo.toml"),
            ]
        )
    )
    for data in metadata["packages"]:
        if data["source"] is None:
            continue
        packages.append(
            {
                "kind": "cargo",
                "name": data["name"],
                "version": data["version"],
                "license": data["license"],
                "repository": data["repository"],
                "authors": data["authors"],
                "notices": preserve(
                    data["name"], data["version"], Path(data["manifest_path"]).parent, "cargo"
                ),
            }
        )
    for filename in ["LICENSE", "THIRD_PARTY_NOTICES.md"]:
        shutil.copy2(ROOT / filename, DESTINATION / filename)
    (DESTINATION / "index.json").write_text(json.dumps(packages, indent=2), encoding="utf-8")
    print("DESKTOP LICENSE NOTICES PRESERVED", len(packages), flush=True)


if __name__ == "__main__":
    build()
