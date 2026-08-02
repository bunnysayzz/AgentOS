"""Time helpers for consistent aware-datetime arithmetic across services.

SQLite does not persist timezone information, so ``DateTime(timezone=True)``
columns read back from the database are *naive* datetimes. Subtracting a naive
datetime from an aware one raises::

    TypeError: can't subtract offset-naive and offset-aware datetimes

All execution-lifecycle services must use :func:`safe_duration_ms` when
computing durations from persisted timestamps.
"""

from datetime import datetime, timezone


def safe_duration_ms(started_at: datetime | None, now: datetime | None = None) -> int | None:
    """Compute the elapsed duration in milliseconds from ``started_at`` to ``now``.

    Naive ``started_at`` values are interpreted as UTC, matching the timezone
    used by the application when writing timestamps.
    """
    if started_at is None:
        return None
    if now is None:
        now = datetime.now(timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return int((now - started_at).total_seconds() * 1000)
