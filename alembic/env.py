from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Pastikan project root masuk sys.path agar import app.* bisa dilakukan
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings  # noqa: E402
from app.db.database import Base  # noqa: E402
from app.db import models  # noqa: E402, F401 — import agar metadata terdaftar

# Objek konfigurasi Alembic (dari alembic.ini)
config = context.config

# Setup logging dari alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database URL dari Settings app (satu sumber kebenaran)
config.set_main_option("sqlalchemy.url", get_settings().database_url)

# Metadata target untuk autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Jalankan migration dalam mode 'offline' (tanpa koneksi aktif)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # render_as_batch wajib untuk SQLite agar bisa ALTER COLUMN
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Jalankan migration dalam mode 'online' (dengan koneksi aktif)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # render_as_batch wajib untuk SQLite agar bisa ALTER COLUMN
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
