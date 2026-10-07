"""Audit installer presence/resources and write checksums without installing on the build host."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "apps/desktop/src-tauri/target/release/bundle"
parser = argparse.ArgumentParser()
parser.add_argument("--target", choices=["linux", "windows", "macos"], required=True)
args = parser.parse_args()
expected = {"linux": [".deb", ".AppImage"], "windows": [".exe"], "macos": [".dmg"]}[args.target]
artifacts = [
    path for path in BUNDLE.rglob("*") if path.is_file() and any(path.name.endswith(ext) for ext in expected)
]
for extension in expected:
    assert any(path.name.endswith(extension) for path in artifacts), f"Missing installer {extension}"
for artifact in artifacts:
    assert artifact.stat().st_size > 20 * 1024**2, f"Installer is suspiciously small: {artifact.name}"
    assert artifact.stat().st_size < 2 * 1024**3, f"Installer exceeds GitHub's asset limit: {artifact.name}"
if args.target == "linux":
    deb = next(path for path in artifacts if path.suffix == ".deb")
    with tempfile.TemporaryDirectory(prefix="Separator package café ") as temp:
        subprocess.run(["dpkg-deb", "-x", str(deb), temp], check=True)
        roots = list(Path(temp).rglob("runtime/python/bin/python3"))
        assert len(roots) == 1, "The installer must contain exactly one private Python runtime"
        resources = roots[0].parents[3]
        assert (resources / "engine/separator_engine/server.py").is_file()
        assert (resources / "runtime-manifests/linux-cuda.txt").is_file()
        probe = resources / "engine/separator_engine/runtime_probe.py"
        subprocess.run([str(roots[0]), "-I", str(probe)], check=True)
        print("EXTRACTED INSTALLER RUNTIME PASSED", flush=True)
    appimage = next(path for path in artifacts if path.name.endswith(".AppImage"))
    with tempfile.TemporaryDirectory(prefix="Separator AppImage café ") as temp:
        subprocess.run(
            [str(appimage.resolve()), "--appimage-extract"], cwd=temp, check=True, stdout=subprocess.DEVNULL
        )
        roots = list(Path(temp).rglob("runtime/python/bin/python3"))
        assert len(roots) == 1, "AppImage omitted or duplicated its private runtime"
        subprocess.run(
            [str(roots[0]), "-I", str(roots[0].parents[3] / "engine/separator_engine/runtime_probe.py")],
            check=True,
        )
if args.target == "macos":
    apps = list(BUNDLE.rglob("Separator.app"))
    assert apps, "Missing native application bundle"
    resources = apps[0] / "Contents/Resources"
    python = resources / "runtime/python/bin/python3"
    assert python.is_file() and (resources / "engine/separator_engine/server.py").is_file()
    subprocess.run(
        [str(python), "-I", str(resources / "engine/separator_engine/runtime_probe.py")], check=True
    )
if args.target == "windows":
    installer = next(path for path in artifacts if path.suffix == ".exe")
    with tempfile.TemporaryDirectory(prefix="separator-installed-") as temp:
        destination = Path(temp) / "app"
        subprocess.run([str(installer.resolve()), "/S", f"/D={destination}"], check=True, timeout=240)
        roots = list(destination.rglob("runtime/python/python.exe"))
        assert len(roots) == 1, "NSIS installation omitted its private runtime"
        resources = roots[0].parents[2]
        assert (resources / "engine/separator_engine/server.py").is_file()
        subprocess.run(
            [str(roots[0]), "-I", str(resources / "engine/separator_engine/runtime_probe.py")], check=True
        )
files = [
    path
    for path in BUNDLE.rglob("*")
    if path.is_file() and (path in artifacts or path.suffix == ".sig" or path.name.endswith(".tar.gz"))
]
lines = []
for path in sorted(files):
    with path.open("rb") as stream:
        lines.append(
            f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {path.relative_to(BUNDLE).as_posix()}"
        )
(BUNDLE / "SHA256SUMS").write_text("\n".join(lines) + "\n")
manifest = json.loads((ROOT / "apps/desktop/src-tauri/resources/runtime/manifest.json").read_text())
assert manifest["target"] == args.target
print("PACKAGE AUDIT PASSED", [path.name for path in artifacts], flush=True)
