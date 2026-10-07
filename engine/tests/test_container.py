"""Path and mount boundary regressions independent of a container daemon."""

import csv
from pathlib import Path

import pytest
from separator_engine.container import mount, result_paths


def test_comma_and_unicode_mounts_are_single_csv_fields():
    source = '/tmp/recording, 音楽 "quote".wav'
    parsed = next(csv.reader([mount(source, "/input/file.wav", True)]))
    assert parsed == ["type=bind", "source=" + source, "target=/input/file.wav", "readonly"]


def test_container_results_are_mapped_and_confined(tmp_path):
    result = {"outputs": [{"path": "/output/音楽/stem.flac"}], "engine": "native"}
    mapped = result_paths(result, tmp_path)
    assert Path(mapped["outputs"][0]["path"]) == tmp_path / "音楽/stem.flac"
    assert mapped["engine"] == "container"
    for path in ["/etc/passwd", "/output/../../outside.flac"]:
        with pytest.raises(ValueError):
            result_paths({"outputs": [{"path": path}]}, tmp_path)
