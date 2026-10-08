"""Release selection must exclude expanded installer payloads and retain both Linux formats."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def release_tree(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/prepare_release.py"
    spec = importlib.util.spec_from_file_location("prepare_release", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = {
        "appimage": "Separator_0.1.0_amd64.AppImage",
        "deb": "Separator_0.1.0_amd64.deb",
        "nsis": "Separator_0.1.0_x64-setup.exe",
        "dmg": "Separator_0.1.0_aarch64.dmg",
        "macos": "Separator.app.tar.gz",
    }
    for folder, name in names.items():
        path = tmp_path / "bundles" / folder / name
        path.parent.mkdir(parents=True)
        path.write_bytes(b"selection fixture")
        if folder != "dmg":
            path.with_name(name + ".sig").write_text("signature selection fixture")
    for target in ["linux", "windows", "macos"]:
        (tmp_path / f"FFmpeg-corresponding-source-{target}.tar.gz").write_bytes(b"source selection fixture")
    return module.release_assets, tmp_path


def test_release_selection_excludes_expanded_payloads(release_tree):
    select, root = release_tree
    for folder in ["deb/data", "appimage/Separator.AppDir"]:
        payload = root / "bundles" / folder / "runtime"
        payload.mkdir(parents=True)
        for name in [
            "corresponding-source.tar.gz",
            "store.tar.gz",
            "pip.exe",
            "Separator_0.1.0_x64-setup.exe",
        ]:
            (payload / name).write_bytes(b"not a release asset")
    assets = select(root, "v0.1.0")
    assert len(assets) == 12
    assert "Separator_0.1.0_amd64.deb.sig" in assets
    assert "Separator_0.1.0_amd64.AppImage.sig" in assets
    assert not {"pip.exe", "corresponding-source.tar.gz", "store.tar.gz"}.intersection(assets)


def test_release_selection_rejects_duplicates(release_tree):
    select, root = release_tree
    duplicate = root / "another" / "deb" / "Separator_0.1.0_amd64.deb"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_bytes(b"duplicate")
    with pytest.raises(ValueError, match="Duplicate"):
        select(root, "v0.1.0")


def test_release_selection_requires_all_platforms_and_sources(release_tree):
    select, root = release_tree
    (root / "FFmpeg-corresponding-source-windows.tar.gz").unlink()
    with pytest.raises(ValueError, match="Every platform"):
        select(root, "v0.1.0")


def test_release_selection_rejects_version_mismatch(release_tree):
    select, root = release_tree
    with pytest.raises(ValueError, match="exactly one"):
        select(root, "v0.2.0")
