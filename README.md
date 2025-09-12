# FriCAS Pro CLI (Windows)

Professional, monolithic Python CLI wrapper around the FriCAS REPL on Windows.

- **Persistent REPL** with prompt detection (no per-call startup cost).
- Subcommands: `version`, `help`, `summary`, `what`, `eval`, `file`, `pipe`, `system`, `repl`.
- **Windows-friendly**: quotes paths for `)read`, runs `system` commands via Python on Windows.
- **Diagnostics**: `--verbose` (implies `--raw` + `--debug`) dumps RAW REPL blocks.

## Requirements
- Windows, Python 3.9+
- FriCAS installed (e.g., Scoop path: `%USERPROFILE%\scoop\apps\fricas\1.3.12\bin\FRICASsys.exe`)
- Optional: GitHub CLI (`gh`) for publishing the repo

## Quick start
```cmd
python fricas_pro_cli.py version
python fricas_pro_cli.py help read
python fricas_pro_cli.py eval "2 + 3"
python fricas_pro_cli.py file examples\000_demo.input
type examples\000_demo.input | python fricas_pro_cli.py pipe
python fricas_pro_cli.py system "dir"
python fricas_pro_cli.py repl
````

Verbose diagnostics:

```cmd
python fricas_pro_cli.py --verbose file examples\000_demo.input
```

## Notes

* On Windows, FriCAS `)system` doesn’t relay child stdout; the wrapper executes the command via Python and prints the captured output.
* Paths for `)read` are quoted to handle backslashes and spaces.