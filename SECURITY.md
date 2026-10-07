# Security and privacy

Report a suspected vulnerability privately to elias-kanakidis@gmx.de with reproduction steps, affected version and redacted logs. Do not publish recordings, credentials or personal paths.

Audio processing and previews are local. Network access is for explicitly selected model/runtime downloads and update checks. No telemetry is collected. Model downloads use atomic temporary files; curated defaults are checked against recorded publisher SHA256 hashes. Catalog entries without publisher hashes use locally recorded integrity baselines, which do not establish publisher authenticity. Download model checkpoints only from publishers you trust.

The native host owns child processes and a token-scoped loopback media endpoint. Only registered engine-generated previews are streamed; arbitrary paths, unexpected origins and invalid ranges are rejected. The endpoint is not a remotely hosted service.

Runtime installation uses an independent staged PBS tree, hash-verified wheel downloads and offline installation. System Python, pip configuration and drivers are not modified. Signed application updates use a separate trust key; model/runtime updates do not replace user data.

See docs/UPDATE_RULES.md for protected data and THIRD_PARTY_NOTICES.md for dependency/model licenses.
