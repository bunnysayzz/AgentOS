"""Webhook debugger service — test, inspect, and retry webhook calls."""

import json
import re
import time
import httpx
from urllib.parse import urlparse
from app.core.db import FirestoreDB, new_id, now_iso

WEBHOOK_LOGS = "webhook_logs"


def log_webhook(
    db: FirestoreDB,
    workspace_id: str,
    webhook_id: str,
    direction: str,  # "inbound" or "outbound"
    method: str,
    url: str,
    headers: dict | None = None,
    body: str | None = None,
    status_code: int | None = None,
    response_body: str | None = None,
    duration_ms: int | None = None,
    error: str | None = None,
) -> dict:
    """Log a webhook request/response for debugging."""
    entry = {
        "id": new_id(),
        "workspace_id": workspace_id,
        "webhook_id": webhook_id,
        "direction": direction,
        "method": method,
        "url": url,
        "headers": {k: v for k, v in (headers or {}).items() if k.lower() not in ("authorization", "cookie")},
        "body": body,
        "status_code": status_code,
        "response_body": response_body[:4000] if response_body else None,
        "duration_ms": duration_ms,
        "error": error,
        "created_at": now_iso(),
    }
    db.add(WEBHOOK_LOGS, entry)
    return entry


def list_webhook_logs(
    db: FirestoreDB,
    workspace_id: str,
    webhook_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List recent webhook logs for a workspace."""
    if webhook_id:
        rows = db.query(WEBHOOK_LOGS, "webhook_id", webhook_id)
    else:
        rows = db.query(WEBHOOK_LOGS, "workspace_id", workspace_id)
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[:limit]


def get_webhook_log(db: FirestoreDB, log_id: str) -> dict | None:
    """Get a specific webhook log entry."""
    return db.get(WEBHOOK_LOGS, log_id)


def _is_safe_url(url: str) -> bool:
    """SSRF protection: block private IPs, localhost, and cloud metadata endpoints."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname or ""
        # Block localhost and private IPs
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]"):
            return False
        # Block cloud metadata endpoints
        if hostname in ("169.254.169.254", "metadata.google.internal"):
            return False
        # Block private IP ranges (10.x, 172.16-31.x, 192.168.x)
        if re.match(r"^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)", hostname):
            return False
        return True
    except Exception:
        return False


def test_webhook(
    db: FirestoreDB,
    workspace_id: str,
    url: str,
    method: str = "POST",
    headers: dict | None = None,
    body: str | None = None,
) -> dict:
    """Send a test webhook and log the result."""
    start = time.monotonic()
    error = None
    status_code = None
    response_body = None
    
    if not _is_safe_url(url):
        return {
            "id": new_id(),
            "workspace_id": workspace_id,
            "webhook_id": "test",
            "direction": "outbound",
            "method": method,
            "url": url,
            "headers": {},
            "body": body,
            "status_code": None,
            "response_body": None,
            "duration_ms": 0,
            "error": "Blocked: URL points to a private/internal network (SSRF protection)",
            "created_at": now_iso(),
        }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            req_headers = headers or {}
            req_body = None
            if body:
                try:
                    req_body = json.loads(body)
                except json.JSONDecodeError:
                    req_body = body
            
            if method.upper() == "GET":
                resp = client.get(url, headers=req_headers)
            elif method.upper() == "PUT":
                resp = client.put(url, headers=req_headers, json=req_body if isinstance(req_body, dict) else None)
            elif method.upper() == "PATCH":
                resp = client.patch(url, headers=req_headers, json=req_body if isinstance(req_body, dict) else None)
            elif method.upper() == "DELETE":
                resp = client.delete(url, headers=req_headers)
            else:
                resp = client.post(url, headers=req_headers, json=req_body if isinstance(req_body, dict) else None)
            
            status_code = resp.status_code
            response_body = resp.text[:4000]
    except Exception as e:
        error = str(e)
    
    duration_ms = int((time.monotonic() - start) * 1000)
    
    # Log the test
    entry = log_webhook(
        db, workspace_id, "test",
        direction="outbound",
        method=method,
        url=url,
        headers=headers,
        body=body,
        status_code=status_code,
        response_body=response_body,
        duration_ms=duration_ms,
        error=error,
    )
    
    return entry


def retry_webhook(db: FirestoreDB, log_id: str) -> dict:
    """Retry a webhook from a previous log entry."""
    original = db.get(WEBHOOK_LOGS, log_id)
    if not original:
        from app.services.workspace_service import WorkspaceNotFoundError
        raise WorkspaceNotFoundError()
    
    # Re-send with original parameters
    return test_webhook(
        db,
        workspace_id=original["workspace_id"],
        url=original["url"],
        method=original["method"],
        headers=original.get("headers"),
        body=original.get("body"),
    )
