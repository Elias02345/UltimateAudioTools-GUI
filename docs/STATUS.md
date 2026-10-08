# Project status

## Implemented and locally verified

Native Tauri shell, real Python inference, generated/validated IPC, persistent queue/presets/settings, model catalog/downloads/integrity checks, float ensembling/exports, waveform/player, blind comparison ranges and cache management.

Linux development host: RTX 3070 8 GB. Actual CUDA float32 separation passed for Resurrection, Inst v1e+ + Becruily Instrumental Ultra, Resurrection + Big Beta6x Vocal Ultra, and four-stem `htdemucs_ft`. A 31-second CUDA test passed with 10-second contextual float chunks. Private CPU PBS 3.12.15 runtime built, relocated and passed readiness plus real CPU RoFormer inference.

Actual native-window tests passed first-run setup, native drag/drop event import, Ultra enqueue/completion, result loading and playback with advancing transport time. WebKit's asset URI limitation is handled with a token-scoped, ranged loopback preview stream. NVIDIA/Wayland renderer compatibility is handled before GTK starts.

Current automated local checks: 37 Python tests, 8 frontend contract tests, 2 Rust tests; lint/typecheck/build/clippy passed. Real Torch and ONNX CUDA operations passed. A private CUDA installation transaction, real container CPU inference/cancellation, native range comparison, moved-source playback recovery and minimum-window library search have also passed. A fresh production AppImage also passed private-runtime readiness, production CSP, real native preview playback and minimum-window checks. Test reports/screenshots are in the development-only `.test-output` folder.

## In progress

Final cross-platform package validation and publication of cryptographically verified updater/release artifacts. Actual installer testing exposed and corrected production CSP evaluation, Linux TBB dependency, incomplete local media plugins and Apple Vorbis linker issues. The production media test now exercises playback. A transient Ubuntu CI package-mirror timeout is handled by a bounded retry helper. Do not interpret an in-progress CI run as a pass.

## Platform evidence

Linux x64 CPU/CUDA is executed locally. Extracted Linux Debian/AppImage runtimes passed actual Torch/ONNX CPU operations and seven audio codec checks; real separated CPU results also played synchronously in the production AppImage. Windows x64 NSIS installation, private C++ DLL loading, runtime/codec audit and uninstall passed on a native Windows runner. Apple Silicon application/DMG packaging and private-runtime/codec checks passed on a native GitHub Actions runner. Those runs do not establish real Windows GPU or Apple MPS separation performance.

Intel macOS lacks current compatible upstream Torch wheels. DirectML conflicts with the current Torch requirement and is not offered as verified. MPS is the supported Apple provider; MLX model conversion/parity has not been demonstrated and is not marketed as available.
