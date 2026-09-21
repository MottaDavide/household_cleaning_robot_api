# Cleaning Robot API
#
#   docker build -t cleaning-robot .
#   docker run --rm -p 8000:8000 cleaning-robot
#
# Two stages: the builder resolves dependencies from uv.lock, the runtime gets
# only the resulting virtualenv and the source. uv itself, the build cache and
# the dev dependencies never reach the shipped image.

# ---------------------------------------------------------------- builder ---
FROM python:3.12-slim-bookworm AS builder

# uv is pinned by digest-bearing tag rather than installed, so the dependency
# resolver is the same byte-for-byte on every machine that builds this.
COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Only the dependency manifests, so this layer is reused on every build that
# does not change them -- editing src/ must not re-resolve the environment.
COPY pyproject.toml uv.lock ./

# --frozen             fail if uv.lock disagrees with pyproject.toml, never
#                      silently resolve something the lockfile did not pin
# --no-dev             pytest, ruff and friends stay out of the image
# --no-install-project the app is imported from src/ as a namespace package and
#                      has no build backend, so there is nothing to install
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


# ---------------------------------------------------------------- runtime ---
FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Nothing here needs root, so nothing here runs as root.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv ./.venv
COPY --chown=appuser:appuser src ./src

USER appuser

EXPOSE 8000

# No curl in a slim image, and adding one for a health probe is not worth the
# attack surface -- the interpreter is already here.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request as r; r.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

# 0.0.0.0, not 127.0.0.1: the port has to be reachable from outside the
# container for `-p 8000:8000` to mean anything.
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
