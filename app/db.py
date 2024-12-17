"""Database management module."""

import time
from typing import Optional

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.models import Base

logger = structlog.get_logger()


def init_db(
    dsn: str, max_retries: int = 5, retry_delay: int = 5
) -> tuple[bool, Optional[str]]:  # sourcery skip: extract-duplicate-method
    """Initialize the database with retry logic.

    Args:
        dsn: Database connection string
        max_retries: Maximum number of connection attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    engine = None
    for attempt in range(max_retries):
        try:
            logger.debug(f"Database initialization attempt {attempt + 1}/{max_retries}")
            engine = create_engine(dsn, poolclass=NullPool)

            # Test connection first
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
            logger.debug("Database connection test successful")

            # Create tables if they don't exist
            Base.metadata.create_all(engine)
            logger.debug("Database tables created successfully")

            # Verify tables
            Session = sessionmaker(bind=engine)
            with Session() as session:
                session.execute(text("SELECT 1"))
                session.commit()

            logger.info("Database initialized successfully")
            return True, None

        except OperationalError as e:
            if attempt < max_retries - 1:
                logger.warning(
                    "Failed to connect to database, retrying...",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                    error=str(e),
                )
                time.sleep(retry_delay)
            else:
                error_msg = (
                    f"Database connection failed after {max_retries} attempts: {str(e)}"
                )
                logger.error(error_msg)
                return False, error_msg

        except SQLAlchemyError as e:
            error_msg = f"Database initialization failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error during database initialization: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

        finally:
            if engine:
                engine.dispose()

    return False, "Maximum retries exceeded"


def get_session(dsn: str) -> Optional[Session]:
    """Get a database session with retry logic.

    Args:
        dsn: Database connection string

    Returns:
        Optional[Session]: Database session or None if connection fails
    """
    engine = None
    try:
        engine = create_engine(dsn, poolclass=NullPool)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Test the session
        session.execute(text("SELECT 1"))
        session.commit()

        return session
    except Exception as e:
        logger.error("Failed to create database session", error=str(e))
        if engine:
            engine.dispose()
        return None
