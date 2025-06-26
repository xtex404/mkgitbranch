"""
Git command helpers for mkgitbranch.

This module provides functions for interacting with git, such as retrieving the current branch name and parsing branch names for metadata.
"""

import re
import shlex
import subprocess
from typing import Any, Optional

from PySide6.QtWidgets import QApplication
from loguru import logger

from .config import load_regexes

__all__ = [
    "get_current_git_branch",
    "show_git_error_dialog",
    "parse_branch_for_jira_and_type",
    "is_branch_tracked_by_remote",
    "run_git_create_branch",
    "run_git_checkout_branch",
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

def is_branch_tracked_by_remote(branch: str, env: dict[str, str] | None = None) -> bool:
    """
    Determine if the given branch is tracked by a remote server.

    Args:
        branch: The name of the branch to check.
        env: Optional environment variables for subprocess.

    Returns:
        bool: True if the branch is tracked by a remote, False otherwise.

    Raises:
        RuntimeError: If the git command fails unexpectedly.

    Examples:
        >>> is_branch_tracked_by_remote('main')
        True
    """
    try:
        logger.debug(f"Running subprocess: ['git', 'rev-parse', '--abbrev-ref', '{branch}@{{upstream}}'] with env: {env}")
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        logger.debug(f"subprocess stdout: {result.stdout}")
        logger.debug(f"subprocess stderr: {result.stderr}")
        logger.debug(f"subprocess returncode: {result.returncode}")
        if result.returncode == 0 and result.stdout.strip():
            logger.debug(f"Branch '{branch}' is tracked by a remote")
            return True
        logger.debug(f"Branch '{branch}' is NOT tracked by a remote")
        return False
    except Exception as exc:
        logger.error(f"Failed to check if branch '{branch}' is tracked by a remote: {exc}")
        raise RuntimeError(f"Failed to check if branch '{branch}' is tracked by a remote: {exc}")

def run_git_create_branch(
    branch: str,
    template: str,
    env: dict[str, str] | None = None,
    parent: Any = None,
) -> bool:
    """
    Create a new git branch using the provided template.

    If the command is 'git branch', remove '--track' and its parameter and log a warning.
    Returns True if 'git branch' was used, otherwise False.

    Args:
        branch: The branch name to create.
        template: The command template string.
        env: Optional environment variables for subprocess.
        parent: Parent widget for dialogs.

    Returns:
        bool: True if 'git branch' was used, False otherwise.

    Raises:
        SystemExit: If the git command fails.
    """
    safe_branch = shlex.quote(branch)
    command = template.replace("{branch_name}", safe_branch)
    command_args = shlex.split(command)
    used_git_branch = False
    if len(command_args) > 1 and command_args[1] == "branch":
        new_args = []
        skip_next = False
        for arg in command_args:
            if skip_next:
                skip_next = False
                continue
            if arg == "--track":
                skip_next = True
                continue
            new_args.append(arg)
        logger.warning(
            "Detected use of 'git branch' for branch creation; '--track' parameter has been removed. "
            "It is recommended to use 'git switch' for branch creation"
        )
        command_args = new_args
        command = shlex.join(command_args)
        used_git_branch = True

    logger.debug(
        f"Running subprocess: {command} with env: {{k: v for k, v in (env or {{}}).items() if k == 'PATH' or k.startswith('GIT_')}}"
    )
    result = subprocess.run(
        command_args,
        shell=False,
        capture_output=True,
        text=True,
        env=env,
    )
    logger.debug(f"subprocess stdout: {result.stdout}")
    logger.debug(f"subprocess stderr: {result.stderr}")
    if result.returncode != 0:
        logger.error(f"Git command failed with return code {result.returncode}, stderr: {result.stderr}")
        from .gui import ErrorDialog
        dlg = ErrorDialog(
            result.stderr or result.stdout or "Unknown error",
            result.returncode,
            parent,
        )
        dlg.exec()
        import sys
        sys.exit(result.returncode)
    return used_git_branch

def run_git_checkout_branch(
    branch: str,
    env: dict[str, str] | None = None,
    parent: Any = None,
) -> None:
    """
    Switch to the given branch using 'git checkout {branch}'.

    Args:
        branch: The branch name to switch to.
        env: Optional environment variables for subprocess.
        parent: Parent widget for dialogs.

    Raises:
        SystemExit: If the checkout fails.
    """
    cmd = ["git", "checkout", branch]
    logger.warning(f"Running 'git checkout {branch}' to switch to the new branch after 'git branch'")
    logger.debug(
        f"Running subprocess: {shlex.join(cmd)} with env: {{k: v for k, v in (env or {{}}).items() if k == 'PATH' or k.startswith('GIT_')}}"
    )
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
    )
    logger.debug(f"subprocess stdout: {result.stdout}")
    logger.debug(f"subprocess stderr: {result.stderr}")
    if result.returncode != 0:
        logger.error(f"Git checkout failed with return code {result.returncode}, stderr: {result.stderr}")
        from .gui import ErrorDialog
        dlg = ErrorDialog(
            result.stderr or result.stdout or "Unknown error",
            result.returncode,
            parent,
            header_message="Failed to switch to new branch",
        )
        dlg.exec()
        import sys
        sys.exit(result.returncode)
