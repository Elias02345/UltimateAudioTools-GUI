# Upstream research

Research date: 2026-10-07. Development host: Linux x86_64, RTX 3070 8 GiB, NVIDIA driver 615.71.09. This document records inspected sources, not unmeasured quality claims.

## Primary engine

[audio-separator 0.47.0](https://github.com/nomadkaraoke/python-audio-separator/releases/tag/v0.47.0) is the selected release. Its [Separator source](https://github.com/nomadkaraoke/python-audio-separator/blob/v0.47.0/audio_separator/separator/separator.py) exposes Separator(...), load_model(filename or list, force_reload=False), separate(path, custom_output_names=None), list_supported_model_files(), download_model_and_data(). It supports output format/bitrate, normalization, sample rate, autocast/native FP16 (mutually exclusive), chunk duration, architecture parameter dictionaries and ensemble presets/algorithms/weights.

[Upstream presets](https://github.com/nomadkaraoke/python-audio-separator/blob/v0.47.0/audio_separator/ensemble_presets.json) retain all four requested models:

| User model | Current mapping | Default use |
| --- | --- | --- |
| melband_roformer_inst_v1e_plus.ckpt | Same filename | Ultra instrumental, instrumental_full |
| mel_band_roformer_instrumental_becruily.ckpt | Same filename | Ultra instrumental, instrumental_full |
| bs_roformer_vocals_resurrection_unwa.ckpt | Same filename | Ultra vocals, vocal_balanced |
| melband_roformer_big_beta6x.ckpt | Same filename | Ultra vocals, vocal_balanced |

instrumental_full uses uvr_max_spec; vocal_balanced uses avg_fft. Other upstream presets offer different bleed/preservation tradeoffs; their existence is not proof of a universal quality improvement. No new model replaces these defaults without controlled listening evidence. Advanced selection exposes the full current catalogue and all compatible custom combinations.

RoFormer overlap is an integer count, not an MDX fractional overlap. None preserves model YAML inference settings. override_model_segment_size=False preserves trained context. Inputs shorter than ten seconds trigger an upstream segment override, so GPU acceptance fixtures must be at least 20 seconds. [Ensembler](https://github.com/nomadkaraoke/python-audio-separator/blob/v0.47.0/audio_separator/separator/ensembler.py) receives channel-by-sample arrays and implements avg_fft/uvr_max_spec and other algorithms. Only avg_wave and avg_fft use weights meaningfully. We reuse it and avoid lossy/PCM16 intermediate exports.

## Desktop and platforms

[Tauri 2 sidecars](https://v2.tauri.app/develop/sidecar/) require per-target binaries when using externalBin. A relocatable bundled Python directory is instead resolved through the Rust resource path and spawned directly without a shell. [Tauri asset protocol](https://v2.tauri.app/security/capabilities/) file access must be explicitly scoped to imported files and completed outputs.

Apple Silicon uses current PyTorch MPS, with capability verification and explicit device reporting. [PyTorch Intel macOS wheel deprecation](https://dev-discuss.pytorch.org/t/pytorch-macos-x86-builds-deprecation-starting-january-2024/1690) means the current engine cannot honestly be distributed on Intel macOS with modern torch; first current macOS target is arm64/macOS 14+. MLX remains an optional provider only after model/API parity is tested.

DirectML is experimental and not advertised as verified RoFormer acceleration. torch-directml's published dependency pins conflict with modern torch runtime releases; it requires a separate validated runtime. NVIDIA support is determined from actual torch.cuda availability, not GPU name alone.

## Runtime

[python-build-standalone](https://github.com/astral-sh/python-build-standalone) supplies relocatable private CPython. Runtime preparation pins dependencies, bundles FFmpeg, verifies runtime startup and emits an archive/checksum manifest. Native runtime is default; optional container execution uses private pipes and explicit bind mounts, without a network service or Docker Desktop installation.

Model weights are fetched from legitimate upstream sources after user action, never included in installers. Engine MIT licensing does not establish model redistribution permission. Unknown individual weight licenses are displayed explicitly; see THIRD_PARTY_NOTICES.md.
