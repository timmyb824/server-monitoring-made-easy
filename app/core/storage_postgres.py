"""PostgreSQL storage backend for alert persistence."""

import time
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import and_, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.storage import AlertStorage
from app.models import Alert

logger = structlog.get_logger()


class PostgresAlertStorage(AlertStorage):
    """PostgreSQL implementation of alert storage."""

    def __init__(self, dsn: str):
        """Initialize PostgreSQL storage.

        Args:
            dsn: PostgreSQL connection string
        """
        self.dsn = dsn
        self.logger = logger.bind(component="PostgresAlertStorage")
        self._engine = None
        self._Session = None

        # Try to initialize the database connection
        max_retries = 5
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                # Create engine with NullPool to prevent connection pooling issues
                self._engine = create_engine(dsn, poolclass=NullPool)

                # Test the connection
                with self._engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    conn.commit()

                # Set up session maker
                self._Session = sessionmaker(bind=self._engine)
                self.logger.info("Database connection successful")
                break

            except OperationalError as e:
                if attempt < max_retries - 1:
                    self.logger.warning(
                        "Failed to connect to database, retrying...",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e),
                    )
                    time.sleep(retry_delay)
                else:
                    self.logger.error(
                        "Failed to connect to database after all retries", error=str(e)
                    )
                    raise
            except Exception as e:
                self.logger.error(
                    "Failed to initialize database connection", error=str(e)
                )
                if self._engine:
                    self._engine.dispose()
                raise

    def _get_session(self) -> Session:
        """Get a new database session."""
        if self._Session is None:
            self._engine = create_engine(self.dsn, poolclass=NullPool)
            self._Session = sessionmaker(bind=self._engine)
        return self._Session()

    def save_alert(self, alert_data: dict) -> None:
        """Save an alert to storage."""
        session = None
        try:
            session = self._get_session()
            alert = Alert(
                hostname=alert_data.get("hostname", "unknown"),
                monitor_name=alert_data["monitor"],
                alert_state=alert_data["state"],
                details=alert_data,
                created_at=datetime.fromtimestamp(alert_data["timestamp"]),
            )
            session.add(alert)
            session.commit()
            self.logger.debug("Alert saved successfully", alert_id=alert.id)
        except Exception as e:
            self.logger.error("Failed to save alert", error=str(e), exc_info=True)
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    def resolve_alert(self, monitor_name: str, resolved_at: datetime) -> None:
        """Mark an alert as resolved."""
        session = None
        try:
            session = self._get_session()
            alerts = (
                session.query(Alert)
                .filter(
                    and_(
                        Alert.monitor_name == monitor_name, Alert.resolved_at.is_(None)
                    )
                )
                .all()
            )
            for alert in alerts:
                alert.resolved_at = resolved_at
                alert.alert_state = "RESOLVED"
            session.commit()
            self.logger.debug(
                f"Resolved {len(alerts)} alerts for monitor", monitor=monitor_name
            )
        except Exception as e:
            self.logger.error("Failed to resolve alert", error=str(e), exc_info=True)
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    def get_active_alerts(self) -> list[dict]:
        """Get list of currently active alerts.

        Returns:
            List of active alert dictionaries
        """
        session = None
        try:
            session = self._get_session()
            alerts = (
                session.query(Alert)
                .filter(Alert.resolved_at.is_(None))
                .order_by(Alert.created_at.desc())
                .all()
            )
            return [
                {
                    "id": alert.id,
                    "hostname": alert.hostname,
                    "monitor": alert.monitor_name,
                    "state": alert.alert_state,
                    "details": alert.details,
                    "timestamp": alert.created_at.timestamp(),
                }
                for alert in alerts
            ]
        except Exception as e:
            self.logger.error(
                "Failed to get active alerts", error=str(e), exc_info=True
            )
            return []  # Return empty list on error
        finally:
            if session:
                session.close()

    def get_alert_history(
        self,
        monitor_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[dict]:
        """Get alert history with optional filters."""
        session = None
        try:
            session = self._get_session()
            query = session.query(Alert)

            # Apply filters
            if monitor_name:
                query = query.filter(Alert.monitor_name == monitor_name)
            if start_time:
                query = query.filter(Alert.created_at >= start_time)
            if end_time:
                query = query.filter(Alert.created_at <= end_time)

            # Order by creation time
            query = query.order_by(Alert.created_at.desc())

            alerts = query.all()
            return [
                {
                    "id": alert.id,
                    "hostname": alert.hostname,
                    "monitor": alert.monitor_name,
                    "state": alert.alert_state,
                    "details": alert.details,
                    "timestamp": alert.created_at.timestamp(),
                }
                for alert in alerts
            ]
        except Exception as e:
            self.logger.error(
                "Failed to get alert history", error=str(e), exc_info=True
            )
            return []  # Return empty list on error
        finally:
            if session:
                session.close()

    def __del__(self):
        """Clean up database connections."""
        if self._engine:
            self._engine.dispose()
