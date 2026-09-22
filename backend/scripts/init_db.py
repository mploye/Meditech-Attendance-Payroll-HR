"""Initialize the database schema by importing models and creating tables.

Usage:
    python -m scripts.init_db
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from sqlalchemy import inspect

from core.database import engine
from models import Base  # noqa: F401  imports register all models


def main() -> None:
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    Base.metadata.create_all(bind=engine)
    new_tables = sorted(set(Base.metadata.tables.keys()) - existing)
    print(f"Total tables in metadata: {len(Base.metadata.tables)}")
    print(f"Created new tables: {new_tables}")


if __name__ == "__main__":
    main()