"""File-based storage backend for Server Monitoring Made Easy."""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

import structlog

from app.core.storage import AlertStorage

logger = structlog.get_logger()


class FileAlertStorage(AlertStorage):
    """File-based storage for alerts."""

    def __init__(self, file_path: str, pruning_config: Optional[Dict] = None):
        """Initialize file storage.

        Args:
            file_path: Path to the JSON file for storing alerts
            pruning_config: Optional configuration for alert pruning
        """
        self.logger = logger.bind(component="FileAlertStorage")
        self.file_path = file_path
        self.data_dir = os.path.dirname(file_path)
        self.pruning_config = pruning_config or {}

        # Create directory if it doesn't exist
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, mode=0o755, exist_ok=True)

        # Initialize storage file if it doesn't exist
        if not os.path.exists(file_path):
            self._write_data({"active_alerts": {}, "alert_history": []})

        self.logger.info("File storage initialized", file_path=file_path)

    def _read_data(self) -> dict:
        """Read data from storage file."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error("Error reading storage file", error=str(e))
            return {"active_alerts": {}, "alert_history": []}

    def _write_data(self, data: dict):
        """Write data to storage file."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            self.logger.error("Error writing to storage file", error=str(e))

    def _prune_alerts(self, data: dict) -> dict:  # sourcery skip: extract-method
        """Prune old alerts based on configuration.

        Args:
            data: Current alert data

        Returns:
            Pruned alert data
        """
        if not self.pruning_config.get("enabled", False):
            return data

        try:
            max_age_days = self.pruning_config.get("max_age_days", 30)
            max_alerts = self.pruning_config.get("max_alerts", 1000)
            current_time = time.time()
            cutoff_time = current_time - (max_age_days * 24 * 60 * 60)

            # Filter alerts by age
            alert_history = data["alert_history"]
            alert_history = [
                alert
                for alert in alert_history
                if alert.get("timestamp", 0) > cutoff_time
            ]

            # Sort by timestamp (newest first) and limit to max_alerts
            alert_history.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            alert_history = alert_history[:max_alerts]

            # Update data with pruned history
            data["alert_history"] = alert_history

            self.logger.debug(
                "Pruned alerts",
                original_count=len(data["alert_history"]),
                pruned_count=len(alert_history),
                max_age_days=max_age_days,
                max_alerts=max_alerts,
            )

            return data
        except Exception as e:
            self.logger.error("Error pruning alerts", error=str(e))
            return data

    def save_alert(self, alert: dict):  # sourcery skip: class-extract-method
        """Save a new alert."""
        try:
            data = self._read_data()
            monitor_name = alert["monitor"]

            # Store in active alerts
            data["active_alerts"][monitor_name] = alert

            # Add to history
            data["alert_history"].append(alert)

            # Prune old alerts
            data = self._prune_alerts(data)

            self._write_data(data)
            self.logger.debug("Alert saved", monitor=monitor_name)
        except Exception as e:
            self.logger.error("Error saving alert", error=str(e))
            raise

    def resolve_alert(self, monitor_name: str, resolved_at: datetime):
        # sourcery skip: extract-method
        """Mark an alert as resolved."""
        try:
            data = self._read_data()

            if monitor_name in data["active_alerts"]:
                alert = data["active_alerts"][monitor_name]
                alert["resolved_at"] = resolved_at

                # Remove from active alerts
                del data["active_alerts"][monitor_name]

                # Update history
                data["alert_history"].append(alert)

                # Prune old alerts
                data = self._prune_alerts(data)

                self._write_data(data)
                self.logger.debug("Alert resolved", monitor=monitor_name)
        except Exception as e:
            self.logger.error("Error resolving alert", error=str(e))
            raise

    def get_active_alerts(self) -> List[Dict]:
        """Get all active alerts."""
        try:
            data = self._read_data()
            return list(data["active_alerts"].values())
        except Exception as e:
            self.logger.error("Error getting active alerts", error=str(e))
            return []

    def get_alert_history(
        self,
        monitor_name: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[Dict]:
        """Get alert history with optional filters."""
        try:
            data = self._read_data()
            alerts = data["alert_history"]

            # Apply filters
            if monitor_name:
                alerts = [a for a in alerts if a["monitor"] == monitor_name]
            if start_time:
                alerts = [a for a in alerts if a["timestamp"] >= start_time]
            if end_time:
                alerts = [a for a in alerts if a["timestamp"] <= end_time]

            return alerts
        except Exception as e:
            self.logger.error("Error getting alert history", error=str(e))
            return []
