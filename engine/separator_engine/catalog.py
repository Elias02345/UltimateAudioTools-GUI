"""Discover actual upstream metadata; keep a complete offline snapshot."""

from __future__ import annotations

import hashlib
import importlib.resources as resources
import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests
from filelock import FileLock

from .audio import canonical_stems
from .schema import Preset

CHECKS_URL = "https://raw.githubusercontent.com/TRvlvr/application_data/main/filelists/download_checks.json"
MODEL_SOURCES = {
    "melband_roformer_inst_v1e_plus.ckpt": {
        "url": "https://huggingface.co/pcunwa/Mel-Band-Roformer-Inst/resolve/main/inst_v1e_plus.ckpt",
        "size": 913090472,
        "sha256": "6a4ddba739f0352407fb6e18b29206b82318ec427fe37fcedb0f83241e4e15fb",
    },
    "mel_band_roformer_instrumental_becruily.ckpt": {
        "url": "https://huggingface.co/becruily/mel-band-roformer-instrumental/resolve/main/"
        "mel_band_roformer_instrumental_becruily.ckpt",
        "size": 913106900,
        "sha256": "a8da6632a1c25efb1c9be783ce9ea367d226d4b918cd6c3717c8b1d7a396041d",
    },
    "bs_roformer_vocals_resurrection_unwa.ckpt": {
        "url": "https://huggingface.co/pcunwa/BS-Roformer-Resurrection/resolve/main/BS-Roformer-Resurrection.ckpt",
        "size": 204510749,
        "sha256": "9dbfe5cb572e4ed32a15ec727d7bd06c8d7aba97509e6fda5bc008bb1e0b2dd5",
    },
    "melband_roformer_big_beta6x.ckpt": {
        "url": "https://huggingface.co/pcunwa/Mel-Band-Roformer-big/resolve/main/big_beta6x.ckpt",
        "size": 1708527586,
        "sha256": "e16d702f4e20f13d60b293541c1dea75cb4414a5846b36780e28ef70352a4e5c",
    },
}


def package_json(name: str) -> dict:
    return json.loads(resources.files("audio_separator").joinpath(name).read_text())


class Catalog:
    def __init__(self, models: Path, state_root: Path):
        self.models = models
        self.state_root = state_root
        models.mkdir(parents=True, exist_ok=True)

    def checks(self, refresh: bool = False) -> dict:
        with FileLock(str(self.models / "download_checks.json.lock"), timeout=120):
            return self._checks(refresh)

    def _checks(self, refresh: bool = False) -> dict:
        dest = self.models / "download_checks.json"
        if refresh or not dest.exists():
            try:
                response = requests.get(CHECKS_URL, timeout=(10, 30))
                response.raise_for_status()
                data = response.json()
                if not isinstance(data.get("roformer_download_list"), dict):
                    raise ValueError("Upstream metadata has an unsupported shape.")
                tmp = dest.with_suffix(f".{uuid.uuid4().hex}.part")
                tmp.write_text(json.dumps(data))
                os.replace(tmp, dest)
            except (requests.RequestException, ValueError):
                if not dest.exists():
                    fallback = Path(__file__).parent / "data" / "download_checks.json"
                    if not fallback.exists():
                        raise ValueError(
                            "Model catalogue unavailable offline. Connect once to refresh metadata."
                        ) from None
                    dest.write_bytes(fallback.read_bytes())
        return json.loads(dest.read_text())

    def list(self, refresh: bool = False) -> list[dict]:
        checks = self.checks(refresh)
        bundled = package_json("models.json")
        scores = package_json("models-scores.json")
        entries = []
        groups = {
            "VR": ["vr_download_list"],
            "MDX": ["mdx_download_list", "mdx_download_vip_list"],
            "MDXC": ["mdx23c_download_list", "mdx23c_download_vip_list", "roformer_download_list"],
            "Demucs": ["demucs_download_list"],
        }
        index = (
            json.loads((self.models / "integrity.json").read_text())
            if (self.models / "integrity.json").exists()
            else {}
        )
        for family, keys in groups.items():
            merged = {}
            for key in keys:
                merged.update(checks.get(key, {}))
                merged.update(bundled.get(key, {}))
            for name, data in merged.items():
                if family == "Demucs" and not name.startswith("Demucs v4"):
                    continue
                if isinstance(data, dict):
                    filename = (
                        next((f for f in data if f.endswith(".yaml")), None)
                        if family == "Demucs"
                        else next(iter(data))
                    )
                    files = list(data) + list(data.values())
                else:
                    filename, files = data, [data]
                if not filename:
                    continue
                path = self.models / filename
                info = scores.get(filename, {})
                source = MODEL_SOURCES.get(filename, {})
                architecture = family
                if "roformer" in filename.lower():
                    architecture = "MelBand RoFormer" if "mel" in filename.lower() else "BS-RoFormer"
                stems = canonical_stems(info.get("stems", []))
                if not stems and "roformer" in filename.lower():
                    stems = ["Vocals", "Instrumental"]
                if family == "Demucs":
                    stems = ["Vocals", "Drums", "Bass", "Other"]
                physical = list(dict.fromkeys(Path(urlparse(f).path).name for f in files))
                downloaded = all(
                    (self.models / f).is_file() and (self.models / f).stat().st_size > 0 for f in physical
                )
                if downloaded and source.get("size"):
                    downloaded = path.stat().st_size == source["size"]
                entries.append(
                    {
                        "id": filename,
                        "name": name,
                        "family": family,
                        "architecture": architecture,
                        "stems": stems,
                        "target": info.get("target_stem"),
                        "downloaded": downloaded,
                        "size": source.get("size"),
                        "disk_usage": path.stat().st_size if path.exists() else 0,
                        "path": str(path),
                        "sha256": source.get("sha256") or index.get(filename, {}).get("sha256"),
                        "source": source.get("url", "https://github.com/nomadkaraoke/python-audio-separator"),
                        "license": "Individual weight license not specified by upstream",
                        "vip": "VIP" in name,
                        "download_files": files,
                        "physical_files": physical,
                        "benchmark": "Not measured by Separator",
                    }
                )
        return list({e["id"]: e for e in entries}.values())

    def validate_selection(self, preset: Preset) -> None:
        entries = {e["id"]: e for e in self.list()}
        if any(m not in entries for m in preset.models):
            raise ValueError("A selected model is absent from the current catalogue. Refresh Models.")
        if len(preset.models) > 1:
            stems = [set(entries[m]["stems"]) for m in preset.models]
            if any(not s for s in stems):
                raise ValueError("Ensembles require known stem metadata for every model.")
            if any(s != stems[0] for s in stems[1:]):
                raise ValueError("Ensemble models must produce the same stem set.")
        if preset.task != "All":
            wanted = (
                {"Vocals", "Drums", "Bass", "Other"}
                if preset.task == "4 Stems"
                else {"Vocals", "Instrumental"}
                if preset.task == "Both"
                else {preset.task}
            )
            if not wanted.issubset(set(entries[preset.models[0]]["stems"])):
                raise ValueError("The selected model does not supply the requested stem.")

    def verify(self) -> list[dict]:
        with FileLock(str(self.models / "integrity.json.lock"), timeout=600):
            return self._verify()

    def _verify(self) -> list[dict]:
        index_path = self.models / "integrity.json"
        index = json.loads(index_path.read_text()) if index_path.exists() else {}
        results = []
        for entry in self.list():
            if not any((self.models / f).exists() for f in entry["physical_files"]):
                continue
            valid = True
            digests = {}
            for filename in entry["physical_files"]:
                path = self.models / filename
                if not path.is_file() or path.stat().st_size == 0:
                    valid = False
                    continue
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                expected = MODEL_SOURCES.get(filename, {}).get("sha256") or index.get(filename, {}).get(
                    "sha256"
                )
                valid = valid and (expected is None or digest == expected)
                digests[filename] = digest
                if expected is None or digest == expected:
                    index[filename] = {"sha256": digest, "size": path.stat().st_size}
            results.append(
                {
                    "model": entry["id"],
                    "valid": valid,
                    "publisher_hash": entry["id"] in MODEL_SOURCES,
                    "files": digests,
                }
            )
        temp = index_path.with_suffix(".part")
        temp.write_text(json.dumps(index))
        os.replace(temp, index_path)
        return results


def builtin_presets() -> list[dict]:
    upstream = package_json("ensemble_presets.json")["presets"]
    definitions = []
    for key, p in upstream.items():
        task = "Instrumental" if key.startswith("instrumental") or key == "karaoke" else "Vocals"
        definitions.append(
            Preset(
                id=key,
                name=p["name"],
                description="Upstream ensemble · " + p["algorithm"],
                task=task,
                models=p["models"],
                algorithm=p["algorithm"],
                weights=p.get("weights"),
                builtin=True,
                quality="Ultra",
            ).model_dump()
        )
    for task, model in [
        ("Instrumental", "UVR-MDX-NET-Inst_HQ_5.onnx"),
        ("Vocals", "UVR-MDX-NET-Inst_HQ_5.onnx"),
    ]:
        definitions.append(
            Preset(
                id=f"fast_{task.lower()}",
                name=f"Fast {task.lower()}",
                task=task,
                models=[model],
                builtin=True,
                quality="Fast",
                description="Quick MDX separation for previews.",
            ).model_dump()
        )
    for task, model in [
        ("Instrumental", "mel_band_roformer_instrumental_becruily.ckpt"),
        ("Vocals", "bs_roformer_vocals_resurrection_unwa.ckpt"),
    ]:
        definitions.append(
            Preset(
                id=f"balanced_{task.lower()}",
                name=f"Balanced {task.lower()}",
                task=task,
                models=[model],
                builtin=True,
                quality="Balanced",
                description="Single RoFormer pass with model-recommended context.",
            ).model_dump()
        )
    definitions.append(
        Preset(
            id="four_stems",
            name="4-Stem Separation",
            task="4 Stems",
            models=["htdemucs_ft.yaml"],
            builtin=True,
            quality="Ultra",
            description="Fine-tuned Demucs vocals, drums, bass and other.",
        ).model_dump()
    )
    return definitions
