"""Isolated ML process. Protocol stdout is protected from upstream library prints."""

import gc
import hashlib
import json
import logging
import os
import re
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

from .audio import (
    canonical_stems,
    ffmpeg,
    metadata,
    output_name,
    run_ffmpeg,
    safe_name,
    unique_path,
    validate_export,
)
from .catalog import MODEL_SOURCES
from .schema import JobRequest

WIRE = sys.stdout
sys.stdout = sys.stderr


def emit(kind: str, **data):
    WIRE.write(json.dumps({"kind": kind, **data}, allow_nan=False) + "\n")
    WIRE.flush()


def error_message(error: Exception) -> str:
    message = str(error)
    lower = message.lower()
    if "out of memory" in lower:
        return (
            "GPU memory ran out. The selected model was preserved. Close GPU-heavy applications, "
            "choose autocast precision, explicitly reduce context size, or select CPU."
        )
    if "cuda" in lower and ("driver" in lower or "not available" in lower):
        return "CUDA could not initialize. Check the NVIDIA driver and selected runtime, or choose CPU."
    if isinstance(error, PermissionError):
        return "This folder is not writable. Choose an output or model folder you can write to."
    if isinstance(error, OSError) and error.errno == 28:
        return "The disk is full. Free space or choose another output/model folder, then retry."
    return message[:1500] or type(error).__name__


def setup_ffmpeg(root: Path):
    """Provide the bundled FFmpeg to libraries that search PATH, only in this process."""
    import shutil

    root.mkdir(parents=True, exist_ok=True)
    destination = root / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not destination.exists():
        shutil.copy2(ffmpeg(), destination)
        destination.chmod(0o755)
    os.environ["PATH"] = str(root) + os.pathsep + os.environ.get("PATH", "")


class Engine:
    def __init__(self, models: Path, root: Path):
        self.models, self.root = models, root
        setup_ffmpeg(root / "bin")
        self.separator = None
        self.key = None

    def make_separator(self, **kwargs):
        import requests
        from audio_separator.separator import Separator
        from filelock import FileLock

        models = self.models

        class AtomicSeparator(Separator):
            def load_model(self, model_filename, force_reload=False):
                import onnxruntime as ort
                import torch

                if self._loaded_model_filename == model_filename and not force_reload:
                    return super().load_model(model_filename, force_reload=force_reload)
                self._onnx_device = None
                create_session = ort.InferenceSession
                cuda = self.torch_device.type == "cuda"
                gpu_index = torch.cuda.current_device() if cuda else None

                def verified_session(*args, **options):
                    if cuda:
                        options["providers"] = ["CUDAExecutionProvider"]
                        options["provider_options"] = [{"device_id": str(gpu_index)}]
                    session = create_session(*args, **options)
                    providers = session.get_providers()
                    if cuda:
                        configured = session.get_provider_options().get("CUDAExecutionProvider", {})
                        if (
                            "CUDAExecutionProvider" not in providers
                            or int(configured.get("device_id", -1)) != gpu_index
                        ):
                            raise ValueError(
                                "ONNX could not activate the selected CUDA GPU. Repair the NVIDIA "
                                "runtime or explicitly select CPU, then retry."
                            )
                    self._onnx_device = (
                        f"cuda:{gpu_index}"
                        if cuda
                        else "coreml"
                        if "CoreMLExecutionProvider" in providers
                        else "cpu"
                    )
                    return session

                # Model loads are serial inside this isolated worker. Keep the upstream
                # constructor intact outside this scope, including on failed loads.
                with patch.object(ort, "InferenceSession", verified_session):
                    return super().load_model(model_filename, force_reload=force_reload)

            def download_file_if_not_exists(self, url, output_path):
                output = Path(output_path).resolve()
                if not output.is_relative_to(models.resolve()):
                    raise ValueError("Model download attempted to escape the model cache.")
                source = MODEL_SOURCES.get(output.name, {})
                if source and output.suffix == ".ckpt":
                    url = source["url"]
                with FileLock(str(output) + ".lock", timeout=600):
                    if output.exists():
                        if output.stat().st_size == 0:
                            output.unlink()
                        elif source.get("size") and output.stat().st_size != source["size"]:
                            raise ValueError(
                                "Cached model has an incorrect size. Verify or delete it in Models."
                            )
                        else:
                            if source.get("sha256"):
                                with output.open("rb") as stream:
                                    if hashlib.file_digest(stream, "sha256").hexdigest() != source["sha256"]:
                                        raise ValueError(
                                            "Cached model failed its publisher checksum. Delete it and retry."
                                        )
                            return
                    if os.environ.get("SEPARATOR_OFFLINE") == "1":
                        raise ValueError(
                            f"Container asset {output.name} is missing. Prepare it in the host Model Manager."
                        )
                    partial = output.with_suffix(output.suffix + ".part")
                    started = time.monotonic()
                    digest = hashlib.sha256()
                    with requests.get(
                        url, stream=True, timeout=(15, 60), headers={"Accept-Encoding": "identity"}
                    ) as response:
                        if response.status_code != 200:
                            raise RuntimeError(f"Download failed with HTTP {response.status_code}: {url}")
                        wire_size = int(response.headers.get("content-length", 0))
                        encoding = response.headers.get("content-encoding", "").strip().lower()
                        identity_size = wire_size if encoding in {"", "identity"} else 0
                        publisher_size = source.get("size", 0)
                        total = publisher_size or identity_size
                        downloaded, last = 0, 0.0
                        try:
                            with partial.open("wb") as stream:
                                for chunk in response.iter_content(1024 * 1024):
                                    if not chunk:
                                        continue
                                    stream.write(chunk)
                                    digest.update(chunk)
                                    downloaded += len(chunk)
                                    now = time.monotonic()
                                    if now - last > 0.2:
                                        speed = downloaded / max(now - started, 0.01)
                                        emit(
                                            "download_progress",
                                            filename=output.name,
                                            bytes=downloaded,
                                            total=total or None,
                                            speed=speed,
                                            eta=max(0, total - downloaded) / speed if total else None,
                                        )
                                        last = now
                                stream.flush()
                                os.fsync(stream.fileno())
                            if (identity_size and downloaded != identity_size) or (
                                publisher_size and downloaded != publisher_size
                            ):
                                raise ValueError("The model download was incomplete. Retry the download.")
                            if source.get("sha256") and digest.hexdigest() != source["sha256"]:
                                raise ValueError("The downloaded model failed its publisher SHA256 check.")
                            if downloaded == 0:
                                raise ValueError("The downloaded file is empty.")
                            if output.suffix == ".json":
                                json.loads(partial.read_text(encoding="utf-8"))
                            os.replace(partial, output)
                            emit(
                                "download_progress",
                                filename=output.name,
                                bytes=downloaded,
                                total=downloaded,
                                speed=0,
                                eta=0,
                            )
                        finally:
                            partial.unlink(missing_ok=True)

        return AtomicSeparator(model_file_dir=str(models), log_level=logging.WARNING, **kwargs)

    def configure(self, request: JobRequest, output: Path, rate: int):
        import torch

        settings = request.preset.parameters
        if settings.device == "cuda" or (settings.device == "auto" and torch.cuda.is_available()):
            if not torch.cuda.is_available() or settings.gpu_index >= torch.cuda.device_count():
                raise ValueError("The selected CUDA device is not available. Rescan hardware or choose CPU.")
            torch.cuda.set_device(settings.gpu_index)
        if settings.device == "mps" and not torch.backends.mps.is_available():
            raise ValueError("MPS is not available on this system. Choose CPU or automatic device selection.")
        key = json.dumps(
            {"models": request.preset.models, "parameters": settings.model_dump(), "rate": rate},
            sort_keys=True,
        )
        if self.key != key:
            self.separator = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.key = key
        if self.separator is None:
            self.separator = self.make_separator(
                output_dir=str(output),
                output_format="WAV",
                sample_rate=rate,
                use_soundfile=True,
                normalization_threshold=1.0,
                amplification_threshold=0.0,
                use_autocast=settings.precision == "autocast",
                use_native_fp16=settings.precision == "float16",
                use_torch_compile=settings.torch_compile,
                chunk_duration=None,
                mdxc_params={
                    "segment_size": settings.segment_size or 256,
                    "override_model_segment_size": settings.segment_size is not None,
                    "batch_size": settings.batch_size,
                    "overlap": settings.overlap,
                    "pitch_shift": 0,
                },
                mdx_params={
                    "segment_size": settings.mdx_segment_size,
                    "overlap": settings.mdx_overlap,
                    "batch_size": settings.batch_size,
                    "hop_length": 1024,
                    "enable_denoise": settings.denoise,
                },
                vr_params={
                    "batch_size": settings.batch_size,
                    "window_size": 512,
                    "aggression": settings.vr_aggression,
                    "enable_tta": settings.vr_tta,
                },
                demucs_params={
                    "segment_size": "Default",
                    "shifts": settings.demucs_shifts,
                    "overlap": 0.25,
                    "segments_enabled": True,
                },
            )
            if settings.device == "cpu":
                self.separator.torch_device = torch.device("cpu")
                self.separator.onnx_execution_provider = ["CPUExecutionProvider"]
            elif settings.device == "mps":
                self.separator.torch_device = torch.device("mps")
        self.separator.output_dir = str(output)
        if self.separator.model_instance:
            self.separator.model_instance.output_dir = str(output)
        return self.separator

    def run(self, data: dict) -> dict:
        import numpy as np
        import soundfile as sf
        import torch
        from audio_separator.separator.ensembler import Ensembler

        request = JobRequest.model_validate(data["request"])
        work = Path(data["work"])
        work.mkdir(parents=True, exist_ok=True)
        emit("stage", stage="Preparing", model=None)
        original = Path(request.path)
        meta = metadata(str(original))
        validate_export(
            request.preset.output.sample_rate or meta["sample_rate"], request.preset.output.format
        )
        # Model inference is at 44.1k; requested export resampling happens only after ensembling.
        rate = 44100
        decoded = work / "input.wav"
        args = ["-y"]
        if request.range_start is not None:
            args += ["-ss", str(request.range_start)]
        args += ["-i", str(original)]
        if request.range_end is not None:
            args += ["-t", str(request.range_end - request.range_start)]
        run_ffmpeg([*args, "-ac", "2", "-ar", str(rate), "-c:a", "pcm_f32le", str(decoded)])
        stems_by_type = {}
        model_details = []
        started = time.monotonic()
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        for i, model in enumerate(request.preset.models):
            model_dir = work / f"pass-{i}"
            model_dir.mkdir(exist_ok=True)
            emit(
                "stage",
                stage="Loading model",
                model=model,
                pass_index=i + 1,
                pass_count=len(request.preset.models),
            )
            separator = self.configure(request, model_dir, rate)
            # Clear the old model before load: upstream retains it during next model construction.
            if getattr(separator, "_loaded_model_filename", None) != model:
                separator.model_instance = None
                separator._loaded_model_filename = None
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            separator.load_model(model)
            # Preserve floating-point model levels; apply one ceiling after ensembling.
            separator.model_instance.normalization_threshold = float("inf")
            actual_device = str(
                getattr(separator, "_onnx_device", None)
                or getattr(separator.model_instance, "torch_device", separator.torch_device)
            )
            emit(
                "stage",
                stage="Processing",
                model=model,
                device=actual_device,
                pass_index=i + 1,
                pass_count=len(request.preset.models),
            )
            # Float input ensures the upstream writer preserves float intermediate samples.
            if request.preset.parameters.chunk_duration:
                from .chunking import separate_chunks

                outputs = separate_chunks(
                    separator, decoded, model_dir, request.preset.parameters.chunk_duration
                )
            else:
                outputs = separator.separate(str(decoded))
            if not outputs:
                raise ValueError("The engine produced no output stems.")
            labels = []
            for name in outputs:
                match = re.search(r"_\(([^)]+)\)", Path(name).name)
                labels.append(match[1] if match else Path(name).stem.split("_")[-1])
            normalized_labels = canonical_stems(labels)
            for name, stem in zip(outputs, normalized_labels, strict=True):
                path = Path(name)
                if not path.is_absolute():
                    path = model_dir / path
                audio, sr = sf.read(path, dtype="float32", always_2d=True)
                if sr != rate or audio.size == 0 or not np.isfinite(audio).all():
                    raise ValueError("The engine returned invalid audio.")
                stems_by_type.setdefault(stem, []).append(audio.T)
            model_details.append(
                {
                    "model": model,
                    "device": actual_device,
                    "precision": getattr(separator.model_instance, "effective_precision", "float32"),
                }
            )
        selected = request.preset.task
        wanted = (
            {"Vocals", "Drums", "Bass", "Other"}
            if selected == "4 Stems"
            else {"Vocals", "Instrumental"}
            if selected == "Both"
            else set(stems_by_type)
            if selected == "All"
            else {selected}
        )
        if not wanted.issubset(stems_by_type):
            raise ValueError(f"Missing requested stems: {', '.join(sorted(wanted - stems_by_type.keys()))}")
        emit("stage", stage="Ensembling" if len(request.preset.models) > 1 else "Encoding", model=None)
        final_rate = request.preset.output.sample_rate or meta["sample_rate"]
        output_root = Path(request.preset.output.directory).expanduser().resolve()
        if request.preset.output.subfolder:
            output_root = output_root / safe_name(original.stem)
        output_root.mkdir(parents=True, exist_ok=True)
        results = []
        prepared = []
        for stem in sorted(wanted):
            arrays = stems_by_type[stem]
            if len(arrays) != len(request.preset.models):
                raise ValueError("Not every ensemble model produced the requested stem.")
            audio = (
                Ensembler(logging.getLogger(__name__), request.preset.algorithm, request.preset.weights)
                .ensemble(arrays)
                .T
            )
            with sf.SoundFile(decoded) as decoded_file:
                expected_frames = len(decoded_file)
            audio = audio[:expected_frames]
            if len(audio) < expected_frames:
                audio = np.pad(audio, ((0, expected_frames - len(audio)), (0, 0)))
            if not np.isfinite(audio).all():
                raise ValueError("Ensembling produced non-finite samples.")
            peak = float(np.max(np.abs(audio)))
            if peak > request.preset.output.normalization:
                audio *= request.preset.output.normalization / peak
            raw = work / f"final-{stem}.wav"
            sf.write(raw, audio, rate, subtype="FLOAT")
            name = output_name(
                request.preset.output.template,
                original=original.stem,
                stem=stem,
                model=Path(request.preset.models[0]).stem,
                preset=request.preset.name,
            )
            destination = unique_path(
                output_root / f"{name}.{request.preset.output.format.lower()}",
                request.preset.output.collision,
            )
            if destination in {p[1] for p in prepared}:
                destination = unique_path(
                    destination.with_name(f"{destination.stem} - {stem}{destination.suffix}"),
                    request.preset.output.collision,
                )
            if destination.resolve() == original.resolve():
                raise ValueError("An output must never replace the original recording.")
            encoded = work / f"export-{stem}.{request.preset.output.format.lower()}"
            fmt = request.preset.output.format
            codec = {
                "WAV": "pcm_s24le",
                "FLAC": "flac",
                "MP3": "libmp3lame",
                "OGG": "libvorbis",
                "M4A": "aac",
            }[fmt]
            encode_args = ["-y", "-i", str(raw), "-ar", str(final_rate), "-c:a", codec]
            if fmt in {"MP3", "OGG", "M4A"}:
                encode_args += ["-b:a", f"{request.preset.output.bitrate}k"]
            emit("stage", stage="Encoding", model=stem)
            run_ffmpeg([*encode_args, str(encoded)])
            info = metadata(str(encoded))
            if abs(info["duration"] - expected_frames / rate) > 0.2:
                raise ValueError("Output duration did not match the recording.")
            prepared.append((encoded, destination, stem, info))
        # Publish complete files without partial contents or silent overwrites.
        import shutil

        for encoded, destination, stem, info in prepared:
            temp = destination.with_name(f".separator-{data['id']}-{stem}.part")
            try:
                with temp.open("xb") as target, encoded.open("rb") as source:
                    shutil.copyfileobj(source, target)
                    target.flush()
                    os.fsync(target.fileno())
                if request.preset.output.collision == "overwrite":
                    os.replace(temp, destination)
                else:
                    while True:
                        try:
                            os.link(temp, destination)
                            break
                        except FileExistsError:
                            destination = unique_path(destination, request.preset.output.collision)
            finally:
                temp.unlink(missing_ok=True)
            results.append(
                {
                    "stem": stem,
                    "path": str(destination),
                    "duration": info["duration"],
                    "sample_rate": final_rate,
                    "size": destination.stat().st_size,
                }
            )
        return {
            "outputs": results,
            "device": model_details[0]["device"],
            "models": model_details,
            "engine": "audio-separator",
            "engine_version": "0.47.0",
            "elapsed": time.monotonic() - started,
            "peak_vram": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
        }


def main():
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    engine = Engine(Path(sys.argv[2]), Path(sys.argv[3]))
    import signal
    import threading

    def cancelled(_signal, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, cancelled)
    parent_pid = os.getppid()

    def parent_watchdog():
        while True:
            time.sleep(1)
            if os.getppid() != parent_pid:
                if os.name != "nt":
                    os.killpg(os.getpid(), signal.SIGTERM)
                os._exit(1)

    threading.Thread(target=parent_watchdog, daemon=True).start()
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if message["method"] == "download":
                engine.make_separator(info_only=True).download_model_and_data(message["model"])
                emit("result", result={"model": message["model"]})
            elif message["method"] == "run":
                emit("result", result=engine.run(message))
            elif message["method"] == "shutdown":
                break
            else:
                raise ValueError("Unsupported worker method.")
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            engine.separator, engine.key = None, None
            emit("error", error=error_message(error), detail=type(error).__name__)


if __name__ == "__main__":
    main()
