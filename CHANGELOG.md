# Changelog

## 0.1.1 — Verified first release

- Fix compressed model metadata downloads while preserving publisher size, checksum and truncated-transfer checks.
- Honor the selected GPU for MDX/ONNX inference and reject silent CUDA-to-CPU provider fallback.
- Keep the first release gated on all installer and code checks; the superseded 0.1.0 tag was not published.

## 0.1.0 — Initial desktop studio

- Native Tauri interface with first-run readiness checks, drag/drop batch import, persistent queue and local result library.
- Premium Instrumental/Vocal Ultra RoFormer ensembles, individually selectable models, custom weighted presets and four-stem Demucs.
- Private CPU/MPS runtime, transactional NVIDIA acceleration installation, verified model downloads and real CUDA execution.
- Float intermediates, contextual chunking, lossless exports and original sample-rate preservation.
- Native playback with streamed previews, waveform seek, mute/solo, loop and blind range comparisons.
- Surviving stems remain playable when source audio has moved; individual model selection clears ensemble weights and keeps the selected target consistent.
- Reproducible multi-platform packaging and source/runtime validation in GitHub Actions.
- Precompiled IPC validators preserve production CSP; Linux packages also launch a real native window and play an audio preview in CI.
- Debian and AppImage updates each receive a verified, version-bound signature and the matching installer in the release feed.
- Isolated optional container processing, explicit comparison cleanup, and source-built FFmpeg with complete corresponding codec sources and bundled license notices.
