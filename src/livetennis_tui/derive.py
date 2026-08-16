"""Pure derivations and formatting — no I/O, no Textual.

Everything in here is a function of an SDK model (or plain values) to a
string or tuple, so it is unit-testable without a terminal or a network.

The break-point derivation mirrors the semantics the Live Tennis API uses in
its own Break-Point Radar: a break point exists when the RETURNER is one point
from winning the game on the SERVER's serve — returner at ``AD``, or returner
at ``40`` while the server is below ``40``. Tiebreaks never carry break points
(every point in a tiebreak alternates serve; the game-notation rule does not
apply), so ``is_tiebreak`` short-circuits the derivation.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

#: server's point -> number of break points when the returner stands at "40".
_SERVER_POINT_TO_BP = {"0": 3, "15": 2, "30": 1}

#: Match.tour vocabulary, in display order.
TOURS = ("atp", "wta", "challenger", "itf", "juniors")

TOUR_LABELS = {
    "atp": "ATP",
    "wta": "WTA",
    "challenger": "Challenger",
    "itf": "ITF",
    "juniors": "Juniors",
    None: "All tours",
}


def break_point(
    points: list[str] | None,
    server: int | None,
    is_tiebreak: bool | None = False,
) -> tuple[int, int | None]:
    """``(count, returner_side)`` if the current point is a break point, else ``(0, None)``.

    ``points`` is ``[p1, p2]`` in game notation (``"0"``/``"15"``/``"30"``/
    ``"40"``/``"AD"``); ``server`` is ``1`` or ``2``. Returns how many break
    points the returner holds (AD-in for the returner is one; 0-40 is three)
    and which side the returner is. Never fires in a tiebreak.
    """
    if is_tiebreak:
        return (0, None)
    if server not in (1, 2) or not points or len(points) < 2:
        return (0, None)
    sp = str(points[server - 1])  # server's point
    rp = str(points[2 - server])  # returner's point
    returner = 2 if server == 1 else 1
    if rp == "AD":
        return (1, returner)
    if rp == "40" and sp in _SERVER_POINT_TO_BP:
        return (_SERVER_POINT_TO_BP[sp], returner)
    return (0, None)


def set_scores(games: list[list[Any]] | None) -> list[tuple[int, int]]:
    """Per-set ``(p1, p2)`` pairs from the API's player-major ``games`` array.

    ``games`` is ``[games_p1, games_p2]`` where each side is a per-set list —
    ``[[6, 3, 2], [4, 6, 1]]`` reads 6-4, 3-6, 2-1. (Player-major, not
    set-major: indexing it the other way is the classic mistake against this
    API, which is why this helper exists.)
    """
    if not games or len(games) < 2:
        return []
    p1, p2 = games[0] or [], games[1] or []
    out = []
    for i in range(max(len(p1), len(p2))):
        a = p1[i] if i < len(p1) else 0
        b = p2[i] if i < len(p2) else 0
        try:
            out.append((int(a or 0), int(b or 0)))
        except (TypeError, ValueError):
            out.append((0, 0))
    return out


def format_sets(games: list[list[Any]] | None) -> str:
    """``"6-4 3-6 2-1"`` from the player-major games array; ``""`` when unknown."""
    return " ".join(f"{a}-{b}" for a, b in set_scores(games))


def format_points(points: list[str] | None, is_tiebreak: bool | None = False) -> str:
    """The current-game points as ``"40-30"`` (or ``"TB 5-3"`` in a tiebreak)."""
    if not points or len(points) < 2:
        return ""
    body = f"{points[0]}-{points[1]}"
    return f"TB {body}" if is_tiebreak else body


def serve_mark(server: int | None, side: int) -> str:
    """A serving marker for one side: ``"●"`` when serving, ``""`` otherwise."""
    return "●" if server == side else ""


def player_label(player: Any, fallback: str = "?") -> str:
    """``"Alcaraz [2]"`` — name plus world ranking where known."""
    name = getattr(player, "name", None) or fallback
    ranking = getattr(player, "ranking", None)
    return f"{name} [{ranking}]" if ranking else name


def movement_glyph(movement: str | None) -> str:
    """Ranking movement as an arrow: up / down / same / unknown."""
    if not movement:
        return ""
    text = str(movement).strip().lower()
    if text in ("same", "0", ""):
        return "="
    if text.startswith("up") or text.startswith("+"):
        return f"▲ {_movement_amount(text)}".rstrip()
    if text.startswith("down") or text.startswith("-"):
        return f"▼ {_movement_amount(text)}".rstrip()
    return str(movement)


def _movement_amount(text: str) -> str:
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits


def age_years(birthday: date | None, today: date | None = None) -> int | None:
    """Whole years old, or ``None`` when the birthday is unknown."""
    if not isinstance(birthday, date):
        return None
    today = today or datetime.now(timezone.utc).date()
    years = today.year - birthday.year
    if (today.month, today.day) < (birthday.month, birthday.day):
        years -= 1
    return years


def format_start(when: datetime | None, event_date: date | None = None) -> str:
    """A fixture's start moment: time when the order of play has one, else the day.

    A date-only fixture is a real state (the API leaves ``start_time`` null
    until the schedule assigns a time), so it renders as the date rather than
    a fake midnight.
    """
    if isinstance(when, datetime):
        return when.strftime("%a %d %b %H:%M UTC")
    if isinstance(event_date, date):
        return event_date.strftime("%a %d %b")
    return "TBA"


def quota_summary(usage: Any) -> str:
    """Footer text from a ``Usage`` payload: ``"quota 63/100 today"``.

    Reads the documented ``today.calls`` / ``today.remaining_day`` /
    ``limits.per_day`` fields; any missing piece degrades gracefully.
    """
    if usage is None:
        return ""
    today = getattr(usage, "today", None) or {}
    limits = getattr(usage, "limits", None) or {}
    calls = today.get("calls")
    per_day = limits.get("per_day")
    if calls is None:
        return ""
    if per_day is None:
        return f"quota {calls} calls today"
    remaining = today.get("remaining_day")
    tail = f" · {remaining} left" if remaining is not None else ""
    return f"quota {calls}/{per_day} today{tail}"
