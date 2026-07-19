# ── Aego Cyber Cafe Server ─────────────────────────────────
# Lightweight container for Raspberry Pi 5 (ARM64)
# Multi-stage build to minimize image size

# ── Stage 1: Build ─────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ───────────────────────────────────────
FROM python:3.11-slim

# Labels
LABEL maintainer="Aego Cyber Cafe <aego@nyatike.co.ke>"
LABEL description="Aego Cyber Cafe API Server — Nyatike, Migori County"

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Create app directories
RUN mkdir -p /opt/aego/data /opt/aego/output /opt/aego/logs

# Create non-root user
RUN groupadd -r aego && useradd -r -g aego -d /opt/aego aego && \
    chown -R aego:aego /opt/aego

# Set working directory
WORKDIR /opt/aego

# Copy server code
COPY --chown=aego:aego engineering/server/ /opt/aego/server/

# Copy skills (needed by routes that import from them)
COPY --chown=aego:aego engineering/skills/ /opt/aego/skills/

# Copy kiosk UI
COPY --chown=aego:aego engineering/kiosk/kiosk/public/ /opt/aego/kiosk/

# Copy voice pipeline modules
COPY --chown=aego:aego engineering/voice/ /opt/aego/voice/

# Copy voice config (adjust paths in production)
COPY --chown=aego:aego engineering/voice/config.yaml /opt/aego/voice/config.yaml

# Environment variables (defaults — override in production)
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATA_DIR=/opt/aego/data
ENV OUTPUT_DIR=/opt/aego/output
ENV SKILLS_DIR=/opt/aego/skills
ENV KIOSK_DIR=/opt/aego/kiosk
ENV VOICE_CONFIG=/opt/aego/voice/config.yaml
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Switch to non-root user
USER aego

# Run server
CMD ["python", "-m", "uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info", \
     "--app-dir", "/opt/aego/server"]
