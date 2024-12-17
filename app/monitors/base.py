"""Base monitor class."""

from abc import abstractmethod
from typing import Any

from app.core.monitor import Monitor as CoreMonitor


class Monitor(CoreMonitor):
    """Base monitor class."""

    def __init__(self, name: str, config: dict[str, Any], silent: bool = False):
        """Initialize monitor.

        Args:
            name: Name of the monitor
            config: Configuration dictionary
            silent: If True, suppress all logging from this monitor
        """
        super().__init__(name, config, silent)

    @abstractmethod
    def collect(self) -> Any:
        """Collect metric value."""
        pass

    @abstractmethod
    def check_threshold(self, value: Any) -> bool:
        """Check if metric value exceeds threshold."""
        pass
