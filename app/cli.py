"""Command-line interface for Server Monitoring Made Easy."""

import os
import sys
import time
from typing import Optional

import click
import daemon
import structlog
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.config import ConfigManager
from app.core.alerts import AlertManager
from app.monitors import CPUMonitor, DiskMonitor, MemoryMonitor, PingMonitor

logger = structlog.get_logger()


def get_app_paths(config=None):
    """Get application paths based on user permissions and config.

    Args:
        config: Optional configuration dictionary

    Returns:
        tuple: (log_file_path, pid_file_path)
    """
    if config is None:
        config = {}

    paths_config = config.get("paths", {})

    # Default paths
    if os.getuid() == 0:  # Root user
        default_log_path = "/var/log/sme/server-monitor.log"
        default_pid_path = "/var/run/sme/server-monitor.pid"
    else:  # Non-root user
        home = os.path.expanduser("~")
        default_log_path = os.path.join(home, ".local/log/sme/server-monitor.log")
        default_pid_path = os.path.join(home, ".local/run/sme/server-monitor.pid")

    # Get paths from config or use defaults
    log_path = os.path.expanduser(paths_config.get("log_file", default_log_path))
    pid_path = os.path.expanduser(paths_config.get("pid_file", default_pid_path))

    # Ensure directories exist with proper permissions
    for path in [log_path, pid_path]:
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory, mode=0o755, exist_ok=True)
            # Ensure user owns the directory if not root
            if os.getuid() != 0:
                os.chown(directory, os.getuid(), os.getgid())

    return log_path, pid_path


def get_pid_file():
    """Get the appropriate PID file location."""
    _, pid_path = get_app_paths()
    return pid_path


def setup_logging(config, component=None):
    """Set up logging configuration.

    Args:
        config: The configuration dictionary
        component: Optional component name to use component-specific log level
    """
    # Handle None config
    if not config:
        config = {}

    log_config = config.get("logging", {})
    log_path, _ = get_app_paths(config)

    # Get component-specific log level if provided, otherwise use global level
    if component and "components" in log_config:
        log_level = log_config.get("components", {}).get(
            component, log_config.get("level", "INFO")
        )
    else:
        log_level = log_config.get("level", "INFO")

    # Convert log level string to uppercase
    log_level = log_level.upper()

    # Base processors for all outputs
    base_processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
    ]

    # Configure logging handlers
    handlers = [logging.StreamHandler()]  # Always log to console

    try:
        # Try to create/open log file
        handlers.append(logging.FileHandler(log_path))
    except PermissionError:
        logger.warning(
            "Cannot write to log file, falling back to console only", log_path=log_path
        )

    # Configure Python's built-in logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(message)s",
        handlers=handlers,
    )

    # Configure structlog
    processors = [
        *base_processors,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    logger.info(
        "Logging initialized",
        log_path=log_path,
        log_level=log_level,
    )


def monitor_loop(config):
    """Main monitoring loop."""
    try:
        setup_logging(config)
        logger.info("Starting monitoring loop")

        monitors = get_monitor_instances(config)
        logger.info(
            "Initialized monitors",
            monitor_count=len(monitors),
            monitors=[m.name for m in monitors.values()],
        )

        alert_manager = AlertManager(config)
        logger.info("Alert manager initialized")

        if not create_pid_file():
            logger.error("Failed to create PID file, exiting")
            return

        logger.info("Monitor started successfully")

        while True:
            for monitor in monitors.values():
                try:
                    if alert := monitor.check():
                        alert_manager.process_alert(alert)
                except Exception as e:
                    logger.error(
                        "Monitor check failed", monitor=monitor.name, error=str(e)
                    )
            time.sleep(1)

    except Exception as e:
        logger.error("Monitoring loop failed", error=str(e))
    finally:
        remove_pid_file()
        logger.info("Monitoring stopped")


@click.group()
def cli():
    """Server Monitoring Made Easy - Simple and effective server monitoring."""
    pass


@cli.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Path to configuration file"
)
@click.option(
    "--foreground", "-f", is_flag=True, help="Run in foreground instead of as daemon"
)
def start(config: Optional[str], foreground: bool):
    """Start the monitoring daemon."""
    config_manager = ConfigManager(config)

    if not config_manager.validate_config():
        click.echo("Invalid configuration. Please check your config file.")
        sys.exit(1)

    click.echo("Starting server monitoring...")

    if foreground:
        monitor_loop(config_manager.get_config())
    else:
        # Get paths from config
        log_path, pid_path = get_app_paths(config_manager.get_config())

        # Create directories if they don't exist
        for path in [log_path, pid_path]:
            directory = os.path.dirname(path)
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory, mode=0o755, exist_ok=True)
                    if os.getuid() != 0:  # If not root
                        os.chown(directory, os.getuid(), os.getgid())
                except PermissionError:
                    click.echo(
                        f"Error: Cannot create directory {directory}. Please check permissions."
                    )
                    sys.exit(1)

        # Create a more permissive daemon context
        context = daemon.DaemonContext(
            working_directory=os.getcwd(),
            umask=0o002,
            detach_process=True,
            files_preserve=[],  # Add any file descriptors that need to be preserved
        )

        # Set up PID file
        try:
            context.pidfile = get_pid_file()
        except Exception as e:
            click.echo(f"Error setting up PID file: {e}")
            sys.exit(1)

        try:
            with context:
                monitor_loop(config_manager.get_config())
        except Exception as e:
            click.echo(f"Failed to start daemon: {e}")
            sys.exit(1)


@cli.command()
def stop():
    """Stop the monitoring daemon."""
    try:
        with open(get_pid_file(), "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
        os.kill(pid, 15)  # SIGTERM
        click.echo("Stopped server monitoring.")
    except FileNotFoundError:
        click.echo("Server monitor is not running.")
    except ProcessLookupError:
        click.echo("Server monitor is not running.")
        remove_pid_file()
    except Exception as e:
        click.echo(f"Error stopping monitor: {e}")


@cli.command()
def status():
    """Show monitoring status."""
    try:
        with open(get_pid_file(), "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, 0)  # Check if process exists
            click.echo("Server monitor is running.")
        except ProcessLookupError:
            click.echo("Server monitor is not running.")
            remove_pid_file()
    except FileNotFoundError:
        click.echo("Server monitor is not running.")
    except Exception as e:
        click.echo(f"Error checking status: {e}")


@cli.group()
def config():
    """Manage configuration."""
    pass


@config.command("show")
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Path to configuration file"
)
def show_config(config: Optional[str]):
    """Show current configuration."""
    config_manager = ConfigManager(config)
    click.echo(yaml.dump(config_manager.get_config(), default_flow_style=False))


@config.command("validate")
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Path to configuration file"
)
def validate_config(config: Optional[str]):
    """Validate configuration file."""
    config_manager = ConfigManager(config)
    if config_manager.validate_config():
        click.echo("Configuration is valid.")
    else:
        click.echo("Configuration is invalid.")
        sys.exit(1)


@cli.command()
def alerts():
    """Show current alerts."""
    config_manager = ConfigManager()
    alert_manager = AlertManager(config_manager.get_config())

    active_alerts = alert_manager.get_active_alerts()
    if not active_alerts:
        click.echo("No active alerts.")
        return

    for alert in active_alerts:
        click.echo("\n---")
        click.echo(f"Monitor: {alert['monitor']}")
        click.echo(f"State: {alert['state']}")
        click.echo(f"Value: {alert.get('value')}")
        click.echo(f"Threshold: {alert.get('threshold')}")
        click.echo(
            f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert['timestamp']))}"
        )


@cli.command()
def metrics():
    """Display current system metrics."""
    # Load config but don't change logging setup
    config_manager = ConfigManager()
    config = config_manager.load_config()
    if not config:
        config = {}

    console = Console()

    # Initialize monitors with default thresholds if no config
    monitor_config = config.get("monitors", {})
    cpu_monitor = CPUMonitor(
        "cpu", monitor_config.get("cpu", {"threshold": 80}), silent=True
    )
    mem_monitor = MemoryMonitor(
        "memory", monitor_config.get("memory", {"threshold": 80}), silent=True
    )
    disk_monitor = DiskMonitor(
        "disk", monitor_config.get("disk", {"threshold": 85}), silent=True
    )
    ping_monitor = PingMonitor(
        "ping", monitor_config.get("ping", {"threshold": 200}), silent=True
    )

    # Collect metrics
    cpu = cpu_monitor.collect()
    memory = mem_monitor.collect()
    disk = disk_monitor.collect()
    ping_results = ping_monitor.collect()

    # Create and display tables
    table = Table(title="System Metrics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("CPU Usage", f"{cpu:.1f}%")
    table.add_row("Memory Usage", f"{memory:.1f}%")
    table.add_row("Disk Usage", f"{disk:.1f}%")

    ping_table = Table(show_header=True, header_style="bold magenta")
    ping_table.add_column("Host", style="cyan")
    ping_table.add_column("Latency", justify="right", style="green")

    for host, latency in ping_results.items():
        ping_table.add_row(
            host, f"{latency:.1f}ms" if latency is not None else "Timeout"
        )

    console.print(Panel(table, title="System Resources", border_style="blue"))
    console.print(Panel(ping_table, title="Network Latency", border_style="blue"))


@cli.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(),
    default="config.yaml",
    help="Path to create the config file",
)
@click.option(
    "--no-log-file",
    is_flag=True,
    help="Configure logging to console only (no log file)",
)
def init(path: str, no_log_file: bool):
    """Initialize a new configuration file with default settings."""
    if os.path.exists(path):
        click.echo(
            f"Error: {path} already exists. Please choose a different path or remove the existing file."
        )
        sys.exit(1)

    # Create default config
    default_config = {
        "logging": {
            "level": "info",
            "components": {
                "monitors": "info",
                "alerts": "warning",
                "metrics": "warning",
                "daemon": "info",
            },
        },
        "monitors": {
            "cpu": {
                "enabled": True,
                "interval": 60,
                "threshold": 80,
                "alert_count": 3,
            },
            "memory": {
                "enabled": True,
                "interval": 60,
                "threshold": 80,
                "alert_count": 1,
            },
            "disk": {
                "enabled": True,
                "interval": 300,
                "threshold": 85,
                "alert_count": 2,
                "path": "/",
            },
            "ping": {
                "enabled": True,
                "interval": 60,
                "threshold": 200,
                "alert_count": 5,
                "targets": ["8.8.8.8", "1.1.1.1", "google.com"],
            },
        },
        "alerts": {
            "enabled": True,
            "methods": [
                {
                    "type": "console",
                    "enabled": True,
                }
            ],
        },
    }

    # Add paths configuration if log file is desired
    if not no_log_file:
        if os.getuid() == 0:  # Root user
            default_config["paths"] = {
                "log_file": "/var/log/sme/server-monitor.log",
                "pid_file": "/var/run/sme/server-monitor.pid",
            }
        else:  # Non-root user
            default_config["paths"] = {
                "log_file": "~/.local/log/sme/server-monitor.log",
                "pid_file": "~/.local/run/sme/server-monitor.pid",
            }

    # Create the config file
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
        click.echo(f"Created default configuration at {path}")

        # Print next steps
        click.echo("\nNext steps:")
        click.echo("1. Review and customize the configuration file")
        if not no_log_file:
            click.echo("2. Ensure log directory exists and has proper permissions")
            if os.getuid() == 0:
                click.echo("   sudo mkdir -p /var/log/sme /var/run/sme")
                click.echo("   sudo chown -R $USER:$USER /var/log/sme /var/run/sme")
            else:
                click.echo("   mkdir -p ~/.local/log/sme ~/.local/run/sme")
        click.echo(f"3. Start the monitor: sme start -c {path}")
    except Exception as e:
        click.echo(f"Error creating config file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
