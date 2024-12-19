"""Command-line interface for Server Monitoring Made Easy."""

import logging
import os
import sys
import time
import traceback
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

console = Console()
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
        pid_file = get_pid_file()
        if os.path.exists(pid_file):
            os.remove(pid_file)
    except Exception as e:
        logger.warning("Failed to remove PID file", error=str(e))


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

    # Check environment variable first, then config file
    env_log_level = os.environ.get("LOGLEVEL", "").upper()
    if env_log_level:
        log_level = env_log_level
    elif component and "components" in log_config:
        log_level = log_config.get("components", {}).get(
            component, log_config.get("level", "INFO")
        )
    else:
        log_level = log_config.get("level", "INFO")

    # Convert log level string to uppercase
    log_level = log_level.upper()

    # Base processors for all outputs
    base_processors = [
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure logging handlers
    handlers = [logging.StreamHandler()]

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

    # Set log level for specific loggers
    logging.getLogger("sqlalchemy.engine").setLevel(log_level)
    logging.getLogger("alembic").setLevel(log_level)

    # Configure structlog with console and JSON renderers
    if log_config.get("file") == "stdout":
        # For stdout, use a more readable format
        processors = [
            *base_processors,
            structlog.processors.dict_tracebacks,
            structlog.dev.ConsoleRenderer(
                colors=True, exception_formatter=structlog.dev.plain_traceback
            ),
        ]
    else:
        # For file output, use JSON format
        processors = [
            *base_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger.info(
        "Logging initialized",
        log_path=log_path,
        log_level=log_level,
        env_log_level=env_log_level,
    )


def monitor_loop(config):
    """Main monitoring loop."""
    try:
        logger.info("Entering monitor loop")
        logger.info("Creating PID file")
        if not create_pid_file():
            logger.error("Failed to create PID file")
            return

        # Set up logging for monitors component
        logger.info("Setting up monitor logging")
        setup_logging(config, component="monitors")
        logger.info("Monitor logging setup complete")

        # Initialize monitors
        monitors = {}
        monitor_config = config.get("monitors", {})
        logger.info("Monitor configuration loaded", config=monitor_config)

        logger.info("Starting monitor initialization")
        if monitor_config.get("cpu", {}).get("enabled", True):
            logger.info("Initializing CPU monitor")
            try:
                monitors["cpu"] = CPUMonitor(
                    "cpu", monitor_config.get("cpu", {"threshold": 80})
                )
                logger.info("CPU monitor initialized")
            except Exception as e:
                logger.error(
                    "Failed to initialize CPU monitor", error=str(e), exc_info=True
                )

        if monitor_config.get("memory", {}).get("enabled", True):
            logger.info("Initializing Memory monitor")
            try:
                monitors["memory"] = MemoryMonitor(
                    "memory", monitor_config.get("memory", {"threshold": 80})
                )
                logger.info("Memory monitor initialized")
            except Exception as e:
                logger.error(
                    "Failed to initialize Memory monitor", error=str(e), exc_info=True
                )

        if monitor_config.get("disk", {}).get("enabled", True):
            logger.info("Initializing Disk monitor")
            try:
                monitors["disk"] = DiskMonitor(
                    "disk", monitor_config.get("disk", {"threshold": 85})
                )
                logger.info("Disk monitor initialized")
            except Exception as e:
                logger.error(
                    "Failed to initialize Disk monitor", error=str(e), exc_info=True
                )

        if monitor_config.get("ping", {}).get("enabled", True):
            logger.info("Initializing Ping monitor")
            try:
                monitors["ping"] = PingMonitor(
                    "ping", monitor_config.get("ping", {"threshold": 200})
                )
                logger.info("Ping monitor initialized")
            except Exception as e:
                logger.error(
                    "Failed to initialize Ping monitor", error=str(e), exc_info=True
                )

        if not monitors:
            logger.error("No monitors enabled")
            return

        # Initialize alert manager
        alert_manager = None
        try:
            logger.info("Starting alert manager initialization")
            logger.debug("Alert manager config", config=config)
            alert_manager = AlertManager(config)
            logger.info("Alert manager initialized successfully")
        except Exception as e:
            logger.error(
                "Failed to initialize alert manager", error=str(e), exc_info=True
            )
            return

        logger.info(f"Starting monitoring loop with {len(monitors)} monitors")
        iteration = 0
        while True:
            try:
                iteration += 1
                logger.debug(f"Starting iteration {iteration} of monitoring loop")
                for monitor_name, monitor in monitors.items():
                    logger.debug(f"Processing {monitor_name} monitor")
                    try:
                        if monitor.should_check():
                            logger.debug(f"Checking {monitor.name}")
                            try:
                                value = monitor.collect()
                                logger.debug(f"{monitor.name} value: {value}")
                                if alert := monitor.check():
                                    logger.info(
                                        f"Alert detected from {monitor.name}",
                                        alert=alert,
                                    )
                                    alert_manager.process_alert(alert)
                            except Exception as e:
                                logger.error(
                                    f"Error checking {monitor.name}",
                                    error=str(e),
                                    exc_info=True,
                                )
                        else:
                            logger.debug(
                                f"Skipping {monitor.name}, not time to check yet"
                            )
                    except Exception as e:
                        logger.error(
                            f"Error processing {monitor.name}",
                            error=str(e),
                            exc_info=True,
                        )
                        continue
                logger.debug(f"Completed iteration {iteration}, sleeping for 1 second")
                time.sleep(1)
            except Exception as e:
                logger.error(
                    "Error in monitoring loop iteration", error=str(e), exc_info=True
                )
                time.sleep(1)  # Prevent tight error loop

    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error("Monitoring loop failed", error=str(e), exc_info=True)
        raise
    finally:
        logger.info("Exiting monitor loop")
        remove_pid_file()


@click.group()
def cli():
    """Server Monitoring Made Easy - Simple and effective server monitoring."""
    pass


@cli.command("version", help="Show version information")
def show_version():
    """Show version information."""
    try:
        from importlib.metadata import version

        sme_version = version("server-monitoring-made-easy")
        console.print(f"[blue]Server Monitoring Made Easy version {sme_version}[/blue]")
    except ImportError:
        console.print("[red]Error: Could not determine version[/red]")


@cli.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Path to configuration file"
)
@click.option(
    "--foreground", "-f", is_flag=True, help="Run in foreground instead of as daemon"
)
def start(config: Optional[str], foreground: bool):
    """Start the monitoring daemon."""
    try:
        logger.info("Starting server monitoring process")
        config_manager = ConfigManager(config)
        logger.info("Config manager initialized")

        if not config_manager.validate_config():
            click.echo("Invalid configuration. Please check your config file.")
            sys.exit(1)
        logger.info("Config validation successful")

        click.echo("Starting server monitoring...")

        # Initialize storage backend
        storage_config = config_manager.get_config().get("storage", {})
        if storage_config.get("type") == "postgres":
            logger.info("PostgreSQL storage detected")
            dsn = storage_config.get("dsn")
            if not dsn:
                logger.error("PostgreSQL DSN not configured")
                sys.exit(1)

            try:
                # Initialize database
                from app.db import init_db

                db_success, db_error = init_db(dsn)

                if not db_success:
                    logger.warning(
                        "Database initialization failed, continuing without database",
                        error=db_error,
                    )
            except Exception as e:
                logger.warning(
                    "Database setup failed, continuing without database", error=str(e)
                )

        if foreground:
            logger.info("Starting monitor loop in foreground mode")
            try:
                monitor_loop(config_manager.get_config())
            except Exception as e:
                logger.error(
                    "Monitor loop failed to start",
                    error=str(e),
                    traceback=traceback.format_exc(),
                )
                sys.exit(1)
        else:
            logger.info("Starting monitor loop in daemon mode")
            # Get paths from config
            log_path, pid_path = get_app_paths(config_manager.get_config())

            # Create directories if they don't exist
            for path in [log_path, pid_path]:
                directory = os.path.dirname(path)
                if not os.path.exists(directory):
                    try:
                        os.makedirs(directory, mode=0o755, exist_ok=True)
                        if os.getuid() != 0:
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
                files_preserve=[],
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
                logger.error(
                    "Failed to start daemon",
                    error=str(e),
                    traceback=traceback.format_exc(),
                )
                sys.exit(1)
    except Exception as e:
        logger.error("Startup failed", error=str(e), traceback=traceback.format_exc())
        sys.exit(1)


@cli.command()
def stop():
    """Stop the monitoring daemon."""
    try:
        with open(get_pid_file(), "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
        os.kill(pid, 15)
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
            os.kill(pid, 0)
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
    config = config_manager.load_config() or {}

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
        "storage": {
            "type": "postgres",
            "dsn": "postgresql://user:password@localhost:5432/monitoring",
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
        if os.getuid() == 0:
            default_config["paths"] = {
                "log_file": "/var/log/sme/server-monitor.log",
                "pid_file": "/var/run/sme/server-monitor.pid",
            }
        else:
            default_config["paths"] = {
                "log_file": "~/.local/log/sme/server-monitor.log",
                "pid_file": "~/.local/run/sme/server-monitor.pid",
            }

    # Create the config file
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
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
