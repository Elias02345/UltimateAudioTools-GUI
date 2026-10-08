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

## Successor comparison, checked 2026-10-08

Newer public checkpoints exist. The following are evaluation candidates, absent from the pinned 0.47.0 model catalogue; Separator does not present them as already integrated or tested.

| Candidate and author files | Published evidence and decision |
| --- | --- |
| [Big Beta7](https://huggingface.co/pcunwa/Mel-Band-Roformer-big/tree/main): `big_beta7.ckpt` and `.yaml` | The [Beta7 submission](https://mvsep.com/quality_checker/entry/10516) reports vocal SDR 11.1179 versus [Beta6X](https://mvsep.com/quality_checker/entry/8093) 11.1155. Different configurations and the small difference provide no compelling case to replace the tested ensemble member. |
| [HyperACE v2](https://huggingface.co/pcunwa/BS-Roformer-HyperACE/tree/main): `v2_inst/bs_roformer_inst_hyperacev2.ckpt` and `v2_voc/bs_roformer_voc_hyperacev2.ckpt`, with their config and custom implementation | [Vocal HyperACE](https://mvsep.com/quality_checker/entry/9470) reports SDR 11.3957 and bleedless 34.0758; [Resurrection](https://mvsep.com/quality_checker/entry/8683) reports 11.3363 and 39.9861. Higher SDR does not establish superior bleed suppression. [Instrumental HyperACE](https://mvsep.com/quality_checker/entry/9475) reports SDR 17.4007; ensemble improvement remains unmeasured. |
| [Leap and Leap Xe](https://huggingface.co/pcunwa/BS-Roformer-Leap/tree/main): `bs_roformer_leap_{inst,voc}.ckpt`; `Xe/bs_leap_xe_{inst,voc}.ckpt`, with matching YAML files | The [author confirms](https://huggingface.co/pcunwa/BS-Roformer-Leap/discussions/2) standard Leap entry 10146 and Xe entry 10178. Their vocal SDRs are 11.7222 and 11.7577. [Xe submission 10846](https://mvsep.com/quality_checker/entry/10846), a separate October 7 test naming the exact vocal checkpoint/config, reports 11.7920 and bleedless 38.0739. These are promising individual-model results, with no measured comparison against our actual Ultra ensemble. |

Entries 10516, 10146, 10178 and 10846 were verified through the official [Multisong leaderboard API](https://mvsep.com/api/quality_checker/leaderboard?dataset_type=1&limit=20&algo_name_filter=leap) (use `algo_name_filter=beta7` for Beta7). The entry 10178 text says overlap 2 while its tester's author-repository reply says 4; retain that reproducibility uncertainty. These submissions do not prove a universal listening-quality ranking, identical inference settings or RTX 3070 parity. The four shipped checkpoints remain individually selectable, and their compatible custom ensembles remain available.

Avoid a common attribution error: the original [Becruily instrumental submission](https://mvsep.com/quality_checker/entry/7704) reports SDR 16.4719 with explicit inference settings; 17.5466 belongs to the different [Becruily Deux model](https://mvsep.com/quality_checker/entry/9482). [Inst v1e+](https://mvsep.com/quality_checker/entry/8115) reports 16.6472. We do not assign Deux's score to the shipped original checkpoint or label untested successors as verified improvements. Default selection prioritizes the preserved, working multi-model workflows and explicit evidence over an isolated leaderboard number.

## Desktop and platforms

[Tauri 2 sidecars](https://v2.tauri.app/develop/sidecar/) require per-target binaries when using externalBin. A relocatable bundled Python directory is instead resolved through the Rust resource path and spawned directly without a shell. [Tauri asset protocol](https://v2.tauri.app/security/capabilities/) file access must be explicitly scoped to imported files and completed outputs.

Apple Silicon uses current PyTorch MPS, with capability verification and explicit device reporting. [PyTorch Intel macOS wheel deprecation](https://dev-discuss.pytorch.org/t/pytorch-macos-x86-builds-deprecation-starting-january-2024/1690) means the current engine cannot honestly be distributed on Intel macOS with modern torch; first current macOS target is arm64/macOS 14+. MLX remains an optional provider only after model/API parity is tested.

DirectML is experimental and not advertised as verified RoFormer acceleration. torch-directml's published dependency pins conflict with modern torch runtime releases; it requires a separate validated runtime. NVIDIA support is determined from actual torch.cuda availability, not GPU name alone.

## Runtime

[python-build-standalone](https://github.com/astral-sh/python-build-standalone) supplies relocatable private CPython. Runtime preparation pins dependencies, bundles FFmpeg, verifies runtime startup and emits an archive/checksum manifest. Native runtime is default; optional container execution uses private pipes and explicit bind mounts, without a network service or Docker Desktop installation.

Model weights are fetched from legitimate upstream sources after user action, never included in installers. Engine MIT licensing does not establish model redistribution permission. Unknown individual weight licenses are displayed explicitly; see THIRD_PARTY_NOTICES.md.
