"""Firestore-backed data access layer for AgentOS Studio.

Replaces the SQLAlchemy engine/session layer with Cloud Firestore. Design
rules that keep the migration simple and index-free:

- Documents are plain dicts that ALWAYS include ``id`` plus ISO-8601
  ``created_at``/``updated_at`` strings and an optional ``deleted_at`` —
  matching the field names the public API schemas already expose, so the API
  contract (and the frontend) does not change.
- At most ONE equality filter is pushed down to Firestore (single-field
  indexes are auto-created by Firebase). All additional filtering, ordering,
  pagination and aggregation happen in Python — this avoids composite-index
  setup entirely, so a brand-new Firestore database works with zero console
  work.
- ``set`` persists every key (including explicit ``None``) so reads mirror
  the old relational rows (every column present).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.firebase import get_firestore_db


class AttrDict(dict):
    """A dict that also exposes its keys as attributes (read/write).

    The routers historically used ``current_user.id`` style attribute access
    on ORM objects; documents are dicts now, so this shim keeps both styles
    working (``user.id`` and ``user["id"]``).
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


def new_id() -> str:
    """Generate a UUID string used as the document ID (matches API UUID ids)."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string (lexicographically sortable)."""
    return datetime.now(timezone.utc).isoformat()


def stamp(payload: dict) -> dict:
    """Ensure a payload has id/created_at/updated_at timestamps."""
    payload.setdefault("id", new_id())
    if not payload.get("created_at"):
        payload["created_at"] = now_iso()
    payload["updated_at"] = now_iso()
    return AttrDict(payload)


def sort_rows(
    rows: list[dict],
    key: str,
    desc: bool = True,
    nulls_last: bool = True,
) -> list[dict]:
    """Sort document dicts by a field (ISO timestamps sort lexicographically)."""

    def _key(row: dict):
        v = row.get(key)
        return v if v is not None else ("" if nulls_last else "\uffff")

    return sorted(rows, key=_key, reverse=desc)


class FirestoreDB:
    """Thin, lazy wrapper around a google-cloud-firestore client.

    The client is constructed on first use so importing this module never
    requires Firebase credentials (tests inject a fake client instead).
    """

    def __init__(self, client: Any = None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            self._client = get_firestore_db()
        return self._client

    # ─── Document operations ───────────────────────────────────────────

    def get(self, coll: str, doc_id: str) -> dict | None:
        """Fetch a single document; returns None when missing."""
        snap = self.client.collection(coll).document(doc_id).get()
        if not snap.exists:
            return None
        data = dict(snap.to_dict() or {})
        data["id"] = doc_id
        return AttrDict(data)

    def set(self, coll: str, doc_id: str, data: dict) -> None:
        """Create or overwrite a document (every key persisted, incl. None)."""
        payload = dict(data)
        if not payload.get("created_at"):
            payload["created_at"] = now_iso()
        payload["updated_at"] = now_iso()
        self.client.collection(coll).document(doc_id).set(payload)

    def add(self, coll: str, data: dict) -> str:
        """Insert a document, auto-generating an id; returns the id.

        ``data`` is stamped in place so callers that return the same dict get
        the id/created_at/updated_at fields for their response schemas.
        """
        stamp(data)
        doc_id = data["id"]
        self.set(coll, doc_id, data)
        return doc_id

    def delete(self, coll: str, doc_id: str) -> None:
        """Hard-delete a document."""
        self.client.collection(coll).document(doc_id).delete()

    def exists(self, coll: str, doc_id: str) -> bool:
        return self.get(coll, doc_id) is not None

    # ─── Query operations (single equality filter pushed to Firestore) ──

    def query(self, coll: str, field: str | None = None, value: Any = None) -> list[dict]:
        """Return all documents matching one equality filter (or all)."""
        from google.cloud.firestore_v1.base_query import FieldFilter

        ref = self.client.collection(coll)
        if field is not None:
            ref = ref.where(filter=FieldFilter(field, "==", value))
        rows: list[dict] = []
        for snap in ref.stream():
            data = dict(snap.to_dict() or {})
            data["id"] = snap.id
            rows.append(AttrDict(data))
        return rows

    def query_since(
        self,
        coll: str,
        field: str | None,
        value: Any,
        since_iso: str,
        limit: int | None = None,
    ) -> list[dict]:
        """Documents with one equality filter AND ``created_at >= since_iso``.

        Pushes BOTH filters down to Firestore first (composite ``(field,
        created_at)`` index declared in firestore.indexes.json). Only if the
        pushdown fails (missing index, client without support) does it fall
        back to a single-filter query + in-memory range filter. The fallback
        must NEVER run first — that would turn every call back into the full
        collection scan this helper exists to eliminate.
        """
        from google.cloud.firestore_v1.base_query import FieldFilter

        try:
            ref = self.client.collection(coll)
            if field is not None:
                ref = ref.where(filter=FieldFilter(field, "==", value))
            ref = ref.where(filter=FieldFilter("created_at", ">=", since_iso))
            if limit is not None:
                ref = ref.limit(limit)
            pushed: list[dict] = []
            for snap in ref.stream():
                data = dict(snap.to_dict() or {})
                data["id"] = snap.id
                pushed.append(AttrDict(data))
            return pushed
        except Exception:
            pass  # Composite index missing or client unsupported — filter below.
        rows = self.query(coll, field, value)
        rows = [r for r in rows if (r.get("created_at") or "") >= since_iso]
        if limit is not None:
            rows = rows[:limit]
        return rows

    def query_top(
        self,
        coll: str,
        field: str | None,
        value: Any,
        limit: int,
    ) -> list[dict]:
        """Newest N documents matching one equality filter (created_at DESC).

        Pushes ``order_by(created_at DESC).limit(N)`` to Firestore first
        (composite index in firestore.indexes.json); falls back to a
        single-filter query + Python sort/slice only if the pushdown fails.
        """
        from google.cloud.firestore_v1.base_query import FieldFilter

        try:
            ref = self.client.collection(coll)
            if field is not None:
                ref = ref.where(filter=FieldFilter(field, "==", value))
            from google.cloud.firestore_v1.query import Direction
            ref = ref.order_by("created_at", direction=Direction.DESCENDING)
            ref = ref.limit(limit)
            pushed: list[dict] = []
            for snap in ref.stream():
                data = dict(snap.to_dict() or {})
                data["id"] = snap.id
                pushed.append(AttrDict(data))
            return pushed
        except Exception:
            pass
        rows = self.query(coll, field, value)
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return rows[:limit]

    # ─── Aggregate query builders (internal) ────────────────────────────

    def _aggregate(self, coll: str, field: str | None, value: Any):
        """Server-side count() over an equality filter (or the whole set)."""
        from google.cloud.firestore_v1.base_query import FieldFilter

        ref = self.client.collection(coll)
        if field is not None:
            ref = ref.where(filter=FieldFilter(field, "==", value))
        return ref.count().get()

    def _aggregate_since(self, coll: str, field: str | None, value: Any, since_iso: str):
        """Server-side count() over equality + created_at >= range."""
        from google.cloud.firestore_v1.base_query import FieldFilter

        ref = self.client.collection(coll)
        if field is not None:
            ref = ref.where(filter=FieldFilter(field, "==", value))
        ref = ref.where(filter=FieldFilter("created_at", ">=", since_iso))
        return ref.count().get()

    def get_first(self, coll: str, field: str | None = None, value: Any = None) -> dict | None:
        """Return the first matching document (or None)."""
        rows = self.query(coll, field, value)
        return rows[0] if rows else None

    def count(self, coll: str, field: str | None = None, value: Any = None) -> int:
        """Count documents (native Firestore aggregation when available).

        Uses the server-side ``count()`` aggregate query when the client
        supports it (google-cloud-firestore >= 2.16); falls back to a Python
        scan otherwise (tests / fake client). This avoids downloading every
        matching document just to compute a number.
        """
        try:
            agg = self._aggregate(coll, field, value)
            return int(agg[0][0].value)
        except Exception:
            return len(self.query(coll, field, value))

    def sum_field(self, coll: str, field: str | None, value: Any, sum_key: str) -> float:
        """Sum a numeric field over matching documents."""
        total = 0
        for row in self.query(coll, field, value):
            total += row.get(sum_key) or 0
        return total

    def sum_since(self, coll: str, field: str | None, value: Any, sum_key: str, since_iso: str) -> float:
        """Sum a numeric field over documents with created_at >= since."""
        total = 0
        for row in self.query_since(coll, field, value, since_iso):
            total += row.get(sum_key) or 0
        return total

    def count_since(self, coll: str, field: str | None, value: Any, since_iso: str) -> int:
        """Count documents with created_at >= since (aggregate when possible).

        Falls back to filtering the equality-filtered rows in Python (never
        rethrows a composite-index error — the range is applied in memory).
        """
        try:
            agg = self._aggregate_since(coll, field, value, since_iso)
            return int(agg[0][0].value)
        except Exception:
            rows = self.query(coll, field, value)
            return sum(1 for r in rows if (r.get("created_at") or "") >= since_iso)

    def avg_field(self, coll: str, field: str | None, value: Any, avg_key: str) -> float:
        """Average a numeric field over matching documents."""
        rows = self.query(coll, field, value)
        if not rows:
            return 0.0
        return sum(row.get(avg_key) or 0 for row in rows) / len(rows)

    def group_sum(
        self,
        coll: str,
        field: str | None,
        value: Any,
        group_key: str,
        sum_key: str,
    ) -> dict[str, float]:
        """Sum a numeric field grouped by another field (top-N friendly)."""
        result: dict[str, float] = {}
        for row in self.query(coll, field, value):
            group = row.get(group_key)
            if group is None:
                continue
            result[group] = result.get(group, 0) + (row.get(sum_key) or 0)
        return result
