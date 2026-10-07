"""Install our verified build and preserve its complete corresponding sources and notices."""

import hashlib
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def install(runtime: Path, target: str):
    build = ROOT / "runtime/build/ffmpeg"
    executable = build / "prefix/bin" / ("ffmpeg.exe" if target == "windows" else "ffmpeg")
    if not executable.is_file():
        raise ValueError(
            "Build verified-source FFmpeg with scripts/build_ffmpeg.sh before packaging the runtime."
        )
    destination = runtime / "separator-bin"
    destination.mkdir(exist_ok=True)
    shutil.copy2(executable, destination / executable.name)
    notices = runtime / "third-party-licenses/FFmpeg"
    notices.mkdir(parents=True, exist_ok=True)
    for component, files in {
        "ffmpeg-9.0.2": ["COPYING.LGPLv2.1", "LICENSE.md"],
        "lame-3.100": ["COPYING"],
        "libogg-1.3.6": ["COPYING"],
        "libvorbis-1.3.7": ["COPYING"],
    }.items():
        for filename in files:
            shutil.copy2(build / "src" / component / filename, notices / f"{component}-{filename}")
    for filename in ["LICENSE.txt", "build-configuration.txt"]:
        shutil.copy2(build / filename, notices / filename)
    manifest = json.loads((ROOT / "runtime/ffmpeg-sources.json").read_text())
    with executable.open("rb") as stream:
        binary_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    (notices / "binary.json").write_text(
        json.dumps({"sha256": binary_hash, "target": target, "sources": manifest}, indent=2)
    )
    archive = notices / "corresponding-source.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        for entry in manifest.values():
            filename = entry["url"].rsplit("/", 1)[1]
            output.add(ROOT / "runtime/ffmpeg-sources" / filename, arcname=filename)
        output.add(ROOT / "scripts/build_ffmpeg.sh", arcname="build_ffmpeg.sh")
        output.add(ROOT / "runtime/ffmpeg-sources.json", arcname="sources.json")
        output.add(build / "ffmpeg/configure.log", arcname="configure.log")
        for filename in ["build-configuration.txt", "LICENSE.txt", "compiler.txt"]:
            output.add(build / filename, arcname=filename)
    shutil.copy2(archive, ROOT / "runtime/build" / f"FFmpeg-corresponding-source-{target}.tar.gz")
    (notices / "README.txt").write_text(
        "FFmpeg is a separate command-line program, LGPL 2.1 or later. Codec notices are included.\n"
        "All exact source archives and the unmodified build script are in corresponding-source.tar.gz.\n"
        "Extract corresponding-source.tar.gz into a temporary directory.\n"
        "Place its original .tar.* archives in <repository>/runtime/ffmpeg-sources and its build_ffmpeg.sh\n"
        "in <repository>/scripts, then run bash scripts/build_ffmpeg.sh from the repository.\n"
        "See the public repository BUILDING.md for native compiler prerequisites.\n"
    )
    print("VERIFIED-SOURCE FFMPEG INSTALLED", binary_hash, flush=True)
