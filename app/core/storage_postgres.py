"""PostgreSQL storage backend for alert persistence."""

import time
from datetime import datetime
from typing import List, Optional

import structlog
from sqlalchemy import and_, create_engine, or_, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.storage import AlertStorage
from app.db import get_session, init_db
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
        self._Session = None

        # Try to initialize the database with retries
        max_retries = 5
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                # Test the connection first
                engine = create_engine(dsn)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    conn.commit()

                # If connection successful, initialize the database
                init_db(dsn)
                self._Session = sessionmaker(bind=engine)
                self.logger.info("Database connection and initialization successful")
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
                self.logger.error("Failed to initialize database", error=str(e))
                raise

    def _get_session(self) -> Session:
        """Get a new database session."""
        if self._Session is None:
            engine = create_engine(self.dsn)
            self._Session = sessionmaker(bind=engine)
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
            raise
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
            raise
        finally:
            if session:
                session.close()

    def get_active_alerts(self) -> List[dict]:
        """Get all currently active alerts."""
        session = None
        try:
            self.logger.debug("Creating new session for active alerts query")
            session = self._get_session()

            self.logger.debug("Executing active alerts query")
            alerts = session.query(Alert).filter(Alert.resolved_at.is_(None)).all()
            self.logger.debug(f"Found {len(alerts)} active alerts")

            # Convert alerts to dictionaries
            alert_list = []
            for alert in alerts:
                try:
                    alert_dict = alert.details
                    alert_list.append(alert_dict)
                    self.logger.debug("Processed alert", alert_id=alert.id)
                except Exception as e:
                    self.logger.error(
                        "Failed to process alert details",
                        alert_id=getattr(alert, "id", "unknown"),
                        error=str(e),
                    )

            self.logger.debug(f"Successfully processed {len(alert_list)} alerts")
            return alert_list

        except Exception as e:
            self.logger.error(
                "Failed to get active alerts", error=str(e), exc_info=True
            )
            return []
        finally:
            if session:
                try:
                    session.close()
                    self.logger.debug("Database session closed")
                except Exception as e:
                    self.logger.error("Error closing database session", error=str(e))

    def get_alert_history(
        self,
        monitor_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[dict]:
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
            return [alert.details for alert in alerts]
        except Exception as e:
            self.logger.error(
                "Failed to get alert history", error=str(e), exc_info=True
            )
            return []
        finally:
            if session:
                session.close()
