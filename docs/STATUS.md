# Project status

## Implemented and locally verified

Native Tauri shell, real Python inference, generated/validated IPC, persistent queue/presets/settings, model catalog/downloads/integrity checks, float ensembling/exports, waveform/player, blind comparison ranges and cache management.

Linux development host: RTX 3070 8 GB. Actual CUDA float32 separation passed for Resurrection, Inst v1e+ + Becruily Instrumental Ultra, Resurrection + Big Beta6x Vocal Ultra, and four-stem `htdemucs_ft`. A 31-second CUDA test passed with 10-second contextual float chunks. Private CPU PBS 3.12.15 runtime built, relocated and passed readiness plus real CPU RoFormer inference.

Actual native-window tests passed first-run setup, native drag/drop event import, Ultra enqueue/completion, result loading and playback with advancing transport time. WebKit's asset URI limitation is handled with a token-scoped, ranged loopback preview stream. NVIDIA/Wayland renderer compatibility is handled before GTK starts.

Current automated local checks: 25 Python tests, 5 frontend contract tests, 2 Rust tests; lint/typecheck/build/clippy passed. Real Torch and ONNX CUDA operations passed. Test reports/screenshots are in the development-only `.test-output` folder.

## In progress

Complete NVIDIA runtime transaction, broader native acceptance automation, container distribution, installer smoke tests, signed updater preparation, release artifacts and final CI validation. Do not interpret an in-progress CI run as a pass.

## Platform evidence

Linux x64 CPU/CUDA is executed locally. Windows x64 and Apple Silicon packages/checks are being built in native GitHub Actions runners. Those runs do not establish real Windows GPU or Apple MPS separation performance.

Intel macOS lacks current compatible upstream Torch wheels. DirectML conflicts with the current Torch requirement and is not offered as verified. MPS is the supported Apple provider; MLX model conversion/parity has not been demonstrated and is not marketed as available.
