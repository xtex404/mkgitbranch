"""
Main GUI application for mkgitbranch.

This module defines the main window and logic for generating conventional git branch names.

Example:
    >>> from mkgitbranch.gui import run_app
    >>> run_app()
"""

import argparse
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from functools import lru_cache

from PySide6.QtCore import QUrl, Qt, QTimer, QEvent
from PySide6.QtGui import QClipboard
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from loguru import logger

from mkgitbranch.config import load_config, load_regexes
from mkgitbranch.git_utils import get_current_git_branch, parse_branch_for_jira_and_type

BRANCH_TYPES: list[str] = ["feat", "fix", "chore", "test", "refactor", "hotfix"]

APPLICATION_NAME: str = "mkgitbranch"


def _show_git_error_dialog(message: str, exit_code: int = 1, header_message: str = None) -> None:
    """
    Show an error dialog for git errors and exit with the given code.

    Args:
        message: The error message to display.
        exit_code: The exit code to use when exiting.
        header_message: Optional header for the dialog.
    """
    import sys
    dlg = ErrorDialog(
        message,
        exit_code=exit_code,
        parent=None,
        header_message=header_message,
    )
    dlg.exec()
    sys.exit(exit_code)


def format_branch_name(username: str, type_: str, jira: str, description: str) -> str:
    """
    Format the branch name according to the conventional branch spec.

    Args:
        username: Username string.
        type_: Branch type.
        jira: JIRA issue string.
        description: Description string.

    Returns:
        str: Formatted branch name.
    """
    desc = description.strip().lower().replace(" ", "-")
    return f"{username}/{type_}/{jira}/{desc}"


class ErrorDialog(QDialog):
    """
    Dialog to display error messages in monospace font with a dismiss button.

    Args:
        message: Error message to display.
        exit_code: Exit code to use if dialog is closed.
        parent: Parent widget.
        header_message: Optional header message.
        window_title: Window title for the dialog.
    """

    def __init__(
        self,
        message: str,
        exit_code: int,
        parent: Any,
        header_message: str | None = None,
        window_title: str = f"{APPLICATION_NAME} Error",
    ):
        # --- Dialog setup ---
        super().__init__(parent)
        self.setWindowTitle(window_title)
        self.setMinimumWidth(500)
        layout = QVBoxLayout()

        # --- Header message (if provided) ---
        if header_message:
            header_label = QLabel(
                f'<div style="text-align:center; font-weight:bold;">{header_message}</div>'
            )
            layout.addWidget(header_label)

        # --- Error message ---
        error_label = QLabel(f"<div style=\"text-align:center\">{message}</div>")
        error_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(error_label)

        # --- Spacer for visual separation ---
        from PySide6.QtWidgets import QSpacerItem, QSizePolicy
        layout.addSpacerItem(QSpacerItem(0, 13, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # --- Close button setup ---
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        btn_width = 130
        btn.setFixedWidth(btn_width)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.exit_code = exit_code


class SuccessDialog(QDialog):
    """
    Dialog to display a success message after branch creation.

    Exits the application with code 0 when the user presses OK or after a 1-minute timeout.
    Plays a configurable sound file when shown.

    Args:
        message: Success message to display.
        parent: Parent widget.
        window_title: Window title for the dialog.
        sound_file: Path to the sound file to play.
    """

    def __init__(
        self,
        message: str,
        parent: Any = None,
        window_title: str = f"{APPLICATION_NAME} Success",
        sound_file: str = "resources/leeroy.mp3",
    ):
        # --- Dialog setup ---
        super().__init__(parent)
        self.setWindowTitle(window_title)
        self.setMinimumWidth(400)
        layout = QVBoxLayout()

        # --- Success message ---
        success_label = QLabel(message)
        success_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(success_label)

        # --- Spacer for visual separation ---
        from PySide6.QtWidgets import QSpacerItem, QSizePolicy
        layout.addSpacerItem(QSpacerItem(0, 13, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # --- OK button setup ---
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setFixedWidth(130)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # --- Play sound if file exists ---
        self._player = None
        if sound_file:
            logger.debug(f"Attempting to play sound file: {sound_file}")
            self._play_sound(sound_file)

    def _play_sound(self, sound_file: str) -> None:
        """
        Play the specified sound file using QMediaPlayer.

        Args:
            sound_file: Path to the sound file.
        """
        from pathlib import Path

        logger.debug(f"_play_sound called with: {sound_file}")

        # --- Try to resolve the sound file path in several ways ---
        resolved_path: Path | None = None

        # Try as given, with expanduser and resolve
        candidate = Path(sound_file).expanduser().resolve()
        if candidate.is_file():
            resolved_path = candidate
            logger.debug(f"Sound file found as given: {resolved_path}")
        else:
            # Try relative to this file's directory (i.e., package resource)
            gui_dir = Path(__file__).parent
            candidate_pkg = (gui_dir / sound_file).expanduser().resolve()
            logger.debug(f"Trying package-relative path: {candidate_pkg}")
            if candidate_pkg.is_file():
                resolved_path = candidate_pkg
                logger.debug(f"Sound file found at package-relative path: {resolved_path}")
            else:
                # Try relative to project root (one level up from src/mkgitbranch)
                project_root = gui_dir.parent.parent
                candidate_root = (project_root / sound_file).expanduser().resolve()
                logger.debug(f"Trying project-root-relative path: {candidate_root}")
                if candidate_root.is_file():
                    resolved_path = candidate_root
                    logger.debug(f"Sound file found at project-root-relative path: {resolved_path}")
                else:
                    logger.debug(
                        f"Sound file does not exist: {sound_file} "
                        f"(checked: {candidate}, {candidate_pkg}, {candidate_root})"
                    )
                    return
        # --- Setup and play sound using QMediaPlayer ---
        try:
            self._player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_output)
            self._audio_output.setVolume(0.8)

            # Connect to mediaStatusChanged to play as soon as loaded
            def on_media_status_changed(status):
                from PySide6.QtMultimedia import QMediaPlayer
                logger.debug(f"QMediaPlayer mediaStatusChanged: {status}")
                if status == QMediaPlayer.MediaStatus.LoadedMedia:
                    logger.debug("Media loaded, calling play()")
                    self._player.play()
                    # Disconnect to avoid repeated calls
                    self._player.mediaStatusChanged.disconnect(on_media_status_changed)

            self._player.mediaStatusChanged.connect(on_media_status_changed)
            logger.debug(f"Setting QMediaPlayer source to: {resolved_path}")
            self._player.setSource(QUrl.fromLocalFile(str(resolved_path)))
            # If already loaded, play immediately (for cached files)
            from PySide6.QtMultimedia import QMediaPlayer as QMP
            if self._player.mediaStatus() == QMP.MediaStatus.LoadedMedia:
                logger.debug("Media already loaded, calling play() immediately")
                self._player.play()
        except Exception as exc:
            logger.error(f"Exception while trying to play sound file '{sound_file}': {exc}")

    def _on_ok(self) -> None:
        """Gracefully exit the application on OK or timeout."""
        self.accept()
        QApplication.quit()


class BranchDialog(QDialog):
    """
    Main dialog for branch name generation.

    Validates all fields using regexes loaded from regex_config.toml.
    Automatically normalizes JIRA and description fields as the user types.

    Attributes:
        env: Environment variables for subprocesses.
        regexes: Regex patterns for validation.
    """

    def on_username_changed(self, text: str) -> None:
        """
        Normalize and validate username field.

        Args:
            text: Input text from username field.
        """
        filtered = "".join(c for c in text if c.isalnum() or c in {".", "-", "_"})
        filtered = filtered[:32]
        if filtered != text:
            cursor = self.username_edit.cursorPosition()
            self.username_edit.setText(filtered)
            self.username_edit.setCursorPosition(min(cursor, len(filtered)))
        self.update_preview()

    def on_type_changed(self, text: str) -> None:
        """
        Validate type field.

        Args:
            text: Input text from type combo box.
        """
        if text not in BRANCH_TYPES:
            self.type_combo.setCurrentText(BRANCH_TYPES[0])
        self.update_preview()

    def on_jira_changed(self, text: str) -> None:
        """
        Normalize and validate JIRA field.

        If the user switches from letters to numbers without a dash, insert the dash automatically.

        Args:
            text: Input text from JIRA field.
        """
        filtered = "".join(c for c in text.upper() if c.isalnum() or c == "-")
        # Auto-insert dash if user switches from letters to numbers without a dash
        if "-" not in filtered:
            # Find the first digit after a sequence of letters
            match = re.match(r"^([A-Z]+)([0-9].*)$", filtered)
            if match:
                filtered = f"{match.group(1)}-{match.group(2)}"
        if filtered != text:
            cursor = self.jira_edit.cursorPosition()
            self.jira_edit.setText(filtered)
            # Adjust cursor position if dash was inserted
            if "-" in filtered and "-" not in text:
                cursor += 1
            self.jira_edit.setCursorPosition(min(cursor, len(filtered)))
        self.update_preview()

    def on_desc_changed(self, text: str) -> None:
        """
        Normalize and validate description field.

        Args:
            text: Input text from description field.
        """
        filtered = text.lower().replace(" ", "-")
        filtered = "".join(c for c in filtered if c.isalnum() or c == "-")
        if filtered != text:
            cursor = self.desc_edit.cursorPosition()
            self.desc_edit.setText(filtered)
            self.desc_edit.setCursorPosition(min(cursor, len(filtered)))
        self.update_preview()

    def _set_field_color(self, widget: QLineEdit, valid: bool) -> None:
        """
        Set the foreground color of a QLineEdit based on validity.

        Args:
            widget: QLineEdit widget.
            valid: Whether the field is valid.
        """
        # Only change the text color, never the background color
        color = self._field_fg if valid else self._error_fg
        style = widget.styleSheet()
        # Remove any previous color setting (but not background)
        style = re.sub(r"color:\s*#[0-9a-fA-F]{3,6};?", "", style)
        widget.setStyleSheet(style + f"color: {color};")

    def update_preview(self) -> None:
        """
        Update the branch preview label and button states.
        Show the preview as each component matches its regex, not only when all are valid.
        """
        # --- Gather and normalize field values ---
        username = self.username_edit.text().strip()
        type_ = self.type_combo.currentText().strip()
        jira = self.jira_edit.text().strip().upper()
        desc = self.desc_edit.text().strip().lower().replace(" ", "-")

        # --- Validate each field using regexes ---
        valid_username = bool(self.regexes["username"].fullmatch(username))
        valid_type = bool(self.regexes["type"].fullmatch(type_))
        valid_jira = bool(self.regexes["jira"].fullmatch(jira))
        valid_desc = bool(self.regexes["description"].fullmatch(desc))

        # --- Set field colors based on validity ---
        self._set_field_color(self.username_edit, valid_username)
        self._set_field_color(self.jira_edit, valid_jira)
        self._set_field_color(self.desc_edit, valid_desc)

        # --- Build preview using only valid components ---
        preview_username = username if valid_username else ""
        preview_type = type_ if valid_type else ""
        preview_jira = jira if valid_jira else ""
        preview_desc = desc if valid_desc else ""

        preview_parts = [preview_username, preview_type, preview_jira, preview_desc]
        preview = "/".join([part for part in preview_parts if part])

        self.preview_value_label.setText(preview)

        # --- Enable/disable buttons based on validity ---
        prev_copy_enabled = self.copy_btn.isEnabled()
        prev_create_enabled = self.create_btn.isEnabled()
        all_valid = valid_username and valid_type and valid_jira and valid_desc
        self.copy_btn.setEnabled(all_valid)
        self.create_btn.setEnabled(all_valid)

        # --- Set default button logic ---
        if not prev_create_enabled and self.create_btn.isEnabled():
            self.create_btn.setDefault(True)
            self.copy_btn.setDefault(False)
            self.cancel_btn.setDefault(False)
        elif not prev_copy_enabled and self.copy_btn.isEnabled():
            if not self.create_btn.isEnabled():
                self.copy_btn.setDefault(True)
                self.copy_btn.setDefault(False)
                self.cancel_btn.setDefault(False)
        if not self.copy_btn.isEnabled() and not self.create_btn.isEnabled():
            self.copy_btn.setDefault(False)
            self.create_btn.setDefault(False)
            self.cancel_btn.setDefault(True)

    def copy_to_clipboard(self) -> None:
        """
        Copy the branch name to the clipboard.
        """
        branch = self.preview_value_label.text()
        if branch:
            QApplication.clipboard().setText(branch, QClipboard.Mode.Clipboard)

    def setup_field_normalization(self) -> None:
        """
        Connect field normalization handlers.
        """
        self.username_edit.textChanged.connect(self.on_username_changed)
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        self.jira_edit.textChanged.connect(self.on_jira_changed)
        self.desc_edit.textChanged.connect(self.on_desc_changed)

    def create_branch(self) -> None:
        """
        Create a new git branch using the formatted branch name.

        After executing the branch creation command, re-check the current git branch.
        If the branch has not changed to the expected branch, display an error dialog.
        On success, display a success dialog and exit with code 0.

        Raises:
            SystemExit: If the git command fails or the branch is not switched.

        Examples:
            >>> dlg = BranchDialog()
            >>> dlg.create_branch()
        """
        import shlex

        # --- Gather branch name and config ---
        branch = self.preview_value_label.text()
        if not branch:
            return
        config = load_config()
        template = config.get(
            "branch_create_command_template",
            'git switch --quiet --track --create "{branch_name}"',
        )

        # --- Prepare git command ---
        safe_branch = shlex.quote(branch)
        command = template.replace("{branch_name}", safe_branch)
        command_args = shlex.split(command)

        # --- Handle 'git branch' command special case ---
        if len(command_args) > 1 and command_args[1] == "branch":
            new_args = []
            skip_next = False
            for i, arg in enumerate(command_args):
                if skip_next:
                    skip_next = False
                    continue
                if arg == "--track":
                    skip_next = True
                    continue
                new_args.append(arg)
            logger.warning(
                "Detected use of 'git branch' for branch creation; '--track' parameter has been removed. "
                "It is recommended to use 'git switch' for branch creation."
            )
            command_args = new_args
            command = shlex.join(command_args)

        try:
            # --- Run git command to create branch ---
            logger.debug(
                f"Running subprocess: `{command}`"
            )
            result = subprocess.run(
                command_args if not isinstance(command, str) else command,
                shell=isinstance(command, str),
                capture_output=True,
                text=True,
                env=self.env,
            )
            logger.debug(f"subprocess stdout: {result.stdout}")
            logger.debug(f"subprocess stderr: {result.stderr}")

            # --- Handle git command failure ---
            if result.returncode != 0:
                logger.error(f"Git command failed with return code {result.returncode}, stderr: {result.stderr}")
                dlg = ErrorDialog(
                    result.stderr or result.stdout or "Unknown error",
                    result.returncode,
                    self,
                )
                dlg.exec()
                import sys
                sys.exit(result.returncode)

            # --- Verify branch switch ---
            current_branch = get_current_git_branch(env=self.env)
            logger.debug(f"Current branch after command: {current_branch}")
            if current_branch != branch:
                logger.error(
                    f"Branch switch failed: expected '{branch}', got '{current_branch or 'unknown'}'"
                )
                dlg = ErrorDialog(
                    f"Expected branch '{branch}' but current branch is '{current_branch or 'unknown'}'",
                    exit_code=1,
                    parent=self,
                    header_message="Branch switch failed",
                )
                dlg.exec()
                import sys
                sys.exit(1)

            # --- Show success dialog and exit with code 0 ---
            self.accept()
            sound_file = config.get("success_sound_file", "resources/leeroy.mp3")
            dlg = SuccessDialog(
                f'<div style="text-align:center;">Branch created and checked out successfully:<br/><br/><span style="color:lime;font-weight:bold;font-face:Monaco,Menlo,monospace">{branch}</span></div>',
                parent=None,
                sound_file=sound_file,
            )
            dlg.exec()
            import sys
            sys.exit(0)
        except Exception as e:
            logger.error(f"Exception during branch creation: {e}")
            dlg = ErrorDialog(
                str(e),
                header_message="git returned an error",
                exit_code=1,
                parent=self,
            )
            dlg.exec()
            import sys
            sys.exit(1)

    def eventFilter(self, obj: Any, event: QEvent) -> bool:
        """
        Custom event filter for JIRA and description field tab/enter handling.

        Args:
            obj: The object receiving the event.
            event: The event object.

        Returns:
            bool: True if event handled, else False.
        """
        from PySide6.QtGui import QKeyEvent

        # Tab in JIRA field: jump after dash if selected
        if obj == self.jira_edit and event.type() == QEvent.Type.KeyPress:
            if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_Tab:
                if self.jira_edit.hasSelectedText():
                    dash_pos = self.jira_edit.text().find('-')
                    if dash_pos != -1:
                        self.jira_edit.setCursorPosition(dash_pos + 1)
                        self.jira_edit.deselect()
                        return True

        # Tab or Enter in description field: focus/create
        if obj == self.desc_edit and event.type() == QEvent.Type.KeyPress:
            if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_Tab:
                self.create_btn.setFocus()
                return True
            if isinstance(event, QKeyEvent) and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.create_btn.isEnabled():
                    self.create_branch()
                    return True
                else:
                    QApplication.beep()
                    return True

        # Prevent ENTER from activating Cancel when Create is not enabled
        if obj in (self.username_edit, self.type_combo, self.jira_edit) and event.type() == QEvent.Type.KeyPress:
            if isinstance(event, QKeyEvent) and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.create_btn.isEnabled():
                    self.create_branch()
                else:
                    QApplication.beep()
                return True

        return super().eventFilter(obj, event)

    def __init__(
        self,
        parent: Any = None,
        env: dict[str, str] | None = None,
        prefill_jira: str | None = None,
    ):
        """
        Initialize the BranchDialog.

        Args:
            parent: Parent widget.
            env: Optional environment variables for subprocesses.
            prefill_jira: JIRA value to pre-fill, if available.
        """
        # --- Dialog setup and config ---
        super().__init__(parent)
        self.env = env or None
        self.setWindowTitle("Generate Conventional Git Branch Name")
        self.setMinimumWidth(500)

        config = load_config()
        self.regexes = load_regexes()

        # --- Pre-fill fields based on current branch and config ---
        branch = get_current_git_branch(env=self.env) or ""
        jira, type_ = parse_branch_for_jira_and_type(branch)
        config_username = config.get("username", None)
        username = config_username if config_username is not None else get_os_username()
        username_readonly = config.get("username_readonly", False)
        effective_jira = prefill_jira if prefill_jira is not None else (jira or None)

        # --- Setup fields, UI, timers, and preview ---
        self._setup_fields(username, username_readonly, type_, effective_jira, config)
        self._setup_ui(config)
        self._setup_timers(config)
        self.update_preview()

    def _setup_fields(self, username: str, username_readonly: bool, type_: str, jira: str | None, config: dict[str, Any]) -> None:
        """
        Set up the input fields for the dialog.
        """
        self.username_edit = QLineEdit(username)
        self.username_edit.setReadOnly(bool(username_readonly))
        self.username_edit.setStyleSheet("padding: 4px;")
        self.type_combo = QComboBox()
        self.type_combo.addItems(BRANCH_TYPES)
        self.type_combo.setStyleSheet("padding: 4px 4px 4px 16px;")
        jira_prefix = config.get("jira_prefix", "")
        # Use the provided jira value if available, otherwise fall back to config
        jira_value = jira if jira is not None else jira_prefix
        self.jira_edit = QLineEdit(jira_value)
        self.jira_edit.setStyleSheet("padding: 4px;")
        self.desc_edit = QLineEdit()
        self.desc_edit.setStyleSheet("padding: 4px;")
        self.copy_btn = QPushButton("Copy")
        self.create_btn = QPushButton("Create")
        self.cancel_btn = QPushButton("Cancel")
        self.copy_btn.setEnabled(False)
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.create_branch)
        self.cancel_btn.clicked.connect(self.reject)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        for btn in (self.cancel_btn, self.copy_btn, self.create_btn):
            btn.setFixedWidth(125)
        field_widths = config.get("field_widths", {})
        self.username_edit.setFixedWidth(field_widths.get("username", 100))
        self.type_combo.setFixedWidth(field_widths.get("type", 110))
        self.jira_edit.setFixedWidth(field_widths.get("jira", 90))
        self.desc_edit.setFixedWidth(field_widths.get("description", 250))
        self.setup_field_normalization()
        self.jira_edit.installEventFilter(self)
        self.desc_edit.installEventFilter(self)

    def _setup_ui(self, config: dict[str, Any]) -> None:
        """
        Set up the UI layout and theme for the dialog.
        """
        theme = config.get("theme", {})
        import platform
        is_dark = False
        if "dark_mode" in theme:
            is_dark = bool(theme["dark_mode"])
        else:
            if platform.system() == "Darwin":
                try:
                    import subprocess
                    result = subprocess.run(
                        ["defaults", "read", "-g", "AppleInterfaceStyle"],
                        capture_output=True,
                        text=True,
                    )
                    is_dark = "Dark" in result.stdout
                except Exception:
                    is_dark = True
        palette_key = "dark" if is_dark else "light"
        palette = theme.get(palette_key, {})
        if is_dark:
            error_fg = palette.get("error_foreground", "#EE4B2B")
            label_fg = palette.get("label_foreground", "#cccccc")
            field_fg = palette.get("field_foreground", "#ffffff")
        else:
            error_fg = palette.get("error_foreground", "#ffffff")
            label_fg = palette.get("label_foreground", "#222222")
            field_fg = palette.get("field_foreground", "#EE4B2B")
        self._error_fg = error_fg
        self._field_fg = field_fg
        field_style = ""
        if field_fg:
            field_style += f"color: {field_fg};"
        for widget in (self.username_edit, self.jira_edit, self.desc_edit):
            widget.setStyleSheet(widget.styleSheet() + field_style)
        self.type_combo.setStyleSheet(self.type_combo.styleSheet() + field_style)
        if self.type_combo.lineEdit() is not None:
            self.type_combo.lineEdit().setStyleSheet(self.type_combo.lineEdit().styleSheet() + field_style)
        grid = QGridLayout()
        grid.addWidget(self.username_edit, 0, 0)
        slash1 = QLabel("/")
        slash1.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(slash1, 0, 1)
        grid.addWidget(self.type_combo, 0, 2)
        slash2 = QLabel("/")
        slash2.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(slash2, 0, 3)
        grid.addWidget(self.jira_edit, 0, 4)
        slash3 = QLabel("/")
        slash3.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(slash3, 0, 5)
        grid.addWidget(self.desc_edit, 0, 6)
        user_label = QLabel("Username")
        user_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        user_label.setStyleSheet(f"color: {label_fg};")
        grid.addWidget(user_label, 1, 0)
        grid.addWidget(QLabel(""), 1, 1)
        type_label = QLabel("Type")
        type_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        type_label.setStyleSheet(f"color: {label_fg};")
        grid.addWidget(type_label, 1, 2)
        grid.addWidget(QLabel(""), 1, 3)
        jira_label = QLabel("JIRA Issue")
        jira_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        jira_label.setStyleSheet(f"color: {label_fg};")
        grid.addWidget(jira_label, 1, 4)
        grid.addWidget(QLabel(""), 1, 5)
        desc_label = QLabel("Description")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        desc_label.setStyleSheet(f"color: {label_fg};")
        grid.addWidget(desc_label, 1, 6)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.copy_btn)
        btns.addWidget(self.create_btn)
        layout = QVBoxLayout()
        layout.addLayout(grid)
        from PySide6.QtWidgets import QSpacerItem, QSizePolicy
        layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        self.preview_value_label = QLabel()
        self.preview_value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_value_label.setStyleSheet(
            "font-family: Menlo, Monaco, 'Fira Mono', 'Liberation Mono', monospace; font-size: 1.1em;"
        )
        layout.addWidget(self.preview_value_label)
        layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        layout.addLayout(btns)
        self.setLayout(layout)
        cursor_start = config.get("cursor_start", "description")
        jira_regex = self.regexes["jira"]
        jira_text = self.jira_edit.text()
        # --- Add 'type' as a valid option for cursor_start ---
        if cursor_start == "username":
            self.username_edit.setFocus()
            self.username_edit.setCursorPosition(0)
        elif cursor_start == "type":
            self.type_combo.setFocus()
            # Optionally select the text in the combo box if editable
            if self.type_combo.lineEdit() is not None:
                self.type_combo.lineEdit().selectAll()
        elif cursor_start == "jira_start":
            self.jira_edit.setFocus()
            self.jira_edit.selectAll()
        elif cursor_start == "jira_after_dash":
            self.jira_edit.setFocus()
            dash_pos = self.jira_edit.text().find("-")
            if dash_pos != -1:
                self.jira_edit.setCursorPosition(dash_pos + 1)
            else:
                self.jira_edit.setCursorPosition(0)
            self.jira_edit.deselect()
        elif cursor_start == "description":
            if jira_text and jira_regex.fullmatch(jira_text):
                self.desc_edit.setFocus()
                self.desc_edit.setCursorPosition(0)
            else:
                self.jira_edit.setFocus()
                self.jira_edit.selectAll()
        else:
            self.desc_edit.setFocus()
            self.desc_edit.setCursorPosition(0)

    def _setup_timers(self, config: dict[str, Any]) -> None:
        """
        Set up the inactivity timeout timer for the dialog.
        """
        timeout_minutes = config.get("timeout_minutes", 10)
        if timeout_minutes and timeout_minutes > 0:
            self.timeout_timer = QTimer(self)
            self.timeout_timer.setInterval(timeout_minutes * 60_000)
            self.timeout_timer.setSingleShot(True)
            self.timeout_timer.timeout.connect(self._on_timeout)
            self.timeout_timer.start()
            self.username_edit.textEdited.connect(self._reset_timeout)
            self.type_combo.currentTextChanged.connect(self._reset_timeout)
            self.jira_edit.textEdited.connect(self._reset_timeout)
            self.desc_edit.textEdited.connect(self._reset_timeout)
        else:
            self.timeout_timer = None

        self.update_preview()

    def _reset_timeout(self, *args) -> None:
        """
        Reset the inactivity timeout timer.
        """
        self.timeout_timer.start()

    def _on_timeout(self) -> None:
        """
        Handle inactivity timeout.
        """
        logger.error("No input for 10 minutes, exiting with code 1")
        import sys
        sys.exit(1)


def _filtered_env_for_log(env: dict[str, str] | None) -> dict[str, str]:
    """
    Return a filtered copy of the environment containing only PATH and variables starting with GIT_.

    Args:
        env: The environment dictionary.

    Returns:
        dict: Filtered environment dictionary.
    """
    if not env:
        return {}
    return {k: v for k, v in env.items() if k == "PATH" or k.startswith("GIT_")}


def get_os_username() -> str:
    """
    Get the current OS username.

    Returns:
        str: Username of the current OS user.
    """
    import getpass
    return getpass.getuser()


def strip_anchors(pattern: str) -> str:
    """Remove ^ and $ anchors from a regex pattern string."""
    return pattern.removeprefix("^").removesuffix("$")


def run_app() -> None:
    """
    Run the mkgitbranch GUI application.

    This function determines the working directory for git operations in the following order:
    1. If the GIT_WORK_TREE environment variable is set, use its value as the worktree and do not modify it.
    2. If the --directory argument is provided, use it as the worktree and set GIT_WORK_TREE accordingly.
    3. Otherwise, use the current working directory.

    Raises:
        SystemExit: If the directory is invalid or not a git repo.

    Examples:
        >>> run_app()
    """
    import sys

    parser = argparse.ArgumentParser(description="Generate a conventional git branch name.")
    parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="Optional working directory for git operations",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    if args.debug:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
    env = os.environ.copy()
    work_tree = None

    # Prefer GIT_WORK_TREE if set in the environment
    git_work_tree_env = env.get("GIT_WORK_TREE")
    if git_work_tree_env:
        work_tree = git_work_tree_env
        # Do not change env or cwd if GIT_WORK_TREE is set
    elif args.directory:
        dir_path = Path(args.directory).expanduser().resolve()
        if dir_path.is_dir():
            env["GIT_WORK_TREE"] = str(dir_path)
            work_tree = str(dir_path)
            os.chdir(dir_path)
        else:
            logger.error(f"Provided directory is not valid: {args.directory}")
            app = QApplication(sys.argv)
            dlg = ErrorDialog(
                f'<span style="text-align:center;font-family:Menlo,Monaco,monospace;font-size:0.8em">{args.directory}</span> is not a directory!',
                parent=None,
                exit_code=1,
            )
            dlg.exec()
            sys.exit(1)
    # If neither GIT_WORK_TREE nor directory is set, use current directory
    try:
        logger.debug(
            f"Running subprocess: ['git', 'rev-parse', '--is-inside-work-tree'] "
            f"with env: {_filtered_env_for_log(env)}"
        )
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        logger.debug(f"subprocess stdout: {result.stdout}")
        logger.debug(f"subprocess stderr: {result.stderr}")
        if result.stdout.strip() != "true":
            raise Exception()
    except Exception:
        logger.error(f"Directory is not a valid git repo: {work_tree or args.directory or os.getcwd()}")
        app = QApplication(sys.argv)
        dlg = ErrorDialog(
            f'<span style="text-align:center;font-family:Menlo,Monaco,monospace;font-size:0.8em;">{work_tree or args.directory or os.getcwd()}</span> is not a valid git repo!',
            parent=None,
            exit_code=1,
        )
        dlg.exec()
        sys.exit(1)

    # --- Check for dirty repo if allow_dirty is False ---
    config = load_config()
    allow_dirty = config.get("allow_dirty", False)
    if not allow_dirty:
        logger.debug("Checking for dirty working tree because allow_dirty is False or unset")
        dirty_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            env=env,
        )
        logger.debug(f"git status --porcelain output: {dirty_result.stdout!r}")
        if dirty_result.stdout.strip():
            logger.error("Repository has uncommitted changes and allow_dirty is False")
            app = QApplication(sys.argv)
            dlg = ErrorDialog(
                "Repository has uncommitted changes. Please commit or stash them before continuing.",
                exit_code=1,
                parent=None,
                header_message="Uncommitted Changes Detected",
            )
            dlg.exec()
            sys.exit(1)

    # --- Check forbidden_source_branches before proceeding ---
    forbidden_patterns = config.get("forbidden_source_branches", [])
    if forbidden_patterns:
        logger.debug(f"Checking forbidden_source_branches: {forbidden_patterns}")
        current_branch = get_current_git_branch(env=env)
        for pattern in forbidden_patterns:
            try:
                regex = re.compile(pattern)
                if regex.fullmatch(current_branch):
                    logger.error(
                        f"Current branch '{current_branch}' matches forbidden pattern '{pattern}' from configuration"
                    )
                    app = QApplication(sys.argv)
                    dlg = ErrorDialog(
                        f"Branch <b>{current_branch}</b> is not allowed as a source branch for new branches.",
                        exit_code=1,
                        parent=None,
                        header_message="Forbidden Source Branch",
                    )
                    dlg.exec()
                    sys.exit(1)
            except re.error as exc:
                logger.error(f"Invalid regex in forbidden_source_branches: {pattern} ({exc})")
    # --- New logic: pre-fill JIRA from current branch if possible ---

    logger.debug("Attempting to pre-fill JIRA from current branch using env: {}", _filtered_env_for_log(env))
    current_branch = get_current_git_branch(env=env)
    logger.debug(f"Current branch detected: {current_branch!r}")

    prefill_jira = None
    if current_branch:
        # Try to match username/type/jira/description exactly
        regexes = load_regexes()

        username_re = strip_anchors(regexes["username"].pattern)
        type_re = strip_anchors(regexes["type"].pattern)
        jira_re = strip_anchors(regexes["jira"].pattern)
        desc_re = strip_anchors(regexes["description"].pattern)
        logger.debug(
            f"Regex patterns (no anchors): username={username_re!r}, type={type_re!r}, "
            f"jira={jira_re!r}, desc={desc_re!r}"
        )
        pattern = re.compile(
            rf"^(?P<username>{username_re})/(?P<type>{type_re})/(?P<jira>{jira_re})/(?P<desc>{desc_re})$",
            re.IGNORECASE,
        )
        logger.debug(f"Compiled branch pattern: {pattern.pattern}")
        m = pattern.match(current_branch)
        if m:
            prefill_jira = m.group("jira")
            logger.debug(f"JIRA prefill matched from branch: {prefill_jira}")
        else:
            logger.debug("Current branch did not match the expected pattern for JIRA prefill")
    # --------------------------------------------------------------

    app = QApplication(sys.argv)
    dlg = BranchDialog(env=env, prefill_jira=prefill_jira)
    result = dlg.exec()
    # Use sys.exit here if you want to set an exit code
    if result == QDialog.DialogCode.Accepted:
        app.exec()  # Wait for any further dialogs (e.g., SuccessDialog) to finish
        sys.exit(0)
    else:
        sys.exit(0)  # Changed from 100 to 0 for cancel
