# FriCAS Pro CLI (Windows)

Professional command-line interface wrapper for FriCAS Computer Algebra System on Windows.

## The Problem

FriCAS is a powerful open-source computer algebra system, but accessing it on Windows presents significant challenges:

- **Limited Package Management**: Scoop is currently the only Windows package manager that provides FriCAS packages
- **REPL-Only Interface**: The installed executable (`FRICASsys.exe`) only provides an interactive REPL with no CLI functionality
- **Poor Windows Integration**: No built-in support for batch processing, file execution, or scriptable operations
- **Verbose Output**: Raw FriCAS output includes extensive startup banners and REPL artifacts

This wrapper addresses these limitations by providing a clean, professional command-line interface with proper Windows integration.

## Solution Features

- **Persistent REPL** with prompt detection (eliminates per-call startup overhead)
- **Clean CLI Interface** with subcommands: `version`, `help`, `summary`, `what`, `eval`, `file`, `pipe`, `system`, `repl`
- **Windows Integration**: Proper path quoting, system command execution, and file handling
- **Batch Processing**: Execute FriCAS script files and pipe commands from stdin
- **Debug Diagnostics**: Comprehensive `--verbose` mode with RAW REPL output dumps

## Requirements

- Windows 10/11
- Python 3.9 or later
- FriCAS installed via Scoop: `scoop install fricas`
  - Default path: `%USERPROFILE%\scoop\apps\fricas\1.3.12\bin\FRICASsys.exe`

## Installation

Clone or download this repository. No additional Python dependencies required.

## Quick Start

```cmd
# Show version information
python fricas_pro_cli.py version

# Get help on specific topics
python fricas_pro_cli.py help integrate
python fricas_pro_cli.py summary

# Evaluate mathematical expressions
python fricas_pro_cli.py eval "2 + 3"
python fricas_pro_cli.py eval "integrate(x^2, x)"
python fricas_pro_cli.py eval "factor(x^4 - 1)"

# Execute script files
python fricas_pro_cli.py file examples\001_linear_algebra.input

# Pipe commands from stdin
type examples\000_demo.input | python fricas_pro_cli.py pipe

# Run system commands
python fricas_pro_cli.py system "dir"

# Interactive REPL with clean interface
python fricas_pro_cli.py repl
```

## Verbose Diagnostics

For troubleshooting and development:

```cmd
python fricas_pro_cli.py --verbose eval "integrate(sin(x), x)"
python fricas_pro_cli.py --debug --raw file examples\002_polynomials_calculus.input
```

## Example Files

The `examples/` directory contains sample FriCAS scripts demonstrating:

- Basic arithmetic and algebra
- Linear algebra operations
- Polynomial manipulation and calculus
- Number theory functions
- Symbolic equation solving
- Series expansions and special functions
- Linear systems and matrix operations
- Polynomial ideals and Gröbner bases

## Architecture Notes

- **Persistent Session**: Maintains a single FriCAS process with background stdout reader
- **Prompt Detection**: Uses regex pattern `\(\d+\)\s*->` to frame command boundaries
- **Windows Compatibility**: Handles path quoting and executes system commands via Python subprocess
- **Output Cleaning**: Minimal filtering preserves mathematical results while removing startup noise

## License

This project is licensed under **CC BY-NC-SA 4.0** (Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International).

You are free to:
- **Share** — copy and redistribute the material in any medium or format
- **Adapt** — remix, transform, and build upon the material

Under the following terms:
- **Attribution** — You must give appropriate credit
- **NonCommercial** — You may not use the material for commercial purposes
- **ShareAlike** — If you remix, transform, or build upon the material, you must distribute your contributions under the same license

## Contributing

This wrapper was developed through extensive trial and error to solve the fundamental limitations of FriCAS on Windows. See `lessons_learned.md` for detailed technical insights and development challenges encountered.

## Acknowledgments

FriCAS is developed by the FriCAS community. This wrapper provides Windows CLI functionality but does not modify the core FriCAS system.
