"""Preserve installed distribution license notices without relabeling third-party software."""

import argparse
import importlib.metadata
import json
import shutil
import sys
from pathlib import Path


def inventory(destination):
    destination.mkdir(parents=True, exist_ok=True)
    packages = []
    for distribution in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = distribution.metadata["Name"]
        notices = []
        for item in distribution.files or []:
            if any(word in str(item).lower() for word in ["license", "copying", "copyright", "notice"]):
                source = Path(distribution.locate_file(item)).resolve()
                if source.is_file() and source.is_relative_to(Path(sys.prefix).resolve()):
                    target = destination / name / str(item).replace("../", "")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    notices.append(str(target.relative_to(destination)))
        metadata = distribution.metadata
        packages.append(
            {
                "name": name,
                "version": distribution.version,
                "license": metadata.get("License-Expression")
                or metadata.get("License")
                or "Not declared in package metadata",
                "classifiers": [v for v in metadata.get_all("Classifier", []) if v.startswith("License")],
                "source": metadata.get_all("Project-URL", []) or [metadata.get("Home-page", "")],
                "notices": notices,
            }
        )
    (destination / "index.json").write_text(json.dumps(packages, indent=2), encoding="utf-8")
    print("LICENSE NOTICES PRESERVED", len(packages), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(sys.prefix) / "third-party-licenses")
    inventory(parser.parse_args().output)
