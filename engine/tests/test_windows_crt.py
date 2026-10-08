import importlib.util
import json
import urllib.request
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def installer():
    script = Path(__file__).resolve().parents[2] / "scripts/install_windows_crt.py"
    spec = importlib.util.spec_from_file_location("install_windows_crt", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_original_documents_are_verified_and_valid_docx(installer):
    documents = installer.verified_license_documents()
    assert set(documents) == set(installer.DOCUMENTS)
    for name in documents:
        with zipfile.ZipFile(installer.LICENSES / name) as document:
            assert "word/document.xml" in document.namelist()


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_missing_or_changed_document_rejects_packaging(installer, tmp_path, monkeypatch, damage):
    documents = installer.verified_license_documents()
    for name, content in documents.items():
        (tmp_path / name).write_bytes(content)
    first = tmp_path / next(iter(documents))
    if damage == "missing":
        first.unlink()
    else:
        first.write_bytes(first.read_bytes() + b"changed")
    monkeypatch.setattr(installer, "LICENSES", tmp_path)
    with pytest.raises(FileNotFoundError if damage == "missing" else ValueError):
        installer.verified_license_documents()


def test_install_preserves_exact_notices_and_provenance_offline(installer, tmp_path, monkeypatch):
    studio = tmp_path / "Visual Studio"
    crt = studio / "VC/Redist/MSVC/14.44.1/x64/Microsoft.VC143.CRT"
    crt.mkdir(parents=True)
    for name in ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"]:
        (crt / name).write_bytes(name.encode())
    installation = {
        "installationPath": str(studio),
        "productId": "Enterprise",
        "installationVersion": "17.14",
    }

    def output(command, **kwargs):
        return "14.44.1" if command[0] == "powershell" else json.dumps([installation])

    def forbidden(*args, **kwargs):
        raise AssertionError("License packaging must not make a network request")

    monkeypatch.setattr(installer.subprocess, "check_output", output)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    runtime = tmp_path / "runtime"
    installer.install(runtime)
    notices = runtime / "third-party-licenses/MicrosoftVisualCRuntime"
    manifest = json.loads((notices / "manifest.json").read_text())
    for name, (url, digest) in installer.DOCUMENTS.items():
        assert (notices / name).read_bytes() == (installer.LICENSES / name).read_bytes()
        assert manifest["documents"][name] == {"url": url, "sha256": digest}
    for name in ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"]:
        assert (runtime / name).read_bytes() == (crt / name).read_bytes()


def test_invalid_documents_fail_before_any_crt_staging(installer, tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "LICENSES", tmp_path)
    (tmp_path / next(iter(installer.DOCUMENTS))).write_bytes(b"invalid document")

    def forbidden(*args, **kwargs):
        raise AssertionError("CRT discovery must follow license validation")

    monkeypatch.setattr(installer.subprocess, "check_output", forbidden)
    runtime = tmp_path / "runtime"
    with pytest.raises(ValueError, match="checksum changed"):
        installer.install(runtime)
    assert not runtime.exists()
