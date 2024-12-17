"""Storage backends for alert persistence."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class AlertStorage(ABC):
    """Abstract base class for alert storage backends."""

    @abstractmethod
    def save_alert(self, alert: dict) -> None:
        """Save an alert to storage.

        Args:
            alert: Alert dictionary containing monitor name, state, and details
        """
        pass

    @abstractmethod
    def resolve_alert(self, monitor_name: str, resolved_at: datetime) -> None:
        """Mark an alert as resolved.

        Args:
            monitor_name: Name of the monitor that generated the alert
            resolved_at: Timestamp when the alert was resolved
        """
        pass

    @abstractmethod
    def get_active_alerts(self) -> list[dict]:
        """Get all currently active (unresolved) alerts.

        Returns:
            List of active alert dictionaries
        """
        pass

    @abstractmethod
    def get_alert_history(
        self,
        monitor_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[dict]:
        """Get alert history with optional filters.

        Args:
            monitor_name: Optional monitor name to filter by
            start_time: Optional start time for the query
            end_time: Optional end time for the query

        Returns:
            List of alert dictionaries matching the criteria
        """
        pass
