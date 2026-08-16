"""Capture the README screenshots.

Runs the real app headlessly against the test suite's mocked service and
exports Textual's built-in SVG screenshots — genuine captures of the actual
UI, just with canned data instead of a live network.

    python scripts/screenshots.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # for `tests.conftest`

from tests.conftest import FakeService  # noqa: E402

from livetennis_tui.app import LiveTennisTUI  # noqa: E402
from livetennis_tui.config import Settings  # noqa: E402

DOCS = ROOT / "docs"
SIZE = (110, 14)


def make_app() -> LiveTennisTUI:
    return LiveTennisTUI(
        service=FakeService(),
        settings=Settings(api_key="twjp_demo", refresh_seconds=60),
    )


async def settle(pilot) -> None:
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def save(app: LiveTennisTUI, name: str) -> None:
    svg = app.export_screenshot(title=f"livetennis-tui — {name}")
    path = DOCS / f"{name}.svg"
    path.write_text(svg, encoding="utf-8")
    print(f"wrote {path}")


async def capture_live() -> None:
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        save(app, "live")


async def capture_fixtures() -> None:
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await pilot.press("f")
        await settle(pilot)
        save(app, "fixtures")


async def capture_search() -> None:
    app = make_app()
    async with app.run_test(size=(110, 30)) as pilot:
        await settle(pilot)
        await pilot.press("slash")
        await pilot.pause()
        await pilot.press(*"alcaraz")
        await pilot.press("enter")
        await settle(pilot)
        save(app, "search")


async def main() -> None:
    DOCS.mkdir(exist_ok=True)
    await capture_live()
    await capture_fixtures()
    await capture_search()


if __name__ == "__main__":
    asyncio.run(main())
