"""FFmpeg and filesystem boundaries. Never mutate an input recording."""

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

SUPPORTED = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".aiff", ".aif", ".wma", ".mp4"}


def canonical_stems(labels: list[str]) -> list[str]:
    normalized = [s.strip().title() for s in labels]
    if len(normalized) == 2 and "Vocals" in normalized and "Other" in normalized:
        normalized = ["Instrumental" if s == "Other" else s for s in normalized]
    return normalized


def validate_export(rate: int, fmt: str):
    if fmt == "MP3" and rate not in {8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000}:
        raise ValueError("MP3 cannot preserve this sample rate. Choose 44.1/48 kHz or a lossless format.")


def ffmpeg() -> str:
    import imageio_ffmpeg

    return os.environ.get("SEPARATOR_FFMPEG") or imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args: list[str], timeout: int | None = None) -> None:
    result = subprocess.run(
        [ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise ValueError("Audio conversion failed: " + result.stderr[-1500:])


def input_path(value: str) -> Path:
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in SUPPORTED:
        raise ValueError("Choose a supported audio file (WAV, FLAC, MP3, M4A, AAC, OGG or AIFF).")
    return path


def metadata(value: str) -> dict:
    import soundfile as sf

    path = input_path(value)
    try:
        info = sf.info(path)
        if info.frames <= 0 or info.samplerate <= 0:
            raise ValueError("This audio file is empty.")
        duration, rate, channels, codec = info.duration, info.samplerate, info.channels, info.format
    except (RuntimeError, sf.LibsndfileError):
        # ffprobe is optional: FFmpeg's decoder supplies the fallback metadata.
        proc = subprocess.run(
            [ffmpeg(), "-nostdin", "-hide_banner", "-i", str(path), "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode:
            raise ValueError("This recording could not be decoded. Check that it is not corrupt.") from None
        dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", proc.stderr)
        audio = re.search(r"Audio: ([^,]+).*?(\d+) Hz, ([^,]+)", proc.stderr)
        if not dur or not audio:
            raise ValueError("The audio metadata could not be read.") from None
        duration = int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3])
        rate, codec = int(audio[2]), audio[1]
        channels = 1 if audio[3] == "mono" else 2
    size = path.stat().st_size
    return {
        "path": str(path),
        "name": path.name,
        "duration": duration,
        "sample_rate": rate,
        "channels": channels,
        "codec": codec,
        "size": size,
        "bitrate": round(size * 8 / duration / 1000),
    }


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")[:160]
    value = value or "audio"
    if value.split(".")[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        value = "_" + value
    return value


def output_name(template: str, **values: str) -> str:
    if set(re.findall(r"\{([^{}]+)\}", template)) - {"original", "stem", "model", "preset"}:
        raise ValueError("Filename variables are {original}, {stem}, {model} and {preset}.")
    return safe_name(template.format_map(values))


def unique_path(path: Path, policy: str) -> Path:
    if not path.exists() or policy == "overwrite":
        return path
    if policy == "ask":
        raise FileExistsError(
            "An output already exists. Choose unique filenames or explicitly enable overwrite."
        )
    for i in range(2, 100000):
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError("Could not find a free output filename.")


def directory_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())


def waveform(path: str, cache: Path, points: int = 1600) -> dict:
    import numpy as np
    import soundfile as sf

    src = input_path(path)
    stat = src.stat()
    key = hashlib.sha256(f"{src}:{stat.st_size}:{stat.st_mtime_ns}:{points}".encode()).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{key}.json"
    if target.exists():
        return json.loads(target.read_text())
    decoded = cache / f"{key}.wav"
    try:
        try:
            stream = sf.SoundFile(src)
        except (RuntimeError, sf.LibsndfileError):
            run_ffmpeg(["-y", "-i", str(src), "-ac", "1", "-ar", "12000", str(decoded)])
            stream = sf.SoundFile(decoded)
        with stream:
            length, rate = len(stream), stream.samplerate
            # Keep input frames bounded: streaming bins instead of a full-track decode.
            bin_frames = max(1, (length + points - 1) // points)
            peaks = []
            remaining, peak = bin_frames, 0.0
            while True:
                block = stream.read(min(65536, remaining), dtype="float32", always_2d=True)
                if not len(block):
                    if remaining != bin_frames:
                        peaks.append(peak)
                    break
                peak = max(peak, float(np.max(np.abs(block))))
                remaining -= len(block)
                if remaining == 0:
                    peaks.append(peak)
                    remaining, peak = bin_frames, 0.0
        result = {"peaks": peaks, "duration": length / rate, "sample_rate": rate}
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(result))
        os.replace(tmp, target)
        return result
    finally:
        decoded.unlink(missing_ok=True)


def preview(path: str, cache: Path, range_start: float | None = None, range_end: float | None = None) -> str:
    src = input_path(path)
    stat = src.stat()
    if range_start is not None and (not math.isfinite(range_start) or range_start < 0):
        raise ValueError("Preview range start must be finite and non-negative.")
    if range_end is not None and (
        range_start is None or not math.isfinite(range_end) or range_end <= range_start
    ):
        raise ValueError("Preview range end must follow its start.")
    key = hashlib.sha256(
        f"{src}:{stat.st_size}:{stat.st_mtime_ns}:{range_start}:{range_end}".encode()
    ).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{key}.wav"
    if not target.exists():
        tmp = cache / f"{key}.part.wav"
        args = ["-y"]
        if range_start is not None:
            args += ["-ss", str(range_start)]
        args += ["-i", str(src)]
        if range_end is not None:
            args += ["-t", str(range_end - range_start)]
        run_ffmpeg([*args, "-c:a", "pcm_s24le", str(tmp)])
        os.replace(tmp, target)
    return str(target)


def clear_cache(cache: Path) -> None:
    if cache.exists():
        shutil.rmtree(cache)
    cache.mkdir(parents=True, exist_ok=True)
