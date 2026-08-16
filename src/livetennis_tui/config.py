"""API-key and settings resolution.

Precedence, first hit wins:

1. ``LIVETENNIS_API_KEY`` — this app's own variable.
2. ``LIVETENNISAPI_KEY`` — the official SDK's variable, honoured so a key that
   already works for ``pip install livetennisapi`` works here unchanged.
3. ``~/.config/livetennis-tui/config`` (``$XDG_CONFIG_HOME`` respected) — a
   plain-text file: either a bare key on the first non-comment line, or
   ``key = value`` lines (``api_key`` for the key, ``refresh`` for the
   auto-refresh interval in seconds).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: Honest default: one live refresh a minute. At the FREE tier's 100 calls a
#: day, a continuously open live view spends the day's quota in about 1h40m —
#: the footer shows exactly where you stand (that read is quota-exempt).
DEFAULT_REFRESH_SECONDS = 60

#: Floor. Anything faster than this is disallowed rather than silently allowed:
#: 30 requests/minute is the FREE burst window, and a sub-15s refresh would
#: also eat the daily quota in minutes.
MIN_REFRESH_SECONDS = 15


@dataclass
class Settings:
    api_key: str | None
    refresh_seconds: int = DEFAULT_REFRESH_SECONDS
    #: Where the key came from — shown in the no-key help so the user knows
    #: what was searched.
    source: str | None = None


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    return Path(base) / "livetennis-tui" / "config"


def _parse_config_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            values[key.strip().lower()] = value.strip().strip("'\"")
        elif "api_key" not in values:
            # A bare token on its own line is the simplest possible config.
            values["api_key"] = line
    return values


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ

    refresh = DEFAULT_REFRESH_SECONDS
    key: str | None = None
    source: str | None = None

    file_values = _parse_config_file(config_path())
    if file_values.get("refresh"):
        try:
            refresh = int(file_values["refresh"])
        except ValueError:
            pass

    for var in ("LIVETENNIS_API_KEY", "LIVETENNISAPI_KEY"):
        value = (env.get(var) or "").strip()
        if value:
            key, source = value, f"${var}"
            break
    if key is None and file_values.get("api_key"):
        key, source = file_values["api_key"], str(config_path())

    refresh = max(MIN_REFRESH_SECONDS, refresh)
    return Settings(api_key=key, refresh_seconds=refresh, source=source)
