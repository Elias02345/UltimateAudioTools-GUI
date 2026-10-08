# Project status

## Implemented and locally verified

Native Tauri shell, real Python inference, generated/validated IPC, persistent queue/presets/settings, model catalog/downloads/integrity checks, float ensembling/exports, waveform/player, blind comparison ranges and cache management.

Linux development host: RTX 3070 8 GB. Actual CUDA float32 separation passed for Resurrection, Inst v1e+ + Becruily Instrumental Ultra, Resurrection + Big Beta6x Vocal Ultra, and four-stem `htdemucs_ft`. A 31-second CUDA test passed with 10-second contextual float chunks. Private CPU PBS 3.12.15 runtime built, relocated and passed readiness plus real CPU RoFormer inference.

Actual native-window tests passed first-run setup, native drag/drop event import, Ultra enqueue/completion, result loading and playback with advancing transport time. WebKit's asset URI limitation is handled with a token-scoped, ranged loopback preview stream. NVIDIA/Wayland renderer compatibility is handled before GTK starts.

Current automated local checks: 76 Python tests, 19 frontend tests, 2 Rust tests; lint/typecheck/build/clippy passed. Real Torch and ONNX CUDA operations passed. A private CUDA installation transaction, real container CPU inference/cancellation, native range comparison, moved-source playback recovery and minimum-window library search have also passed. A fresh production AppImage also passed private-runtime readiness, production CSP, real native preview playback and minimum-window checks. Test reports/screenshots are in the development-only `.test-output` folder.

The default Fast MDX model also passed real 20-second CUDA inference and unprivileged CPU-container inference. A fresh 0.1.1 private CUDA installation from the packaged CPU runtime passed actual Torch/ONNX GPU operations and preserved 85 dependency license notices. Compressed metadata downloads now distinguish decoded file sizes from HTTP transfer sizes; truncated transfers and publisher integrity failures remain rejected. MDX verifies the requested ONNX provider and GPU index instead of accepting a silent CPU fallback.

## Release verification

All three [native package jobs](https://github.com/Elias02345/UltimateAudioTools-GUI/actions/runs/37708177809) and the [complete code checks](https://github.com/Elias02345/UltimateAudioTools-GUI/actions/runs/37708177569) passed. The Linux CI test plays an actual preview in a fresh production window. Windows readiness cleanup now closes its SQLite database explicitly, and installer/uninstaller checks leave no private runtime installed on the runner.

An independent release preparation using real CI artifacts verified all four updater signatures and their signed versions, the separate Debian/AppImage feed entries, and exact installer/source selection. Tagged publication repeats validation and refuses publication when any platform, signature or version check fails. Package builds run on release tags or explicit workflow dispatch. Actual installer testing corrected production CSP evaluation, Linux TBB/media dependencies and Apple Vorbis linking; bounded retries handle transient Ubuntu mirror failures.

## Platform evidence

Linux x64 CPU/CUDA is executed locally. Extracted Linux Debian/AppImage runtimes passed actual Torch/ONNX CPU operations and seven audio codec checks; real separated CPU results also played synchronously in the production AppImage. Windows x64 NSIS installation, private C++ DLL loading, runtime/codec audit and uninstall passed on a native Windows runner. Apple Silicon application/DMG packaging and private-runtime/codec checks passed on a native GitHub Actions runner. Those runs do not establish real Windows GPU or Apple MPS separation performance.

Intel macOS lacks current compatible upstream Torch wheels. DirectML conflicts with the current Torch requirement and is not offered as verified. MPS is the supported Apple provider; MLX model conversion/parity has not been demonstrated and is not marketed as available.

The native WebDriver harness invokes IPC once and polls a stored Promise through synchronous script reads. Three fresh production-window repetitions passed after a CI async transport reset; failed tests preserve driver/process, desktop-log and window diagnostics. Release publication still requires all package and validation jobs.

## Result workflow (0.1.5)

Real native-window tests passed single- and multi-stem selected exports, sample-accurate FLAC trim/gain parity, exported-file playback, exact original copies, repeated unique names, incomplete range validation, edit persistence and return-to-search. Actual CUDA Ultra/Fast comparison playback confirmed that individual saved levels do not leak into blind comparisons. Light/dark and 900 × 640 views passed without horizontal overflow. Fifteen export tests cover real codecs, source preservation, unsupported-hard-link fallback and partial-file cleanup.

The 0.1.3 publication was canceled when testing the shipped FFmpeg revealed a missing volume filter. The build now includes it, and every installer audit checks actual sample-accurate WAV/FLAC trim and gain using that package's private executable.

A host NVIDIA 615.71.09 display-driver hang temporarily blocked an additional isolated CUDA installation check. That check subsequently completed: actual Torch/ONNX CUDA operations passed and 85 dependency license notices were preserved. The existing 0.1.2 profile remains intact. No drivers or system services were modified and no automatic restart was performed.

The Linux production-window check now performs real Fast CPU inference on a six-second generated recording, then tests the full result export workflow, including overlapping-playback prevention and dialog keyboard behavior.


## Projects, support and updates (0.1.8)

A real native development window passed project creation, new/existing generation assignment, persistence, rename, archive/restore and safe removal. Two genuine CPU separations produced stems used for audible single-stem playback, muted-stem recovery, switching, all-stem playback and exact multi-result batch export. Original recording/stem hashes remained identical. Support addresses/contributor attribution, the real native signed-update checker and 900 × 640 layout checks passed. Native CI repeats these workflows against the actual packaged application. Frontend tests cover updater progress, offline errors, installation safety, resource cleanup, donation links and address copying; backend tests cover legacy state, atomic project changes and scoped history cleanup.

Creator/support messages use only Elias’s first name and his first-person voice, documented in `PRODUCT.md`. The 0.1.6 release candidate was canceled before publication. Windows packaging previously received HTTP 403 for an original Microsoft license document; both exact checksum-verified originals are now retained in the repository and verified before CRT staging.

The 0.1.7 Linux release gate encountered two WebDriver forwarding connection resets, first while polling IPC and then reading a trim field. The harness now uses tauri-driver only to launch/map capabilities and sends subsequent requests to WebKitWebDriver with the unchanged session ID. Complete local result/project workflows passed through this direct connection, including a new real CPU separation and unchanged original-file hashes. No mutating request is retried and no assertion is skipped. Packaged validation remains required before publication.
