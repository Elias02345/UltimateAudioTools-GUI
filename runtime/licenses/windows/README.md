# Original Microsoft license documents

These unmodified originals accompany the licensed Visual Studio 2022 x64 CRT files in Windows packages. Their publisher URLs and pinned SHA-256 hashes are recorded in `scripts/install_windows_crt.py` and included in each emitted notice manifest.

The installer validates both documents before copying DLLs. Keeping the exact originals here avoids depending on the publisher's document server during every build. A missing or changed document fails packaging; license verification is never skipped.
