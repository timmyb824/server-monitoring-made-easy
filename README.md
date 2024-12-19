# Server Monitoring Made Easy (SME)

A lightweight, easy-to-configure server monitoring tool that focuses on the metrics that matter most.

## Features

- Monitor critical server metrics:
  - CPU usage
  - Memory consumption
  - Disk space
  - Network latency (ping)
- Flexible storage options:
  - File-based storage with JSON
  - PostgreSQL database support
- Advanced alert management:
  - Customizable thresholds
  - Alert count requirements before triggering
  - Automatic alert resolution
  - Alert history and pruning
- Comprehensive logging:
  - Component-level log configuration
  - Configurable log paths
  - Debug logging support
- Run modes:
  - Daemon mode with proper PID management
  - Foreground mode for debugging
  - Container support
- Easy-to-use CLI interface
- Extensible architecture for custom monitors

## Installation

From source:

```bash
git clone https://github.com/timmyb824/server-monitoring-made-easy.git
cd server-monitoring-made-easy
pip install -e .
```

## Configuration

Create a configuration file `config.yaml`. Here's a complete example with all available options (required options are marked with \*):

````yaml
# Logging Configuration
logging:
  level: debug # Global log level (debug, info, warning, error)
  components: # Component-specific log levels (all optional)
    monitors: debug
    alerts: debug
    metrics: debug
    daemon: debug
    storage: debug
    alerts: debug

# Path Configuration (all optional - defaults will be used if not specified)
paths:
  # Log file path - ensure this directory exists and has proper permissions
  log_file: "/path/to/log/server-monitor.log"
  # PID file location
  pid_file: "/path/to/pid/server-monitor.pid"

# Storage Configuration (required *)
storage: # * At least one storage type must be configured
  # Storage type: 'file' or 'postgres' (required *)
  type: file
  # For file storage:
  file_path: "/path/to/alerts.json" # * Required if type is 'file'
  # For PostgreSQL storage:
  # dsn: "postgresql://user:password@localhost:5432/dbname" # * Required if type is 'postgres'

  # Alert pruning configuration (optional)
  pruning:
    enabled: true
    max_age_days: 30 # Remove alerts older than this
    max_alerts: 1000 # Keep only the most recent N alerts

# Monitor Configuration (required *)
monitors: # * At least one monitor must be enabled
  cpu:
    enabled: true # * Required for each monitor
    interval: 60 # Check every 60 seconds (optional, default: 60)
    threshold: 80 # Alert when CPU usage > 80% (optional, default: 80)
    alert_count: 3 # Require 3 consecutive threshold violations (optional, default: 1)

  memory:
    enabled: true
    interval: 60
    threshold: 80
    alert_count: 1 # Alert immediately on threshold violation

  disk:
    enabled: true
    interval: 300 # Check every 5 minutes
    threshold: 85
    alert_count: 2
    path: / # Monitor specific path (optional, default: /)

  ping:
    enabled: true
    interval: 60
    threshold: 200 # Alert when ping > 200ms
    alert_count: 5
    targets: # * Required if ping monitor is enabled
      - 8.8.8.8
      - 1.1.1.1
      - google.com

# Alert Configuration (optional)
alerts:
  # Global alert settings
  default_alert_count: 1 # Default threshold violations before alerting (optional)
  resolution_time: 300 # Seconds to wait before auto-resolving (optional, default: 300)

{{ ... }}

## CLI Commands

- `server-monitor start [-f/--foreground] [-c/--config PATH]`: Start monitoring
  - `-f/--foreground`: Run in foreground instead of as daemon
  - `-c/--config`: Specify config file path
- `server-monitor stop`: Stop the monitoring daemon
- `server-monitor status`: Show daemon status
- `server-monitor metrics`: Display current system metrics
- `server-monitor alerts`: Show current and historical alerts
- `server-monitor config show`: Display current configuration
- `server-monitor config validate`: Validate configuration file
- `server-monitor init PATH`: Create new configuration file with defaults

## Running as a Service

### Using systemd

1. Create a systemd service file at `/etc/systemd/system/server-monitor.service`:

```ini
[Unit]
Description=Server Monitoring Made Easy
After=network.target

[Service]
Type=simple
User=your_user
Environment="SME_CONFIG=/path/to/config.yaml"
ExecStart=/path/to/python/bin/server-monitor start --foreground
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
````

2. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable server-monitor
sudo systemctl start server-monitor
```

### Using Docker

```yaml
version: "3"
services:
  monitor:
    build: .
    pid: "host" # Required for accurate system metrics
    volumes:
      - /proc:/host/proc:ro # For host metrics
      - ./config.yaml:/app/config.yaml:ro
    restart: unless-stopped
```

## Development

For development and testing:

```bash
# Install development dependencies
poetry install

# Run tests
poetry run pytest tests/ -v
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License
