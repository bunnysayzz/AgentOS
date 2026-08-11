"""Regression tests — FIREBASE_SERVICE_ACCOUNT_JSON must actually be used.

History: a bare ``import json`` inside get_firestore_db() made ``json`` a
function-local name, so ``json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)``
at the top of the function raised ``UnboundLocalError``. The except clause
swallowed it, logged a warning, and the app silently fell through to the
legacy (dead) refresh-token path → ``401 UNAUTHENTICATED`` in production even
though a valid service account was configured.

These tests assert the service-account path is genuinely taken whenever the
env var is set.
"""

import json

import pytest

from app.core import firebase as firebase_core
from app.core.config import settings

# A minimal-but-structurally-valid service account JSON (not a real key).
FAKE_SA_JSON = json.dumps(
    {
        "type": "service_account",
        "project_id": "agentos-7f01e",
        "private_key_id": "test",
        "private_key": "-----BEGIN PRIVATE KEY-----\nZmFrZWtleQ==\n-----END PRIVATE KEY-----\n",
        "client_email": "test@agentos-7f01e.iam.gserviceaccount.com",
        "client_id": "123",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test%40agentos-7f01e.iam.gserviceaccount.com",
    }
)


@pytest.fixture(autouse=True)
def _reset_firestore_cache():
    """get_firestore_db caches in a module global — reset around every test."""
    firebase_core._firestore_db = None
    yield
    firebase_core._firestore_db = None


def test_service_account_json_path_is_taken_when_set(monkeypatch):
    """The preferred path must win: SA JSON set → service-account credentials
    are built from it (not skipped in favour of the refresh token)."""

    captured = {}

    def fake_from_info(info):
        captured["info"] = info
        return object()  # opaque creds; we only assert the path was used

    def fake_client(project=None, credentials=None, client_options=None):
        captured["project"] = project
        captured["credentials"] = credentials
        return object()

    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", FAKE_SA_JSON)
    monkeypatch.setattr(settings, "FIREBASE_REFRESH_TOKEN", "dead-token")
    monkeypatch.setattr(settings, "FIREBASE_CLIENT_ID", "dead-client-id")
    monkeypatch.setattr(
        firebase_core.service_account.Credentials,
        "from_service_account_info",
        staticmethod(fake_from_info),
    )
    monkeypatch.setattr(firebase_core.firestore, "Client", fake_client)

    db = firebase_core.get_firestore_db()

    assert captured.get("info", {}).get("client_email") == "test@agentos-7f01e.iam.gserviceaccount.com"
    assert captured.get("project") == "agentos-7f01e"
    assert db is not None


def test_no_json_shadowing_unbound_local(monkeypatch):
    """The exact regression: json.loads inside get_firestore_db() must not hit
    UnboundLocalError (which previously made the SA path silently fail)."""
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", FAKE_SA_JSON)
    monkeypatch.setattr(
        firebase_core.service_account.Credentials,
        "from_service_account_info",
        staticmethod(lambda info: object()),
    )
    monkeypatch.setattr(
        firebase_core.firestore, "Client", lambda project=None, credentials=None, client_options=None: object()
    )
    # If `import json` shadowed the module json again, this raises UnboundLocalError.
    db = firebase_core.get_firestore_db()
    assert db is not None
