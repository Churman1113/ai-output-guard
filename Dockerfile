FROM python:3.11-slim

LABEL org.opencontainers.image.title="AgentGuard API Proxy"
LABEL org.opencontainers.image.description="Zero-intrusion safety proxy for LLM API calls"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install system dependencies for potential ML extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install package
COPY . .
RUN pip install --no-cache-dir -e ".[proxy]" && \
    rm -rf /root/.cache/pip

# Default environment
ENV AGENTGUARD_HOST=0.0.0.0
ENV AGENTGUARD_PORT=8080

# Policy volume
VOLUME ["/policies"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

ENTRYPOINT ["agentguard-proxy"]
