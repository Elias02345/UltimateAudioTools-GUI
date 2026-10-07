"""Build a private, relocatable processing runtime for the current release platform."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(target: str):
    manifest = json.loads((ROOT / "runtime/targets.json").read_text())
    details = manifest["targets"][target]
    archive_name = (
        f"cpython-{manifest['python']}+{manifest['release']}-{details['triple']}-install_only_stripped.tar.gz"
    )
    cache = ROOT / "runtime/downloads"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / archive_name
    if not archive.exists():
        print(f"Downloading private Python {manifest['python']}", flush=True)
        url = (
            "https://github.com/astral-sh/python-build-standalone/releases/download/"
            f"{manifest['release']}/{archive_name}"
        )
        urllib.request.urlretrieve(url, archive)
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != details["sha256"]:
        archive.unlink()
        raise ValueError("Private Python archive failed its publisher SHA256 check.")
    resource = ROOT / "apps/desktop/src-tauri/resources/runtime"
    staging = resource.with_name("runtime-staging")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    with tarfile.open(archive) as stream:
        stream.extractall(staging, filter="data")
    python = staging / "python" / ("python.exe" if target == "windows" else "bin/python3")
    requirements = ROOT / "runtime" / details["requirements"]
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("PYTHON", "PIP_", "UV_")) and k != "VIRTUAL_ENV"
    }
    env["PIP_CONFIG_FILE"] = os.devnull
    from install_ffmpeg import install

    install(staging / "python", target)
    subprocess.run(
        [
            "uv",
            "--no-config",
            "pip",
            "install",
            "--python",
            str(python),
            "--system",
            "--index-strategy",
            "unsafe-best-match",
            "--require-hashes",
            "-r",
            str(requirements),
        ],
        check=True,
        env=env,
    )
    # Remove upstream binaries whose exact corresponding sources are unavailable.
    for vendor_binary in (staging / "python").rglob("imageio_ffmpeg/binaries/ffmpeg*"):
        if vendor_binary.is_file():
            vendor_binary.unlink()
    env["PYTHONPATH"] = str(ROOT / "engine")
    env["PYTHONNOUSERSITE"] = "1"
    env["PIP_CONFIG_FILE"] = os.devnull
    probe = (
        "from separator_engine.server import Supervisor; from tempfile import TemporaryDirectory; "
        "from pathlib import Path; t=TemporaryDirectory(); s=Supervisor(Path(t.name),lambda *a,**kw:None); "
        "checks=s.self_test(); print(checks); assert all(c['passed'] for c in checks); s.close()"
    )
    subprocess.run([str(python), "-c", probe], check=True, env=env)
    subprocess.run(
        [str(python), "-I", str(ROOT / "engine/separator_engine/license_inventory.py")], check=True, env=env
    )
    versions = subprocess.check_output(
        [str(python), "-I", "-m", "pip", "list", "--format=json"], text=True, env=env
    )
    (staging / "manifest.json").write_text(
        json.dumps(
            {
                "python": manifest["python"],
                "target": target,
                "architecture": platform.machine().lower(),
                "archive_sha256": actual,
                "packages": json.loads(versions),
            },
            indent=2,
        )
    )
    shutil.rmtree(resource, ignore_errors=True)
    staging.rename(resource)
    # A second check proves the runtime did not retain its build path.
    relocated = resource / "python" / ("python.exe" if target == "windows" else "bin/python3")
    subprocess.run(
        [
            str(relocated),
            "-c",
            (
                "import torch,soundfile,onnxruntime; from separator_engine.audio import ffmpeg; "
                "print(torch.__version__,ffmpeg())"
            ),
        ],
        check=True,
        env=env,
    )
    print(f"Private runtime ready: {resource}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        choices=["linux", "windows", "macos"],
        default={"Linux": "linux", "Windows": "windows", "Darwin": "macos"}.get(platform.system()),
    )
    args = parser.parse_args()
    build(args.target)
