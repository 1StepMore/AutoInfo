# =============================================================================
# AutoInfo Dockerfile
# Multi-stage build: builder installs deps + Playwright browsers,
# runtime stage contains only what's needed at runtime.
#
# Build:
#   docker build -t autoinfo:latest .
#
# Run:
#   docker run --rm -it \
#     -e AUTOINFO_LLM_API_KEY="sk-..." \
#     -v /path/to/data:/app/data \
#     autoinfo:latest --help
#
#   docker run --rm -it \
#     -e AUTOINFO_LLM_API_KEY="sk-..." \
#     autoinfo:latest collect --domain medical-research
#
# Default entrypoint is `autoinfo`. Override with `--entrypoint` or append
# subcommand after image name.
# =============================================================================

# ---- Builder stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies and Playwright system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install all dependencies including optional web (Playwright) and pdf support
RUN pip install --no-cache-dir ".[web,pdf]"

# Install Playwright browsers (chromium for web scraping)
RUN python -m playwright install chromium

# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime system dependencies required by Playwright browsers
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy Playwright browser binaries
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

ENV PYTHONUNBUFFERED=1

# Default: show help
ENTRYPOINT ["autoinfo"]
CMD ["--help"]
