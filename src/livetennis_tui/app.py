"""The Textual application.

Three surfaces, all on FREE-tier endpoints:

- **Live** — in-play matches, refreshed every 60s by default.
- **Fixtures** — upcoming matches, earliest first.
- **Player search** — a modal search over the roster, opening a profile card.

All network work happens in thread workers; the UI thread never blocks. The
footer keeps an honest quota count via ``/usage`` (that read is quota-exempt),
and when the daily quota is spent the app *pauses* data refreshes instead of
hammering 429s — the quota poll notices the reset and resumes by itself.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static

from .config import Settings, load_settings
from .derive import (
    TOUR_LABELS,
    age_years,
    break_point,
    format_points,
    format_sets,
    format_start,
    movement_glyph,
    player_label,
    quota_summary,
    serve_mark,
)
from .service import FriendlyError, TennisService

ACCENT = "#c8f04b"  # tennis-ball green


NO_KEY_HELP = """\
[b]No API key found.[/b]

livetennis-tui looks for a key in, in order:

  1. [b]$LIVETENNIS_API_KEY[/b]
  2. [b]$LIVETENNISAPI_KEY[/b]  (the official SDK's variable)
  3. [b]~/.config/livetennis-tui/config[/b]  — a file containing either the
     bare key, or an [b]api_key = …[/b] line

A FREE key takes a minute: [b]livetennisapi.com/subscribe/free[/b]
(FREE tier: live + upcoming matches, players — 30 requests/min, 100/day.)

Then:  [b]export LIVETENNIS_API_KEY=twjp_…[/b]  and run [b]livetennis-tui[/b] again.
"""


def _match_row(match: Any) -> tuple[Text, ...]:
    """One live-table row from a Match model."""
    score = getattr(match, "score", None)
    points = getattr(score, "points", None) if score else None
    server = getattr(score, "server", None) if score else None
    tiebreak = bool(getattr(score, "is_tiebreak", False)) if score else False

    bp_count, _bp_side = break_point(points, server, tiebreak)

    p1 = getattr(match, "p1", None)
    p2 = getattr(match, "p2", None)
    sets = getattr(score, "sets", None) if score else None
    sets_txt = "-".join(str(s) for s in sets) if sets else ""

    def side(player, num: int) -> Text:
        mark = serve_mark(server, num)
        label = player_label(player)
        text = Text()
        if mark:
            text.append(mark + " ", style=f"bold {ACCENT}")
        else:
            text.append("  ")
        text.append(label)
        return text

    points_text = Text(format_points(points, tiebreak))
    if tiebreak:
        points_text.stylize("bold yellow")
    if bp_count:
        points_text.append(f"  BP×{bp_count}" if bp_count > 1 else "  BP", style="bold red")

    tour = (getattr(match, "tour", None) or "").upper()
    tournament = Text(getattr(match, "tournament", None) or "?")
    if tour:
        tournament.append(f"  {tour}", style="dim")

    return (
        tournament,
        side(p1, 1),
        side(p2, 2),
        Text(sets_txt, style="bold"),
        Text(format_sets(getattr(score, "games", None) if score else None)),
        points_text,
    )


def _fixture_row(match: Any) -> tuple[str, ...]:
    p1 = getattr(match, "p1", None)
    p2 = getattr(match, "p2", None)
    tour = (getattr(match, "tour", None) or "").upper()
    return (
        format_start(getattr(match, "scheduled_time", None)),
        getattr(match, "tournament", None) or "?",
        tour,
        getattr(match, "round", None) or "",
        f"{player_label(p1)}  vs  {player_label(p2)}",
    )


class PlayerProfile(ModalScreen[None]):
    """A profile card for one player, fetched on open."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def __init__(self, service: TennisService, player_id: int, name: str) -> None:
        super().__init__()
        self._service = service
        self._player_id = player_id
        self._name = name

    def compose(self) -> ComposeResult:
        with Container(id="profile-box"):
            yield Label(self._name, id="profile-name")
            yield Static("Loading…", id="profile-body")
            yield Label("esc to close", classes="modal-hint")

    def on_mount(self) -> None:
        self.run_worker(self._load, thread=True, exclusive=True)

    def _load(self) -> None:
        try:
            player = self._service.player(self._player_id)
        except FriendlyError as err:
            self.app.call_from_thread(self._show_text, f"[red]{err.title}[/red]\n{err.detail}")
            return
        self.app.call_from_thread(self._show_player, player)

    def _show_text(self, markup: str) -> None:
        self.query_one("#profile-body", Static).update(markup)

    def _show_player(self, player: Any) -> None:
        if player is None:
            self._show_text("Player not found.")
            return
        rows = []

        def add(label: str, value) -> None:
            if value not in (None, ""):
                rows.append(f"[b]{label:<10}[/b] {value}")

        tour = (getattr(player, "tour", None) or "").upper()
        ranking = getattr(player, "ranking", None)
        move = movement_glyph(getattr(player, "ranking_movement", None))
        add("Tour", tour)
        add("Ranking", f"#{ranking}  {move}".rstrip() if ranking else None)
        add("Points", getattr(player, "ranking_points", None))
        add("Country", (getattr(player, "country", None) or "").upper() or None)
        hand = {"R": "Right-handed", "L": "Left-handed"}.get(
            (getattr(player, "hand", None) or "").upper(), getattr(player, "hand", None)
        )
        add("Plays", hand)
        age = age_years(getattr(player, "birthday", None))
        add("Age", age)
        self._show_text("\n".join(rows) or "No details on file for this player.")


class PlayerSearch(ModalScreen[None]):
    """Type-a-name player search; Enter on a row opens the profile."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def __init__(self, service: TennisService) -> None:
        super().__init__()
        self._service = service
        self._players: list[Any] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Label("Player search", id="search-title")
            yield Input(placeholder="Name — e.g. alcaraz", id="search-input")
            table = DataTable(id="search-results", cursor_type="row")
            table.add_columns("Player", "Tour", "Rank", "Points", "Country")
            yield table
            yield Static("", id="search-status")
            yield Label("enter to search / open · esc to close", classes="modal-hint")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if len(query) < 2:
            self.query_one("#search-status", Static).update("Type at least two characters.")
            return
        self.query_one("#search-status", Static).update(f"Searching “{query}”…")
        self.run_worker(lambda: self._search(query), thread=True, exclusive=True, group="search")

    def _search(self, query: str) -> None:
        try:
            players = self._service.search_players(query)
        except FriendlyError as err:
            self.app.call_from_thread(
                self.query_one("#search-status", Static).update,
                f"[red]{err.title}[/red] — {err.detail}",
            )
            return
        self.app.call_from_thread(self._show_results, players)

    def _show_results(self, players: list[Any]) -> None:
        self._players = players
        table = self.query_one("#search-results", DataTable)
        table.clear()
        status = self.query_one("#search-status", Static)
        if not players:
            status.update("No players matched — ranked players surface first, try a surname.")
            return
        status.update(f"{len(players)} result(s). Enter opens a profile.")
        for i, p in enumerate(players):
            table.add_row(
                getattr(p, "name", None) or "?",
                (getattr(p, "tour", None) or "").upper(),
                f"#{p.ranking}" if getattr(p, "ranking", None) else "—",
                str(getattr(p, "ranking_points", None) or "—"),
                (getattr(p, "country", None) or "").upper(),
                key=str(i),
            )
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            player = self._players[int(event.row_key.value)]
        except (TypeError, ValueError, IndexError):
            return
        player_id = getattr(player, "id", None)
        if player_id is None:
            return
        self.app.push_screen(
            PlayerProfile(self._service, int(player_id), getattr(player, "name", None) or "Player")
        )


class NoKeyScreen(ModalScreen[None]):
    """Shown instead of data when no API key could be found. q still quits."""

    def compose(self) -> ComposeResult:
        with Container(id="nokey-box"):
            yield Static(NO_KEY_HELP, id="nokey-help")


class LiveTennisTUI(App[None]):
    """Live tennis in the terminal, on the Live Tennis API FREE tier."""

    TITLE = "livetennis-tui"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("l", "show_view('live')", "Live"),
        Binding("f", "show_view('fixtures')", "Fixtures"),
        Binding("slash,s", "search", "Search players", key_display="/"),
        Binding("a", "filter_tour('atp')", "ATP"),
        Binding("w", "filter_tour('wta')", "WTA"),
        Binding("t", "cycle_tour", "All tours"),
        Binding("r", "refresh_now", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        service: TennisService | None = None,
        settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings or load_settings()
        self._service = service
        self.tour: str | None = None
        self.view = "live"
        self.quota_paused = False
        self._timer = None

    # -- layout ---------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="main"):
            live = DataTable(id="live-table", cursor_type="row")
            live.add_columns("Tournament", "Player 1", "Player 2", "Sets", "Games", "Points")
            yield live
            fixtures = DataTable(id="fixtures-table", cursor_type="row")
            fixtures.add_columns("Start (UTC)", "Tournament", "Tour", "Round", "Match")
            fixtures.display = False
            yield fixtures
            yield Static("", id="empty-state")
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "Live"
        if self._service is None:
            if not self.settings.api_key:
                self.push_screen(NoKeyScreen())
                self._set_status("No API key — see instructions above.", error=True)
                return
            self._service = TennisService(api_key=self.settings.api_key)
        self._timer = self.set_interval(self.settings.refresh_seconds, self._tick)
        self.action_refresh_now()

    # -- actions --------------------------------------------------------------

    def action_show_view(self, view: str) -> None:
        self.view = view
        self.sub_title = "Live" if view == "live" else "Fixtures"
        self.query_one("#live-table", DataTable).display = view == "live"
        self.query_one("#fixtures-table", DataTable).display = view == "fixtures"
        self.action_refresh_now()

    def action_filter_tour(self, tour: str) -> None:
        # Pressing the active filter again clears it.
        self.tour = None if self.tour == tour else tour
        self.action_refresh_now()

    def action_cycle_tour(self) -> None:
        self.tour = None
        self.action_refresh_now()

    def action_search(self) -> None:
        if self._service is not None:
            self.push_screen(PlayerSearch(self._service))

    def action_refresh_now(self) -> None:
        if self._service is None:
            return
        self.run_worker(self._fetch, thread=True, exclusive=True, group="refresh")

    # -- data flow ------------------------------------------------------------

    def _tick(self) -> None:
        self.action_refresh_now()

    def _fetch(self) -> None:
        """Worker: read the active view (unless quota-paused) plus /usage."""
        service = self._service
        assert service is not None
        matches: list[Any] | None = None
        error: FriendlyError | None = None

        if not self.quota_paused:
            try:
                if self.view == "live":
                    matches = service.live_matches(self.tour)
                else:
                    matches = service.upcoming_matches(self.tour)
            except FriendlyError as err:
                error = err

        usage = None
        try:
            usage = service.usage()  # quota-exempt: safe even while paused
        except FriendlyError:
            pass

        self.call_from_thread(self._apply, matches, usage, error)

    def _apply(self, matches: list[Any] | None, usage: Any, error: FriendlyError | None) -> None:
        if usage is not None and self.quota_paused:
            remaining = (getattr(usage, "today", None) or {}).get("remaining_day")
            if remaining is not None and remaining > 0:
                self.quota_paused = False  # the day rolled over — resume
        if error is not None:
            if error.kind == "quota_day":
                self.quota_paused = True
            self._set_status(f"{error.title} — {error.detail}", error=True, usage=usage)
            self._show_empty(f"[b]{error.title}[/b]\n\n{error.detail}")
            return
        if matches is not None:
            if self.view == "live":
                self._fill_live(matches)
            else:
                self._fill_fixtures(matches)
        self._set_status("", usage=usage)

    def _fill_live(self, matches: list[Any]) -> None:
        table = self.query_one("#live-table", DataTable)
        table.clear()
        for m in matches:
            table.add_row(*_match_row(m))
        if matches:
            self._show_empty(None)
        else:
            scope = TOUR_LABELS.get(self.tour, self.tour)
            self._show_empty(
                f"[b]No live {scope} matches right now.[/b]\n\n"
                "The tour never sleeps for long — f shows what's coming up next."
            )

    def _fill_fixtures(self, matches: list[Any]) -> None:
        table = self.query_one("#fixtures-table", DataTable)
        table.clear()
        for m in matches:
            table.add_row(*_fixture_row(m))
        if matches:
            self._show_empty(None)
        else:
            scope = TOUR_LABELS.get(self.tour, self.tour)
            self._show_empty(f"[b]No upcoming {scope} fixtures found.[/b]")

    def _show_empty(self, markup: str | None) -> None:
        empty = self.query_one("#empty-state", Static)
        if markup is None:
            empty.update("")
            empty.display = False
        else:
            empty.update(markup)
            empty.display = True

    def _set_status(self, message: str, *, error: bool = False, usage: Any = None) -> None:
        bar = self.query_one("#status-bar", Static)
        pieces = []
        scope = TOUR_LABELS.get(self.tour, self.tour)
        pieces.append(f"[b]{scope}[/b]")
        quota = quota_summary(usage)
        if quota:
            pieces.append(quota)
        if self.quota_paused:
            pieces.append("[yellow]auto-refresh paused (daily quota)[/yellow]")
        else:
            pieces.append(f"refresh {self.settings.refresh_seconds}s")
        if message:
            style = "red" if error else "dim"
            pieces.append(f"[{style}]{message}[/{style}]")
        bar.update("  ·  ".join(pieces))

    def on_unmount(self) -> None:
        if self._service is not None:
            self._service.close()


def main() -> None:
    """Console entry point."""
    LiveTennisTUI().run()


if __name__ == "__main__":  # pragma: no cover
    main()
