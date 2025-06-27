"""
Test suite for mkgitbranch GUI logic.

This module contains unit tests for the main functions and classes in gui.py that can be tested
without a running QApplication event loop.

Run with:
    pytest tests/
"""

import pytest
from mkgitbranch import gui


def test_git_error_dialog_exception():
    """
    Test that GitErrorDialogException stores message and exit_code correctly.
    """
    exc = gui.GitErrorDialogException("error message", exit_code=42)
    assert str(exc) == "error message"
    assert exc.exit_code == 42


def test_format_branch_name():
    """
    Test branch name formatting logic.
    """
    result = gui.format_branch_name("alice", "feat", "JIRA-123", "Add new feature")
    assert result == "alice/feat/JIRA-123/add-new-feature"


def test_strip_anchors():
    """
    Test that strip_anchors removes ^ and $ from regex patterns.
    """
    assert gui.strip_anchors("^abc$") == "abc"
    assert gui.strip_anchors("abc$") == "abc"
    assert gui.strip_anchors("^abc") == "abc"
    assert gui.strip_anchors("abc") == "abc"


def test_get_os_username(monkeypatch):
    """
    Test get_os_username returns the expected username.
    """
    monkeypatch.setattr("getpass.getuser", lambda: "testuser")
    assert gui.get_os_username() == "testuser"


def test__filtered_env_for_log():
    """
    Test that _filtered_env_for_log returns only PATH and GIT_ variables.
    """
    env = {
        "PATH": "/bin:/usr/bin",
        "GIT_WORK_TREE": "/repo",
        "HOME": "/home/user",
        "GIT_DIR": ".git",
    }
    filtered = gui._filtered_env_for_log(env)
    assert filtered == {
        "PATH": "/bin:/usr/bin",
        "GIT_WORK_TREE": "/repo",
        "GIT_DIR": ".git",
    }


def test_determine_work_tree(tmp_path, monkeypatch):
    """
    Test determine_work_tree sets GIT_WORK_TREE and changes directory if directory is valid.
    """
    env = {}
    d = tmp_path / "repo"
    d.mkdir()
    cwd = tmp_path.cwd()
    monkeypatch.chdir(tmp_path)
    result = gui.determine_work_tree(str(d), env)
    assert env["GIT_WORK_TREE"] == str(d)
    assert result == str(d)
    # Should not change directory if GIT_WORK_TREE is set
    env2 = {"GIT_WORK_TREE": str(d)}
    result2 = gui.determine_work_tree("/should/not/change", env2)
    assert result2 == str(d)


def test_validate_git_repo_invalid(monkeypatch):
    """
    Test validate_git_repo raises GitErrorDialogException if not a git repo.
    """

    def fake_run(*a, **kw):
        raise Exception("not a git repo")

    monkeypatch.setattr(gui.subprocess, "run", fake_run)
    with pytest.raises(gui.GitErrorDialogException):
        gui.validate_git_repo("/not/a/repo", {})


def test_validate_dirty_repo(monkeypatch):
    """
    Test validate_dirty_repo raises GitErrorDialogException if repo is dirty and allow_dirty is False.
    """
    monkeypatch.setattr(gui, "load_config", lambda: {"allow_dirty": False})

    class Result:
        stdout = " M file.py\n"

    monkeypatch.setattr(gui.subprocess, "run", lambda *a, **k: Result())
    with pytest.raises(gui.GitErrorDialogException):
        gui.validate_dirty_repo({})


def test_validate_source_branch(monkeypatch):
    """
    Test validate_source_branch raises GitErrorDialogException if branch matches forbidden pattern.
    """
    monkeypatch.setattr(
        gui, "load_config", lambda: {"forbidden_source_branches": ["main"]}
    )
    monkeypatch.setattr(gui, "get_current_git_branch", lambda env=None: "main")
    with pytest.raises(gui.GitErrorDialogException):
        gui.validate_source_branch({})


def test_extract_prefill_jira(monkeypatch):
    """
    Test extract_prefill_jira extracts JIRA from branch name.
    """
    monkeypatch.setattr(
        gui, "get_current_git_branch", lambda env=None: "alice/feat/ABC-123/desc"
    )
    monkeypatch.setattr(
        gui,
        "load_regexes",
        lambda: {
            "username": gui.re.compile(r"[a-z]+"),
            "type": gui.re.compile(r"feat|fix"),
            "jira": gui.re.compile(r"[A-Z]+-[0-9]+"),
            "description": gui.re.compile(r"[a-z-]+"),
        },
    )
    assert gui.extract_prefill_jira({}) == "ABC-123"
