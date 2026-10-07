"""Flatten native artifacts, cryptographically verify updates and prepare a Tauri release feed."""

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def prepare(source: Path, output: Path, version: str, verifier: Path):
    config = json.loads((ROOT / "apps/desktop/src-tauri/tauri.conf.json").read_text())
    if version.removeprefix("v") != config["version"]:
        raise ValueError("Release tag must match the application version")
    output.mkdir(parents=True, exist_ok=False)
    signatures = {
        "linux-x86_64": ".AppImage.sig",
        "windows-x86_64": ".exe.sig",
        "darwin-aarch64": ".app.tar.gz.sig",
    }
    platforms = {}
    with tempfile.TemporaryDirectory(prefix="separator-signatures-") as temp:
        key = Path(temp) / "public.key"
        key.write_bytes(base64.b64decode(config["plugins"]["updater"]["pubkey"], validate=True))
        for platform, extension in signatures.items():
            matches = list(source.rglob("*" + extension))
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one signed update for {platform}, found {len(matches)}")
            signature = matches[0]
            artifact = signature.with_suffix("")
            decoded = Path(temp) / "signature"
            encoded = signature.read_text().strip()
            decoded.write_bytes(base64.b64decode(encoded, validate=True))
            subprocess.run([str(verifier.resolve()), str(key), str(decoded), str(artifact)], check=True)
            comment = decoded.read_text().splitlines()[2].removeprefix("trusted comment: ")
            signed_version = next(
                (field[8:] for field in comment.split("\t") if field.startswith("version:")), None
            )
            if signed_version != config["version"]:
                raise ValueError(f"The signature for {platform} is not bound to the release version")
            platforms[platform] = {
                "signature": encoded,
                "url": f"https://github.com/Elias02345/UltimateAudioTools-GUI/releases/download/{version}/"
                + quote(artifact.name),
            }
    candidates = [
        path
        for path in source.rglob("*")
        if path.is_file()
        and any(path.name.endswith(ext) for ext in [".AppImage", ".deb", ".exe", ".dmg", ".sig", ".tar.gz"])
    ]
    for path in candidates:
        destination = output / path.name
        if destination.exists():
            raise ValueError(f"Duplicate release asset name: {path.name}")
        if path.stat().st_size >= 2 * 1024**3:
            raise ValueError(f"Release asset exceeds GitHub's limit: {path.name}")
        shutil.copy2(path, destination)
    for target in ["linux", "windows", "macos"]:
        assert (output / f"FFmpeg-corresponding-source-{target}.tar.gz").is_file()
    manifest = {
        "version": config["version"],
        "notes": "See the release notes for changes and platform verification.",
        "pub_date": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "platforms": platforms,
    }
    (output / "latest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checksums = []
    for path in sorted(output.iterdir()):
        with path.open("rb") as stream:
            checksums.append(f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {path.name}")
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
    print("RELEASE PREPARED", sorted(platforms), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--verifier", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.input, args.output, args.version, args.verifier)
