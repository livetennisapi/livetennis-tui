"""App-shell tests with Textual's pilot — mocked service, no network."""

import pytest
from textual.widgets import DataTable, Static

from livetennis_tui.app import LiveTennisTUI, NoKeyScreen, PlayerProfile, PlayerSearch
from livetennis_tui.config import Settings
from livetennis_tui.service import FriendlyError

from .conftest import FakeService


def make_app(service=None, api_key="twjp_test") -> LiveTennisTUI:
    settings = Settings(api_key=api_key, refresh_seconds=60)
    return LiveTennisTUI(service=service, settings=settings)


async def _settle(pilot):
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def test_live_view_populates(fake_service):
    app = make_app(fake_service)
    async with app.run_test(size=(120, 32)) as pilot:
        await _settle(pilot)
        table = app.query_one("#live-table", DataTable)
        assert table.row_count == 2
        assert ("live", None) in fake_service.calls
        # /usage polled alongside the refresh (quota-exempt)
        assert ("usage", None) in fake_service.calls
        bar = app.query_one("#status-bar", Static)
        assert "37/100" in str(bar.render())


async def test_fixtures_view(fake_service):
    app = make_app(fake_service)
    async with app.run_test(size=(120, 32)) as pilot:
        await _settle(pilot)
        await pilot.press("f")
        await _settle(pilot)
        assert ("upcoming", None) in fake_service.calls
        table = app.query_one("#fixtures-table", DataTable)
        assert table.display is True
        assert table.row_count == 1
        assert app.query_one("#live-table", DataTable).display is False


async def test_tour_filter_keys(fake_service):
    app = make_app(fake_service)
    async with app.run_test(size=(120, 32)) as pilot:
        await _settle(pilot)
        await pilot.press("w")
        await _settle(pilot)
        assert app.tour == "wta"
        assert ("live", "wta") in fake_service.calls
        # only the WTA match remains
        assert app.query_one("#live-table", DataTable).row_count == 1
        # pressing the active filter again clears it
        await pilot.press("w")
        await _settle(pilot)
        assert app.tour is None
        await pilot.press("a")
        await _settle(pilot)
        assert app.tour == "atp"


async def test_no_key_state():
    app = make_app(service=None, api_key=None)
    async with app.run_test(size=(120, 32)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, NoKeyScreen)
        help_text = str(app.screen.query_one("#nokey-help", Static).render())
        assert "LIVETENNIS_API_KEY" in help_text
        assert "livetennisapi.com/subscribe/free" in help_text


async def test_error_state_shows_friendly_message():
    service = FakeService(error=FriendlyError("Rate limited (429)", "The FREE tier allows 30 requests/minute.", kind="rate"))
    app = make_app(service)
    async with app.run_test(size=(120, 32)) as pilot:
        await _settle(pilot)
        empty = app.query_one("#empty-state", Static)
        assert empty.display is True
        assert "30 requests/minute" in str(empty.render())
        assert app.quota_paused is False


async def test_daily_quota_pauses_refresh_and_usage_resumes_it():
    service = FakeService(
        error=FriendlyError("Daily quota reached (429)", "100 requests/day spent.", kind="quota_day"),
        usage={"limits": {"per_day": 100}, "today": {"calls": 100, "remaining_day": 0}},
    )
    app = make_app(service)
    async with app.run_test(size=(120, 32)) as pilot:
        await _settle(pilot)
        assert app.quota_paused is True
        data_calls_before = [c for c in service.calls if c[0] in ("live", "upcoming")]
        # While paused, a refresh only polls /usage — no data calls are burned.
        await pilot.press("r")
        await _settle(pilot)
        data_calls_after = [c for c in service.calls if c[0] in ("live", "upcoming")]
        assert data_calls_after == data_calls_before
        # The day rolls over: usage shows headroom again -> refresh resumes.
        service._usage = __import__("tests.conftest", fromlist=["make_usage"]).make_usage(
            {"limits": {"per_day": 100}, "today": {"calls": 0, "remaining_day": 100}}
        )
        service.error = None
        await pilot.press("r")
        await _settle(pilot)
        assert app.quota_paused is False


async def test_player_search_flow(fake_service):
    app = make_app(fake_service)
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        await pilot.press("slash")
        await pilot.pause()
        assert isinstance(app.screen, PlayerSearch)
        await pilot.press(*"alcaraz")
        await pilot.press("enter")
        await _settle(pilot)
        results = app.screen.query_one("#search-results", DataTable)
        assert results.row_count == 1
        assert ("search", "alcaraz") in fake_service.calls
        # open the profile
        await pilot.press("enter")
        await _settle(pilot)
        assert isinstance(app.screen, PlayerProfile)
        body = str(app.screen.query_one("#profile-body", Static).render())
        assert "#2" in body           # ranking
        assert "Right-handed" in body
        assert "ESP" in body
        # esc unwinds both modals
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PlayerSearch)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, (PlayerSearch, PlayerProfile))


async def test_search_rejects_short_query(fake_service):
    app = make_app(fake_service)
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        await pilot.press("slash")
        await pilot.pause()
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.pause()
        status = str(app.screen.query_one("#search-status", Static).render())
        assert "two characters" in status
        assert ("search", "a") not in fake_service.calls


async def test_quit_closes_service(fake_service):
    app = make_app(fake_service)
    async with app.run_test(size=(120, 32)) as pilot:
        await _settle(pilot)
    assert fake_service.closed is True
