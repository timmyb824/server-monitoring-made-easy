"""CPU monitor."""

from typing import Any

import psutil

from .base import Monitor


class CPUMonitor(Monitor):
    """Monitor CPU usage."""

    def __init__(self, name: str, config: dict[str, Any], silent: bool = False):
        """Initialize CPU monitor.

        Args:
            name: Name of the monitor
            config: Configuration dictionary
            silent: If True, suppress all logging from this monitor
        """
        super().__init__(name, config, silent)

    def collect(self) -> float:
        """Collect CPU usage percentage."""
        return psutil.cpu_percent(interval=1)

    def check_threshold(self, value: float) -> bool:
        """Check if CPU usage exceeds threshold."""
        return value > self.threshold
