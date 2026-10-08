"""Audit installer presence/resources and write checksums without installing on the build host."""

import argparse
import hashlib
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "apps/desktop/src-tauri/target/release/bundle"
parser = argparse.ArgumentParser()
parser.add_argument("--target", choices=["linux", "windows", "macos"], required=True)
args = parser.parse_args()


def extract_deb(archive: Path, destination: str):
    with archive.open("rb") as stream:
        assert stream.read(8) == b"!<arch>\n", "Invalid Debian archive"
        while header := stream.read(60):
            assert len(header) == 60 and header[-2:] == b"`\n", "Invalid archive member"
            size = int(header[48:58])
            name = header[:16].decode().strip().rstrip("/")
            if name.startswith("data.tar."):
                with tarfile.open(fileobj=stream, mode="r|*") as payload:
                    payload.extractall(destination, filter="data")
                return
            stream.seek(size + size % 2, 1)
    raise ValueError("Missing Debian data payload")


def audit_runtime(python: Path, resources: Path):
    assert (resources / "dependency-notices/index.json").is_file(), "Missing desktop license notices"
    subprocess.run(
        [str(python), "-I", str(resources / "engine/separator_engine/runtime_probe.py")], check=True
    )
    runtime = resources / "runtime/python"
    executable = runtime / "separator-bin" / ("ffmpeg.exe" if args.target == "windows" else "ffmpeg")
    notices = runtime / "third-party-licenses"
    assert (notices / "index.json").is_file(), "Missing complete Python license inventory"
    assert (notices / "FFmpeg/corresponding-source.tar.gz").is_file(), "Missing exact FFmpeg sources"
    assert not list(runtime.rglob("imageio_ffmpeg/binaries/ffmpeg*")), "Unverified vendor FFmpeg shipped"
    if args.target == "windows":
        crt = notices / "MicrosoftVisualCRuntime"
        manifest = json.loads((crt / "manifest.json").read_text(encoding="utf-8"))
        assert {"msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"}.issubset(
            entry["name"] for entry in manifest["files"]
        ), "Incomplete private Windows C++ runtime"
        for entry in manifest["files"]:
            assert hashlib.sha256((runtime / entry["name"]).read_bytes()).hexdigest() == entry["sha256"]
        for name, document in manifest["documents"].items():
            assert hashlib.sha256((crt / name).read_bytes()).hexdigest() == document["sha256"]
    subprocess.run(
        [str(python), "-I", str(ROOT / "scripts/check_ffmpeg.py"), "--executable", str(executable)],
        check=True,
    )


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
        extract_deb(deb, temp)
        roots = list(Path(temp).rglob("runtime/python/bin/python3"))
        assert len(roots) == 1, "The installer must contain exactly one private Python runtime"
        resources = roots[0].parents[3]
        assert (resources / "engine/separator_engine/server.py").is_file()
        assert (resources / "runtime-manifests/linux-cuda.txt").is_file()
        audit_runtime(roots[0], resources)
        print("EXTRACTED INSTALLER RUNTIME PASSED", flush=True)
    appimage = next(path for path in artifacts if path.name.endswith(".AppImage"))
    with tempfile.TemporaryDirectory(prefix="Separator AppImage café ") as temp:
        subprocess.run(
            [str(appimage.resolve()), "--appimage-extract"], cwd=temp, check=True, stdout=subprocess.DEVNULL
        )
        roots = list(Path(temp).rglob("runtime/python/bin/python3"))
        assert len(roots) == 1, "AppImage omitted or duplicated its private runtime"
        audit_runtime(roots[0], roots[0].parents[3])
if args.target == "macos":
    apps = list(BUNDLE.rglob("Separator.app"))
    assert apps, "Missing native application bundle"
    resources = apps[0] / "Contents/Resources"
    python = resources / "runtime/python/bin/python3"
    assert python.is_file() and (resources / "engine/separator_engine/server.py").is_file()
    audit_runtime(python, resources)
if args.target == "windows":
    installer = next(path for path in artifacts if path.suffix == ".exe")
    with tempfile.TemporaryDirectory(prefix="separator-installed-") as temp:
        destination = Path(temp) / "app"
        subprocess.run([str(installer.resolve()), "/S", f"/D={destination}"], check=True, timeout=240)
        roots = list(destination.rglob("runtime/python/python.exe"))
        assert len(roots) == 1, "NSIS installation omitted its private runtime"
        resources = roots[0].parents[2]
        assert (resources / "engine/separator_engine/server.py").is_file()
        audit_runtime(roots[0], resources)
        uninstallers = list(destination.glob("*uninstall*.exe"))
        assert len(uninstallers) == 1, "Missing native uninstaller"
        subprocess.run([str(uninstallers[0]), "/S"], check=True, timeout=240)
        deadline = time.monotonic() + 30
        while roots[0].exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        assert not roots[0].exists(), "Uninstaller left the private runtime installed"
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
