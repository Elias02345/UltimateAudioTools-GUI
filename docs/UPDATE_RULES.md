# Local data and update contract

Separator is a native desktop application. It does not install system services or manage a self-hosted backend.

Application data is under the platform's local application-data directory for `de.eliaskanakidis.separator`. Protected data includes `state.sqlite3` and its WAL/SHM files (settings, projects, presets and history), model cache/integrity records, and installed private runtimes. Exported audio belongs to the user at the selected output directory; original recordings are never overwritten. A custom model directory is equally protected.

Application updates replace the installation's executable, frontend and bundled CPU runtime. They do not clear application data or redownload existing weights. An incompatible older CUDA runtime is retained and the new bundled CPU runtime is selected until a compatible private GPU runtime is installed. SQLite changes must be additive and preserve old records; never drop/truncate user tables.

Cache cleanup targets only generated previews, waveforms and inactive inference work. It does not remove model files, presets, history or exports. Removing a history entry does not delete audio. Explicit comparison cleanup is separately confirmed and scoped to that comparison's generated files.

Runtime upgrades copy the baseline into app-owned staging, verify downloads, perform native device tests and atomically publish the active pointer. Failure/cancellation leaves the previous runtime selected. Abandoned staging is cleaned under an installation lock. Never share hard links between mutable runtime generations.

Keep the repository-local SSH commit-signing and Tauri update-signing private keys backed up securely; only public verification keys belong in source control. OS installer signing uses separate platform credentials.

Projects are additive metadata in the existing state database. Older generations default to unfiled. Project assignment and removal commit grouping changes atomically; removing a project never removes a generation or audio file.
