FROM python:3.11-buster AS builder

RUN pip install poetry==1.7.1

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./

# poetry complains if README.md is not present (there are build benefits to create empty one instead of copying the real one)
RUN touch README.md

RUN poetry install --without dev --no-root && rm -rf $POETRY_CACHE_DIR

####################################################################################################

FROM python:3.11-slim as runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    CONTAINER=1 \
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
    mkdir -p /etc/sme /var/log/sme /var/run/sme && \
    chown -R sme:sme /etc/sme /var/log/sme /var/run/sme && \
    chmod 755 /var/log/sme && \
    chmod 755 /var/run/sme

# Set up the application
WORKDIR /app
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY app ./app

# Give ping capabilities to non-root user
RUN setcap cap_net_raw+ep /bin/ping && \
    # Ensure proper permissions for the sme user
    chown -R sme:sme /app && \
    # Make sure the PID directory is writable
    chmod 1777 /var/run/sme

# Switch to sme user
USER sme

# Run the monitor using poetry run
CMD ["python", "-m", "app.cli", "start", "-c", "/etc/sme/config.yaml", "-f"]
