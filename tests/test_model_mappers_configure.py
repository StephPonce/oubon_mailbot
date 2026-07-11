"""
Mapper-configuration guard (regression for the T161 shared-metadata fallout).

Consolidating every model onto one shared ``Base`` (T161) means SQLAlchemy now
configures ALL mappers together. ``configure_mappers()`` fires on the FIRST ORM
query anywhere in the app — so a single model with a relationship that lacks a
resolvable ForeignKey takes down the entire app on first request, not just one
feature. That is exactly what happened: ``ActionTemplate.creator`` referenced
``User`` with no FK on ``creator_id`` and raised ``NoForeignKeysError``.

This test imports the whole model registry and configures every mapper. If any
model ever ships a broken relationship again, this fails in CI instead of in
production on the first query.
"""

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-mapper-config")


def test_all_mappers_configure_cleanly():
    from ospra_os.database.base import Base  # noqa: F401
    from ospra_os.database.connection import _import_all_models
    from sqlalchemy.orm import configure_mappers

    _import_all_models()
    # Raises NoForeignKeysError / InvalidRequestError if any relationship in the
    # shared registry can't resolve its join. Must stay clean.
    configure_mappers()


def test_full_schema_builds_from_shared_metadata():
    """create_all() on the shared Base must build the whole schema without error."""
    from sqlalchemy import create_engine
    from ospra_os.database.base import Base
    from ospra_os.database.connection import _import_all_models

    _import_all_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)  # raises if any table/FK is malformed
