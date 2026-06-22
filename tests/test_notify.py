"""Tests for Telegram delivery: mock urlopen, no real network calls."""
import io
import json
from contextlib import contextmanager

import pytest

from ssq_checker import notify


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


@contextmanager
def _patch_urlopen(monkeypatch, body: str, capture: dict):
    def fake_urlopen(req, timeout=None):
        capture["url"] = req.full_url
        capture["method"] = req.get_method()
        capture["body"] = json.loads(req.data.decode("utf-8"))
        capture["timeout"] = timeout
        return _FakeResponse(body.encode("utf-8"))

    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
    yield


def test_send_builds_correct_request(monkeypatch):
    cap: dict = {}
    with _patch_urlopen(monkeypatch, '{"ok": true}', cap):
        notify.send_telegram("hello 双色球", token="TKN", chat_id="-100123", timeout=7)
    assert cap["url"] == "https://api.telegram.org/botTKN/sendMessage"
    assert cap["method"] == "POST"
    assert cap["body"] == {"chat_id": "-100123", "text": "hello 双色球"}
    assert cap["timeout"] == 7


def test_missing_credentials_raises():
    with pytest.raises(ValueError):
        notify.send_telegram("x", token="", chat_id="-100")
    with pytest.raises(ValueError):
        notify.send_telegram("x", token="TKN", chat_id="")


def test_api_not_ok_raises(monkeypatch):
    cap: dict = {}
    with _patch_urlopen(monkeypatch, '{"ok": false, "description": "bad chat"}', cap):
        with pytest.raises(RuntimeError):
            notify.send_telegram("x", token="TKN", chat_id="-100")
