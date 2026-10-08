"""Exercise the HTTP decoding boundary and real nested worker integration."""

import gzip
import hashlib
import importlib
import logging
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
import requests


@pytest.fixture
def worker(monkeypatch):
    stdout = sys.stdout
    try:
        module = importlib.import_module("separator_engine.worker")
    finally:
        sys.stdout = stdout
    events = []
    monkeypatch.setattr(module, "emit", lambda kind, **data: events.append((kind, data)))
    module.test_events = events
    return module


@pytest.mark.parametrize(
    ("device", "family", "requested", "pytorch", "supported"),
    [
        ("cpu", "mdx", "float32", False, True),
        ("cuda", "mel_band_roformer", "float16", True, True),
        ("cuda", "bs_roformer", "autocast", True, True),
        ("cpu", "mel_band_roformer", "float16", True, False),
        ("cuda", "demucs", "float16", True, False),
        ("cuda", "mdx", "float16", False, False),
        ("cuda", "mdx", "autocast", False, False),
    ],
)
def test_requested_precision_matches_upstream_policy(
    worker, device, family, requested, pytorch, supported
):
    import torch
    from audio_separator.separator.execution_policy import resolve_execution_policy

    policy = resolve_execution_policy(
        device=torch.device(device),
        model_family=family,
        use_autocast=requested == "autocast",
        use_native_fp16=requested == "float16",
        use_torch_compile=False,
        logger=logging.getLogger(__name__),
        uses_pytorch_inference=pytorch,
    )
    separator = SimpleNamespace(effective_precision=policy.precision)
    if supported:
        worker.verify_precision(separator, requested, "selected-model", device)
    else:
        with pytest.raises(ValueError, match="not supported.*inference was not started"):
            worker.verify_precision(separator, requested, "selected-model", device)


@pytest.fixture
def separator(worker, monkeypatch, tmp_path):
    class BaseSeparator:
        def __init__(self, **kwargs):
            self._loaded_model_filename = None
            self.torch_device = SimpleNamespace(type="cpu")

        def load_model(self, filename, force_reload=False):
            if self._loaded_model_filename == filename and not force_reload:
                return
            import onnxruntime as ort

            self.session = ort.InferenceSession(filename, providers=["CPUExecutionProvider"])
            self._loaded_model_filename = filename

    monkeypatch.setitem(sys.modules, "audio_separator.separator", SimpleNamespace(Separator=BaseSeparator))
    engine = worker.Engine.__new__(worker.Engine)
    engine.models = tmp_path
    return engine.make_separator()


@pytest.fixture
def serve():
    servers = []

    def start(body, encoding="identity", length=None):
        wire = gzip.compress(body) if encoding == "gzip" else body

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Encoding", encoding)
                self.send_header("Content-Length", str(len(wire) if length is None else length))
                self.end_headers()
                self.wfile.write(wire)
                self.close_connection = True

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}/model"

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_gzip_metadata_uses_decoded_bytes(separator, worker, serve, tmp_path):
    body = ('{"name":"café","value":"' + "valid" * 200 + '"}').encode()
    output = tmp_path / "metadata.json"
    separator.download_file_if_not_exists(serve(body, "gzip"), output)
    assert output.read_bytes() == body
    assert not output.with_suffix(".json.part").exists()
    progress = [data for kind, data in worker.test_events if kind == "download_progress"]
    assert progress[0]["total"] is None and progress[0]["eta"] is None
    assert progress[-1]["total"] == len(body)


def test_truncated_identity_never_publishes(separator, serve, tmp_path):
    output = tmp_path / "metadata.json"
    body = b'{"valid": true}'
    with pytest.raises((requests.RequestException, ValueError)):
        separator.download_file_if_not_exists(serve(body, length=len(body) + 10), output)
    assert not output.exists() and not output.with_suffix(".json.part").exists()


def test_invalid_compressed_json_never_publishes(separator, serve, tmp_path):
    output = tmp_path / "metadata.json"
    with pytest.raises(ValueError):
        separator.download_file_if_not_exists(serve(b"invalid JSON", "gzip"), output)
    assert not output.exists() and not output.with_suffix(".json.part").exists()


@pytest.mark.parametrize("bad", ["size", "sha256"])
def test_compression_preserves_publisher_integrity(separator, worker, serve, tmp_path, monkeypatch, bad):
    body = b'{"valid": true}'
    output = tmp_path / "metadata.json"
    source = {"size": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    source[bad] = len(body) + 1 if bad == "size" else "0" * 64
    monkeypatch.setitem(worker.MODEL_SOURCES, output.name, source)
    with pytest.raises(ValueError, match="incomplete|SHA256"):
        separator.download_file_if_not_exists(serve(body, "gzip"), output)
    assert not output.exists() and not output.with_suffix(".json.part").exists()


def test_onnx_selected_gpu_and_cached_device(separator, monkeypatch):
    import onnxruntime as ort
    import torch

    calls = []

    def factory(*args, **options):
        calls.append(options)
        return SimpleNamespace(
            get_providers=lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"],
            get_provider_options=lambda: {"CUDAExecutionProvider": {"device_id": "1"}},
        )

    monkeypatch.setattr(ort, "InferenceSession", factory)
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 1)
    separator.torch_device.type = "cuda"
    separator.load_model("model.onnx")
    assert calls[0]["providers"] == ["CUDAExecutionProvider"]
    assert calls[0]["provider_options"] == [{"device_id": "1"}]
    separator.load_model("model.onnx")
    assert len(calls) == 1 and separator._onnx_device == "cuda:1"
    assert ort.InferenceSession is factory


def test_onnx_cpu_fallback_is_reported_as_failure(separator, monkeypatch):
    import onnxruntime as ort
    import torch

    def factory(*args, **options):
        return SimpleNamespace(
            get_providers=lambda: ["CPUExecutionProvider"], get_provider_options=lambda: {}
        )

    monkeypatch.setattr(ort, "InferenceSession", factory)
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 0)
    separator.torch_device.type = "cuda"
    with pytest.raises(ValueError, match="selected CUDA GPU"):
        separator.load_model("model.onnx")
    assert ort.InferenceSession is factory and separator._onnx_device is None
