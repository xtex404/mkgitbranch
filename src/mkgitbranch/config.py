"""
Configuration loading and validation utilities for mkgitbranch.

This module provides functions to load configuration from TOML files and extract regex patterns for field validation.
"""

import os
import re
import tomllib
from pathlib import Path
from typing import Any
import platformdirs
from loguru import logger

def find_pyproject_config(start_path: Path) -> dict[str, Any]:
    """
    Walk backwards from start_path to root, looking for a pyproject.toml file.
    If found, return the [tool.mkgitbranch] section as a dict, or {} if not found.

    Args:
        start_path: The directory to start searching from.

    Returns:
        dict: The [tool.mkgitbranch] config dict, or {} if not found or invalid.
    """
    current = start_path.expanduser().resolve()
    logger.debug(f"Searching for pyproject.toml starting from {current}")
    for parent in [current] + list(current.parents):
        pyproject = parent / "pyproject.toml"
        logger.debug(f"Checking for pyproject.toml at {pyproject}")
        if pyproject.is_file():
            logger.debug(f"Found pyproject.toml at {pyproject}")
            try:
                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
                tool_section = data.get("tool")
                if not isinstance(tool_section, dict):
                    logger.debug(f"No [tool] section in {pyproject}")
                    continue
                mkgitbranch_section = tool_section.get("mkgitbranch")
                if isinstance(mkgitbranch_section, dict):
                    logger.debug(f"Found [tool.mkgitbranch] section in {pyproject}")
                    return mkgitbranch_section
                else:
                    logger.debug(f"No [tool.mkgitbranch] section in {pyproject}")
                    return {}
            except Exception as e:
                logger.error(f"Failed to read pyproject.toml at {pyproject}: {e}")
                return {}
    logger.debug("No pyproject.toml with [tool.mkgitbranch] found in any parent directory")
    return {}

def find_toml_config(path: Path) -> dict[str, Any]:
    """
    Load a TOML config file if it exists.

    Args:
        path: Path to the TOML file.

    Returns:
        dict: The config dict, or {} if not found or invalid.
    """
    logger.debug(f"Checking for config file at {path}")
    if path.is_file():
        logger.debug(f"Found config file at {path}")
        try:
            with path.open("rb") as f:
                config = tomllib.load(f)
            logger.debug(f"Loaded config from {path}")
            return config
        except Exception as e:
            logger.error(f"Failed to read config at {path}: {e}")
            return {}
    logger.debug(f"No config file found at {path}")
    return {}

def load_config() -> dict[str, Any]:
    """
    Load configuration from the first available source:
    1. pyproject.toml [tool.mkgitbranch] (searching upwards from cwd)
    2. mkgitbranch.toml in $XDG_CONFIG_HOME/mkgitbranch/
    3. mkgitbranch.toml in platformdirs.user_config_dir
    4. .mkgitbranch.toml in the user home directory

    Returns:
        dict: Configuration dictionary. Empty if file not found or invalid.
    """
    logger.debug("Starting configuration loading process")
    cwd = Path.cwd()
    logger.debug(f"Attempting to load config from pyproject.toml [tool.mkgitbranch] starting at {cwd}")
    pyproject_config = find_pyproject_config(cwd)
    if pyproject_config:
        logger.debug("Using configuration from pyproject.toml [tool.mkgitbranch]")
        return pyproject_config
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        xdg_config_path = Path(xdg_config_home).expanduser().resolve() / "mkgitbranch" / "mkgitbranch.toml"
        logger.debug(f"Attempting to load config from {xdg_config_path} (XDG_CONFIG_HOME)")
        config = find_toml_config(xdg_config_path)
        if config:
            logger.debug(f"Using configuration from {xdg_config_path}")
            return config
    config_dir = Path(platformdirs.user_config_dir("mkgitbranch")).expanduser().resolve()
    config_path = config_dir / "mkgitbranch.toml"
    logger.debug(f"Attempting to load config from {config_path}")
    config = find_toml_config(config_path)
    if config:
        logger.debug(f"Using configuration from {config_path}")
        return config
    home_config_path = Path.home().expanduser().resolve() / ".mkgitbranch.toml"
    logger.debug(f"Attempting to load config from {home_config_path}")
    config = find_toml_config(home_config_path)
    if config:
        logger.debug(f"Using configuration from {home_config_path}")
        return config
    logger.debug("No configuration file found, using empty config")
    return {}

def load_regexes() -> dict[str, re.Pattern]:
    """
    Load regex patterns for field validation from config.

    Returns:
        dict: Dictionary of regex patterns for username, type, jira, and description.
    """
    config = load_config()
    regex_section = config.get("regex", {})
    return {
        "username": re.compile(regex_section.get("username", r"^[a-zA-Z0-9_-]{2,7}$")),
        "type": re.compile(regex_section.get("type", r"^(feat|fix|chore|test|refactor|hotfix)$")),
        "jira": re.compile(regex_section.get("jira", r"^[A-Z]{2,6}-[1-9][0-9]{,4}$")),
        "description": re.compile(regex_section.get("description", r"^[a-z][a-z0-9-]{,30}$")),
    }
