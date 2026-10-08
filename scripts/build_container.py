"""Build an optional image from exactly the private Linux runtime and engine sources."""

import argparse
import errno
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copy_runtime_file(source, destination):
    try:
        os.link(source, destination)
        return destination
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        return shutil.copy2(source, destination)


parser = argparse.ArgumentParser()
parser.add_argument("--runtime", type=Path, default=ROOT / "apps/desktop/src-tauri/resources/runtime/python")
parser.add_argument("--command", choices=["docker", "podman"], default="docker")
parser.add_argument("--image", default="separator-engine:0.1.2")
parser.add_argument("--backend", choices=["cpu", "cuda"], default="cpu")
parser.add_argument("--network", choices=["default", "host"], default="default")
args = parser.parse_args()
if platform.system() != "Linux" or not (args.runtime / "bin/python3").is_file():
    raise SystemExit("Build container images on Linux with a complete Linux private runtime.")
subprocess.run(
    [
        str(args.runtime / "bin/python3"),
        "-I",
        str(ROOT / "engine/separator_engine/runtime_probe.py"),
        *(["--cuda"] if args.backend == "cuda" else []),
    ],
    check=True,
)
context_root = ROOT / ".test-state"
context_root.mkdir(exist_ok=True)
subprocess.run([str(args.runtime / "bin/python3"), str(ROOT / "scripts/fetch_ffmpeg_sources.py")], check=True)
with tempfile.TemporaryDirectory(prefix="container-context-", dir=context_root) as temp:
    context = Path(temp)
    shutil.copyfile(ROOT / "container/Dockerfile", context / "Dockerfile")
    shutil.copyfile(ROOT / "runtime/ffmpeg-sources.json", context / "ffmpeg-sources.json")
    shutil.copytree(ROOT / "runtime/ffmpeg-sources", context / "codec-sources")
    (context / "codec-scripts").mkdir()
    for name in ["build_ffmpeg.sh", "fetch_ffmpeg_sources.py", "install_ffmpeg.py"]:
        shutil.copyfile(ROOT / "scripts" / name, context / "codec-scripts" / name)
    # Link immutable runtime files when possible; installed/extracted runtimes can
    # live on another filesystem. Docker receives only the intended source trees.
    shutil.copytree(
        args.runtime,
        context / "runtime",
        symlinks=True,
        copy_function=copy_runtime_file,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copytree(
        ROOT / "engine/separator_engine",
        context / "engine/separator_engine",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    subprocess.run(
        [
            args.command,
            "build",
            "--network",
            args.network,
            "--build-arg",
            f"BACKEND={args.backend}",
            "--tag",
            args.image,
            str(context),
        ],
        check=True,
    )
print("CONTAINER IMAGE READY", args.image, flush=True)
