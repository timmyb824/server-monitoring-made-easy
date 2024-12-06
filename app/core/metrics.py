"""Metric collectors for different system resources."""

import platform
import subprocess
from typing import Any, Optional

import psutil

from .monitor import Monitor


class CPUMonitor(Monitor):
    """Monitor CPU usage."""

    def collect(self) -> float:
        """Collect CPU usage percentage."""
        return psutil.cpu_percent(interval=1)

    def check_threshold(self, value: float) -> bool:
        """Check if CPU usage exceeds threshold."""
        return value > self.threshold


class MemoryMonitor(Monitor):
    """Monitor memory usage."""

    def collect(self) -> float:
        """Collect memory usage percentage."""
        memory = psutil.virtual_memory()
        return memory.percent

    def check_threshold(self, value: float) -> bool:
        """Check if memory usage exceeds threshold."""
        return value > self.threshold


class DiskMonitor(Monitor):
    """Monitor disk usage."""

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize disk monitor.

        Args:
            name: Name of the monitor
            config: Configuration dictionary
        """
        super().__init__(name, config)
        self.path = config.get("path", "/")

    def collect(self) -> float:
        """Collect disk usage percentage."""
        try:
            usage = psutil.disk_usage(self.path)
            return usage.percent
        except PermissionError:
            self.logger.error(
                f"Permission denied accessing {self.path}. "
                "Make sure the sme user has required permissions."
            )
            return 0.0

    def check_threshold(self, value: float) -> bool:
        """Check if disk usage exceeds threshold."""
        return value > self.threshold


class PingMonitor(Monitor):
    """Monitor network latency via ping."""

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize ping monitor.

        Args:
            name: Name of the monitor
            config: Configuration dictionary
        """
        super().__init__(name, config)
        self.targets = config.get("targets", ["8.8.8.8"])  # Default to Google DNS
        self.timeout = config.get("timeout", 5)  # Default 5 second timeout

    def _ping(self, host: str) -> Optional[float]:
        """Ping a single host.

        Args:
            host: Host to ping

        Returns:
            Round trip time in milliseconds or None if failed
        """
        param = "-n" if platform.system().lower() == "windows" else "-c"
        command = ["ping", param, "1", "-W", str(self.timeout), host]

        try:
            output = subprocess.check_output(command).decode().strip()
            if platform.system().lower() == "windows":
                if "Average" in output:
                    return float(
                        output.rsplit("Average = ", maxsplit=1)[-1].split("ms")[0]
                    )
            elif "time=" in output:
                return float(output.rsplit("time=", maxsplit=1)[-1].split(" ")[0])
        except Exception:
            self.logger.warning(f"Failed to ping {host}")
            return None

        return None

    def collect(self) -> dict[str, Optional[float]]:
        """Collect ping times for all targets."""
        return {target: self._ping(target) for target in self.targets}

    def check_threshold(self, value: dict[str, Optional[float]]) -> bool:
        """Check if any ping time exceeds threshold."""
        for target, latency in value.items():
            if latency is None:  # Connection failed
                return True
            if latency > self.threshold:
                return True
        return False
