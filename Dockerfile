FROM python:3.11-slim

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
COPY . .

RUN touch README.md

# Install poetry and dependencies
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev && \
    poetry install

# Give ping capabilities to non-root user
RUN setcap cap_net_raw+ep /bin/ping

# Set container environment variable
ENV CONTAINER=1

# Switch to sme user
USER sme

# Run the monitor using poetry run
CMD ["poetry", "run", "sme", "start", "-c", "/etc/sme/config.yaml", "-f"]