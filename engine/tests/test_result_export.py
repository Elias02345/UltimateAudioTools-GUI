import hashlib
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from pydantic import ValidationError
from separator_engine.result_export import ResultExport, export_results


@pytest.fixture
def result(tmp_path):
    source = tmp_path / "stems" / "音楽 - Vocals.wav"
    source.parent.mkdir()
    samples = np.arange(44100 * 2) / 44100
    data = np.stack(
        [0.2 * np.sin(2 * np.pi * 440 * samples), 0.1 * np.sin(2 * np.pi * 220 * samples)], axis=1
    )
    sf.write(source, data, 44100, subtype="PCM_24")
    directory = tmp_path / "export"
    directory.mkdir()
    jobs = [
        {"id": "one", "status": "Completed", "result": {"outputs": [{"path": str(source), "stem": "Vocals"}]}}
    ]
    request = {"job_ids": ["one"], "paths": [str(source)], "directory": str(directory)}
    return source, directory, jobs, request


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_exact_copies_repeat_without_overwrites(result):
    source, directory, jobs, request = result
    before = digest(source)
    first = export_results(ResultExport(**request), jobs)
    second = export_results(ResultExport(**request), jobs)
    assert first["paths"] != second["paths"]
    assert all(digest(path) == before for path in first["paths"] + second["paths"])
    assert digest(source) == before
    assert len(list(directory.iterdir())) == 2


def test_actual_gain_trim_lossless_and_source_preservation(result):
    source, _, jobs, request = result
    before = digest(source)
    exported = export_results(
        ResultExport(
            **request, start=0.5, end=1.25, gains={str(source): 0.4}, format="FLAC", name="../Edit: 音楽"
        ),
        jobs,
    )
    audio, rate = sf.read(exported["paths"][0], always_2d=True)
    original, _ = sf.read(source, always_2d=True)
    assert rate == 44100 and audio.shape == (33075, 2)
    assert np.isfinite(audio).all()
    np.testing.assert_allclose(audio, original[22050:55125] * 0.4, atol=2e-7)
    assert digest(source) == before
    assert Path(exported["paths"][0]).parent == Path(request["directory"])


def test_comparison_duplicate_names_are_distinct(result, tmp_path):
    source, _, jobs, request = result
    other = tmp_path / "second" / source.name
    other.parent.mkdir()
    sf.write(other, np.zeros((44100, 2)), 44100, subtype="PCM_24")
    jobs.append(
        {"id": "two", "status": "Completed", "result": {"outputs": [{"path": str(other), "stem": "Vocals"}]}}
    )
    request.update(job_ids=["one", "two"], paths=[str(source), str(other)])
    output = export_results(ResultExport(**request), jobs)
    assert len(set(output["paths"])) == 2
    assert digest(output["paths"][0]) == digest(source)
    assert digest(output["paths"][1]) == digest(other)


@pytest.mark.parametrize(
    "options",
    [
        {"start": 1, "end": 1},
        {"start": float("nan")},
        {"gains": {"path": float("inf")}},
        {"gains": {"path": 1.1}},
    ],
)
def test_invalid_edits_rejected(result, options):
    with pytest.raises(ValidationError):
        ResultExport(**result[3], **options)


def test_input_preflight_and_unknown_paths_create_no_files(result, tmp_path):
    source, directory, jobs, request = result
    unknown = tmp_path / "unknown.wav"
    with pytest.raises(ValueError, match="selected completed"):
        export_results(ResultExport(**{**request, "paths": [str(unknown)]}), jobs)
    with pytest.raises(ValueError, match="outside"):
        export_results(ResultExport(**request, end=3), jobs)
    source.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        export_results(ResultExport(**request), jobs)
    assert not list(directory.iterdir())


def test_encoding_failure_rolls_back_staged_batch(result, monkeypatch):
    from separator_engine import result_export

    source, directory, jobs, request = result
    before = digest(source)

    def fail(*args):
        raise RuntimeError("Encoder failure")

    monkeypatch.setattr(result_export, "run_ffmpeg", fail)
    with pytest.raises(RuntimeError, match="Encoder failure"):
        export_results(ResultExport(**request, format="WAV"), jobs)
    assert not list(directory.iterdir())
    assert digest(source) == before


@pytest.mark.parametrize("format", ["WAV", "MP3", "OGG", "M4A"])
def test_real_export_codecs(result, format):
    from separator_engine.audio import metadata

    source, _, jobs, request = result
    before = digest(source)
    output = export_results(ResultExport(**request, format=format, start=0.2, end=1.5), jobs)
    info = metadata(output["paths"][0])
    assert abs(info["duration"] - 1.3) < 0.1
    assert info["sample_rate"] == 44100 and info["channels"] == 2
    assert digest(source) == before


def test_removable_drive_fallback_is_exclusive_and_exact(result, monkeypatch):
    import errno

    from separator_engine import result_export

    source, directory, jobs, request = result
    existing = directory / source.name
    existing.write_bytes(b"Keep this existing file")
    before = digest(source)

    def unsupported(*args):
        raise OSError(errno.EOPNOTSUPP, "Hard links not supported")

    monkeypatch.setattr(result_export.os, "link", unsupported)
    exported = export_results(ResultExport(**request), jobs)
    assert existing.read_bytes() == b"Keep this existing file"
    assert digest(exported["paths"][0]) == before
    assert digest(source) == before
    assert len(list(directory.iterdir())) == 2


def test_removable_drive_failed_copy_leaves_no_partial_file(result, monkeypatch):
    import errno

    from separator_engine import result_export

    source, directory, jobs, request = result
    before = digest(source)

    def unsupported(*args):
        raise OSError(errno.EOPNOTSUPP, "Hard links not supported")

    def fail(source, destination):
        destination.write(b"Partial")
        raise OSError("Disk full")

    monkeypatch.setattr(result_export.os, "link", unsupported)
    monkeypatch.setattr(result_export.shutil, "copyfileobj", fail)
    with pytest.raises(OSError, match="Disk full"):
        export_results(ResultExport(**request), jobs)
    assert not list(directory.iterdir())
    assert digest(source) == before
