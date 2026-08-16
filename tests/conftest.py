"""Shared fakes: real SDK models, no network.

The fixtures build ``livetennisapi`` model objects from dict payloads exactly
as the SDK would from JSON, so the app is exercised against the real parsing
path — only the transport is faked.
"""

from __future__ import annotations

import pytest
from livetennisapi import Match, Player, Usage

from livetennis_tui.service import FriendlyError

LIVE_PAYLOADS = [
    {
        "id": 18953,
        "tournament": "Wimbledon",
        "tour": "atp",
        "round": "SF",
        "status": "live",
        "players": {
            "p1": {"id": 101, "name": "C. Alcaraz", "ranking": 2, "country": "esp"},
            "p2": {"id": 102, "name": "J. Sinner", "ranking": 1, "country": "ita"},
        },
        "score": {
            "sets": [1, 1],
            "games": [[6, 3, 2], [4, 6, 1]],
            "points": ["30", "40"],
            "server": 1,
            "is_tiebreak": False,
        },
    },
    {
        "id": 18954,
        "tournament": "Cincinnati Open",
        "tour": "wta",
        "round": "QF",
        "status": "live",
        "players": {
            "p1": {"id": 201, "name": "I. Swiatek", "ranking": 3, "country": "pol"},
            "p2": {"id": 202, "name": "A. Sabalenka", "ranking": 1, "country": "blr"},
        },
        "score": {
            "sets": [0, 0],
            "games": [[6], [6]],
            "points": ["5", "3"],
            "server": 2,
            "is_tiebreak": True,
        },
    },
]

UPCOMING_PAYLOADS = [
    {
        "id": 19001,
        "tournament": "Cincinnati Open",
        "tour": "atp",
        "round": "R16",
        "status": "upcoming",
        "scheduled_time": "2026-08-17T15:00:00Z",
        "players": {
            "p1": {"id": 301, "name": "N. Djokovic", "ranking": 5, "country": "srb"},
            "p2": {"id": 302, "name": "T. Fritz", "ranking": 4, "country": "usa"},
        },
    },
]

PLAYER_PAYLOADS = [
    {
        "id": 101,
        "name": "C. Alcaraz",
        "tour": "atp",
        "country": "esp",
        "ranking": 2,
        "ranking_points": 8600,
        "ranking_movement": "up 1",
        "hand": "R",
        "birthday": "2003-05-05",
    },
]

USAGE_PAYLOAD = {
    "tier": "free",
    "limits": {"per_minute": 30, "per_day": 100},
    "today": {"calls": 37, "errors": 0, "remaining_day": 63},
}


def make_matches(payloads):
    return [Match.from_dict(p) for p in payloads]


def make_usage(payload=None):
    return Usage.from_dict(payload or USAGE_PAYLOAD)


class FakeService:
    """Duck-typed TennisService: canned data, call recording, optional failure."""

    def __init__(
        self,
        live=None,
        upcoming=None,
        players=None,
        usage=USAGE_PAYLOAD,
        error: FriendlyError | None = None,
    ) -> None:
        self._live = make_matches(LIVE_PAYLOADS if live is None else live)
        self._upcoming = make_matches(UPCOMING_PAYLOADS if upcoming is None else upcoming)
        self._players = [Player.from_dict(p) for p in (PLAYER_PAYLOADS if players is None else players)]
        self._usage = make_usage(usage) if usage else None
        self.error = error
        self.calls: list[tuple] = []
        self.closed = False

    def _maybe_fail(self):
        if self.error is not None:
            raise self.error

    def live_matches(self, tour=None):
        self.calls.append(("live", tour))
        self._maybe_fail()
        return [m for m in self._live if tour is None or m.tour == tour]

    def upcoming_matches(self, tour=None):
        self.calls.append(("upcoming", tour))
        self._maybe_fail()
        return [m for m in self._upcoming if tour is None or m.tour == tour]

    def search_players(self, query):
        self.calls.append(("search", query))
        self._maybe_fail()
        q = query.lower()
        return [p for p in self._players if q in (p.name or "").lower()]

    def player(self, player_id):
        self.calls.append(("player", player_id))
        self._maybe_fail()
        for p in self._players:
            if p.id == player_id:
                return p
        return None

    def usage(self):
        self.calls.append(("usage", None))
        return self._usage

    def close(self):
        self.closed = True


@pytest.fixture
def fake_service():
    return FakeService()
