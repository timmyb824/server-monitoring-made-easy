"""Memory monitor."""

import os
import platform
from typing import Any

import psutil
import structlog

from .base import Monitor

logger = structlog.get_logger()


def read_cgroup_memory() -> tuple[int, int]:
    """Read memory stats from cgroup."""
    try:
        # Check if we're on Linux
        is_linux = platform.system() == "Linux"
        meminfo_path = (
            "/host/proc/meminfo"
            if (is_linux and os.path.exists("/host/proc"))
            else "/proc/meminfo"
        )

        if not is_linux:
            logger.warning(
                "Container memory monitoring is only fully supported on Linux hosts. "
                "On non-Linux systems (like macOS), container memory metrics will reflect "
                "the VM's memory usage, not the host system.",
                platform=platform.system(),
            )

        with open(meminfo_path, "r") as f:
            meminfo = f.read()

        # Log raw meminfo for debugging
        logger.debug("Raw meminfo", content=meminfo, source=meminfo_path)

        # Parse meminfo
        lines = meminfo.strip().split("\n")
        stats = {}
        for line in lines:
            fields = line.split()
            if len(fields) < 2:
                continue
            stats[fields[0].rstrip(":")] = int(fields[1]) * 1024  # Convert to bytes

        total = stats.get("MemTotal", 0)
        available = stats.get("MemAvailable", 0)

        # Log all memory stats for debugging
        logger.debug("Parsed meminfo", stats=stats)

        return total, available
    except Exception as e:
        logger.error("Failed to read cgroup memory", error=str(e))
        return 0, 0


class MemoryMonitor(Monitor):
    """Monitor memory usage."""

    def __init__(self, name: str, config: dict[str, Any], silent: bool = False):
        """Initialize memory monitor.

        Args:
            name: Name of the monitor
            config: Configuration dictionary
            silent: If True, suppress all logging from this monitor
        """
        super().__init__(name, config, silent)

    def collect(self) -> float:
        """Collect memory usage percentage.

        When running in a container with pid=host, this will return the host's
        memory usage by reading directly from /proc/meminfo.
        """
        # Check if we're running in a container
        in_container = os.getenv("CONTAINER") == "1"

        if in_container:
            # When in container, read directly from /proc/meminfo
            total, available = read_cgroup_memory()
            if total == 0:
                # Fallback to psutil if cgroup reading fails
                memory = psutil.virtual_memory()
                total = memory.total
                available = memory.available
                logger.debug("Using psutil fallback", memory=memory._asdict())
        else:
            # When running directly on host, use psutil
            memory = psutil.virtual_memory()
            total = memory.total
            available = memory.available
            logger.debug("Using psutil on host", memory=memory._asdict())

        # Log detailed memory information
        logger.debug(
            "Memory details",
            total=total,
            available=available,
            in_container=in_container,
        )

        if total == 0:
            logger.error("Failed to get memory information")
            return 0.0

        used = total - available
        percent = (used / total) * 100

        logger.debug(
            "Memory calculation",
            total=total,
            used=used,
            available=available,
            percent=percent,
        )

        return percent

    def check_threshold(self, value: float) -> bool:
        """Check if memory usage exceeds threshold."""
        return value > self.threshold
