"""Data access — Firestore-backed, with a SQLAlchemy Base kept for compat.

Cloud Firestore is the only runtime data store. ``get_db`` yields a lazy
:class:`FirestoreDB` wrapper (see ``app.core.db``); no credentials are needed
at import time, so tests and API-only builds work without Firebase.

``Base`` (a plain SQLAlchemy declarative base) is kept solely so the ORM
model files — which define the enum types that ``app.schemas`` re-export —
remain importable. No tables are ever created or queried at runtime.
"""

from sqlalchemy.orm import DeclarativeBase

from app.core.db import FirestoreDB


class Base(DeclarativeBase):
    """Compatibility base class for ORM model definitions (unused at runtime)."""


_db = FirestoreDB()


def get_db():
    """FastAPI dependency that yields the Firestore-backed data layer."""
    yield _db
