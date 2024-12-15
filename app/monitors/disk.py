"""Disk monitor."""

from typing import Any

import psutil

from .base import Monitor


class DiskMonitor(Monitor):
    """Monitor disk usage."""

    def __init__(self, name: str, config: dict[str, Any], silent: bool = False):
        """Initialize disk monitor.

        Args:
            name: Name of the monitor
            config: Configuration dictionary
            silent: If True, suppress all logging from this monitor
        """
        super().__init__(name, config, silent)
        self.path = config.get("path", "/")

    def collect(self) -> float:
        """Collect disk usage percentage."""
        disk = psutil.disk_usage(self.path)
        return disk.percent

    def check_threshold(self, value: float) -> bool:
        """Check if disk usage exceeds threshold."""
        return value > self.threshold
