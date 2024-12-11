"""Alert management system for Server Monitoring Made Easy."""

import time

import apprise
import structlog

logger = structlog.get_logger()


class AlertManager:
    """Manages alerts and notifications."""

    def __init__(self, config: dict):
        """Initialize the alert manager.

        Args:
            config: Configuration dictionary containing notification settings
        """
        self.config = config
        self.apprise = apprise.Apprise()
        self.active_alerts: dict[str, dict] = {}
        self.logger = logger.bind(component="AlertManager")

        self._setup_notifications()

    def _setup_notifications(self):
        """Set up notification channels from config."""
        notifications = self.config.get("notifications", [])

        for notifier in notifications:
            if not notifier.get("enabled", True):
                self.logger.debug(
                    f"Skipping disabled notification type: {notifier.get('type')}"
                )
                continue

            uri = notifier.get("uri")
            if not uri:
                self.logger.error(
                    f"Missing URI for notification type: {notifier.get('type')}"
                )
                continue

            try:
                self.apprise.add(uri)
                self.logger.debug(f"Added notification service: {notifier.get('type')}")
            except Exception as e:
                self.logger.error(
                    "Failed to add notification service",
                    type=notifier.get("type"),
                    error=str(e),
                )

    def process_alert(self, alert: dict) -> None:
        """Process an incoming alert.

        Args:
            alert: Alert dictionary containing monitor name, state, and details
        """
        monitor_name = alert["monitor"]

        if alert["state"] == "FIRING":
            if monitor_name not in self.active_alerts:
                self.active_alerts[monitor_name] = alert
                self._send_notification(
                    f"🚨 Alert: {monitor_name}", self._format_alert_message(alert)
                )

        elif alert["state"] == "OK":
            if monitor_name in self.active_alerts:
                self._send_notification(
                    f"✅ Resolved: {monitor_name}", self._format_resolve_message(alert)
                )
                del self.active_alerts[monitor_name]

        elif alert["state"] == "ERROR":
            self._send_notification(
                f"⚠️ Error: {monitor_name}",
                f"Error collecting metric: {alert.get('error', 'Unknown error')}",
            )

    def _format_alert_message(self, alert: dict) -> str:
        """Format alert message for notification.

        Args:
            alert: Alert dictionary

        Returns:
            Formatted message string
        """
        return (
            f"Monitor: {alert['monitor']}\n"
            f"State: {alert['state']}\n"
            f"Value: {alert.get('value')}\n"
            f"Threshold: {alert.get('threshold')}\n"
            f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert['timestamp']))}"
        )

    def _format_resolve_message(self, alert: dict) -> str:
        """Format resolve message for notification.

        Args:
            alert: Alert dictionary

        Returns:
            Formatted message string
        """
        return (
            f"Monitor: {alert['monitor']}\n"
            f"State: Resolved\n"
            f"Current Value: {alert.get('value')}\n"
            f"Threshold: {alert.get('threshold')}\n"
            f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert['timestamp']))}"
        )

    def _send_notification(self, title: str, body: str) -> None:
        """Send notification through configured channels.

        Args:
            title: Notification title
            body: Notification body
        """
        try:
            self.apprise.notify(title=title, body=body)
        except Exception as e:
            self.logger.error("Failed to send notification", error=str(e), title=title)

    def get_active_alerts(self) -> list[dict]:
        """Get list of currently active alerts.

        Returns:
            List of active alert dictionaries
        """
        return list(self.active_alerts.values())
