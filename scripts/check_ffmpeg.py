"""Validate real encoders/decoders and stereo samples in our corresponding-source FFmpeg build."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

parser = argparse.ArgumentParser()
parser.add_argument("--executable", type=Path, required=True)
parser.add_argument("--report", type=Path)
args = parser.parse_args()
executable = str(args.executable.resolve())
with tempfile.TemporaryDirectory(prefix="Separator codec 音楽 café ") as directory:
    root = Path(directory)
    rate = 44100
    t = np.arange(rate * 2) / rate
    samples = np.stack([0.1 * np.sin(2 * np.pi * 440 * t), 0.08 * np.sin(2 * np.pi * 220 * t)], axis=1)
    source = root / "original 🎵.wav"
    sf.write(source, samples, rate, subtype="PCM_24")
    checks = []
    for extension, codec in [
        ("flac", "flac"),
        ("wav", "pcm_s24le"),
        ("mp3", "libmp3lame"),
        ("ogg", "libvorbis"),
        ("m4a", "aac"),
        ("aiff", "pcm_s16be"),
        ("wma", "wmav2"),
    ]:
        encoded = root / ("output 音楽." + extension)
        command = [
            executable,
            "-nostdin",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vn",
            "-c:a",
            codec,
        ]
        if extension in {"mp3", "ogg", "m4a", "wma"}:
            command += ["-b:a", "192k"]
        subprocess.run([*command, str(encoded)], check=True, timeout=30)
        decoded = root / "decoded.wav"
        subprocess.run(
            [
                executable,
                "-nostdin",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(encoded),
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "pcm_f32le",
                str(decoded),
            ],
            check=True,
            timeout=30,
        )
        audio, sr = sf.read(decoded, always_2d=True)
        assert sr == rate and audio.shape[1] == 2
        assert abs(len(audio) / rate - 2) < 0.2 and np.isfinite(audio).all() and np.max(np.abs(audio)) > 0.01
        if extension in {"flac", "wav"}:
            np.testing.assert_allclose(audio, samples, atol=2e-7)
        checks.append(extension)
    baseline, _ = sf.read(source, always_2d=True)
    edit_checks = []
    for extension, codec in [("wav", "pcm_s24le"), ("flac", "flac")]:
        edited = root / ("edited 音楽." + extension)
        subprocess.run(
            [
                executable,
                "-nostdin",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-ss",
                "0.5",
                "-t",
                "0.75",
                "-af",
                "volume=0.4",
                "-ar",
                str(rate),
                "-c:a",
                codec,
                str(edited),
            ],
            check=True,
            timeout=30,
        )
        audio, sr = sf.read(edited, always_2d=True)
        assert sr == rate and audio.shape == (33075, 2) and np.isfinite(audio).all()
        np.testing.assert_allclose(audio, baseline[22050:55125] * 0.4, rtol=0, atol=2e-7)
        edit_checks.append(extension)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                {
                    "codecs": checks,
                    "trim_gain_exports": edit_checks,
                    "version": subprocess.check_output([executable, "-version"], text=True).splitlines()[0],
                },
                indent=2,
            )
        )
    print("REAL CODEC TESTS PASSED", checks, flush=True)
    print("RESULT EDIT FILTERS PASSED", edit_checks, flush=True)
