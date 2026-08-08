"""Tests for the Firebase auth-helper reverse proxy (/__/auth, /__/firebase).

Google sign-in helper code is served from <project>.firebaseapp.com. The
proxy makes it same-origin on the app domain so browsers that block
third-party storage (Safari ITP, Chrome 115+, Firefox 109+) can complete
Google sign-in. These tests verify transparent forwarding and that the
proxied responses stay frameable (no X-Frame-Options / frame-ancestors).
"""

from httpx import AsyncClient


class FakeUpstreamResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"<html>ok</html>"):
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": "text/html; charset=utf-8"}


class FakeProxyClient:
    """Captures forwarded requests; returns a canned upstream response."""

    def __init__(self):
        self.requests: list[dict] = []

    async def request(self, method: str, url, headers=None, content=None):
        self.requests.append({
            "method": method,
            "url": url,
            "headers": dict(headers or {}),
            "content": content,
        })
        return FakeUpstreamResponse()


def _patch_client(monkeypatch) -> FakeProxyClient:
    from app.core import auth_proxy

    fake = FakeProxyClient()
    monkeypatch.setattr(auth_proxy, "_get_client", lambda: fake)
    return fake


async def test_proxy_forwards_auth_iframe_with_query(
    client: AsyncClient, monkeypatch
):
    fake = _patch_client(monkeypatch)

    resp = await client.get("/__/auth/iframe?apiKey=abc&appName=%5BDEFAULT%5D")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"
    assert resp.text == "<html>ok</html>"

    assert len(fake.requests) == 1
    req = fake.requests[0]
    assert req["method"] == "GET"
    assert req["url"].path == "/__/auth/iframe"
    assert "apiKey=abc" in str(req["url"])


async def test_proxy_forwards_post_with_body(client: AsyncClient, monkeypatch):
    fake = _patch_client(monkeypatch)

    resp = await client.post("/__/auth/handler", content=b"payload")

    assert resp.status_code == 200
    req = fake.requests[0]
    assert req["method"] == "POST"
    assert req["content"] == b"payload"
    # The Host header must NOT be forwarded upstream (it identifies the
    # proxy's vhost, not firebaseapp.com).
    assert "host" not in {k.lower() for k in req["headers"]}


async def test_proxy_forwards_firebase_init_json(client: AsyncClient, monkeypatch):
    fake = _patch_client(monkeypatch)

    resp = await client.get("/__/firebase/init.json")

    assert resp.status_code == 200
    assert fake.requests[0]["url"].path == "/__/firebase/init.json"


async def test_proxied_responses_are_framable(client: AsyncClient, monkeypatch):
    # The auth iframe MUST be embeddable by the app page — the app's own
    # frame-blocking headers (X-Frame-Options DENY, frame-ancestors 'none')
    # must never land on /__/ responses, or Google sign-in breaks.
    _patch_client(monkeypatch)

    resp = await client.get("/__/auth/iframe")

    assert resp.headers.get("x-frame-options") is None
    assert "frame-ancestors" not in resp.headers.get("content-security-policy", "")


async def test_normal_pages_still_deny_framing(client: AsyncClient):
    """Hardening headers must still apply everywhere else."""
    resp = await client.get("/health")
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "frame-ancestors 'none'" in resp.headers.get("content-security-policy", "")


async def test_csp_allows_self_framing_of_the_auth_helper(client: AsyncClient):
    """The app page must be allowed to frame/run the same-origin helper."""
    resp = await client.get("/health")
    csp = resp.headers.get("content-security-policy", "")
    assert "frame-src 'self'" in csp
    assert "worker-src 'self'" in csp
