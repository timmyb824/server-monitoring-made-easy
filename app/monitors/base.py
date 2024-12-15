"""Base monitor class."""

from abc import ABC, abstractmethod
from typing import Any

from app.core.monitor import Monitor as CoreMonitor


class Monitor(CoreMonitor):
    """Base monitor class."""

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize monitor.

        Args:
            name: Name of the monitor
            config: Configuration dictionary
        """
        super().__init__(name, config)

    @abstractmethod
    def collect(self) -> Any:
        """Collect metric value."""
        pass

    @abstractmethod
    def check_threshold(self, value: Any) -> bool:
        """Check if metric value exceeds threshold."""
        pass
