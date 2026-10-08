#!/usr/bin/env bash
# Build-only packages on disposable CI runners; never run this on an end-user machine.
set -Eeuo pipefail
[[ "${CI:-}" == true ]] || { echo 'This helper is restricted to CI runners.' >&2; exit 1; }

run_apt() {
  local limit=600 attempt
  [[ "$1" == update ]] && limit=120
  for attempt in 1 2 3; do
    if sudo timeout "$limit" apt-get -o DPkg::Lock::Timeout=60 \
      -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 "$@"; then return 0; fi
    echo "[WARN] apt-get $1 failed on attempt ${attempt}; retrying the preserved download cache." >&2
    [[ "$attempt" == 3 ]] || sleep 5
  done
  return 1
}

run_apt update
run_apt install -y libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev patchelf "$@"
