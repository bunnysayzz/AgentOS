"""Firebase core module — initializes Cloud Firestore client for AgentOS Studio backend."""

import os
import logging
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.cloud import firestore
from app.core.config import settings

logger = logging.getLogger(__name__)

CONFIGSTORE_PATH = Path.home() / ".config" / "configstore" / "firebase-tools.json"

FIREBASE_CLI_CLIENT_SECRET = "s9fK2i10383bGe2VZuWQqA-M"

_firestore_db = None


def get_firestore_db() -> firestore.Client:
    """Get or initialize the Cloud Firestore client using secure production order.
    
    1. Service Account (FIREBASE_PRIVATE_KEY & FIREBASE_CLIENT_EMAIL) -> For Production Cloud Hosting.
    2. Local CLI OAuth tokens (~/.config/configstore/firebase-tools.json) -> Local Dev.
    3. ENV OAuth Refresh Token (FIREBASE_REFRESH_TOKEN & FIREBASE_CLIENT_ID).
    4. GOOGLE_APPLICATION_CREDENTIALS / GCP ADC -> For GCP Services.
    """
    global _firestore_db
    if _firestore_db is not None:
        return _firestore_db

    project_id = settings.FIREBASE_PROJECT_ID or "agentos-7f01e"
    client_opts = {"quota_project_id": project_id}

    try:
        # ─── 1. Production Strategy: Service Account Private Key from ENV ───
        if settings.FIREBASE_PRIVATE_KEY and settings.FIREBASE_CLIENT_EMAIL:
            formatted_key = settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n")
            cred_dict = {
                "type": "service_account",
                "project_id": project_id,
                "client_email": settings.FIREBASE_CLIENT_EMAIL,
                "private_key": formatted_key,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            creds = service_account.Credentials.from_service_account_info(cred_dict)
            _firestore_db = firestore.Client(project=project_id, credentials=creds, client_options=client_opts)
            logger.info(f"Cloud Firestore initialized using Service Account ENV for project {project_id}.")
            return _firestore_db

        # ─── 2. Local Developer Strategy: Local CLI Credentials File ────────
        if CONFIGSTORE_PATH.exists():
            import json
            with open(CONFIGSTORE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                tokens = data.get("tokens", {})
                cli_user = data.get("user", {})
                client_id = cli_user.get("azp") or cli_user.get("aud") or settings.FIREBASE_CLIENT_ID
            if tokens.get("access_token") and tokens.get("refresh_token") and client_id:
                creds = Credentials(
                    token=tokens["access_token"],
                    refresh_token=tokens["refresh_token"],
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=FIREBASE_CLI_CLIENT_SECRET,
                )
                _firestore_db = firestore.Client(project=project_id, credentials=creds, client_options=client_opts)
                logger.info(f"Cloud Firestore initialized using local CLI tokens for project {project_id}.")
                return _firestore_db

        # ─── 3. ENV Credentials Strategy: OAuth Refresh Token from ENV ───────
        if settings.FIREBASE_REFRESH_TOKEN and settings.FIREBASE_CLIENT_ID:
            creds = Credentials(
                token=getattr(settings, "FIREBASE_ACCESS_TOKEN", None),
                refresh_token=settings.FIREBASE_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.FIREBASE_CLIENT_ID,
                client_secret=FIREBASE_CLI_CLIENT_SECRET,
            )
            _firestore_db = firestore.Client(project=project_id, credentials=creds, client_options=client_opts)
            logger.info(f"Cloud Firestore initialized using ENV OAuth credentials ({settings.FIREBASE_USER_EMAIL}) for project {project_id}.")
            return _firestore_db

        # ─── 4. Default Fallback ───────────────────────────────────────────
        _firestore_db = firestore.Client(project=project_id, client_options=client_opts)
        logger.info(f"Cloud Firestore initialized using default client for project {project_id}.")
        return _firestore_db

    except Exception as e:
        logger.error(f"Failed to initialize Cloud Firestore client for project {project_id}: {e}")
        raise e
