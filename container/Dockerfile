FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libstdc++6 libgomp1 libcrypt1 \
    && rm -rf /var/lib/apt/lists/*
COPY runtime/ /opt/python/
COPY engine/separator_engine /opt/engine/separator_engine
ENV PATH="/opt/python/bin:${PATH}" PYTHONPATH=/opt/engine PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 HOME=/tmp
ARG BACKEND=cpu
LABEL org.separator.protocol="1" org.separator.version="0.1.0" org.separator.backend="${BACKEND}"
CMD ["python", "-u", "-m", "separator_engine.worker", "serve", "/models", "/state"]
