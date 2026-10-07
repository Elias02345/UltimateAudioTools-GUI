import sys
import time

import numpy as np
import pytest
import soundfile as sf
from pydantic import ValidationError
from separator_engine.audio import (
    canonical_stems,
    metadata,
    output_name,
    safe_name,
    unique_path,
    validate_export,
    waveform,
)
from separator_engine.catalog import MODEL_SOURCES, Catalog, builtin_presets
from separator_engine.schema import Job, JobRequest, Preset, Request
from separator_engine.server import Supervisor, terminate
from separator_engine.state import State


@pytest.fixture
def recording(tmp_path):
    path = tmp_path / "音楽 café 🎵.wav"
    rate = 44100
    t = np.arange(rate * 2) / rate
    sf.write(path, np.stack([0.1 * np.sin(2 * np.pi * 440 * t)] * 2, axis=1), rate, subtype="FLOAT")
    return path


@pytest.fixture
def supervisor(tmp_path):
    instance = Supervisor(tmp_path / "state", lambda *args, **kwargs: None)
    instance.settings.output.directory = str(tmp_path / "outputs")
    yield instance
    instance.close()
    instance.queue_thread.join(timeout=8)
    instance.pool.shutdown(wait=True, cancel_futures=True)
    instance.state.close()


def test_preset_validation_and_weights():
    for model in ["../model.ckpt", "C:\\bad\\model.ckpt"]:
        with pytest.raises(ValidationError):
            Preset(id="test", name="test", models=[model])
    with pytest.raises(ValidationError):
        Preset(id="test", name="test", models=["a", "b"], weights=[0, 0])
    with pytest.raises(ValidationError):
        Preset(id="test", name="test", models=["a", "b"], weights=[1, 1], algorithm="uvr_max_spec")
    with pytest.raises(ValidationError):
        Preset(id="test", name="test", models=["a", "a"])


def test_protocol_and_range_validation():
    assert Request(v=1, id="id", method="initialize").params == {}
    with pytest.raises(ValidationError):
        Request(v=2, id="id", method="initialize")
    with pytest.raises(ValidationError):
        JobRequest(path="foo", preset=Preset(id="x", name="x", models=["m"]), range_start=5, range_end=4)


def test_canonical_labels_are_contextual():
    assert canonical_stems(["vocals", "other"]) == ["Vocals", "Instrumental"]
    assert canonical_stems(["other", "vocals"]) == ["Instrumental", "Vocals"]
    assert canonical_stems(["vocals", "drums", "bass", "other"])[-1] == "Other"


@pytest.mark.parametrize("value", ["../bad:name", "CON", "LPT1", "音楽 🎵", "a/b\\c", " "])
def test_safe_names(value):
    name = safe_name(value)
    assert name not in {"", ".", "..", "CON", "LPT1"}
    assert "/" not in name and "\\" not in name and ":" not in name


def test_output_collision_is_explicit(tmp_path):
    dest = tmp_path / "test.wav"
    dest.write_bytes(b"existing")
    assert unique_path(dest, "unique").name == "test (2).wav"
    with pytest.raises(FileExistsError):
        unique_path(dest, "ask")
    assert dest.read_bytes() == b"existing"
    with pytest.raises(ValueError):
        output_name("{invalid}", original="x", stem="Vocals", model="m", preset="p")


def test_export_compatibility_before_inference():
    with pytest.raises(ValueError, match="MP3 cannot preserve"):
        validate_export(96000, "MP3")
    validate_export(96000, "FLAC")
    validate_export(48000, "MP3")


def test_real_metadata_and_streamed_waveform(recording, tmp_path):
    info = metadata(str(recording))
    assert info["duration"] == 2
    assert info["sample_rate"] == 44100
    assert info["channels"] == 2
    cache = tmp_path / "waveforms"
    result = waveform(str(recording), cache, points=200)
    assert len(result["peaks"]) <= 201
    assert max(result["peaks"]) > 0
    assert waveform(str(recording), cache, points=200) == result


def test_corrupt_audio_error(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_text("not audio")
    with pytest.raises(ValueError):
        metadata(str(bad))


def test_state_persistence_and_reorder(tmp_path):
    first = State(tmp_path)
    first.put("settings", {"quality": "Ultra"})
    first.save_job({"id": "a"})
    first.save_job({"id": "b"})
    first.reorder(["b", "a"])
    first.close()
    second = State(tmp_path)
    assert second.get("settings") == {"quality": "Ultra"}
    assert [j["id"] for j in second.jobs()] == ["b", "a"]
    with pytest.raises(ValueError):
        second.reorder(["a", "a"])
    second.close()


def test_all_requested_models_and_presets_are_real(supervisor):
    entries = {m["id"]: m for m in supervisor.catalog.list()}
    assert set(MODEL_SOURCES).issubset(entries)
    for name in MODEL_SOURCES:
        assert "Instrumental" in entries[name]["stems"]
    presets = {p["id"]: p for p in builtin_presets()}
    assert presets["instrumental_full"]["algorithm"] == "uvr_max_spec"
    assert presets["vocal_balanced"]["algorithm"] == "avg_fft"
    supervisor.catalog.validate_selection(Preset.model_validate(presets["instrumental_full"]))


def test_queue_and_preset_survive_restart(supervisor, recording):
    preset = Preset.model_validate(builtin_presets()[0])
    preset.id, preset.builtin = "user_test", False
    supervisor.dispatch("save_preset", {"preset": preset.model_dump()})
    job = supervisor.dispatch(
        "enqueue", {"requests": [JobRequest(path=str(recording), preset=preset).model_dump()]}
    )[0]
    Job.model_validate(job)
    assert supervisor.state.jobs()[0]["status"] == "Pending"
    assert supervisor.state.get("user_presets")[0]["id"] == "user_test"
    supervisor.dispatch("remove_job", {"id": job["id"]})
    assert recording.exists()


def test_interrupted_job_recovery(tmp_path, recording):
    state = State(tmp_path / "state")
    preset = Preset.model_validate(builtin_presets()[0])
    state.save_job(
        {
            "id": "crashed",
            "status": "Processing",
            "created_at": time.time(),
            "request": JobRequest(path=str(recording), preset=preset).model_dump(),
            "source": metadata(str(recording)),
            "error": None,
            "result": None,
        }
    )
    state.close()
    engine = Supervisor(tmp_path / "state", lambda *a, **kw: None)
    assert engine.jobs[0]["status"] == "Interrupted"
    engine.close()
    engine.queue_thread.join(timeout=3)
    engine.pool.shutdown()
    engine.state.close()


def test_no_download_without_consent(supervisor, recording):
    preset = Preset.model_validate(builtin_presets()[0])
    job = supervisor.dispatch(
        "enqueue", {"requests": [JobRequest(path=str(recording), preset=preset).model_dump()], "start": True}
    )[0]
    deadline = time.monotonic() + 10
    while job["status"] not in {"Failed", "Completed"} and time.monotonic() < deadline:
        time.sleep(0.05)
    assert job["status"] == "Failed"
    assert "Required models are missing" in job["error"]
    assert supervisor.worker is None


def test_cancel_and_retry_barrier(supervisor, recording):
    preset = Preset.model_validate(builtin_presets()[0])
    job = supervisor.dispatch(
        "enqueue", {"requests": [JobRequest(path=str(recording), preset=preset).model_dump()]}
    )[0]
    supervisor.current = job["id"]
    job["status"] = "Processing"
    supervisor.dispatch("cancel_job", {"id": job["id"]})
    with pytest.raises(ValueError, match="Cancellation is finishing"):
        supervisor.dispatch("retry_job", {"id": job["id"]})
    supervisor.current = None
    supervisor.dispatch("retry_job", {"id": job["id"]})
    assert job["status"] == "Pending"


def test_shutdown_rejects_new_work(supervisor):
    supervisor.close()
    with pytest.raises(ValueError, match="shutting down"):
        supervisor.dispatch("download_model", {"model": "anything"})


def test_terminate_real_owned_process():
    import subprocess

    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=sys.platform != "win32"
    )
    terminate(proc)
    assert proc.poll() is not None


def test_offline_catalog_and_empty_checkpoint(tmp_path, monkeypatch):
    import requests

    def offline(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "get", offline)
    catalog = Catalog(tmp_path / "models", tmp_path)
    entries = catalog.list()
    assert len(entries) > 100
    model = next(m for m in entries if m["id"] == "bs_roformer_vocals_resurrection_unwa.ckpt")
    for file in model["physical_files"]:
        (catalog.models / file).write_bytes(b"")
    assert not next(m for m in catalog.list() if m["id"] == model["id"])["downloaded"]


def test_comparison_preview_uses_same_range_and_cache_key(tmp_path):
    from separator_engine.audio import preview
    import numpy as np
    import soundfile as sf

    source = tmp_path / "range.wav"
    sf.write(
        source,
        np.concatenate([np.zeros((44100, 2)), np.full((44100, 2), 0.25), np.full((44100, 2), 0.5)]),
        44100,
        subtype="FLOAT",
    )
    clip = preview(str(source), tmp_path / "previews", 1, 2)
    samples, rate = sf.read(clip)
    assert rate == 44100 and len(samples) == 44100
    assert np.allclose(samples, 0.25, atol=1e-6)
    assert sf.info(clip).subtype == "PCM_24"
    assert preview(str(source), tmp_path / "previews", 0, 1) != clip
    with pytest.raises(ValueError):
        preview(str(source), tmp_path / "previews", 2, 1)
