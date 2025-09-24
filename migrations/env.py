# migrations/env.py
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Explicit imports so Alembic sees tables on Base.metadata
from app.models.chapter import Chapter      # noqa: F401
from app.models.user import User            # noqa: F401
from app.models.read_event import ReadEvent # noqa: F401

# Secret Key
SECRET_KEY=a654sdfga654df6DFKJHIUY8ljkadfsg89077908asdfg

# --- Make project importable (run alembic from repo root) ---
# /home/kirk/echoline/migrations/env.py -> add ../../ to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# --- Load env and inject DATABASE_URL into Alembic config ---
from dotenv import load_dotenv
load_dotenv()

config = context.config
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# --- Configure logging from alembic.ini ---
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Import Base + models so autogenerate can see tables ---
from app.db.base import Base  # this is the declarative_base()

# Import *all* models to register them on Base.metadata.
# If you keep app/models/__init__.py updated, this one import is enough:
import app.models  # noqa: F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # detect type/nullable/length changes
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (uses an Engine connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detect type/nullable/length changes
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()