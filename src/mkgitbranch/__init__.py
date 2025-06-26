"""
A cross-platform GUI tool for generating conventional git branch names.

This module provides a graphical interface to assist users in creating branch names
that follow the Conventional Branch specification (https://conventional-branch.github.io).

Features:
- Auto-detects the current git branch and pre-fills type and JIRA issue fields if possible.
- Auto-fills the username from the operating system.
- Provides a dropdown for branch type and input fields for JIRA issue and description.
- Validates input and previews the resulting branch name.
- Designed for cross-platform use with a modern GUI library (PySide6).

Example:
    >>> from mkgitbranch import main
    >>> main()

Notes:
    This tool is intended to be run as a standalone application.
    Ensure that PySide6 is installed in your environment.
"""


def main() -> None:
    """Run the mkgitbranch GUI application."""
    from .gui import run_app

    run_app()
