# Build and validate

Use Node 24, Rust stable (1.90+), Python 3.12 and uv 0.12.23. Linux needs GTK 3, WebKitGTK 4.1, librsvg, patchelf and GStreamer base/good/bad/libav/pulseaudio packages. AppImage builds must include the complete Good plugin set, including the autodetect audio sink and PulseAudio backend. Windows needs the MSVC build tools and WebView2; macOS builds target Apple Silicon 14+.

```sh
npm ci
uv venv --python 3.12
uv pip install --python .venv/bin/python -c runtime/constraints.txt '.[cpu,dev]'
npm run dev
```

On Windows use `.venv\Scripts\python.exe`. For development CUDA, install matching Torch 2.14.1 and torchvision 0.29.1 from the official cu130 index, plus onnxruntime-gpu 1.30.0. Do not coinstall the CPU and GPU ONNX Runtime distributions.

## Complete installer

```sh
python scripts/fetch_ffmpeg_sources.py
bash scripts/build_ffmpeg.sh
python scripts/build_runtime.py --target linux
python scripts/build_dependency_notices.py
npm run package -- --bundles deb,appimage --ci
```

Choose `windows`/`macos` and `nsis`/`app,dmg` on their native build machines. FFmpeg compilation needs a C compiler, make, tar, xz and pkg-config. Windows uses MSYS2 UCRT64 with GCC/pkgconf and runs the FFmpeg script in that shell; application compilation still uses MSVC. macOS uses Xcode command-line tools and pkg-config. The builder verifies the pinned PBS archive and hash-locked dependencies, tests the private runtime, relocates it and checks imports again. It never installs into global Python. The package command includes the runtime resource overlay. Dependencies that require compilation are built on the build machine, never on the user's first launch. Run `python scripts/check_packages.py --target linux` (or the matching platform) to probe the installed runtime and exercise its actual audio encoders/decoders.

Set `TAURI_SIGNING_PRIVATE_KEY` and its optional password for signed updater artifacts. Local/fork builds without this key produce installers without update artifacts; tagged publication requires the key. OS signing/notarization credentials belong in CI secrets; never commit them. Preserve signing keys for future releases.

The Desktop packages workflow runs on signed release tags or manual workflow dispatch. Normal development branches run the cross-platform code checks; dispatch the package workflow when an installer change needs native package verification before release.

## Checks

Windows packaging also requires a licensed Visual Studio 2022 Enterprise or Professional installation containing its x64 C++ redistributables. The builder copies one complete unmodified CRT set beside private Python, preserves Microsoft's original license documents and records DLL hashes/product versions. Both staging and installed-package probes assert that Torch loads those private DLLs, so the runner's system-wide runtime cannot mask an incomplete installer.

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

Native UI testing uses `tauri-driver` and WebKitWebDriver on Linux, or the supported Windows WebDriver. `scripts/native_ui.py` contains the actual-window harness. Start Vite, build the debug application, and create a tauri-driver session with its executable; save the returned session JSON to `.test-output/webdriver-session.json`. Run `npm run test:e2e` for preset persistence, cancellation/retry and real result playback; run the development Python with `scripts/native_comparison.py` for an actual ranged custom-ensemble comparison and safe cleanup. These tests require cached models, a real audio output backend and available CUDA or CPU; they execute inference. Linux AppImages bundle the media framework. [Verified results](docs/STATUS.md).

After building an AppImage, run `python scripts/smoke_packaged_window.py --application apps/desktop/src-tauri/target/release/bundle/appimage/Separator_0.1.6_amd64.AppImage`. This launches a fresh native production window, tests its private runtime and CSP, plays a real preview through the packaged media framework, and checks the minimum window size. CI uses an isolated virtual PulseAudio sink. The smoke test downloads the Fast MDX model, performs genuine CPU separation, and exercises result editing/export plus projects, individual stem playback, batch exports, support and signed-update checks. `scripts/install_linux_ci_dependencies.sh` is restricted to disposable CI runners and retries transient package-mirror failures.

Tagged releases verify every updater artifact's signature and signed version before publication. The update feed has separate Debian and AppImage targets, and only the explicitly named installers, update archives, signature sidecars and corresponding FFmpeg sources are published.
