"""
Test suite for mkgitbranch git_utils module.

Covers branch name parsing and current branch retrieval logic.

Run with:
    pytest tests/
"""

import pytest
from mkgitbranch import git_utils


def test_parse_branch_for_jira_and_type():
    """
    Test parsing of branch names for JIRA and type extraction.
    """
    branch = "alice/feat/ABC-123/description"
    jira, type_ = git_utils.parse_branch_for_jira_and_type(branch)
    assert jira == "ABC-123"
    assert type_ == "feat"
    # Test with missing parts
    branch2 = "bob/fix/description"
    jira2, type2 = git_utils.parse_branch_for_jira_and_type(branch2)
    assert jira2 is None
    assert type2 == "fix"


def test_get_current_git_branch(monkeypatch):
    """
    Test get_current_git_branch returns the branch name from git output.
    """

    class Result:
        stdout = "main\n"
        returncode = 0

    monkeypatch.setattr(git_utils.subprocess, "run", lambda *a, **k: Result())
    branch = git_utils.get_current_git_branch()
    assert branch == "main"


def test_get_current_git_branch_error(monkeypatch):
    """
    Test get_current_git_branch returns None if git fails.
    """

    class Result:
        stdout = ""
        returncode = 1

    monkeypatch.setattr(git_utils.subprocess, "run", lambda *a, **k: Result())
    branch = git_utils.get_current_git_branch()
    assert branch is None


def test_parse_branch_for_jira_and_type_invalid():
    """
    Test parse_branch_for_jira_and_type returns (None, None) for invalid input.
    """
    branch = "invalidbranchname"
    jira, type_ = git_utils.parse_branch_for_jira_and_type(branch)
    assert jira is None
    assert type_ is None


def test_parse_branch_for_jira_and_type_partial():
    """
    Test parse_branch_for_jira_and_type returns type but not jira if jira is missing.
    """
    branch = "alice/feat/desc"
    jira, type_ = git_utils.parse_branch_for_jira_and_type(branch)
    assert jira is None
    assert type_ == "feat"


def test_parse_branch_for_jira_and_type_exception_handling(monkeypatch, caplog):
    """
    Test that parse_branch_for_jira_and_type handles exceptions and does not expose sensitive info.
    """
    # Simulate an exception in the function (e.g., by monkeypatching re.match)
    import re

    original_match = re.match

    def raise_exc(*a, **k):
        raise ValueError("Sensitive info: should not be exposed")

    monkeypatch.setattr(re, "match", raise_exc)
    with caplog.at_level("ERROR"):
        jira, type_ = git_utils.parse_branch_for_jira_and_type(
            "alice/feat/ABC-123/desc"
        )
        assert jira is None
        assert type_ is None
        # Ensure sensitive info is not in logs
        for record in caplog.records:
            assert "Sensitive info" not in record.getMessage()
