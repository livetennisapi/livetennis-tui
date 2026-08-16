"""Key/settings resolution: env precedence, config file, refresh floor."""

from livetennis_tui.config import (
    DEFAULT_REFRESH_SECONDS,
    MIN_REFRESH_SECONDS,
    config_path,
    load_settings,
)


def _isolate(monkeypatch, tmp_path):
    """Point config at an empty temp dir and clear both env vars."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("LIVETENNIS_API_KEY", raising=False)
    monkeypatch.delenv("LIVETENNISAPI_KEY", raising=False)


def _write_config(tmp_path, text):
    cfg_dir = tmp_path / "livetennis-tui"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config").write_text(text, encoding="utf-8")


def test_no_key_anywhere(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    settings = load_settings()
    assert settings.api_key is None
    assert settings.refresh_seconds == DEFAULT_REFRESH_SECONDS


def test_app_env_var_wins(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("LIVETENNIS_API_KEY", "twjp_app")
    monkeypatch.setenv("LIVETENNISAPI_KEY", "twjp_sdk")
    _write_config(tmp_path, "api_key = twjp_file\n")
    settings = load_settings()
    assert settings.api_key == "twjp_app"
    assert settings.source == "$LIVETENNIS_API_KEY"


def test_sdk_env_var_is_honoured(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("LIVETENNISAPI_KEY", "twjp_sdk")
    settings = load_settings()
    assert settings.api_key == "twjp_sdk"
    assert settings.source == "$LIVETENNISAPI_KEY"


def test_config_file_key_value(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_config(tmp_path, "# my key\napi_key = 'twjp_file'\nrefresh = 90\n")
    settings = load_settings()
    assert settings.api_key == "twjp_file"
    assert settings.refresh_seconds == 90
    assert settings.source == str(config_path())


def test_config_file_bare_key(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_config(tmp_path, "\n# comment\ntwjp_bare\n")
    settings = load_settings()
    assert settings.api_key == "twjp_bare"


def test_refresh_floor_is_enforced(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_config(tmp_path, "api_key = k\nrefresh = 1\n")
    settings = load_settings()
    assert settings.refresh_seconds == MIN_REFRESH_SECONDS


def test_bad_refresh_value_falls_back(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_config(tmp_path, "api_key = k\nrefresh = fast\n")
    settings = load_settings()
    assert settings.refresh_seconds == DEFAULT_REFRESH_SECONDS


def test_blank_env_var_is_ignored(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("LIVETENNIS_API_KEY", "   ")
    _write_config(tmp_path, "api_key = twjp_file\n")
    settings = load_settings()
    assert settings.api_key == "twjp_file"
