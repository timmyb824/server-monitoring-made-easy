import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import apprise
import yaml

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration from config.yaml file."""
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config file: {str(e)}")
        return {"notifications": []}


async def send_notification_async(
    message: str, title: str = "Server Monitor Alert"
) -> None:
    """Send notification asynchronously using Apprise with config file."""

    def notify_sync():
        config = load_config()
        notifications = config.get("notifications", [])

        if not notifications:
            logger.warning("No notifications configured")
            return

        apobj = apprise.Apprise()

        # Add all configured notification services
        for notification in notifications:
            if not notification.get("enabled", True):
                logger.debug(
                    f"Skipping disabled notification of type: {notification.get('type', 'unknown')}"
                )
                continue

            notification_type = notification.get("type", "unknown")
            uri = notification.get("uri")

            if not uri:
                logger.error(f"Missing URI for notification type: {notification_type}")
                continue

            try:
                apobj.add(uri)
                logger.info(
                    f"Successfully added {notification_type} notification service"
                )
            except Exception as e:
                logger.error(
                    f"Failed to add {notification_type} notification service: {str(e)}"
                )

        # Send the notification
        try:
            result = apobj.notify(body=message, title=title)
            if result:
                logger.info("Successfully sent notifications")
            else:
                logger.error("Failed to send notifications")
        except Exception as e:
            logger.error(f"Error sending notifications: {str(e)}")

    loop = asyncio.get_running_loop()
    # Run the synchronous notification function in a separate thread
    await loop.run_in_executor(ThreadPoolExecutor(), notify_sync)
