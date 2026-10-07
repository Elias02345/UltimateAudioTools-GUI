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
| FFmpeg binary | Its build configuration governs LGPL/GPL licensing; Linux 7.0.2 static distribution is GPLv3, https://johnvansickle.com/ffmpeg/ |
| GStreamer | LGPL component licenses, https://gstreamer.freedesktop.org/ |
| NVIDIA CUDA redistributables | NVIDIA component license terms bundled with the vendor wheels; https://docs.nvidia.com/cuda/eula/ |

FFmpeg corresponding sources/build information are available from the original binary distributor and https://ffmpeg.org/releases/. Preserve the included runtime/native library license files when redistributing packages. Generate and review a complete license inventory for release artifacts; this table highlights major components rather than replacing their full texts.

## Model weights

Model weights are downloaded on user request and are not bundled. The authors' repositories for Inst v1e+, Becruily instrumental, Resurrection and Big Beta6x do not currently specify an individual weight license. The application therefore reports that fact rather than treating weights as MIT. Availability through audio-separator does not confer commercial-use rights.

- https://huggingface.co/pcunwa/Mel-Band-Roformer-Inst
- https://huggingface.co/becruily/mel-band-roformer-instrumental
- https://huggingface.co/pcunwa/BS-Roformer-Resurrection
- https://huggingface.co/pcunwa/Mel-Band-Roformer-big

Consult each publisher's current terms before redistribution or commercial use.
