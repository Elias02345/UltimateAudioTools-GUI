FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587 AS codecs
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config python3 xz-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY codec-scripts/ scripts/
COPY codec-sources/ runtime/ffmpeg-sources/
COPY ffmpeg-sources.json runtime/ffmpeg-sources.json
RUN python3 scripts/fetch_ffmpeg_sources.py && bash scripts/build_ffmpeg.sh \
    && mkdir /output && python3 -c "from pathlib import Path; import sys; sys.path.insert(0,'scripts'); from install_ffmpeg import install; install(Path('/output'),'linux')"

FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libstdc++6 libgomp1 libcrypt1 libtbb12 \
    && rm -rf /var/lib/apt/lists/*
COPY runtime/ /opt/python/
COPY --from=codecs /output/ /opt/python/
COPY engine/separator_engine /opt/engine/separator_engine
RUN /opt/python/bin/python3 -I /opt/engine/separator_engine/runtime_probe.py \
    && /opt/python/separator-bin/ffmpeg -hide_banner -version
ENV PATH="/opt/python/bin:${PATH}" PYTHONPATH=/opt/engine PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 HOME=/tmp
ARG BACKEND=cpu
LABEL org.separator.protocol="1" org.separator.version="0.1.1" org.separator.backend="${BACKEND}"
CMD ["python", "-u", "-m", "separator_engine.worker", "serve", "/models", "/state"]
