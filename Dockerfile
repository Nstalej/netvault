# ============================================
# NetVault - Network Monitor & Auditor
# ============================================
FROM python:3.11-slim-bookworm

LABEL maintainer="NetVault Contributors"
LABEL description="Open source network monitoring & auditing platform"
LABEL version="0.1.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV NETVAULT_ENV=production

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    iputils-ping \
    net-tools \
    snmp \
    snmp-mibs-downloader \
    openssh-client \
    traceroute \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories for runtime data
RUN mkdir -p /app/data /app/logs

# Ports
EXPOSE 8080 8443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Entry point
CMD ["python", "-m", "core.main"]