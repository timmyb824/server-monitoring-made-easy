FROM python:3.11-slim

ENV CONTAINER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    POETRY_VERSION=1.8.5 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    LOGLEVEL=debug

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==$POETRY_VERSION"

# Create sme user and directories
RUN useradd -r -s /bin/false sme && \
    mkdir -p /home/sme/logs /home/sme/run && \
    chown -R sme:sme /home/sme && \
    chmod -R 755 /home/sme

# Set up the application
WORKDIR /app

# Copy only dependencies first
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --without dev

# Copy application code and Alembic files
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

# Give ping capabilities to non-root user
RUN setcap cap_net_raw+ep /bin/ping && \
    chown -R sme:sme /app

USER sme

CMD ["python", "-m", "app.cli", "start", "--foreground", "--config", "/home/sme/config.yaml"]
