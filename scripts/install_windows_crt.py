"""Bundle one licensed Visual Studio x64 CRT set; never depend on the build runner's System32."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

DOCUMENTS = {
    "Visual-Studio-2022-Enterprise-Professional-License-EN.docx": (
        "https://visualstudio.microsoft.com/wp-content/uploads/2021/11/"
        "Visual-Studio-2022-Enterprise-Professional-License-EN.docx",
        "9c0cd52b20db9d081854c75bd1b50c75514b8f8cb09c8cad15e89d90b97b5bf3",
    ),
    "Visual-C-Runtime-2015-2022-License-1.docx": (
        "https://visualstudio.microsoft.com/wp-content/uploads/2021/09/"
        "Visual-C-Runtime-2015-2022-License-1.docx",
        "f1e3d56ceb2ad68aae0711b910375009e651ac5530fa0760f0dea6e81e54fae1",
    ),
}


def install(runtime: Path):
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / (
        "Microsoft Visual Studio/Installer/vswhere.exe"
    )
    installations = json.loads(
        subprocess.check_output(
            [
                str(vswhere),
                "-latest",
                "-products",
                "Microsoft.VisualStudio.Product.Enterprise",
                "Microsoft.VisualStudio.Product.Professional",
                "-version",
                "[17.0,18.0)",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-format",
                "json",
                "-utf8",
            ],
            encoding="utf-8",
        )
    )
    if not installations:
        raise ValueError(
            "Visual Studio 2022 Enterprise or Professional with its licensed x64 C++ redistributables "
            "is required to package Windows."
        )
    installation = installations[0]
    folders = list(Path(installation["installationPath"]).glob("VC/Redist/MSVC/*/x64/Microsoft.VC*.CRT"))
    required = ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"]
    complete = [folder for folder in folders if all((folder / name).is_file() for name in required)]
    if not complete:
        raise ValueError("The Visual Studio x64 redistributable CRT set is incomplete.")
    source = max(
        complete, key=lambda folder: tuple(int(n) for n in re.findall(r"\d+", folder.parents[1].name))
    )
    notices = runtime / "third-party-licenses/MicrosoftVisualCRuntime"
    notices.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(source.glob("*.dll")):
        version = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-Item -LiteralPath $env:SEPARATOR_CRT_INSPECT_PATH).VersionInfo.ProductVersion",
            ],
            env={**os.environ, "SEPARATOR_CRT_INSPECT_PATH": str(path)},
            text=True,
        ).strip()
        shutil.copy2(path, runtime / path.name)
        files.append(
            {"name": path.name, "version": version, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
    for name, (url, expected) in DOCUMENTS.items():
        content = urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(
                "Microsoft license document checksum changed; review the new original before packaging."
            )
        (notices / name).write_bytes(content)
    (notices / "manifest.json").write_text(
        json.dumps(
            {
                "compiler_product": installation.get("productId"),
                "compiler_version": installation.get("installationVersion"),
                "files": files,
                "redistribution_terms": "https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution",
                "documents": {
                    name: {"url": url, "sha256": digest} for name, (url, digest) in DOCUMENTS.items()
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("PRIVATE WINDOWS CRT INSTALLED", [entry["name"] for entry in files], flush=True)
