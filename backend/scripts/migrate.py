"""Pre-deploy schema migration: ``python -m backend.scripts.migrate``.

Run before the new release starts (Railway ``preDeployCommand``, CI or a
one-off task). The API no longer alters the schema at startup.

* Fresh database (no tables): create the current schema and stamp head.
* Legacy database created by the old startup ``create_all``/ALTER loop
  (tables but no ``alembic_version``): stamp the last revision that loop
  covered, then upgrade - every later migration is idempotent.
* Otherwise: ``alembic upgrade head``.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

LEGACY_BASELINE = "f3e7bed01971"
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("migrate")


def main() -> int:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from backend.app.database import engine
    from backend.app.models.registry import import_all_models

    metadata = import_all_models()
    config = Config(str(ALEMBIC_INI))
    tables = set(inspect(engine).get_table_names())
    if "users" not in tables:
        log.info("Fresh database: creating schema and stamping head")
        metadata.create_all(engine)
        command.stamp(config, "head")
        return 0
    if "alembic_version" not in tables:
        log.info("Legacy database without alembic_version: stamping %s", LEGACY_BASELINE)
        command.stamp(config, LEGACY_BASELINE)
    command.upgrade(config, "head")
    log.info("Schema is at head")
    return 0


if __name__ == "__main__":
    sys.exit(main())
