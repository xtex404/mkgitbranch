"""
Git command helpers for mkgitbranch.

This module provides functions for interacting with git, such as retrieving the current branch name and parsing branch names for metadata.
"""

from typing import Optional, Any
import subprocess
import re
from loguru import logger
from PySide6.QtWidgets import QApplication, QDialog
from .config import load_regexes

__all__ = [
    "get_current_git_branch",
    "show_git_error_dialog",
    "parse_branch_for_jira_and_type",
]

def get_current_git_branch(env: dict[str, str] | None = None) -> Optional[str]:
    """
    Return the current git branch name, or None if not in a git repo.

    If an error occurs, display an error dialog and exit with code 1.

    Args:
        env: Optional environment variables to use for subprocess.

    Returns:
        str | None: Current branch name, or None if not found.

    Raises:
        SystemExit: If the branch name is blank, unknown, or an error occurs.

    Examples:
        >>> get_current_git_branch()
        'main'
    """
    try:
        logger.debug(
            "Running subprocess: ['git', 'rev-parse', '--abbrev-ref', 'HEAD']"
        )
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        logger.debug(f"subprocess stdout: {result.stdout}")
        logger.debug(f"subprocess stderr: {result.stderr}")
        if result.returncode != 0:
            logger.error(f"git rev-parse failed with return code {result.returncode}, stderr: {result.stderr}")
            show_git_error_dialog(
                result.stderr or result.stdout or "Unknown error",
                exit_code=1,
                header_message="Failed to get current git branch"
            )
        branch = result.stdout.strip()
        if not branch or branch.lower() == "unknown":
            logger.error(f"Current branch is blank or unknown: '{branch}'")
            show_git_error_dialog(
                "Current branch is blank or unknown",
                exit_code=1,
                header_message="Failed to get current git branch"
            )
        return branch
    except Exception as exc:
        logger.error(f"Exception in get_current_git_branch: {exc}")
        show_git_error_dialog(
            str(exc),
            exit_code=1,
            header_message="Failed to get current git branch"
        )
        return None

def show_git_error_dialog(message: str, exit_code: int = 1, header_message: str = None) -> None:
    """
    Show an error dialog for git errors and exit with the given code.

    Args:
        message: The error message to display.
        exit_code: The exit code to use when exiting.
        header_message: Optional header for the dialog.
    """
    from .gui import ErrorDialog
    import sys
    app = QApplication.instance() or QApplication([])
    dlg = ErrorDialog(
        message,
        exit_code=exit_code,
        parent=None,
        header_message=header_message,
    )
    dlg.exec()
    sys.exit(exit_code)

def parse_branch_for_jira_and_type(branch: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract JIRA issue and type from a branch name if present.

    Args:
        branch: Branch name string.

    Returns:
        tuple: (jira, type) if found, else (None, None).
    """
    regexes = load_regexes()
    jira = None
    type_ = None
    m = regexes["jira"].search(branch)
    if m:
        jira = m.group(0)
    # The list of types should be kept in sync with config.BRANCH_TYPES or passed in
    type_match = re.search(r"/(feat|fix|chore|test|refactor|hotfix)/", branch)
    if type_match:
        type_ = type_match.group(1)
    return jira, type_
