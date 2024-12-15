# Server Monitoring Made Easy (SME)

A lightweight, easy-to-configure server monitoring tool that focuses on the metrics that matter most.

## Features

- Monitor critical server metrics:
  - CPU usage
  - Memory consumption
  - Disk space
  - Network latency (ping)
  - Server uptime
- Simple YAML configuration
- Flexible alerting with customizable thresholds
- Multi-channel notifications via Apprise
- Run as a daemon or in the background
- Easy-to-use CLI interface
- Extensible architecture for custom monitors

## Installation

```bash
pip install server-monitoring-made-easy
```

Or from source:

```bash
git clone https://github.com/yourusername/server-monitoring-made-easy.git
cd server-monitoring-made-easy
poetry install
```

## Quick Start

1. Create a configuration file `config.yaml`:

```yaml
monitors:
  cpu:
    enabled: true
    threshold: 80 # Alert when CPU usage > 80%
    interval: 60 # Check every 60 seconds
  memory:
    enabled: true
    threshold: 90 # Alert when memory usage > 90%
    interval: 60
  disk:
    enabled: true
    threshold: 85 # Alert when any disk is > 85% full
    interval: 300 # Check every 5 minutes
  ping:
    enabled: true
    targets:
      - google.com
      - cloudflare.com
    threshold: 200 # Alert when ping > 200ms
    interval: 60

notifications:
  - type: telegram
    token: "your-bot-token"
    chat_id: "your-chat-id"
  - type: discord
    webhook: "your-webhook-url"

logging:
  level: INFO
  file: /var/log/sme/server-monitor.log
```

2. Start the monitor:

```bash
sme start --config config.yaml
```

3. Check status:

```bash
sme status
```

## Monitoring using systemd

```bash
# Create system user
sudo useradd -r -s /bin/false sme

# Create necessary directories
sudo mkdir -p /etc/sme /var/log/sme /var/run/sme
sudo chown -R sme:sme /etc/sme /var/log/sme /var/run/sme

# Install the package
pip install server-monitoring-made-easy

# Copy config file
sudo cp config.yaml /etc/sme/

# Copy and enable systemd service
sudo cp packaging/systemd/sme.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sme
sudo systemctl start sme
```

## CLI Usage

- `sme start`: Start the monitoring daemon
- `sme stop`: Stop the monitoring daemon
- `sme status`: Show current monitoring status
- `sme alerts`: List all alerts and their states
- `sme config show`: Show current configuration
- `sme config validate`: Validate configuration file

## Project Structure

```
app/
├── __init__.py
├── cli.py                 # CLI implementation
├── config.py             # Configuration management
├── core/
│   ├── __init__.py
│   ├── monitor.py        # Base monitoring functionality
│   ├── metrics.py        # Metric collection
│   └── alerts.py         # Alert management
├── monitors/
│   ├── __init__.py
│   ├── cpu.py
│   ├── memory.py
│   ├── disk.py
│   └── ping.py
├── notifiers/
│   ├── __init__.py
│   └── apprise_notify.py
└── utils/
    ├── __init__.py
    └── logging.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Container Support

When running in a container:
- Full host metrics support is only available on Linux hosts
- On non-Linux hosts (like macOS), container memory metrics will reflect the VM's memory usage, not the host system
- The container must be run with the following settings:
  - `pid: "host"` for accurate system metrics
  - `/proc:/host/proc:ro` volume mount for host memory metrics
  - Appropriate capabilities for network monitoring

## License

MIT License
