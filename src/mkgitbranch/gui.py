"""
Main GUI application for mkgitbranch.

This module defines the main window and logic for generating conventional git branch names.

Example:
    >>> from mkgitbranch.gui import run_app
    >>> run_app()
"""

import getpass
import os
import re
import subprocess
from pathlib import Path
from typing import Optional
from loguru import logger
import argparse
import tomllib

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QMessageBox,  # Added for error dialog
)
from PySide6.QtCore import Qt, QUrl, QTimer, QEvent
from PySide6.QtGui import QClipboard, QDesktopServices, QKeyEvent

BRANCH_TYPES = ["feat", "fix", "chore", "test", "refactor", "hotfix"]

CONFIG_PATH = Path(__file__).parent.parent.parent / "mkgitbranch_config.toml"


def load_config() -> dict:
    """Load configuration from mkgitbranch_config.toml."""
    try:
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def load_regexes() -> dict[str, re.Pattern]:
    """Load regex patterns for field validation from mkgitbranch_config.toml."""
    config = load_config()
    regex_section = config.get("regex", {})
    return {
        "username": re.compile(regex_section.get("username", r"^[a-zA-Z0-9._-]{2,32}$")),
        "type": re.compile(regex_section.get("type", r"^(feat|fix|chore|test|refactor|hotfix)$")),
        "jira": re.compile(regex_section.get("jira", r"^[A-Z]{2,6}-[0-9]+$")),
        "description": re.compile(regex_section.get("description", r"^[a-z][a-z0-9-]+$")),
    }


def get_current_git_branch() -> Optional[str]:
    """Return the current git branch name, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True
        )
        branch = result.stdout.strip()
        return branch if branch else None
    except Exception:
        return None


def parse_branch_for_jira_and_type(branch: str) -> tuple[Optional[str], Optional[str]]:
    """Extract JIRA issue and type from a branch name if present."""
    # Load regexes for JIRA and type from config
    regexes = load_regexes()
    jira = None
    type_ = None
    # Search for JIRA issue in the branch string
    m = regexes["jira"].search(branch)
    if m:
        jira = m.group(0)
    # Search for type as a slash-delimited segment
    type_match = re.search(r"/(%s)/" % "|".join([re.escape(t) for t in BRANCH_TYPES]), branch)
    if type_match:
        type_ = type_match.group(1)
    return jira, type_


def get_os_username() -> str:
    """Get the current OS username."""
    return getpass.getuser()


def format_branch_name(username: str, type_: str, jira: str, description: str) -> str:
    """Format the branch name according to the conventional branch spec."""
    desc = description.strip().lower().replace(" ", "-")
    return f"{username}/{type_}/{jira}/{desc}"


class ErrorDialog(QDialog):
    """Dialog to display error messages in monospace font with a dismiss button."""
    def __init__(self, message: str, exit_code: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Branch Creation Error")
        self.setMinimumWidth(500)
        layout = QVBoxLayout()
        label = QLabel("<b>Branch creation failed:</b>")
        layout.addWidget(label)
        error_label = QLabel(f'<pre style="font-family: monospace;">{message}</pre>')
        error_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(error_label)
        btn = QPushButton("Dismiss")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        self.setLayout(layout)
        self.exit_code = exit_code


class BranchDialog(QDialog):
    """Main dialog for branch name generation.

    Validates all fields using regexes loaded from regex_config.toml.
    Automatically normalizes JIRA and description fields as the user types.
    """

    def on_username_changed(self, text: str):
        # Only allow alphanumeric, dot, dash, underscore, 2-32 chars
        filtered = "".join(c for c in text if c.isalnum() or c in {".", "-", "_"})
        filtered = filtered[:32]
        if filtered != text:
            cursor = self.username_edit.cursorPosition()
            self.username_edit.setText(filtered)
            self.username_edit.setCursorPosition(min(cursor, len(filtered)))
        self.update_preview()

    def on_type_changed(self, text: str):
        # Only allow valid types from BRANCH_TYPES
        if text not in BRANCH_TYPES:
            self.type_combo.setCurrentText(BRANCH_TYPES[0])
        self.update_preview()

    def on_jira_changed(self, text: str):
        # Only allow A-Z, 0-9, and dash, and force uppercase
        filtered = "".join(c for c in text.upper() if c.isalnum() or c == "-")
        if filtered != text:
            cursor = self.jira_edit.cursorPosition()
            self.jira_edit.setText(filtered)
            self.jira_edit.setCursorPosition(min(cursor, len(filtered)))
        self.update_preview()

    def on_desc_changed(self, text: str):
        # Force lowercase and replace spaces with dashes
        filtered = text.lower().replace(" ", "-")
        filtered = "".join(c for c in filtered if c.isalnum() or c == "-")
        if filtered != text:
            cursor = self.desc_edit.cursorPosition()
            self.desc_edit.setText(filtered)
            self.desc_edit.setCursorPosition(min(cursor, len(filtered)))
        self.update_preview()

    def _set_field_color(self, widget, valid: bool):
        """Set the foreground color of a QLineEdit based on validity."""
        color = self._normal_fg if valid else self._error_fg
        style = widget.styleSheet()
        # Remove any previous color setting
        style = re.sub(r"color:\s*#[0-9a-fA-F]{3,6};?", "", style)
        widget.setStyleSheet(style + f"color: {color};")

    def update_preview(self):
        username = self.username_edit.text().strip()
        type_ = self.type_combo.currentText().strip()
        jira = self.jira_edit.text().strip().upper()
        desc = self.desc_edit.text().strip().lower().replace(" ", "-")
        # Debug: log values and regex match results
        logger.debug(f"username: '{username}', valid: {self.regexes['username'].fullmatch(username)}")
        logger.debug(f"type: '{type_}', valid: {self.regexes['type'].fullmatch(type_)}")
        logger.debug(f"jira: '{jira}', valid: {self.regexes['jira'].fullmatch(jira)}")
        logger.debug(f"description: '{desc}', valid: {self.regexes['description'].fullmatch(desc)}")
        valid_username = bool(self.regexes["username"].fullmatch(username))
        valid_type = bool(self.regexes["type"].fullmatch(type_))
        valid_jira = bool(self.regexes["jira"].fullmatch(jira))
        valid_desc = bool(self.regexes["description"].fullmatch(desc))
        self._set_field_color(self.username_edit, valid_username)
        self._set_field_color(self.jira_edit, valid_jira)
        self._set_field_color(self.desc_edit, valid_desc)
        # type_combo is always valid (from list)
        valid = valid_username and valid_type and valid_jira and valid_desc
        branch = ""
        if valid:
            branch = format_branch_name(username, type_, jira, desc)
        self.preview_value_label.setText(branch)
        self.ok_btn.setEnabled(bool(valid))
        self.copy_btn.setEnabled(bool(valid))

    def copy_to_clipboard(self):
        branch = self.preview_value_label.text()
        if branch:
            QApplication.clipboard().setText(branch, QClipboard.Clipboard)

    def setup_field_normalization(self):
        self.username_edit.textChanged.connect(self.on_username_changed)
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        self.jira_edit.textChanged.connect(self.on_jira_changed)
        self.desc_edit.textChanged.connect(self.on_desc_changed)

    def create_branch(self):
        branch = self.preview_value_label.text()
        if not branch:
            return
        config = load_config()
        template = config.get("branch_create_command_template",
            'git branch --quiet --create --track inherit "{branch_name}"')
        command = template.replace("{branch_name}", branch)
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                dlg = ErrorDialog(result.stderr or result.stdout or "Unknown error", result.returncode, self)
                dlg.exec()
                import sys
                sys.exit(result.returncode)
        except Exception as e:
            dlg = ErrorDialog(str(e), 1, self)
            dlg.exec()
            import sys
            sys.exit(1)

    def eventFilter(self, obj, event):
        """Custom event filter to handle Tab key in JIRA field for dash jump only if text is selected."""
        if obj == self.jira_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Tab:
                # Only jump to after dash if there is a selection
                if self.jira_edit.hasSelectedText():
                    dash_pos = self.jira_edit.text().find('-')
                    if dash_pos != -1:
                        self.jira_edit.setCursorPosition(dash_pos + 1)
                        self.jira_edit.deselect()
                        return True  # Event handled
                # Otherwise, let Tab behave normally (focus next widget)
        return super().eventFilter(obj, event)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Conventional Git Branch Name")
        self.setMinimumWidth(500)

        config = load_config()
        self.regexes = load_regexes()

        # Prefill logic
        branch = get_current_git_branch() or ""
        jira, type_ = parse_branch_for_jira_and_type(branch)
        config_username = config.get("username", None)
        username = config_username if config_username is not None else get_os_username()
        # Username field read-only option
        username_readonly = config.get("username_readonly", False)

        # Widgets
        self.username_edit = QLineEdit(username)
        self.username_edit.setReadOnly(bool(username_readonly))
        self.username_edit.setStyleSheet("padding: 4px;")
        self.type_combo = QComboBox()
        self.type_combo.addItems(BRANCH_TYPES)
        # Add left padding to move text a few pixels to the right in collapsed state
        self.type_combo.setStyleSheet("padding: 4px 4px 4px 16px;")
        # JIRA prefill option
        jira_prefix = config.get("jira_prefix", "")
        jira_value = jira or jira_prefix
        self.jira_edit = QLineEdit(jira_value)
        self.jira_edit.setStyleSheet("padding: 4px;")
        self.desc_edit = QLineEdit()
        self.desc_edit.setStyleSheet("padding: 4px;")
        self.copy_btn = QPushButton("Copy to Clipboard")
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.setEnabled(False)
        self.create_btn = QPushButton("Create Branch")  # New button
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.create_branch)

        # Dialog color theming from config
        theme = config.get("theme", {})
        import platform
        is_dark = False
        if "dark_mode" in theme:
            is_dark = bool(theme["dark_mode"])
        else:
            # Try to auto-detect dark mode (macOS only, fallback to False)
            if platform.system() == "Darwin":
                try:
                    import subprocess
                    result = subprocess.run([
                        "defaults", "read", "-g", "AppleInterfaceStyle"
                    ], capture_output=True, text=True)
                    is_dark = "Dark" in result.stdout
                except Exception:
                    is_dark = False
        palette_key = "dark" if is_dark else "light"
        palette = theme.get(palette_key, {})
        error_fg = palette.get("error_foreground", "#d32f2f")  # Default: red
        normal_fg = palette.get("foreground", "#222222")

        # Field-specific colors
        field_style = ""
        if "field_background" in palette:
            field_style += f"background-color: {palette['field_background']};"
        if "field_foreground" in palette:
            field_style += f"color: {palette['field_foreground']};"
        if field_style:
            self.username_edit.setStyleSheet(self.username_edit.styleSheet() + field_style)
            self.jira_edit.setStyleSheet(self.jira_edit.styleSheet() + field_style)
            self.desc_edit.setStyleSheet(self.desc_edit.styleSheet() + field_style)
            self.type_combo.setStyleSheet(self.type_combo.styleSheet() + field_style)
        # Store for later use
        self._error_fg = error_fg
        self._normal_fg = normal_fg

        # Layout: QGridLayout for fields, slashes, and labels
        grid = QGridLayout()
        grid.addWidget(self.username_edit, 0, 0)
        slash1 = QLabel("/")
        slash1.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        grid.addWidget(slash1, 0, 1)
        grid.addWidget(self.type_combo, 0, 2)
        slash2 = QLabel("/")
        slash2.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        grid.addWidget(slash2, 0, 3)
        grid.addWidget(self.jira_edit, 0, 4)
        slash3 = QLabel("/")
        slash3.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        grid.addWidget(slash3, 0, 5)
        grid.addWidget(self.desc_edit, 0, 6)
        # Row 1: labels
        user_label = QLabel("Username")
        user_label.setAlignment(Qt.AlignHCenter)
        grid.addWidget(user_label, 1, 0)
        grid.addWidget(QLabel(""), 1, 1)
        type_label = QLabel("Type")
        type_label.setAlignment(Qt.AlignHCenter)
        grid.addWidget(type_label, 1, 2)
        grid.addWidget(QLabel(""), 1, 3)
        jira_label = QLabel("JIRA Issue")
        jira_label.setAlignment(Qt.AlignHCenter)
        grid.addWidget(jira_label, 1, 4)
        grid.addWidget(QLabel(""), 1, 5)
        desc_label = QLabel("Description")
        desc_label.setAlignment(Qt.AlignHCenter)
        grid.addWidget(desc_label, 1, 6)

        # Add web link below the fields, above the buttons
        link_label = QLabel(
            '<a href="https://conventional-branch.github.io">Conventional Branch Format Documentation</a>'
        )
        link_label.setOpenExternalLinks(False)
        link_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        link_label.setAlignment(Qt.AlignCenter)
        def open_link():
            QDesktopServices.openUrl(QUrl("https://conventional-branch.github.io"))
        link_label.linkActivated.connect(lambda _: open_link())

        btns = QHBoxLayout()
        btns.addWidget(self.copy_btn)
        btns.addWidget(self.ok_btn)
        btns.addWidget(self.create_btn)  # Add new button

        layout = QVBoxLayout()
        layout.addLayout(grid)
        layout.addWidget(link_label)
        # Only show the preview value (no label)
        # layout.addWidget(self.preview_label)
        # Instead, show the preview value directly in a QLabel
        self.preview_value_label = QLabel()
        self.preview_value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.preview_value_label)
        layout.addLayout(btns)
        self.setLayout(layout)

        # Field-specific widths from config
        field_widths = config.get("field_widths", {})
        self.username_edit.setFixedWidth(field_widths.get("username", 120))
        self.type_combo.setFixedWidth(field_widths.get("type", 100))
        self.jira_edit.setFixedWidth(field_widths.get("jira", 90))
        self.desc_edit.setFixedWidth(field_widths.get("description", 300))

        # Field normalization
        self.setup_field_normalization()
        self.jira_edit.installEventFilter(self)

        # Configurable cursor start options
        # Options: 'username', 'jira_start', 'jira_after_dash', 'description'
        cursor_start = config.get("cursor_start", "description")
        jira_regex = self.regexes["jira"]
        jira_text = self.jira_edit.text()
        if cursor_start == 'username':
            self.username_edit.setFocus()
            self.username_edit.setCursorPosition(0)
        elif cursor_start == 'jira_start':
            self.jira_edit.setFocus()
            self.jira_edit.selectAll()
        elif cursor_start == 'jira_after_dash':
            self.jira_edit.setFocus()
            dash_pos = self.jira_edit.text().find('-')
            if dash_pos != -1:
                self.jira_edit.setCursorPosition(dash_pos + 1)
            else:
                self.jira_edit.setCursorPosition(0)
            self.jira_edit.deselect()
        elif cursor_start == 'description':
            if jira_text and jira_regex.fullmatch(jira_text):
                self.desc_edit.setFocus()
                self.desc_edit.setCursorPosition(0)
            else:
                self.jira_edit.setFocus()
                self.jira_edit.selectAll()
        else:
            self.desc_edit.setFocus()
            self.desc_edit.setCursorPosition(0)

        # Timeout: exit if no typing after configurable minutes (default 10 min, 600,000 ms)
        timeout_minutes = config.get("timeout_minutes", 10)
        if timeout_minutes and timeout_minutes > 0:
            self.timeout_timer = QTimer(self)
            self.timeout_timer.setInterval(timeout_minutes * 60_000)
            self.timeout_timer.setSingleShot(True)
            self.timeout_timer.timeout.connect(self._on_timeout)
            self.timeout_timer.start()
            # Reset timer on any user input
            self.username_edit.textEdited.connect(self._reset_timeout)
            self.type_combo.currentTextChanged.connect(self._reset_timeout)
            self.jira_edit.textEdited.connect(self._reset_timeout)
            self.desc_edit.textEdited.connect(self._reset_timeout)
        else:
            self.timeout_timer = None

        self.update_preview()

    def _reset_timeout(self, *args):
        self.timeout_timer.start()

    def _on_timeout(self):
        logger.error("No input for 10 minutes, exiting with code 1")
        import sys
        sys.exit(1)


def run_app() -> None:
    """Run the mkgitbranch GUI application."""
    import sys

    parser = argparse.ArgumentParser(description="Generate a conventional git branch name.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args, unknown = parser.parse_known_args()
    if args.debug:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
    app = QApplication(sys.argv)
    dlg = BranchDialog()
    if dlg.exec() == QDialog.Accepted:
        pass  # Optionally, do something with the branch name
