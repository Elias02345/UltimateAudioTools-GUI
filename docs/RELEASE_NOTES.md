# Separator 0.1.5

Native audio separation for Windows x64, Linux x64 and Apple Silicon macOS 14+.

This update improves the result workflow: direct Library actions, persistent non-destructive trim/level edits, selected-stem exports with format and destination choices, collision-safe filenames, and in-app playback of exported files. Separation quality and Ultra model defaults are unchanged.

- Instrumental Ultra: Inst v1e+ and Becruily using upstream max-spec ensembling.
- Vocal Ultra: Resurrection and Big Beta6x using upstream FFT averaging.
- Select individual models or create weighted custom ensembles with advanced inference controls.
- Persistent jobs/presets, cancellation/retry, lossless exports, synchronized playback and blind range comparisons.
- Private CPU/MPS runtime and optional verified NVIDIA CUDA installation; no system Python changes.
- Source-built FFmpeg, original third-party notices and exact corresponding codec sources included.

Choose the `.exe` installer on Windows, `.AppImage` or `.deb` on Linux, and `.dmg` on Apple Silicon. `.app.tar.gz` and `.sig` files serve the signed in-app updater. SHA256SUMS covers every published installer/update/source asset.

The RTX 3070 8 GB development system executed both Ultra ensembles in float32, individual RoFormer and Demucs models, native playback/comparison and cancellation, and isolated CPU-container processing. These synthetic execution fixtures do not establish a universal perceptual model ranking. Native CI builds and checks each installed private runtime and its audio codecs; Windows CUDA and Apple MPS inference still require matching hardware validation.

Updater signatures are verified against the committed public key. Apple Developer ID/notarization and Windows Authenticode certificates were not supplied for this release; the installers do not claim these OS signatures. Model weights download on request and retain their authors' licensing terms.
