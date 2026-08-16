"""Unit tests for the pure derivations — above all the break-point marker.

The break-point semantics mirror the API's own Break-Point Radar: a break
point exists only when the RETURNER is one point from taking the server's
game — returner at AD, or returner at 40 with the server below 40 — and never
inside a tiebreak.
"""

from datetime import date, datetime, timezone

import pytest

from livetennis_tui.derive import (
    age_years,
    break_point,
    format_points,
    format_sets,
    format_start,
    movement_glyph,
    player_label,
    quota_summary,
    serve_mark,
    set_scores,
)

from .conftest import make_usage


class TestBreakPoint:
    # -- fires ---------------------------------------------------------------

    def test_returner_at_ad_is_one_break_point(self):
        # server=1, so p2 is the returner; AD for p2 = break point.
        assert break_point(["40", "AD"], server=1) == (1, 2)

    def test_returner_at_ad_other_side(self):
        assert break_point(["AD", "40"], server=2) == (1, 1)

    @pytest.mark.parametrize(
        "server_point,count", [("0", 3), ("15", 2), ("30", 1)]
    )
    def test_returner_at_40_counts_by_server_point(self, server_point, count):
        assert break_point([server_point, "40"], server=1) == (count, 2)
        assert break_point(["40", server_point], server=2) == (count, 1)

    # -- does not fire -------------------------------------------------------

    def test_deuce_is_not_a_break_point(self):
        assert break_point(["40", "40"], server=1) == (0, None)

    def test_server_advantage_is_not_a_break_point(self):
        assert break_point(["AD", "40"], server=1) == (0, None)

    def test_game_point_for_server_is_not_a_break_point(self):
        assert break_point(["40", "30"], server=1) == (0, None)

    def test_early_in_game_is_not_a_break_point(self):
        assert break_point(["15", "30"], server=1) == (0, None)

    def test_never_in_a_tiebreak(self):
        # Even if a feed briefly carries game notation into a tiebreak,
        # the flag wins: no break point is derived.
        assert break_point(["40", "AD"], server=1, is_tiebreak=True) == (0, None)
        assert break_point(["6", "5"], server=1, is_tiebreak=True) == (0, None)

    # -- malformed inputs ----------------------------------------------------

    def test_no_server_means_no_derivation(self):
        assert break_point(["40", "AD"], server=None) == (0, None)
        assert break_point(["40", "AD"], server=3) == (0, None)

    def test_missing_points_means_no_derivation(self):
        assert break_point(None, server=1) == (0, None)
        assert break_point([], server=1) == (0, None)
        assert break_point(["40"], server=1) == (0, None)


class TestScoreFormatting:
    def test_games_are_player_major(self):
        # [[p1 per set], [p2 per set]] -> 6-4 3-6 2-1, NOT 6-3 …
        assert set_scores([[6, 3, 2], [4, 6, 1]]) == [(6, 4), (3, 6), (2, 1)]
        assert format_sets([[6, 3, 2], [4, 6, 1]]) == "6-4 3-6 2-1"

    def test_uneven_sides_are_padded(self):
        assert set_scores([[6, 1], [4]]) == [(6, 4), (1, 0)]

    def test_empty_games(self):
        assert set_scores(None) == []
        assert format_sets([]) == ""

    def test_points_render(self):
        assert format_points(["40", "30"]) == "40-30"
        assert format_points(["5", "3"], is_tiebreak=True) == "TB 5-3"
        assert format_points(None) == ""

    def test_serve_mark(self):
        assert serve_mark(1, 1) == "●"
        assert serve_mark(1, 2) == ""
        assert serve_mark(None, 1) == ""


class TestLabels:
    def test_player_label_with_ranking(self):
        class P:
            name = "C. Alcaraz"
            ranking = 2

        assert player_label(P()) == "C. Alcaraz [2]"

    def test_player_label_unranked_and_missing(self):
        class P:
            name = "Qualifier"
            ranking = None

        assert player_label(P()) == "Qualifier"
        assert player_label(None) == "?"

    @pytest.mark.parametrize(
        "movement,expected",
        [("up 3", "▲ 3"), ("down 12", "▼ 12"), ("same", "="), (None, ""), ("+2", "▲ 2")],
    )
    def test_movement_glyph(self, movement, expected):
        assert movement_glyph(movement) == expected

    def test_age_years(self):
        today = date(2026, 8, 16)
        assert age_years(date(2003, 5, 5), today) == 23
        assert age_years(date(2003, 9, 1), today) == 22  # birthday not yet
        assert age_years(None, today) is None

    def test_format_start(self):
        when = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)
        assert format_start(when) == "Mon 17 Aug 15:00 UTC"
        # Date-only fixtures are a real state: render the day, not midnight.
        assert format_start(None, date(2026, 8, 17)) == "Mon 17 Aug"
        assert format_start(None, None) == "TBA"


class TestQuotaSummary:
    def test_full_payload(self):
        usage = make_usage(
            {"limits": {"per_day": 100}, "today": {"calls": 37, "remaining_day": 63}}
        )
        assert quota_summary(usage) == "quota 37/100 today · 63 left"

    def test_unlimited_day(self):
        usage = make_usage({"limits": {"per_day": None}, "today": {"calls": 5}})
        assert quota_summary(usage) == "quota 5 calls today"

    def test_missing_pieces_degrade(self):
        assert quota_summary(None) == ""
        assert quota_summary(make_usage({"today": {}})) == ""
