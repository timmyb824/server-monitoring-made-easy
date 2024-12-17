"""Core monitoring functionality for Server Monitoring Made Easy."""

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


class Monitor(ABC):
    """Base class for all monitors."""

    def __init__(self, name: str, config: dict[str, Any], silent: bool = False):
        """Initialize the monitor.

        Args:
            name: Name of the monitor
            config: Configuration dictionary for the monitor
            silent: If True, suppress all logging from this monitor
        """
        self.name = name
        self.enabled = config.get("enabled", True)
        self.interval = config.get("interval", 60)  # Default 60 seconds
        self.threshold = config.get("threshold")
        self.alert_count = config.get(
            "alert_count", 3
        )  # Alert after N consecutive failures
        self.last_check = 0
        self.last_value = None
        self.alert_state = "OK"
        self.consecutive_failures = 0
        self.logger = logger.bind(monitor=name)
        self.silent = silent

        if not self.silent:
            self.logger.info(
                "Monitor initialized",
                enabled=self.enabled,
                interval=self.interval,
                threshold=self.threshold,
                alert_count=self.alert_count,
            )

    @abstractmethod
    def collect(self) -> Any:
        """Collect the metric value.

        Returns:
            The collected metric value
        """
        pass

    @abstractmethod
    def check_threshold(self, value: Any) -> bool:
        """Check if the collected value exceeds the threshold.

        Args:
            value: The value to check

        Returns:
            True if threshold is exceeded, False otherwise
        """
        pass

    def should_check(self) -> bool:
        """Determine if it's time to check the metric again."""
        current_time = time.time()
        time_since_last = current_time - self.last_check
        should_check = time_since_last >= self.interval

        if not self.silent:
            self.logger.debug(
                "Check timing",
                current_time=current_time,
                last_check=self.last_check,
                time_since_last=time_since_last,
                interval=self.interval,
                should_check=should_check,
            )
        return should_check

    def check(self) -> Optional[dict[str, Any]]:
        """Perform the monitoring check.

        Returns:
            Alert dictionary if threshold is exceeded, None otherwise
        """
        if not self.enabled:
            if not self.silent:
                self.logger.debug("Monitor is disabled")
            return None

        if not self.should_check():
            if not self.silent:
                self.logger.debug("Not time to check yet")
            return None

        try:
            value = self.collect()
            self.last_check = time.time()
            self.last_value = value

            if not self.silent:
                self.logger.info(
                    "Metric collected",
                    value=value,
                    threshold=self.threshold,
                    consecutive_failures=self.consecutive_failures,
                )

            if self.check_threshold(value):
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.alert_count:
                    if self.alert_state == "OK":
                        self.alert_state = "FIRING"
                        if not self.silent:
                            self.logger.warning(
                                "Threshold exceeded",
                                value=value,
                                threshold=self.threshold,
                                failures=self.consecutive_failures,
                            )
                        return {
                            "monitor": self.name,
                            "state": "FIRING",
                            "value": value,
                            "threshold": self.threshold,
                            "timestamp": self.last_check,
                            "consecutive_failures": self.consecutive_failures,
                        }
                elif not self.silent:
                    self.logger.info(
                        "Threshold exceeded but under alert count",
                        value=value,
                        threshold=self.threshold,
                        failures=self.consecutive_failures,
                        required=self.alert_count,
                    )
            else:
                if self.consecutive_failures > 0 and not self.silent:
                    self.logger.info(
                        "Resetting consecutive failures",
                        old_failures=self.consecutive_failures,
                    )
                self.consecutive_failures = 0
                if self.alert_state == "FIRING":
                    self.alert_state = "OK"
                    if not self.silent:
                        self.logger.info(
                            "Alert resolved",
                            value=value,
                            threshold=self.threshold,
                        )
                    return {
                        "monitor": self.name,
                        "state": "OK",
                        "value": value,
                        "threshold": self.threshold,
                        "timestamp": self.last_check,
                    }

        except Exception as e:
            if not self.silent:
                self.logger.error(
                    "Error collecting metric",
                    error=str(e),
                    exc_info=True,
                )
            return {
                "monitor": self.name,
                "state": "ERROR",
                "error": str(e),
                "timestamp": time.time(),
            }

    def get_status(self) -> dict[str, Any]:
        """Get the current status of the monitor.

        Returns:
            Dictionary containing the monitor's current status
        """
        return {
            "name": self.name,
            "enabled": self.enabled,
            "state": self.alert_state,
            "last_check": self.last_check,
            "last_value": self.last_value,
            "threshold": self.threshold,
            "interval": self.interval,
        }
