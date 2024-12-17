"""Alert management system for Server Monitoring Made Easy."""

import socket
import time
from datetime import datetime

import apprise
import structlog

from app.core.storage_file import FileAlertStorage
from app.core.storage_postgres import PostgresAlertStorage

logger = structlog.get_logger()


class AlertManager:
    """Manages alerts and notifications."""

    def __init__(self, config: dict):
        """Initialize the alert manager.

        Args:
            config: Configuration dictionary containing notification settings
        """
        self.logger = logger.bind(component="AlertManager")
        self.logger.debug("Starting AlertManager initialization")

        try:
            self.config = config
            self.logger.debug("Config loaded", config=config)

            self.apprise = apprise.Apprise()
            self.logger.debug("Apprise instance created")

            self.hostname = socket.gethostname()
            self.logger.debug(f"Hostname set to: {self.hostname}")

            # Initialize storage backend
            storage_config = config.get("storage", {})
            self.logger.debug("Storage config loaded", config=storage_config)

            storage_type = storage_config.get("type")
            if storage_type == "postgres":
                dsn = storage_config.get("dsn", "")
                if not dsn:
                    self.logger.error("PostgreSQL DSN not configured")
                    raise ValueError("PostgreSQL DSN not configured")
                self.logger.debug("Initializing PostgreSQL storage")
                try:
                    self.storage = PostgresAlertStorage(dsn)
                    self.logger.debug("PostgreSQL storage initialized successfully")
                except Exception as e:
                    self.logger.warning(
                        "Failed to initialize PostgreSQL storage, falling back to file storage",
                        error=str(e),
                        exc_info=True,
                    )
                    # Fall back to file storage
                    file_path = "/home/sme/data/alerts.json"  # Default fallback path
                    self.logger.info(f"Using fallback file storage at {file_path}")
                    self.storage = FileAlertStorage(file_path)
            elif storage_type == "file":
                file_path = storage_config.get("file_path")
                if not file_path:
                    self.logger.error("File path not configured")
                    raise ValueError("File path not configured")
                self.logger.debug("Initializing file storage")
                try:
                    pruning_config = storage_config.get("pruning", {})
                    self.storage = FileAlertStorage(file_path, pruning_config)
                    self.logger.debug(
                        "File storage initialized successfully",
                        pruning_enabled=pruning_config.get("enabled", False),
                    )
                except Exception as e:
                    self.logger.error(
                        "Failed to initialize file storage", error=str(e), exc_info=True
                    )
                    raise
            else:
                self.logger.error("No valid storage backend configured")
                raise ValueError("No valid storage backend configured")

            self.logger.debug("Setting up notifications")
            try:
                self._setup_notifications()
                self.logger.debug("Notifications setup complete")
            except Exception as e:
                self.logger.error(
                    "Failed to setup notifications", error=str(e), exc_info=True
                )
                raise

            # Load active alerts from storage
            self.logger.debug("Loading active alerts")
            try:
                self.active_alerts = {}
                active_alerts = self.storage.get_active_alerts()
                for alert in active_alerts:
                    try:
                        if isinstance(alert, dict) and "monitor" in alert:
                            self.active_alerts[alert["monitor"]] = alert
                            self.logger.debug(
                                "Added alert to active alerts", monitor=alert["monitor"]
                            )
                        else:
                            self.logger.warning("Invalid alert format", alert=alert)
                    except Exception as e:
                        self.logger.error(
                            "Error processing alert", alert=alert, error=str(e)
                        )
                        continue
                self.logger.info(
                    f"Successfully loaded {len(self.active_alerts)} active alerts"
                )
            except Exception as e:
                self.logger.error(
                    "Failed to load active alerts", error=str(e), exc_info=True
                )
                # Continue without active alerts
                self.active_alerts = {}

            self.logger.info("AlertManager initialization complete")

        except Exception as e:
            self.logger.error(
                "AlertManager initialization failed", error=str(e), exc_info=True
            )
            raise

    def _setup_notifications(self):
        """Set up notification channels from config."""
        notifications = self.config.get("notifications", [])
        if not notifications:
            self.logger.warning("No notification channels configured")
            return

        for notification in notifications:
            if not notification.get("enabled", True):
                continue

            notification_type = notification.get("type")
            if not notification_type:
                self.logger.warning(
                    "Notification missing type", notification=notification
                )
                continue

            try:
                if notification_type == "console":
                    # Console notifications don't need Apprise
                    continue
                # Add other notification types to Apprise
                self.apprise.add(self._build_notification_url(notification))
                self.logger.debug(
                    "Added notification channel",
                    type=notification_type,
                )
            except Exception as e:
                self.logger.error(
                    "Failed to add notification channel",
                    type=notification_type,
                    error=str(e),
                )

    def _build_notification_url(self, notification):
        """Build Apprise URL for notification channel."""
        notification_type = notification.get("type")
        if notification_type == "telegram":
            token = notification.get("token")
            chat_id = notification.get("chat_id")
            if not token or not chat_id:
                raise ValueError("Telegram notifications require token and chat_id")
            return f"tgram://{token}/{chat_id}"
        # Add other notification types here
        raise ValueError(f"Unsupported notification type: {notification_type}")

    def process_alert(self, alert):
        """Process an alert from a monitor."""
        if not alert:
            return

        try:
            monitor = alert.get("monitor")
            if not monitor:
                self.logger.error("Alert missing monitor name", alert=alert)
                return

            # Add hostname if not present
            if "hostname" not in alert:
                alert["hostname"] = self.hostname

            # Add timestamp if not present
            if "timestamp" not in alert:
                alert["timestamp"] = time.time()

            # Convert timestamp to datetime for display
            timestamp = datetime.fromtimestamp(alert["timestamp"])
            alert_state = alert.get("state", "UNKNOWN")

            if alert_state == "FIRING":
                try:
                    self.storage.save_alert(alert)
                    self.active_alerts[monitor] = alert
                    self._send_notification(
                        f"🚨 Alert from {monitor} on {self.hostname}",
                        f"State: {alert_state}\nValue: {alert.get('value')}\nThreshold: {alert.get('threshold')}\nTime: {timestamp}",
                    )
                except Exception as e:
                    self.logger.error(
                        "Failed to save alert", error=str(e), exc_info=True
                    )
            elif alert_state == "OK":
                if monitor in self.active_alerts:
                    try:
                        self.storage.resolve_alert(monitor, timestamp)
                        del self.active_alerts[monitor]
                        self._send_notification(
                            f"✅ Alert resolved for {monitor} on {self.hostname}",
                            f"State: {alert_state}\nValue: {alert.get('value')}\nThreshold: {alert.get('threshold')}\nTime: {timestamp}",
                        )
                    except Exception as e:
                        self.logger.error(
                            "Failed to resolve alert", error=str(e), exc_info=True
                        )

        except Exception as e:
            self.logger.error(
                "Error processing alert",
                alert=alert,
                error=str(e),
                exc_info=True,
            )

    def _send_notification(self, title, body):
        """Send notification through configured channels."""
        try:
            # Always log to console
            self.logger.info(f"{title}\n{body}")

            # Send through Apprise if configured
            if self.apprise.servers:
                try:
                    self.apprise.notify(
                        title=title,
                        body=body,
                    )
                except Exception as e:
                    self.logger.error(
                        "Failed to send notification through Apprise",
                        error=str(e),
                        exc_info=True,
                    )
        except Exception as e:
            self.logger.error(
                "Error sending notification",
                error=str(e),
                exc_info=True,
            )

    def get_active_alerts(self) -> list[dict]:
        """Get list of currently active alerts.

        Returns:
            List of active alert dictionaries
        """
        try:
            return list(self.active_alerts.values())
        except Exception as e:
            self.logger.error(
                "Error getting active alerts", error=str(e), exc_info=True
            )
            return []

    def get_alert_history(
        self,
        monitor_name: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
    ) -> list[dict]:
        """Get alert history with optional filters.

        Args:
            monitor_name: Optional monitor name to filter by
            start_time: Optional start time for the query
            end_time: Optional end time for the query

        Returns:
            List of alert dictionaries matching the criteria
        """
        try:
            return self.storage.get_alert_history(monitor_name, start_time, end_time)
        except Exception as e:
            self.logger.error(
                "Error getting alert history", error=str(e), exc_info=True
            )
            return []

    def create_alert(self, monitor: str, state: str, details: dict) -> None:
        """Create a new alert."""
        alert = {
            "monitor": monitor,
            "state": state,
            "details": details,
            "timestamp": time.time(),
            "hostname": self.hostname,  # Include hostname in the alert
        }
        self.process_alert(alert)
