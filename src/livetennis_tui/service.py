"""A thin, synchronous data layer over the official SDK.

The app talks only to this class, which keeps the Textual code free of SDK
details and makes the whole app testable with one fake. Errors are translated
into :class:`FriendlyError` — a message fit for a status bar, with the facts
(FREE tier: 30 requests/minute, 100/day) where they help.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from livetennisapi import (
    APIConnectionError,
    LiveTennisAPI,
    LiveTennisAPIError,
    RateLimited,
    Unauthorized,
    UpgradeRequired,
)


@dataclass
class FriendlyError(Exception):
    """An error with a human sentence instead of a traceback."""

    title: str
    detail: str
    #: machine-readable class: auth | quota_day | rate | tier | connection | api
    kind: str = "api"

    def __str__(self) -> str:  # pragma: no cover - repr convenience
        return f"{self.title}: {self.detail}"


def _friendly(exc: Exception) -> FriendlyError:
    if isinstance(exc, Unauthorized):
        return FriendlyError(
            "API key rejected (401)",
            "The key was refused. Check LIVETENNIS_API_KEY (or "
            "~/.config/livetennis-tui/config) — a free key takes a minute at "
            "livetennisapi.com/subscribe/free.",
            kind="auth",
        )
    if isinstance(exc, RateLimited):
        if getattr(exc, "scope", None) == "day":
            resets = getattr(exc, "resets_at", None)
            when = f" It resets at {resets:%H:%M UTC}." if resets else ""
            return FriendlyError(
                "Daily quota reached (429)",
                f"The FREE tier allows 100 requests/day and today's are spent.{when} "
                "Refreshing pauses until then — the quota footer stays live "
                "(that read is quota-exempt).",
                kind="quota_day",
            )
        wait = getattr(exc, "retry_after", None)
        in_s = f" Retrying is fine in {wait:.0f}s." if wait else ""
        return FriendlyError(
            "Rate limited (429)",
            f"The FREE tier allows 30 requests/minute.{in_s}",
            kind="rate",
        )
    if isinstance(exc, UpgradeRequired):
        return FriendlyError(
            "Not on this tier (403)",
            "That data needs a higher tier — this app only uses FREE-tier "
            "endpoints, so seeing this usually means the key itself is limited.",
            kind="tier",
        )
    if isinstance(exc, APIConnectionError):
        return FriendlyError(
            "No connection",
            "Could not reach api.livetennisapi.com — check the network and try r to refresh.",
            kind="connection",
        )
    if isinstance(exc, LiveTennisAPIError):
        return FriendlyError("API error", str(exc))
    return FriendlyError("Unexpected error", f"{type(exc).__name__}: {exc}")


class TennisService:
    """Everything the TUI reads, in five FREE-tier calls."""

    def __init__(self, client: LiveTennisAPI | None = None, api_key: str | None = None) -> None:
        self._client = client or LiveTennisAPI(api_key=api_key)

    def close(self) -> None:
        self._client.close()

    # Each method returns plain SDK models; the app derives display strings.

    def live_matches(self, tour: str | None = None) -> list[Any]:
        return self._call(lambda: list(self._client.list_matches(status="live", tour=tour, limit=50)))

    def upcoming_matches(self, tour: str | None = None) -> list[Any]:
        return self._call(lambda: list(self._client.list_matches(status="upcoming", tour=tour, limit=50)))

    def search_players(self, query: str) -> list[Any]:
        return self._call(lambda: list(self._client.search_players(query, limit=25)))

    def player(self, player_id: int) -> Any:
        return self._call(lambda: self._client.get_player(player_id))

    def usage(self) -> Any:
        """Quota standing. The /usage read itself is quota-exempt, so polling
        it alongside every refresh costs nothing against the daily allowance."""
        return self._call(self._client.get_usage)

    def _call(self, fn):
        try:
            return fn()
        except FriendlyError:
            raise
        except Exception as exc:  # noqa: BLE001 — translated, not swallowed
            raise _friendly(exc) from exc
