"""Tests for Config loading and path-allow-list checks."""

from __future__ import annotations

import dataclasses

import pytest

from macwhisper_mcp.config import DEFAULT_WHISPERCPP_BINARY, Config


def test_from_env_parses_colon_separated_paths(tmp_path, monkeypatch):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()

    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", f"{a}:{b}")
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    # Use default log path (~/Library/Logs/...) — tmp_path is outside home on macOS

    cfg = Config.from_env()

    assert cfg.allowed_paths == (a.resolve(), b.resolve())
    assert cfg.mw_cli == "mw"


def test_from_env_rejects_empty_allow_list(monkeypatch):
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", "")
    # Empty string falls back to default, so force explicit empty via ":" separators
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", ":::")
    with pytest.raises(ValueError):
        Config.from_env()


def test_is_path_allowed_accepts_file_in_allowed_dir(config, audio_file):
    assert config.is_path_allowed(audio_file) is True


def test_is_path_allowed_rejects_file_outside(config, tmp_path):
    outside = tmp_path / "outside.m4a"
    outside.write_bytes(b"x")
    assert config.is_path_allowed(outside) is False


def test_is_path_allowed_rejects_nonexistent_path(config, allowed_dir):
    assert config.is_path_allowed(allowed_dir / "nope.m4a") is False


def test_is_path_allowed_rejects_symlink_escape(config, allowed_dir, tmp_path):
    """A symlink inside the allow-list pointing outside must be rejected."""
    outside_target = tmp_path / "secret.m4a"
    outside_target.write_bytes(b"secret")

    symlink = allowed_dir / "sneaky.m4a"
    symlink.symlink_to(outside_target)

    # Symlink resolves outside the allow-list, so it must be rejected.
    assert config.is_path_allowed(symlink) is False


def test_is_path_allowed_accepts_nested_file(config, allowed_dir):
    nested = allowed_dir / "sub" / "deep" / "file.m4a"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"x")
    assert config.is_path_allowed(nested) is True


def test_from_env_rejects_log_path_outside_home(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.setenv("MACWHISPER_LOG_PATH", "/etc/macwhisper.log")
    with pytest.raises(ValueError, match="MACWHISPER_LOG_PATH"):
        Config.from_env()


def test_from_env_loads_watch_done_dir(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    done = tmp_path / "done"
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.setenv("MACWHISPER_WATCH_DONE_DIR", str(done))
    cfg = Config.from_env()
    assert cfg.watch_done_dir == done.resolve()


def test_from_env_watch_done_dir_defaults_none(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.delenv("MACWHISPER_WATCH_DONE_DIR", raising=False)
    cfg = Config.from_env()
    assert cfg.watch_done_dir is None


def test_is_path_allowed_nonstrict_accepts_nonexistent_inside_allow_list(config, allowed_dir):
    """strict=False lets a not-yet-created path inside an allowed root pass
    (used for the watcher's done dir before it is created)."""
    assert config.is_path_allowed(allowed_dir / "done", strict=False) is True


def test_is_path_allowed_nonstrict_rejects_outside(config, tmp_path):
    assert config.is_path_allowed(tmp_path / "elsewhere" / "done", strict=False) is False


def test_is_path_allowed_strict_rejects_nonexistent(config, allowed_dir):
    """strict=True (default) rejects a missing file — preserves transcribe behavior."""
    assert config.is_path_allowed(allowed_dir / "nope.m4a", strict=True) is False


def test_from_env_language_defaults_empty_by_default(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.delenv("MACWHISPER_LANGUAGE_DEFAULTS", raising=False)
    cfg = Config.from_env()
    assert cfg.language_defaults == ()
    assert cfg.language_for(a.resolve()) is None


def test_from_env_parses_language_defaults(tmp_path, monkeypatch):
    a = tmp_path / "a"
    dk = a / "DK"
    de = a / "DE"
    dk.mkdir(parents=True)
    de.mkdir(parents=True)
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.setenv("MACWHISPER_LANGUAGE_DEFAULTS", f"{dk}=da:{de}=de")
    cfg = Config.from_env()
    assert cfg.language_for(dk.resolve()) == "da"
    assert cfg.language_for(de.resolve()) == "de"
    assert cfg.language_for(a.resolve()) is None


def test_from_env_language_defaults_most_specific_wins(tmp_path, monkeypatch):
    a = tmp_path / "a"
    dk = a / "DK"
    dk.mkdir(parents=True)
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.setenv("MACWHISPER_LANGUAGE_DEFAULTS", f"{a}=en:{dk}=da")
    cfg = Config.from_env()
    # A file directly in DK/ should get "da", not the broader "en" default on `a`.
    assert cfg.language_for(dk.resolve()) == "da"
    # A file elsewhere under `a` falls back to the less specific match.
    assert cfg.language_for(a.resolve()) == "en"


def test_from_env_rejects_invalid_language_code(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.setenv("MACWHISPER_LANGUAGE_DEFAULTS", f"{a}=danish")
    with pytest.raises(ValueError, match="Invalid language code"):
        Config.from_env()


def test_from_env_rejects_malformed_language_entry(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.setenv("MACWHISPER_LANGUAGE_DEFAULTS", str(a))  # missing "=lang"
    with pytest.raises(ValueError, match="expected 'dir=lang'"):
        Config.from_env()


def test_language_for_matches_nested_file_parent(tmp_path, monkeypatch):
    a = tmp_path / "a"
    dk = a / "DK"
    dk.mkdir(parents=True)
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.setenv("MACWHISPER_LANGUAGE_DEFAULTS", f"{dk}=da")
    cfg = Config.from_env()
    # A file's parent nested deeper than the mapped dir still matches.
    nested_parent = (dk / "sub").resolve()
    assert cfg.language_for(nested_parent) == "da"


def test_from_env_whispercpp_defaults(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.delenv("MACWHISPER_WHISPERCPP_BINARY", raising=False)
    monkeypatch.delenv("MACWHISPER_WHISPERCPP_MODEL_DIR", raising=False)
    cfg = Config.from_env()
    assert cfg.whispercpp_binary == DEFAULT_WHISPERCPP_BINARY
    assert cfg.whispercpp_model_dir is None


def test_from_env_loads_whispercpp_config(tmp_path, monkeypatch):
    a = tmp_path / "a"
    models = tmp_path / "models"
    a.mkdir()
    models.mkdir()
    monkeypatch.setenv("MACWHISPER_ALLOWED_PATHS", str(a))
    monkeypatch.setenv("MACWHISPER_CLI", "mw")
    monkeypatch.setenv("MACWHISPER_WHISPERCPP_BINARY", "/opt/homebrew/bin/whisper-cli")
    monkeypatch.setenv("MACWHISPER_WHISPERCPP_MODEL_DIR", str(models))
    cfg = Config.from_env()
    assert cfg.whispercpp_binary == "/opt/homebrew/bin/whisper-cli"
    assert cfg.whispercpp_model_dir == models.resolve()


def test_resolve_whispercpp_model_none_when_dir_unset(config):
    assert config.resolve_whispercpp_model("ggml-base.en.bin") is None


def test_resolve_whispercpp_model_returns_path(config, tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    model_file = models / "ggml-base.en.bin"
    model_file.write_bytes(b"fake model")
    cfg = dataclasses.replace(config, whispercpp_model_dir=models.resolve())
    assert cfg.resolve_whispercpp_model("ggml-base.en.bin") == model_file.resolve()


def test_resolve_whispercpp_model_rejects_missing_file(config, tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    cfg = dataclasses.replace(config, whispercpp_model_dir=models.resolve())
    assert cfg.resolve_whispercpp_model("nope.bin") is None


def test_resolve_whispercpp_model_rejects_traversal(config, tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    secret = tmp_path / "secret.bin"
    secret.write_bytes(b"secret")
    cfg = dataclasses.replace(config, whispercpp_model_dir=models.resolve())
    assert cfg.resolve_whispercpp_model("../secret.bin") is None


def test_resolve_whispercpp_model_rejects_symlink_escape(config, tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    outside_target = tmp_path / "secret.bin"
    outside_target.write_bytes(b"secret")
    symlink = models / "sneaky.bin"
    symlink.symlink_to(outside_target)
    cfg = dataclasses.replace(config, whispercpp_model_dir=models.resolve())
    assert cfg.resolve_whispercpp_model("sneaky.bin") is None
