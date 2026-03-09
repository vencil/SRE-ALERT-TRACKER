"""Alembic env — integrates with project config.py and models."""

from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Project imports — all models must be imported so metadata is populated.
from config import settings  # noqa: E402
from database import Base  # noqa: E402

# Import all model modules to register them on Base.metadata.
import models.alert_record  # noqa: F401, E402
import models.cluster  # noqa: F401, E402
import models.daily_section  # noqa: F401, E402
import models.label  # noqa: F401, E402
import models.shift_report  # noqa: F401, E402
import models.weekly_task  # noqa: F401, E402
import models.filter_rule  # noqa: F401, E402
import models.maintenance_window  # noqa: F401, E402
import models.poller_config  # noqa: F401, E402
import models.retention_config  # noqa: F401, E402

# Alembic Config object
config = context.config

# Set sqlalchemy.url from our config.py (overrides alembic.ini placeholder)
config.set_main_option("sqlalchemy.url", settings.effective_database_url)

# Ensure SQLite data directory exists (needed for alembic upgrade)
if settings.is_sqlite:
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script generation)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (direct DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
