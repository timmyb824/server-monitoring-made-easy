"""Ping monitor."""

import platform
import subprocess
from typing import Any, Optional

from .base import Monitor


class PingMonitor(Monitor):
    """Monitor network latency via ping."""

    def __init__(self, name: str, config: dict[str, Any], silent: bool = False):
        """Initialize ping monitor.

        Args:
            name: Name of the monitor
            config: Configuration dictionary
            silent: If True, suppress all logging from this monitor
        """
        super().__init__(name, config, silent)
        self.targets = config.get("targets", ["1.1.1.1"])  # Default to Cloudflare
        self.timeout = config.get("timeout", 5)  # Default 5 second timeout

    def _ping(self, host: str) -> Optional[float]:
        """Ping a single host.

        Args:
            host: Host to ping

        Returns:
            Round trip time in milliseconds or None if failed
        """
        param = "-n" if platform.system().lower() == "windows" else "-c"
        system = platform.system().lower()

        if system == "darwin":  # macOS
            command = ["ping", "-c", "1", "-t", str(self.timeout), host]
        elif system == "windows":
            command = ["ping", param, "1", "-w", str(self.timeout * 1000), host]
        else:  # Linux
            command = ["ping", param, "1", "-W", str(self.timeout), host]

        try:
            output = subprocess.check_output(command).decode().strip()
            if platform.system().lower() == "darwin":  # macOS
                if "time=" in output:
                    # Extract time value from the line containing "time="
                    time_line = [
                        line for line in output.split("\n") if "time=" in line
                    ][0]
                    return float(time_line.split("time=")[1].split(" ")[0])
            elif platform.system().lower() == "windows":
                if "time=" in output:
                    return float(output.rsplit("time=", maxsplit=1)[-1].split("ms")[0])
            elif "time=" in output:
                return float(output.rsplit("time=", maxsplit=1)[-1].split(" ")[0])
            return None
        except (subprocess.CalledProcessError, ValueError):
            return None

    def collect(self) -> dict[str, Optional[float]]:
        """Collect ping times for all targets."""
        return {target: self._ping(target) for target in self.targets}

    def check_threshold(self, value: dict[str, Optional[float]]) -> bool:
        """Check if any ping time exceeds threshold."""
        return any(
            ping_time and ping_time > self.threshold for ping_time in value.values()
        )
