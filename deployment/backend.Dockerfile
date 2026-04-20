# ROADMAP B4 — Multi-stage backend image
#
# Stage 1 (builder) compiles wheels for every Python dep against a full
# build toolchain, then `pip install --target=/install` collects the final
# site-packages tree. Stage 2 (runtime) imports only that tree plus libpq5
# and curl, so the shipped image carries neither gcc nor the -dev headers.
#
# Net effect on size: the builder image is ~600 MB; the runtime image that
# actually ships is ~150 MB. The separation also means CVEs in build tools
# never reach production.

# ---- Stage 1: builder ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Build-only deps: gcc for any wheel that needs to compile from source,
# libpq-dev so psycopg's binary-free build path has the headers it needs.
# `--no-install-recommends` keeps the builder slim; the whole stage is
# thrown away after the COPY --from=builder in stage 2.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Keep pip / setuptools / wheel current. The python:3.11-slim base image
# ships with older metadata (e.g. wheel 0.45.1, jaraco.context 5.3.0 via
# setuptools) that Trivy flags HIGH (CVE-2026-23949, CVE-2026-24049).
# Upgrading them here patches those before they can be copied into the
# runtime image.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY backend/requirements.txt ./

# --target=/install collects everything into a relocatable tree that the
# runtime stage can copy as a unit. --no-cache-dir avoids baking pip's
# wheel cache into the layer.
RUN pip install --no-cache-dir --target=/install -r requirements.txt

# ---- Stage 2: runtime ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime-only deps:
#   * libpq5 for psycopg's C shims
#   * curl so the HEALTHCHECK below doesn't need Python to be on PATH
#     (it's ~2 MB and pays for itself the first time you `docker exec`
#     into a wedged container)
#
# `apt-get upgrade -y` before installing pulls the latest security
# patches for anything the base image already ships (e.g. the Debian
# libssl3t64 / openssl fix for CVE-2026-28390 that Trivy flags HIGH).
# Without this the build would fail the Trivy gate every time Debian
# point-releases a CVE patch, even though our explicit deps are pinned
# correctly.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Same rationale as the builder stage: the base image's bundled pip /
# setuptools / wheel metadata gets picked up by Trivy's python-pkg
# scanner. Upgrading in-place clears the HIGH findings on wheel and
# jaraco.context (via setuptools).
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Import the pre-built site-packages tree from the builder. PYTHONPATH
# points Python at it without needing to touch /usr/local/lib; PATH picks
# up the console scripts (uvicorn, etc.) that pip drops into
# /install/bin when --target is used.
COPY --from=builder /install /app/site-packages
ENV PYTHONPATH=/app/site-packages \
    PATH=/app/site-packages/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy application source *after* deps so edits don't bust the dep layer.
COPY backend/ ./

# Non-root user. /app/data is the mount point for the encrypted
# credential store (see docker-compose.yml's `backend-data` volume).
RUN groupadd --system kotte \
    && useradd --system --gid kotte --home /app --shell /usr/sbin/nologin kotte \
    && mkdir -p /app/data \
    && chown -R kotte:kotte /app

USER kotte

EXPOSE 8000

# Use --fail so a 5xx response trips the healthcheck instead of exit 0.
# --silent / --show-error keeps the container logs clean on success while
# still surfacing the reason on failure.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl --fail --silent --show-error \
        http://localhost:8000/api/v1/health \
        || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
