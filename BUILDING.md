# Build and validate

Use Node 24, Rust stable (1.90+), Python 3.12 and uv 0.12.23. Linux needs GTK 3, WebKitGTK 4.1, librsvg, patchelf and GStreamer base/good/bad/libav packages. Windows needs the MSVC build tools and WebView2; macOS builds target Apple Silicon 14+.

```sh
npm ci
uv venv --python 3.12
uv pip install --python .venv/bin/python -c runtime/constraints.txt '.[cpu,dev]'
npm run dev
```

On Windows use `.venv\Scripts\python.exe`. For development CUDA, install matching Torch 2.14.1 and torchvision 0.29.1 from the official cu130 index, plus onnxruntime-gpu 1.30.0. Do not coinstall the CPU and GPU ONNX Runtime distributions.

## Complete installer

```sh
python scripts/build_runtime.py --target linux
npm run package -- --bundles deb,appimage --ci
```

Choose `windows`/`macos` and `nsis`/`dmg` on their native build machines. The builder verifies the pinned PBS archive and hash-locked dependencies, tests the private runtime, relocates it and checks imports again. It never installs into global Python. The package command includes the runtime resource overlay. Dependencies that require compilation are built on the build machine, never on the user's first launch.

Set `TAURI_SIGNING_PRIVATE_KEY` and its optional password for signed updater artifacts. OS signing/notarization credentials belong in CI secrets; never commit them. Preserve signing keys for future releases.

## Checks

```sh
npm run lint
npm run typecheck
npm test
npm run build
.venv/bin/ruff check engine scripts
.venv/bin/pytest -q
cargo fmt --manifest-path apps/desktop/src-tauri/Cargo.toml --check
cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
```

Regenerate the shared contract with `PYTHONPATH=engine .venv/bin/python scripts/generate_schema.py` and `node scripts/generate_types.mjs`. Commit schema and TypeScript output together.

## Real inference

```sh
PYTHONPATH=engine .venv/bin/python scripts/smoke_separation.py --preset instrumental_full --device cuda
PYTHONPATH=engine .venv/bin/python scripts/smoke_separation.py --preset vocal_balanced --device cuda
PYTHONPATH=engine .venv/bin/python scripts/smoke_separation.py --model htdemucs_ft.yaml --task '4 Stems' --device cuda
PYTHONPATH=engine .venv/bin/python scripts/smoke_separation.py --duration 31 --chunk 10 --device cuda
PYTHONPATH=engine .venv/bin/python scripts/smoke_runtime_upgrade.py
```

These checks intentionally download real weights or CUDA wheels and write only application/test-owned outputs. They assert actual device selection, finite samples, channel count, duration and real files. A synthetic fixture is a reproducible execution check, not a music-quality benchmark.

Native UI testing uses `tauri-driver` and WebKitWebDriver on Linux, or the supported Windows WebDriver. `scripts/native_ui.py` contains the actual-window harness. The test environment must supply audio output plugins; Linux AppImages bundle the media framework. [Verified results](docs/STATUS.md).
