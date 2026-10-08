# Project status

## Implemented and locally verified

Native Tauri shell, real Python inference, generated/validated IPC, persistent queue/presets/settings, model catalog/downloads/integrity checks, float ensembling/exports, waveform/player, blind comparison ranges and cache management.

Linux development host: RTX 3070 8 GB. Actual CUDA float32 separation passed for Resurrection, Inst v1e+ + Becruily Instrumental Ultra, Resurrection + Big Beta6x Vocal Ultra, and four-stem `htdemucs_ft`. A 31-second CUDA test passed with 10-second contextual float chunks. Private CPU PBS 3.12.15 runtime built, relocated and passed readiness plus real CPU RoFormer inference.

Actual native-window tests passed first-run setup, native drag/drop event import, Ultra enqueue/completion, result loading and playback with advancing transport time. WebKit's asset URI limitation is handled with a token-scoped, ranged loopback preview stream. NVIDIA/Wayland renderer compatibility is handled before GTK starts.

Current automated local checks: 51 Python tests, 8 frontend contract tests, 2 Rust tests; lint/typecheck/build/clippy passed. Real Torch and ONNX CUDA operations passed. A private CUDA installation transaction, real container CPU inference/cancellation, native range comparison, moved-source playback recovery and minimum-window library search have also passed. A fresh production AppImage also passed private-runtime readiness, production CSP, real native preview playback and minimum-window checks. Test reports/screenshots are in the development-only `.test-output` folder.

The default Fast MDX model also passed real 20-second CUDA inference and unprivileged CPU-container inference. A fresh 0.1.1 private CUDA installation from the packaged CPU runtime passed actual Torch/ONNX GPU operations and preserved 85 dependency license notices. Compressed metadata downloads now distinguish decoded file sizes from HTTP transfer sizes; truncated transfers and publisher integrity failures remain rejected. MDX verifies the requested ONNX provider and GPU index instead of accepting a silent CPU fallback.

## Release verification

All three [native package jobs](https://github.com/Elias02345/UltimateAudioTools-GUI/actions/runs/37708177809) and the [complete code checks](https://github.com/Elias02345/UltimateAudioTools-GUI/actions/runs/37708177569) passed. The Linux CI test plays an actual preview in a fresh production window. Windows readiness cleanup now closes its SQLite database explicitly, and installer/uninstaller checks leave no private runtime installed on the runner.

An independent release preparation using real CI artifacts verified all four updater signatures and their signed versions, the separate Debian/AppImage feed entries, and exact installer/source selection. Tagged publication repeats validation and refuses publication when any platform, signature or version check fails. Package builds run on release tags or explicit workflow dispatch. Actual installer testing corrected production CSP evaluation, Linux TBB/media dependencies and Apple Vorbis linking; bounded retries handle transient Ubuntu mirror failures.

## Platform evidence

Linux x64 CPU/CUDA is executed locally. Extracted Linux Debian/AppImage runtimes passed actual Torch/ONNX CPU operations and seven audio codec checks; real separated CPU results also played synchronously in the production AppImage. Windows x64 NSIS installation, private C++ DLL loading, runtime/codec audit and uninstall passed on a native Windows runner. Apple Silicon application/DMG packaging and private-runtime/codec checks passed on a native GitHub Actions runner. Those runs do not establish real Windows GPU or Apple MPS separation performance.

Intel macOS lacks current compatible upstream Torch wheels. DirectML conflicts with the current Torch requirement and is not offered as verified. MPS is the supported Apple provider; MLX model conversion/parity has not been demonstrated and is not marketed as available.

The native WebDriver harness invokes IPC once and polls a stored Promise through synchronous script reads. Three fresh production-window repetitions passed after a CI async transport reset; failed tests preserve driver/process, desktop-log and window diagnostics. Release publication still requires all package and validation jobs.
