"""Float chunk inference with surrounding model context and crossfaded boundaries."""

from pathlib import Path

import numpy as np
import soundfile as sf


def separate_chunks(separator, source: Path, output: Path, seconds: int) -> list[str]:
    info = sf.info(source)
    core = seconds * info.samplerate
    if info.frames <= core:
        return separator.separate(str(source))
    context = 30 * info.samplerate
    fade = min(info.samplerate // 2, core // 4)
    merged: dict[str, sf.SoundFile] = {}
    paths = []
    original_dir = separator.output_dir
    try:
        with sf.SoundFile(source) as stream:
            for index, start in enumerate(range(0, info.frames, core)):
                # Overlap the previous output by half a second, with 30s of real
                # surrounding context on both sides. Context never reaches export.
                begin = max(0, start - fade)
                end = min(info.frames, start + core)
                read_begin = max(0, begin - context)
                read_end = min(info.frames, end + context)
                stream.seek(read_begin)
                samples = stream.read(read_end - read_begin, dtype="float32", always_2d=True)
                chunk_dir = output / f"chunk-{index}"
                chunk_dir.mkdir()
                chunk = chunk_dir / "input.wav"
                sf.write(chunk, samples, info.samplerate, subtype="FLOAT")
                separator.output_dir = str(chunk_dir)
                separator.model_instance.output_dir = str(chunk_dir)
                names = separator.separate(str(chunk))
                if not names:
                    raise ValueError("A processing chunk produced no stems.")
                if index and set(names) != set(merged):
                    raise ValueError("Processing chunks produced inconsistent stems.")
                for name in names:
                    path = Path(name)
                    path = path if path.is_absolute() else chunk_dir / path
                    audio, rate = sf.read(path, dtype="float32", always_2d=True)
                    if (
                        rate != info.samplerate
                        or len(audio) < end - read_begin
                        or not np.isfinite(audio).all()
                    ):
                        raise ValueError("A processing chunk returned invalid audio.")
                    audio = audio[begin - read_begin : end - read_begin]
                    if name not in merged:
                        target = output / Path(name).name
                        merged[name] = sf.SoundFile(
                            target, "w+", samplerate=rate, channels=audio.shape[1], subtype="FLOAT"
                        )
                        paths.append(str(target))
                    dest = merged[name]
                    if start:
                        overlap = start - begin
                        dest.seek(begin)
                        previous = dest.read(overlap, dtype="float32", always_2d=True)
                        weights = np.linspace(0, 1, overlap, dtype=np.float32)[:, None]
                        audio[:overlap] = previous * (1 - weights) + audio[:overlap] * weights
                    dest.seek(begin)
                    dest.write(audio)
                    dest.flush()
    finally:
        separator.output_dir = original_dir
        separator.model_instance.output_dir = original_dir
        for dest in merged.values():
            dest.close()
    return paths
