"""Schema bootstrapping: alembic migrations with a create_all fallback.

- Fresh databases are provisioned through `alembic upgrade head`.
- Databases already created by metadata.create_all (no alembic_version) are
  left for create_all, which is idempotent and remains the dev/test path.
- If alembic is not installed, create_all is used (dev-only safety net).
"""

import logging
import os

from models.base import Base

logger = logging.getLogger(__name__)

_BACKEND_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_ALEMBIC_INI = os.path.join(_BACKEND_ROOT, "alembic.ini")


def run_migrations(engine) -> None:
    """Ensure the schema exists, preferring alembic migrations."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    app_tables = tables - {"alembic_version"}

    if app_tables and "alembic_version" not in tables:
        logger.info("Schema pre-exists without alembic bookkeeping; using create_all.")
        Base.metadata.create_all(bind=engine)
        return

    try:
        from alembic import command  # noqa: F401
        from alembic.config import Config
    except ImportError:
        logger.warning("alembic not installed; falling back to create_all.")
        Base.metadata.create_all(bind=engine)
        return

    config = Config(_ALEMBIC_INI)
    config.set_main_option(
        "script_location", os.path.join(_BACKEND_ROOT, "alembic")
    )
    command.upgrade(config, "head")
    logger.info("Alembic schema is at head.")
    Base.metadata.create_all(bind=engine)