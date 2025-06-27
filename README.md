# mkgitbranch

<!-- mdformat-toc start --slug=github --maxlevel=3 --minlevel=2 -->

- [Features](#features)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Install with uv](#install-with-uv)
- [Usage](#usage)
- [Configuration](#configuration)
  - [Configuration Priorities](#configuration-priorities)
  - [Example: Standalone `mkgitbranch_config.toml`](#example-standalone-mkgitbranch_configtoml)
  - [Example: Embedded in `pyproject.toml`](#example-embedded-in-pyprojecttoml)
- [Configuration Reference](#configuration-reference)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Building Standalone Executables](#building-standalone-executables)
  - [Prerequisites](#prerequisites-1)
  - [Build Steps](#build-steps)
  - [Notes](#notes)
  - [Windows Compatibility Notes](#windows-compatibility-notes)

<!-- mdformat-toc end -->

A modern, user-friendly tool for generating and managing Git branch names according to your team's conventions.

mkgitbranch provides a graphical interface and configuration-driven workflow to help you create consistent, meaningful branch names for your development process.

## Features<a name="features"></a>

- Interactive GUI for branch name creation
- Customizable branch type prefixes (e.g., `feat`, `fix`, `chore`)
- Project-specific configuration via TOML
- Clipboard integration for easy branch name copying
- Cross-platform support (macOS, Linux, Windows)

## Installation<a name="installation"></a>

### Prerequisites<a name="prerequisites"></a>

- Python 3.13 or later
- [uv](https://github.com/astral-sh/uv) for dependency management (recommended)

### Install with uv<a name="install-with-uv"></a>

```sh
uv pip install -e .
```

To run the GUI application directly in the uv environment:

```sh
uv pip run python -m mkgitbranch.gui
```

Or, to open a shell in the uv environment:

```sh
uv pip shell
python -m mkgitbranch.gui
```

Alternatively, use pip:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage<a name="usage"></a>

Run the GUI application:

```sh
python -m mkgitbranch.gui
```

Or, if installed as a script:

```sh
mkgitbranch
```

Follow the prompts to select a branch type, enter a ticket or issue number, and provide a short description. The tool will generate a branch name and copy it to your clipboard.

## Configuration<a name="configuration"></a>

mkgitbranch supports configuration via a TOML file.
The default configuration file is located at:

- `{project_root}/mkgitbranch_config.toml`

You can also place a `pyproject.toml` in your project root with a `[tool.mkgitbranch]` section for project-specific settings.

### Configuration Priorities<a name="configuration-priorities"></a>

mkgitbranch loads configuration in the following order (first found wins):

1. **Project-specific `pyproject.toml`**: If a `pyproject.toml` file exists in the project root (or any parent directory) with a `[tool.mkgitbranch]` section, it will be used.
1. **XDG config (`$XDG_CONFIG_HOME`)**: If no project config is found, mkgitbranch will look for `mkgitbranch.toml` in `$XDG_CONFIG_HOME/mkgitbranch/mkgitbranch.toml` (Linux/macOS, if `XDG_CONFIG_HOME` is set).
1. **Platform user config**: If not found above, mkgitbranch will look for `mkgitbranch.toml` in the platform-specific user config directory (e.g., `~/.config/mkgitbranch/mkgitbranch.toml` on Linux/macOS, `%APPDATA%/mkgitbranch/mkgitbranch.toml` on Windows).
1. **Home directory**: If still not found, mkgitbranch will look for `.mkgitbranch.toml` in your home directory (`~/.mkgitbranch.toml`).
1. **Defaults**: If no configuration file is found, built-in defaults are used.

### Example: Standalone `mkgitbranch_config.toml`<a name="example-standalone-mkgitbranch_configtoml"></a>

```toml
# Example configuration for mkgitbranch
username = "justin"
username_readonly = false
jira_prefix = "IAS-"
timeout_minutes = 10
cursor_start = "description"
branch_create_command_template = 'git switch --quiet --track --create "{branch_name}"'
allow_dirty = false
forbidden_source_branches = ["^master$"]

[regex]
username = "^[a-zA-Z0-9_-]{2,7}$"
type = "^(feat|fix|chore|test|refactor|hotfix)$"
jira = "^[A-Z]{2,6}-[1-9][0-9]{,4}$"
description = "^[a-z][a-z0-9-]{,30}$"

[field_widths]
username = 100
type = 110
jira = 90
description = 250

[theme.light]
error_foreground = "#8B0000"
label_foreground = "#222222"

[theme.dark]
error_foreground = "#EE4B2B"
label_foreground = "#cccccc"
field_foreground = "#ffffff"
```

### Example: Embedded in `pyproject.toml`<a name="example-embedded-in-pyprojecttoml"></a>

```toml
[tool.mkgitbranch]
username = "justin"
username_readonly = false
jira_prefix = "CLP-"
timeout_minutes = 10
cursor_start = "description"
branch_create_command_template = 'git switch --quiet --track --create "{branch_name}"'
allow_dirty = false
forbidden_source_branches = ["^master$"]

[tool.mkgitbranch.regex]
username = "^[a-zA-Z0-9_-]{2,7}$"
type = "^(feat|fix|chore|test|refactor|hotfix)$"
jira = "^[A-Z]{2,6}-[1-9][0-9]{,4}$"
description = "^[a-z][a-z0-9-]{,30}$"
```

## Configuration Reference<a name="configuration-reference"></a>

Below is a comprehensive list of all configuration parameters supported by mkgitbranch, their types, descriptions, and default values. These can be set in a standalone `mkgitbranch_config.toml` or in the `[tool.mkgitbranch]` section of your `pyproject.toml`.

| Option                         | Type   | Default                                               | Description                                                                        |
| ------------------------------ | ------ | ----------------------------------------------------- | ---------------------------------------------------------------------------------- |
| username                       | string | (OS username)                                         | Username to use as branch prefix.                                                  |
| username_readonly              | bool   | false                                                 | If true, username field is read-only in the GUI.                                   |
| jira_prefix                    | string | ""                                                    | Optional prefix to pre-fill in the JIRA field.                                     |
| timeout_minutes                | int    | 10                                                    | Minutes before the GUI auto-exits due to inactivity.                               |
| cursor_start                   | string | "description"                                         | Field to focus when dialog opens. See valid values below.                          |
| branch_create_command_template | string | 'git switch --quiet --track --create "{branch_name}"' | Template for the branch creation command. `{branch_name}` will be replaced.        |
| allow_dirty                    | bool   | false                                                 | If true, allows branch creation with uncommitted changes.                          |
| forbidden_source_branches      | list   | []                                                    | Regex patterns; if current branch matches, new branches cannot be created from it. |
| [regex] username               | string | ^[a-zA-Z0-9\_-]{2,7}$                                 | Regex for validating the username field.                                           |
| [regex] type                   | string | ^(feat                                                | fix                                                                                |
| [regex] jira                   | string | ^[A-Z]{2,6}-[1-9][0-9]{,4}$                           | Regex for JIRA issue keys.                                                         |
| [regex] description            | string | ^[a-z][a-z0-9-]{,30}$                                 | Regex for the description field.                                                   |
| [field_widths] username        | int    | 100                                                   | Width (in pixels) for the username field.                                          |
| [field_widths] type            | int    | 110                                                   | Width (in pixels) for the type dropdown.                                           |
| [field_widths] jira            | int    | 90                                                    | Width (in pixels) for the JIRA field.                                              |
| [field_widths] description     | int    | 250                                                   | Width (in pixels) for the description field.                                       |
| [theme.light] error_foreground | string | #8B0000                                               | Foreground color for error messages in light mode.                                 |
| [theme.light] label_foreground | string | #222222                                               | Foreground color for labels in light mode.                                         |
| [theme.dark] error_foreground  | string | #EE4B2B                                               | Foreground color for error messages in dark mode.                                  |
| [theme.dark] label_foreground  | string | #cccccc                                               | Foreground color for labels in dark mode.                                          |
| [theme.dark] field_foreground  | string | #ffffff                                               | Foreground color for input fields in dark mode.                                    |

**Valid values for `cursor_start`:**

- "description"
- "username"
- "jira_start"
- "jira_after_dash"
- "type"

**Notes:**

- All options are optional; defaults are used if not specified.
- Regexes and field widths can be customized for your team's conventions.
- Theme colors can be further customized by uncommenting and editing the relevant fields in your config.

## Security<a name="security"></a>

- No sensitive data is stored or transmitted.
- All configuration is local to your machine.

## Troubleshooting<a name="troubleshooting"></a>

- Ensure you are using Python 3.13 or later.
- If the GUI does not start, check that all dependencies are installed and your virtual environment is activated.
- For logging and debugging, see the log output in your terminal.

## Contributing<a name="contributing"></a>

Contributions are welcome! Please open issues or pull requests on GitHub.

## License<a name="license"></a>

This project is licensed under the MIT License.

## Building Standalone Executables<a name="building-standalone-executables"></a>

mkgitbranch can be packaged as a standalone executable for macOS and Windows using Hatch and PyInstaller.

### Prerequisites<a name="prerequisites-1"></a>

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended for dependency management; install with `pip install uv`)
- [Hatch](https://hatch.pypa.io/latest/) (install with `uv pip install hatch`)
- Platform-specific build tools (e.g., Xcode command line tools for macOS, Visual Studio Build Tools for Windows)

### Build Steps<a name="build-steps"></a>

1. Create and activate a virtual environment using uv:

    ```sh
    uv venv
    source .venv/bin/activate # or .venv\Scripts\activate on Windows
    ```

1. Install dependencies with uv:

    ```sh
    uv pip install -e .
    uv pip install pyinstaller
    uv pip install hatch
    ```

1. Build the standalone executable:

    ```sh
    pyinstaller --onefile --windowed --name mkgitbranch src/mkgitbranch/gui.py
    ```

    - The output executable will be in the `dist/` directory.
    - For CLI-only builds, remove `--windowed`.

1. (Optional) Build for a specific platform:

    - On Windows:
        ```sh
        pyinstaller --onefile --windowed --name mkgitbranch src/mkgitbranch/gui.py
        ```
    - On macOS:
        ```sh
        pyinstaller --onefile --windowed --name mkgitbranch src/mkgitbranch/gui.py
        ```

### Notes<a name="notes"></a>

- The generated executable is self-contained and does not require Python to be installed on the target system.
- You may need to adjust the `--add-data` option for PyInstaller to include additional resources (see the PyInstaller docs).
- For advanced PyInstaller configuration, see the [PyInstaller documentation](https://pyinstaller.org/).

---

For more information, see the source code and inline documentation.

### Windows Compatibility Notes<a name="windows-compatibility-notes"></a>

- If you customize the `branch_create_command_template` in your configuration, use double quotes for arguments (e.g., `"git switch --quiet --track --create \"{branch_name}\""`). Single quotes may not work in Windows CMD or PowerShell.
- Ensure that `git` is available in your system `PATH`.
- All other features, including clipboard integration and GUI, work cross-platform without changes.
