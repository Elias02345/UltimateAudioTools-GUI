# Architecture

Separator is a native Tauri 2 desktop application. React and TypeScript render inside the system webview. Rust owns native dialogs, process lifecycle, approved file access and application paths. A bundled private Python runtime hosts the separation engine; users do not install Python or Node.

```mermaid
flowchart LR
  UI[React desktop UI] -->|Tauri commands| Rust[Rust process supervisor]
  Rust -->|versioned NDJSON over pipes| Engine[Python queue and state]
  Engine -->|private subprocess pipes| Worker[Reusable inference worker]
  Worker --> Separator[python-audio-separator]
  Separator --> Hardware[CUDA / MPS / CPU]
```

Engine requests use pipes and require no listening service. Each request has an id, protocol version, method and validated parameters. Responses carry a result or actionable error. Events are typed separately. ML stdout is redirected away from protocol pipes. Rust survives worker failures and fails outstanding requests when its engine exits. For native audio playback, Rust starts an ephemeral loopback-only HTTP range server with an unpredictable per-process token and an explicit file registry. It streams only approved previews into the webview; it accepts no engine commands and is never exposed to the network.

The queue is serialized, persisted in SQLite and recovers interrupted jobs after a crash. A persistent inference worker reuses a loaded single model when compatible. Changing models unloads the previous instance. Cancellation terminates the inference worker and its child process group, preserving the UI and queue. Temporary outputs are kept in a job-owned directory and only complete, validated audio is published.

Ensembles use upstream Ensembler DSP with FLOAT WAV intermediates. Ultra instrumental uses upstream instrumental_full; Ultra vocals uses vocal_balanced. No automatic fallback changes the chosen model or context length. Explicit device and precision changes are recorded in job details. Cache integrity and output filename safety are validated before publication.

Application data is stored outside the installation directory. Settings, history, user presets and downloaded models survive application upgrades. Output removal from history never deletes audio. Desktop/runtime/IPC versions are independent.
