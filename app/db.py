"""Database management module."""

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

logger = structlog.get_logger()


def init_db(dsn: str) -> None:
    """Initialize the database.

    Args:
        dsn: Database connection string
    """
    try:
        logger.debug("Creating database engine")
        engine = create_engine(dsn)

        logger.debug("Creating database tables")
        Base.metadata.create_all(engine)

        # Test the connection with a simple query
        Session = sessionmaker(bind=engine)
        with Session() as session:
            session.execute(text("SELECT 1"))
            session.commit()

        logger.info("Database initialized successfully")
    except SQLAlchemyError as e:
        logger.error("Database initialization failed", error=str(e), exc_info=True)
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during database initialization",
            error=str(e),
            exc_info=True,
        )
        raise


def get_session(dsn: str) -> Session:
    """Get a database session.

    Args:
        dsn: Database connection string

    Returns:
        SQLAlchemy session
    """
    try:
        engine = create_engine(dsn)
        Session = sessionmaker(bind=engine)
        return Session()
    except SQLAlchemyError as e:
        logger.error("Failed to create database session", error=str(e), exc_info=True)
        raise
    except Exception as e:
        logger.error(
            "Unexpected error creating database session", error=str(e), exc_info=True
        )
        raise
