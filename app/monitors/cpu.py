"""CPU monitor."""

import psutil

from .base import Monitor


class CPUMonitor(Monitor):
    """Monitor CPU usage."""

    def collect(self) -> float:
        """Collect CPU usage percentage."""
        return psutil.cpu_percent(interval=1)

    def check_threshold(self, value: float) -> bool:
        """Check if CPU usage exceeds threshold."""
        return value > self.threshold
