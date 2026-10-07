# Third-party notices

Separator application source is MIT, copyright Elias Kanakidis. Dependency licenses remain their own; shipping the application does not relicense them. Private runtime package versions are recorded in the bundled `runtime/manifest.json` and committed platform locks. Native Cargo and npm dependencies are fixed by their lockfiles.

| Component | License / source |
|---|---|
| Tauri, Wry and official plugins | MIT/Apache-2.0, https://github.com/tauri-apps/tauri |
| React | MIT, https://github.com/facebook/react |
| Lucide icons | ISC, https://github.com/lucide-icons/lucide |
| audio-separator 0.47.0 | MIT, https://github.com/nomadkaraoke/python-audio-separator/tree/v0.47.0 |
| PyTorch / torchvision | BSD-style, https://github.com/pytorch/pytorch and https://github.com/pytorch/vision |
| ONNX Runtime | MIT, https://github.com/microsoft/onnxruntime |
| CPython / PBS | Python PSF and bundled component licenses, https://github.com/astral-sh/python-build-standalone/releases/tag/20261003 |
| imageio-ffmpeg | BSD-2-Clause wrapper, https://github.com/imageio/imageio-ffmpeg |
| FFmpeg 9.0.2 | LGPL-2.1-or-later, built from verified original sources; https://ffmpeg.org/releases/ |
| LAME 3.100 | LGPL, static encoder only; the GPL decoder/frontend are excluded; https://lame.sourceforge.io/ |
| libogg 1.3.6 / libvorbis 1.3.7 | BSD-style licenses; https://xiph.org/downloads/ |
| GStreamer | LGPL component licenses, https://gstreamer.freedesktop.org/ |
| NVIDIA CUDA redistributables | NVIDIA component license terms bundled with the vendor wheels; https://docs.nvidia.com/cuda/eula/ |

The private runtime contains `python/third-party-licenses/index.json` and the original notices from installed Python distributions. `python/third-party-licenses/FFmpeg` contains full codec licenses, the actual binary hash/build configuration, and every exact original source archive with the build script in `corresponding-source.tar.gz`. The same source archive accompanies each platform release. The upstream imageio-ffmpeg vendor executable is removed before packaging. Preserve all included notices and corresponding sources when redistributing packages. This table highlights major components rather than replacing their full texts.

## Model weights

Model weights are downloaded on user request and are not bundled. The authors' repositories for Inst v1e+, Becruily instrumental, Resurrection and Big Beta6x do not currently specify an individual weight license. The application therefore reports that fact rather than treating weights as MIT. Availability through audio-separator does not confer commercial-use rights.

- https://huggingface.co/pcunwa/Mel-Band-Roformer-Inst
- https://huggingface.co/becruily/mel-band-roformer-instrumental
- https://huggingface.co/pcunwa/BS-Roformer-Resurrection
- https://huggingface.co/pcunwa/Mel-Band-Roformer-big

Consult each publisher's current terms before redistribution or commercial use.
