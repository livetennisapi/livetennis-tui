# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-16

### Added

- Live view: in-play matches with tournament, ranked players, per-set score,
  current points, serving marker, tiebreak flag and a derived break-point
  badge (returner at AD, or at 40 with the server below 40; never in
  tiebreaks — the same semantics as the API's Break-Point Radar).
- Fixtures view: upcoming matches, earliest first, honest about date-only
  fixtures (no invented midnight times).
- Player search modal with profile card (ranking, points, movement, country,
  plays, age).
- Server-side tour filter on `a`/`w` (press again to clear), `t` for all.
- Auto-refresh every 60 s (configurable, floored at 15 s) with a live quota
  readout from the quota-exempt `/usage` endpoint; auto-refresh pauses when
  the daily quota is spent and resumes itself after the reset.
- Friendly no-key, empty, 401 and 429 states citing the real FREE-tier
  limits (30 requests/minute, 100/day).
- Offline test suite (pytest + Textual pilot) and a CI matrix for
  Python 3.10–3.13.

[Unreleased]: https://github.com/livetennisapi/livetennis-tui/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/livetennisapi/livetennis-tui/releases/tag/v0.1.0
