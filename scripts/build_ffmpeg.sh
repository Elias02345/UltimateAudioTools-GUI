#!/usr/bin/env bash
# Build FFmpeg plus its exact audio codec sources; all output stays in this repository.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
FF_BUILD_DIR="${PROJECT_DIR}/runtime/build/ffmpeg"
FF_PREFIX="${FF_BUILD_DIR}/prefix"
FF_JOBS="${FFMPEG_BUILD_JOBS:-4}"
FF_PLATFORM="$(uname -s)"
if [[ "${FF_PLATFORM}" == Darwin ]]; then
  export MACOSX_DEPLOYMENT_TARGET=14.0
  export CFLAGS="-O2 -mmacosx-version-min=14.0"
fi
case "${FF_PLATFORM}" in MINGW*|MSYS*) export CC=gcc CXX=g++;; esac
mkdir -p "${FF_BUILD_DIR}/src" "${FF_PREFIX}"
"${CC:-cc}" --version > "${FF_BUILD_DIR}/compiler.txt"
trap 'for logfile in configure.log build.log install.log; do if [[ -f "${logfile}" ]]; then tail -n 60 "${logfile}" >&2; fi; done' ERR
for archive in "${PROJECT_DIR}"/runtime/ffmpeg-sources/*.tar.*; do
  tar -xf "${archive}" -C "${FF_BUILD_DIR}/src"
done
export PKG_CONFIG_PATH="${FF_PREFIX}/lib/pkgconfig"
export CPPFLAGS="-I${FF_PREFIX}/include"
export LDFLAGS="-L${FF_PREFIX}/lib"
for component in libogg-1.3.6 lame-3.100 libvorbis-1.3.7; do
  mkdir -p "${FF_BUILD_DIR}/${component}"
  cd "${FF_BUILD_DIR}/${component}"
  args=("--prefix=${FF_PREFIX}" --disable-shared --enable-static)
  case "${FF_PLATFORM}" in MINGW*|MSYS*) args+=(--host=x86_64-w64-mingw32);; esac
  if [[ "${component}" == lame-* ]]; then args+=(--disable-decoder --disable-frontend); fi
  component_config="${FF_BUILD_DIR}/src/${component}/configure"
  if [[ "${FF_PLATFORM}" == Darwin && "${component}" == libvorbis-* ]]; then
    # Vorbis 1.3.7 adds an obsolete PowerPC flag rejected by current Apple linkers.
    sed 's/ -force_cpusubtype_ALL//g' "${component_config}" > "${component_config}-separator"
    component_config="${component_config}-separator"
  fi
  bash "${component_config}" "${args[@]}" > configure.log 2>&1
  make -j "${FF_JOBS}" > build.log 2>&1
  make install > install.log 2>&1
done
mkdir -p "${FF_BUILD_DIR}/ffmpeg"
cd "${FF_BUILD_DIR}/ffmpeg"
args=("--prefix=${FF_PREFIX}" --disable-shared --enable-static --disable-doc --disable-debug
  --disable-autodetect --disable-gpl --disable-version3 --disable-nonfree
  --disable-network --disable-x86asm --disable-ffplay --disable-ffprobe
  --disable-indevs --disable-outdevs --disable-avdevice --disable-filters
  --enable-filter=aresample,aformat,anull,atrim,asetpts,abuffer,abuffersink,volume
  --enable-libmp3lame --enable-libvorbis --pkg-config-flags=--static
  "--extra-cflags=-I${FF_PREFIX}/include" "--extra-ldflags=-L${FF_PREFIX}/lib")
case "${FF_PLATFORM}" in MINGW*|MSYS*) args+=(--target-os=mingw32 --arch=x86_64 --cc=gcc --cxx=g++ "--extra-ldflags=-L${FF_PREFIX}/lib -static -static-libgcc");; esac
"${FF_BUILD_DIR}/src/ffmpeg-9.0.2/configure" "${args[@]}" > configure.log 2>&1
make -j "${FF_JOBS}" > build.log 2>&1
make install > install.log 2>&1
"${FF_PREFIX}/bin/ffmpeg" -L > "${FF_BUILD_DIR}/LICENSE.txt" 2>&1
"${FF_PREFIX}/bin/ffmpeg" -buildconf > "${FF_BUILD_DIR}/build-configuration.txt" 2>&1
printf 'Verified-source FFmpeg ready: %s\n' "${FF_PREFIX}/bin/ffmpeg"
