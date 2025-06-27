"""
Test suite for mkgitbranch config module.

Covers config loading and regex loading logic.

Run with:
    pytest tests/
"""

import pytest
from mkgitbranch import config


def test_load_config_default(monkeypatch):
    """
    Test that load_config returns a dict and contains expected keys.
    """
    cfg = config.load_config()
    assert isinstance(cfg, dict)
    # Should have at least one expected key
    assert any(k in cfg for k in ("branch_types", "username", "allow_dirty"))


def test_load_regexes(monkeypatch):
    """
    Test that load_regexes returns a dict of compiled regex patterns.
    """
    regexes = config.load_regexes()
    assert isinstance(regexes, dict)
    for key, value in regexes.items():
        assert hasattr(value, "fullmatch")


def test_load_config_override(tmp_path, monkeypatch):
    """
    Test that load_config loads from a custom config file if specified in env.
    """
    config_path = tmp_path / "custom.toml"
    config_path.write_text(
        """
branch_types = ["feat", "fix"]
username = "bob"
allow_dirty = true
"""
    )
    monkeypatch.setenv("MKGITBRANCH_CONFIG", str(config_path))
    cfg = config.load_config()
    assert cfg["username"] == "bob"
    assert cfg["allow_dirty"] is True
    assert "feat" in cfg["branch_types"]
