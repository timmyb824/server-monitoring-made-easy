import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.models import Base

logger = logging.getLogger("alembic.env")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    logger.info("Running offline migrations with URL: %s", url)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        logger.info("Starting offline migrations")
        context.run_migrations()
        logger.info("Completed offline migrations")


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    logger.info("Starting online migrations")

    # Create SQLAlchemy engine
    configuration = config.get_section(config.config_ini_section)
    if not configuration:
        logger.error("No configuration found")
        return

    logger.info("Creating database engine")
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        logger.info("Connected to database")
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            logger.info("Starting migration transaction")
            context.run_migrations()
            logger.info("Completed migration transaction")

    logger.info("Completed online migrations")


if context.is_offline_mode():
    logger.info("Running in offline mode")
    run_migrations_offline()
else:
    logger.info("Running in online mode")
    run_migrations_online()
