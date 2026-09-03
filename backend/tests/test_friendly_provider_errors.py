"""Regression tests for provider error handling:

1. The real API key is sent to Google (an earlier "security" pass was masking the
   key inside the actual request URL, which guaranteed a 401 from Google).
2. Provider HTTP errors surface as plain-language messages that never include
   the raw body, the request URL, or the API key.
"""

import httpx

from app.services import mcp_service
from app.services.provider_metadata import is_rate_limit_error


def test_friendly_http_error_auth_never_leaks_key_or_url():
    msg = mcp_service._friendly_http_error(
        401,
        "google",
        body_text='{"error": {"message": "API key not valid. key=sk-realsecret123456"}}',
    )
    assert "sk-realsecret123456" not in msg
    assert "generativelanguage" not in msg
    assert "Google Gemini" in msg
    assert "rejected the API key" in msg


def test_friendly_http_error_model_404_names_the_model():
    msg = mcp_service._friendly_http_error(
        404,
        "groq",
        model="llama-3.3-70b-versatile",
        body_text='{"error": {"message": "The model `llama-3.3-70b-versatile` does not exist"}}',
    )
    assert "llama-3.3-70b-versatile" in msg
    assert "doesn't have the model" in msg
    assert "{" not in msg  # raw JSON body never leaks


def test_friendly_429_is_still_detected_as_retryable():
    msg = mcp_service._friendly_http_error(429, "openai")
    assert is_rate_limit_error(msg)


class _FakeClient:
    def __init__(self):
        self.captured_url = None
        self.captured_headers = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        self.captured_url = url
        self.captured_headers = headers or {}
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "hello"}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {
                    "promptTokenCount": 3,
                    "candidatesTokenCount": 2,
                    "totalTokenCount": 5,
                },
            },
        )


async def test_call_google_sends_real_key(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(mcp_service.httpx, "AsyncClient", lambda timeout=60: fake)

    key = "sk-realsecretkey1234567890"
    result = await mcp_service._call_google(
        key,
        [{"role": "user", "content": "Hi"}],
        "gemini-2.0-flash",
        0.7,
        None,
    )

    # The real key is sent to Google (not a mask) but only via the header,
    # so it can never show up in URLs, logs, or transport error messages.
    assert fake.captured_headers["x-goog-api-key"] == key
    assert "key=" not in fake.captured_url
    assert key not in fake.captured_url
    assert result["choices"][0]["message"]["content"] == "hello"
    assert result["usage"]["prompt_tokens"] == 3


async def test_call_openai_compatible_401_is_friendly(monkeypatch):
    class _FakeClient401:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            return httpx.Response(
                401,
                json={"error": {"message": "Incorrect API key provided: sk-LEAKED"}},
            )

    monkeypatch.setattr(
        mcp_service.httpx, "AsyncClient", lambda timeout=60: _FakeClient401()
    )

    try:
        await mcp_service._call_openai_compatible(
            api_key="sk-leakedkey1234567890",
            messages=[{"role": "user", "content": "Hi"}],
            model="gpt-4o",
            temperature=0.7,
            max_tokens=None,
            base_url="https://api.openai.com/v1",
            provider="openai",
        )
        raise AssertionError("expected an MCPError")
    except mcp_service.MCPError as exc:
        assert "sk-LEAKED" not in exc.message
        assert "rejected the API key" in exc.message
        assert exc.status_code == 401
