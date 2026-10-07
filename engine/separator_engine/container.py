"""Isolated, explicitly selected container execution with host-owned paths."""

import csv
import io
import json
import os
import platform
import shutil
import subprocess
import uuid
from pathlib import Path, PurePosixPath

from . import PROTOCOL_VERSION, __version__


def inspect(command, image):
    executable = shutil.which(command)
    if not executable:
        raise ValueError("The selected container runtime is not installed.")
    try:
        result = subprocess.run(
            [executable, "image", "inspect", image], capture_output=True, text=True, check=True, timeout=15
        )
        details = json.loads(result.stdout)[0]
    except (subprocess.SubprocessError, ValueError, IndexError) as error:
        raise ValueError(
            "Container image is unavailable. Build the image described in BUILDING.md "
            "before selecting Container Runtime."
        ) from error
    labels = details.get("Config", {}).get("Labels") or {}
    if (
        details.get("Os") != "linux"
        or labels.get("org.separator.protocol") != str(PROTOCOL_VERSION)
        or labels.get("org.separator.version") != __version__
    ):
        raise ValueError("Choose a compatible Separator Linux container image for this application version.")
    expected = "arm64" if platform.machine().lower() in {"aarch64", "arm64"} else "amd64"
    if details.get("Architecture") != expected:
        raise ValueError("The container image architecture does not match this computer.")
    return executable, labels.get("org.separator.backend", "cpu")


def mount(source, target, readonly=False):
    stream = io.StringIO()
    csv.writer(stream, lineterminator="").writerow(
        ["type=bind", f"source={source}", f"target={target}", *(["readonly"] if readonly else [])]
    )
    return stream.getvalue()


def launch(settings, request, model_dir, work):
    executable, backend = inspect(settings.container_command, settings.container_image)
    device = request["preset"]["parameters"]["device"]
    if device == "mps":
        raise ValueError("Apple acceleration uses Native Runtime; Linux containers support CPU or CUDA.")
    if device == "cuda" and backend != "cuda":
        raise ValueError("This is a CPU container image. Select a CUDA image or choose CPU/Automatic.")
    output = Path(request["preset"]["output"]["directory"]).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    scratch = work / "container-state"
    scratch.mkdir()
    source = Path(request["path"])
    name = "separator-" + uuid.uuid4().hex
    args = [
        executable,
        "run",
        "--rm",
        "--pull=never",
        "--name",
        name,
        "-i",
        "--network=none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,size=1g",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
    ]
    if os.name != "nt":
        args += ["--user", f"{os.getuid()}:{os.getgid()}"]
    if backend == "cuda" and device in {"cuda", "auto"}:
        args += (
            ["--gpus", "all"]
            if settings.container_command == "docker"
            else ["--device", "nvidia.com/gpu=all"]
        )
    for host, target, readonly in [
        (source, "/input/" + source.name, True),
        (output, "/output", False),
        (model_dir, "/models", False),
        (work, "/work", False),
        (scratch, "/state", False),
    ]:
        args += ["--mount", mount(host, target, readonly)]
    args += [
        "--env",
        "SEPARATOR_OFFLINE=1",
        settings.container_image,
        "python",
        "-u",
        "-m",
        "separator_engine.worker",
        "serve",
        "/models",
        "/state",
    ]
    translated = json.loads(json.dumps(request))
    translated["path"] = "/input/" + source.name
    translated["preset"]["output"]["directory"] = "/output"
    if backend == "cpu" and device == "auto":
        translated["preset"]["parameters"]["device"] = "cpu"
    return args, name, translated, output


def result_paths(result, output):
    for item in result["outputs"]:
        path = PurePosixPath(item["path"])
        try:
            relative = path.relative_to("/output")
        except ValueError as error:
            raise ValueError("Container returned an output outside its assigned directory.") from error
        if ".." in relative.parts:
            raise ValueError("Invalid container output path.")
        host = output.joinpath(*relative.parts).resolve()
        if not host.is_relative_to(output):
            raise ValueError("Container output escaped its assigned directory.")
        item["path"] = str(host)
    result["engine"] = "container"
    return result
