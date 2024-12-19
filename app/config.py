"""Configuration management for Server Monitoring Made Easy."""

import logging
import os
from typing import Optional

import structlog
import yaml

# Configure initial logging with WARNING level
logging.basicConfig(level=logging.WARNING)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()

DEFAULT_CONFIG = {
    "monitors": {
        "cpu": {
            "enabled": True,
            "threshold": 80,  # Alert when CPU usage > 80%
            "interval": 60,  # Check every 60 seconds
            "alert_count": 3,  # Alert after 3 consecutive failures
        },
        "memory": {
            "enabled": True,
            "threshold": 90,  # Alert when memory usage > 90%
            "interval": 60,  # Check every 60 seconds
            "alert_count": 3,  # Alert after 3 consecutive failures
        },
        "disk": {
            "enabled": True,
            "threshold": 85,  # Alert when disk is > 85% full
            "interval": 300,  # Check every 5 minutes
            "path": "/",  # Monitor root partition
            "alert_count": 2,  # Alert after 2 consecutive failures (less frequent checks)
        },
        "ping": {
            "enabled": True,
            "threshold": 200,  # Alert when ping > 200ms
            "interval": 60,  # Check every 60 seconds
            "alert_count": 5,  # More consecutive checks for network latency
            "targets": [
                "8.8.8.8",  # Google DNS
                "1.1.1.1",  # Cloudflare DNS
                "google.com",  # Google
            ],
            "timeout": 5,  # Ping timeout in seconds
        },
    },
    "notifications": [],  # Empty by default, user must configure
    "logging": {
        "level": "warning",  # Default to warning level
        "file": "stdout",  # Default to stdout for container compatibility
        "components": {  # Component-specific log levels
            "monitors": "warning",
            "alerts": "warning",
            "metrics": "error",
            "daemon": "warning",
        },
    },
}

DEFAULT_CONFIG_LOCATIONS = [
    "/etc/sme/config.yaml",
    "~/.config/sme/config.yaml",
    "./config.yaml",
]


def _expand_paths(config: dict) -> dict:
    """Expand all path values in the configuration."""
    for key, value in config.items():
        if isinstance(value, dict):
            config[key] = _expand_paths(value)
        elif isinstance(value, str) and os.path.exists(os.path.expanduser(value)):
            config[key] = os.path.expanduser(value)
    return config


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config = DEFAULT_CONFIG.copy()

        # Try to load config from default locations if not specified
        if not config_path:
            for path in DEFAULT_CONFIG_LOCATIONS:
                expanded_path = os.path.expanduser(path)
                if os.path.exists(expanded_path):
                    self.config_path = expanded_path
                    break

            # If no config found, create one in the first writable location
            if not self.config_path:
                self.config_path = self._create_default_config()

        if self.config_path:
            self.load_config()

    def _create_default_config(self) -> str:
        """Create default configuration file in the first writable location.

        Returns:
            Path to the created configuration file
        """
        for path in DEFAULT_CONFIG_LOCATIONS:
            try:
                expanded_path = os.path.expanduser(path)
                os.makedirs(os.path.dirname(expanded_path), exist_ok=True)

                with open(expanded_path, "w", encoding="utf-8") as f:
                    yaml.dump(
                        DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False
                    )

                logger.info(f"Created default configuration at: {expanded_path}")
                return expanded_path

            except (OSError, IOError) as e:
                logger.debug(f"Could not create config at {expanded_path}: {e}")
                continue

        # If we couldn't create in any default location, use current directory
        try:
            path = "./config.yaml"
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Created default configuration at: {path}")
            return path

        except (OSError, IOError) as e:
            logger.error(f"Failed to create default config: {e}")
            return None

    def load_config(self):
        """Load configuration from file."""
        try:
            if not self.config_path:
                return self.config

            with open(self.config_path, "r") as f:
                file_config = yaml.safe_load(f)

            if file_config:
                self._merge_config(self.config, file_config)
                self.config = _expand_paths(self.config)

            # Set up logging based on loaded config
            log_config = self.config.get("logging", {})
            log_level = log_config.get("level", "warning").upper()

            # Configure both Python's logging and structlog
            logging.getLogger().setLevel(getattr(logging, log_level))

            logger.debug("Configuration loaded", config=self.config)
            return self.config

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return None

    def _merge_config(self, base: dict, override: dict) -> None:
        """Recursively merge override config into base config.

        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def validate_config(self) -> bool:
        """Validate the current configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check monitors configuration
            monitors = self.config.get("monitors", {})
            for monitor, settings in monitors.items():
                if not isinstance(settings, dict):
                    logger.error(f"Invalid monitor configuration: {monitor}")
                    return False

                required_fields = ["enabled", "threshold", "interval"]
                for field in required_fields:
                    if field not in settings:
                        logger.error(
                            f"Missing required field '{field}' in monitor: {monitor}"
                        )
                        return False

                # Validate alert_count if present
                if "alert_count" in settings and not isinstance(
                    settings["alert_count"], int
                ):
                    logger.error(f"Invalid alert_count in monitor: {monitor}")
                    return False

            # Check notifications configuration
            notifications = self.config.get("notifications", [])
            if not isinstance(notifications, list):
                logger.error("Notifications must be a list")
                return False

            # Check logging configuration
            logging = self.config.get("logging", {})
            if not isinstance(logging, dict):
                logger.error("Logging configuration must be a dictionary")
                return False

            return True

        except Exception as e:
            logger.error("Configuration validation failed", error=str(e))
            return False

    def get_config(self) -> dict:
        """Get the current configuration.

        Returns:
            The current configuration dictionary
        """
        return self.config

    def save_config(self) -> bool:
        """Save the current configuration to file.

        Returns:
            True if save was successful, False otherwise
        """
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            logger.error("Failed to save configuration", error=str(e))
            return False
