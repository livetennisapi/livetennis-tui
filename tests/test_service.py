"""SDK exceptions become friendly, factual messages — 30/min and 100/day cited."""

import pytest
from livetennisapi import RateLimited, Unauthorized
from livetennisapi.errors import APIConnectionError

from livetennis_tui.service import FriendlyError, TennisService


class _BoomClient:
    """A stand-in for LiveTennisAPI whose every call raises `exc`."""

    def __init__(self, exc):
        self._exc = exc

    def _raise(self, *args, **kwargs):
        raise self._exc

    list_matches = search_players = get_player = get_usage = _raise

    def close(self):
        pass


def _service(exc) -> TennisService:
    return TennisService(client=_BoomClient(exc))


def test_unauthorized_becomes_friendly_401():
    exc = Unauthorized("invalid key", status_code=401)
    with pytest.raises(FriendlyError) as err:
        _service(exc).live_matches()
    assert err.value.kind == "auth"
    assert "401" in err.value.title
    assert "LIVETENNIS_API_KEY" in err.value.detail


def test_minute_rate_limit_cites_30_per_minute():
    exc = RateLimited("slow down", status_code=429, retry_after=12.0)
    with pytest.raises(FriendlyError) as err:
        _service(exc).live_matches()
    assert err.value.kind == "rate"
    assert "30 requests/minute" in err.value.detail
    assert "12s" in err.value.detail


def test_daily_quota_cites_100_per_day_and_pauses():
    exc = RateLimited(
        "quota",
        status_code=429,
        body={"scope": "day", "limit_per_day": 100, "resets_at": "2026-08-17T04:00:00Z"},
    )
    with pytest.raises(FriendlyError) as err:
        _service(exc).upcoming_matches()
    assert err.value.kind == "quota_day"
    assert "100 requests/day" in err.value.detail
    assert "04:00 UTC" in err.value.detail


def test_connection_error_is_friendly():
    with pytest.raises(FriendlyError) as err:
        _service(APIConnectionError("dns")).search_players("alcaraz")
    assert err.value.kind == "connection"
    assert "api.livetennisapi.com" in err.value.detail
