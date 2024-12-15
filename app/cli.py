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
from rich.table import Table
from rich.panel import Panel

from app.config import ConfigManager
from app.core.alerts import AlertManager
from app.monitors import CPUMonitor, DiskMonitor, MemoryMonitor, PingMonitor

logger = structlog.get_logger()


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
    log_file = log_config.get("file", "stdout")
    
    # Get component-specific log level if provided, otherwise use global level
    if component and "components" in log_config:
        log_level = log_config.get("components", {}).get(component, log_config.get("level", "INFO"))
    else:
        log_level = log_config.get("level", "INFO")

    # Convert log level string to uppercase
    log_level = log_level.upper()

    # Base processors for all outputs
    base_processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
    ]

    # Always log to stdout for container environments
    if os.getenv("CONTAINER") == "1":
        # Set up file logging
        file_path = "/var/log/sme/server-monitor.log"
        if os.path.dirname(file_path):
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Configure both console and file logging
        processors = [
            *base_processors,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]

        # Configure Python's built-in logging
        import logging

        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(message)s",
            handlers=[
                logging.StreamHandler(),  # Console output
                logging.FileHandler(file_path),  # File output
            ],
        )
    else:
        # For non-container environments, use console renderer
        processors = [*base_processors, structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    logger.info(
        "Logging initialized",
        log_file=log_file,
        log_level=log_level,
        container=bool(os.getenv("CONTAINER")),
    )


def get_pid_file():
    """Get the appropriate PID file location."""
    if os.getenv("CONTAINER") == "1":  # Running in container
        return "/var/run/sme/server-monitor.pid"
    elif os.getuid() == 0:  # Running as root
        return "/var/run/sme/server-monitor.pid"
    return os.path.expanduser("~/.sme/server-monitor.pid")


def create_pid_file():
    """Create PID file for the daemon."""
    pid = str(os.getpid())
    pid_file = get_pid_file()
    pid_dir = os.path.dirname(pid_file)

    try:
        os.makedirs(pid_dir, exist_ok=True)
        with open(pid_file, "w", encoding="utf-8") as f:
            f.write(pid)
        return pid_file
    except Exception as e:
        logger.error("Failed to create PID file", error=str(e), pid_file=pid_file)
        return None


def remove_pid_file():
    """Remove PID file."""
    try:
        os.remove(get_pid_file())
    except Exception as e:
        logger.warning("Failed to remove PID file", error=str(e))


def get_monitor_instances(config):
    """Create monitor instances from configuration."""
    # Handle None config
    if not config:
        config = {}
        
    # Set up logging for monitors component
    setup_logging(config, component="monitors")
    
    monitors = {}
    monitor_config = config.get("monitors", {})

    if monitor_config.get("cpu", {}).get("enabled", True):  # Default to enabled
        monitors["cpu"] = CPUMonitor("cpu", monitor_config.get("cpu", {"threshold": 80}))

    if monitor_config.get("memory", {}).get("enabled", True):
        monitors["memory"] = MemoryMonitor("memory", monitor_config.get("memory", {"threshold": 80}))

    if monitor_config.get("disk", {}).get("enabled", True):
        monitors["disk"] = DiskMonitor("disk", monitor_config.get("disk", {"threshold": 80}))

    if monitor_config.get("ping", {}).get("enabled", True):
        monitors["ping"] = PingMonitor("ping", monitor_config.get("ping", {"threshold": 100}))

    return monitors


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
        # Create a more permissive daemon context for development
        context = daemon.DaemonContext(
            working_directory=os.getcwd(), umask=0o002, detach_process=True
        )

        # If we're not root, adjust the paths
        if os.getuid() != 0:
            pid_dir = os.path.expanduser("~/.sme")
            os.makedirs(pid_dir, exist_ok=True)
            context.pidfile = get_pid_file()

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
    # Load config and set up logging with metrics component
    config_manager = ConfigManager()
    config = config_manager.load_config()
    if not config:
        config = {}  # Use empty dict as fallback
    setup_logging(config, component="metrics")
    
    console = Console()

    # Initialize monitors with default thresholds if no config
    monitor_config = config.get("monitors", {})
    cpu_monitor = CPUMonitor("cpu", monitor_config.get("cpu", {"threshold": 80}))
    mem_monitor = MemoryMonitor("memory", monitor_config.get("memory", {"threshold": 80}))
    disk_monitor = DiskMonitor("disk", monitor_config.get("disk", {"threshold": 80}))
    ping_monitor = PingMonitor("ping", monitor_config.get("ping", {"threshold": 100}))

    # Collect metrics
    cpu = cpu_monitor.collect()
    memory = mem_monitor.collect()
    disk = disk_monitor.collect()
    ping_results = ping_monitor.collect()

    # Create table
    table = Table(title="System Metrics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    # Add rows
    table.add_row("CPU Usage", f"{cpu:.1f}%")
    table.add_row("Memory Usage", f"{memory:.1f}%")
    table.add_row("Disk Usage", f"{disk:.1f}%")

    # Create ping table
    ping_table = Table(show_header=True, header_style="bold magenta")
    ping_table.add_column("Host", style="cyan")
    ping_table.add_column("Latency", justify="right", style="green")

    for host, latency in ping_results.items():
        ping_table.add_row(
            host, f"{latency:.1f}ms" if latency is not None else "Timeout"
        )

    # Display tables
    console.print(Panel(table, title="System Resources", border_style="blue"))
    console.print(Panel(ping_table, title="Network Latency", border_style="blue"))


if __name__ == "__main__":
    cli()
