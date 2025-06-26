# mkgitbranch

A modern, user-friendly tool for generating and managing Git branch names according to your team's conventions.

mkgitbranch provides a graphical interface and configuration-driven workflow to help you create consistent, meaningful branch names for your development process.

## Features

- Interactive GUI for branch name creation
- Customizable branch type prefixes (e.g., `feat`, `fix`, `chore`)
- Project-specific configuration via TOML
- Clipboard integration for easy branch name copying
- Cross-platform support (macOS, Linux, Windows)

## Installation

### Prerequisites

- Python 3.13 or later
- [uv](https://github.com/astral-sh/uv) for dependency management (recommended)

### Install with uv

```sh
uv venv
uv pip install -e .
```

Alternatively, use pip:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Run the GUI application:

```sh
python -m mkgitbranch.gui
```

Or, if installed as a script:

```sh
mkgitbranch
```

Follow the prompts to select a branch type, enter a ticket or issue number, and provide a short description. The tool will generate a branch name and copy it to your clipboard.

## Configuration

mkgitbranch supports configuration via a TOML file.
The default configuration file is located at:

- `{project_root}/mkgitbranch_config.toml`

You can also place a `pyproject.toml` in your project root with a `[tool.mkgitbranch]` section for project-specific settings.

### Example: Standalone `mkgitbranch_config.toml`

```toml
branch_types = ["feat", "fix", "chore", "test", "refactor", "hotfix"]
default_type = "feat"
branch_format = "{type}/{ticket}-{description}"

[clipboard]
enabled = true

[ui]
theme = "auto"
```

### Example: Embedded in `pyproject.toml`

```toml
[tool.mkgitbranch]
branch_types = ["feat", "fix", "chore", "test", "refactor", "hotfix"]
default_type = "feat"
branch_format = "{type}/{ticket}-{description}"

[tool.mkgitbranch.clipboard]
enabled = true

[tool.mkgitbranch.ui]
theme = "auto"
```

### Configuration Options

| Option         | Type    | Description                                                      |
| --------------| ------- | ---------------------------------------------------------------- |
| branch_types   | list    | List of allowed branch type prefixes                             |
| default_type   | string  | Default branch type                                              |
| branch_format  | string  | Format string for branch names                                   |
| [clipboard]    | table   | Clipboard integration settings                                   |
| enabled        | bool    | Enable/disable clipboard copying                                 |
| [ui]           | table   | User interface settings                                          |
| theme          | string  | UI theme: `auto`, `light`, or `dark`                             |

## Security

- No sensitive data is stored or transmitted.
- All configuration is local to your machine.

## Troubleshooting

- Ensure you are using Python 3.13 or later.
- If the GUI does not start, check that all dependencies are installed and your virtual environment is activated.
- For logging and debugging, see the log output in your terminal.

## Contributing

Contributions are welcome! Please open issues or pull requests on GitHub.

## License

This project is licensed under the MIT License.

## Building Standalone Executables

mkgitbranch can be packaged as a standalone executable for macOS and Windows using Hatch and PyInstaller.

### Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended for dependency management; install with `pip install uv`)
- [Hatch](https://hatch.pypa.io/latest/) (install with `uv pip install hatch`)
- Platform-specific build tools (e.g., Xcode command line tools for macOS, Visual Studio Build Tools for Windows)

### Build Steps

1. Create and activate a virtual environment using uv:
   ```sh
   uv venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   ```

2. Install dependencies with uv:
   ```sh
   uv pip install -e .
   uv pip install pyinstaller
   uv pip install hatch
   ```

3. Build the standalone executable:
   ```sh
   hatch run pyinstaller:pyinstaller --onefile --windowed --name mkgitbranch src/mkgitbranch/gui.py
   ```
   - The output executable will be in the `dist/` directory.
   - For CLI-only builds, remove `--windowed`.

4. (Optional) Build for a specific platform:
   - On Windows:
     ```sh
     hatch run windows:pyinstaller --onefile --windowed --name mkgitbranch src/mkgitbranch/gui.py
     ```
   - On macOS:
     ```sh
     hatch run macos:pyinstaller --onefile --windowed --name mkgitbranch src/mkgitbranch/gui.py
     ```

### Notes
- The generated executable is self-contained and does not require Python to be installed on the target system.
- You may need to adjust the `add-data` option in `pyproject.toml` to include additional resources.
- For advanced PyInstaller configuration, see the [PyInstaller documentation](https://pyinstaller.org/).

---

For more information, see the source code and inline documentation.
