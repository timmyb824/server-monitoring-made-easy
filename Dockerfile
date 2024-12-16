FROM python:3.11-slim

ENV CONTAINER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Create sme user and directories
RUN useradd -r -s /bin/false sme && \
    mkdir -p /home/sme/logs /home/sme/run && \
    chown -R sme:sme /home/sme && \
    chmod -R 755 /home/sme

# Set up the application
WORKDIR /app
COPY requirements.txt .
RUN python -m venv .venv && \
    .venv/bin/pip install -r requirements.txt

ENV PATH="/app/.venv/bin:$PATH"

COPY app ./app

# Give ping capabilities to non-root user
RUN setcap cap_net_raw+ep /bin/ping && \
    # Ensure proper permissions for the sme user
    chown -R sme:sme /app && \
    # Make sure the run directory is writable
    chmod -R 777 /home/sme/run

# Switch to sme user
USER sme

# Run the monitor using the config from the mounted volume
CMD ["python", "-m", "app.cli", "start", "-c", "/home/sme/config.yaml", "-f"]
