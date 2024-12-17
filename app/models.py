"""SQLAlchemy models for the application."""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Alert(Base):
    """Alert model for storing monitoring alerts."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    hostname = Column(String(255), nullable=False)
    monitor_name = Column(String(255), nullable=False)
    alert_state = Column(String(50), nullable=False)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Convert alert to dictionary."""
        return {
            "id": self.id,
            "hostname": self.hostname,
            "monitor_name": self.monitor_name,
            "alert_state": self.alert_state,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
