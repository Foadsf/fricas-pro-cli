# FriCAS CLI Wrapper Development: Lessons Learned

## Project Context
Attempting to create clean command-line wrappers for FriCAS (Computer Algebra System) on Windows, targeting three implementations: Batch script, PowerShell script, and Python script.

## Core Technical Challenges

### 1. FriCAS Input/Output Behavior
**Problem**: FriCAS has inconsistent behavior depending on how input is provided.
- **Echo/Pipe Method**: `echo command & echo )quit | fricas.exe` works for some commands
- **Stdin Redirection**: Direct stdin redirection fails for FriCAS system commands (those starting with `)`)
- **Mathematical vs System Commands**: Mathematical expressions (like `2+3`) work differently than system commands (like `)help`, `)summary`)

**Lesson**: FriCAS system commands require interactive REPL context and fail when piped through stdin redirection.

### 2. Windows Command Line Quoting Issues
**Problem**: Path quoting inconsistencies between different subprocess approaches.
- Subprocess with `shell=False` and manual quotes: Path not recognized
- Subprocess with `shell=True`: Different escaping behavior
- Direct cmd.exe invocation: Yet another quoting scheme

**Lesson**: Windows path handling in subprocess is fragile and method-dependent. Test each approach explicitly.

### 3. Output Cleaning Complexity
**Problem**: FriCAS produces verbose startup banners that need filtering.
- **Too Aggressive**: Removed actual mathematical results and help content
- **Too Permissive**: Left startup noise that cluttered output
- **Regex Complexity**: Complex patterns needed to distinguish banner from content

**Lessons**:
- Start with minimal cleaning and add patterns incrementally
- Test cleaning with debug output to see what gets filtered
- Mathematical results and help content have specific formats worth preserving

### 4. Process Management Issues
**Problem**: Various subprocess approaches had different limitations.
- **Timeouts**: Some methods timed out inconsistently
- **Exit Codes**: FriCAS returning exit code 255 for certain input methods
- **Stderr Handling**: Error messages not always captured properly

**Lesson**: FriCAS process behavior is highly dependent on input method. The echo/pipe approach proved most reliable.

## What We Successfully Resolved

### 1. Persistent Python REPL Session

**Solution**: A single long-lived FriCAS process with a background stdout reader and prompt detection (`\(\d+\)\s*->`) reliably frames command boundaries. This enables system commands like `)help`, `)summary`, and `)what` to work consistently from Python.

### 2. Clean Version Reporting

**Solution**: Capture the startup banner once and print only the three key lines (title, `Version:`, `Timestamp:`) for `version`.

### 3. Robust File Execution

**Solution**: Use `)read "<path>"` with Windows-quoted paths to execute `.input` files; also support `pipe` by writing stdin to a temp `.input` then `)read`-ing it.

### 4. Windows `system` Commands

**Solution**: On Windows, run shell commands via Python (`subprocess.run(..., shell=True)`) and print captured stdout/stderr; on Unix-like systems, defer to FriCAS `)system`.

### 5. Output Cleaning & Diagnostics

**Solution**: Minimal cleanup (remove trailing prompt, keep content) with a `--verbose` switch that enables `--debug` + `--raw` and dumps the RAW REPL block to stderr for canonical diagnosis.

## What Changed Since Early Attempts

### Previously Unresolved (Now Solved)

* **System Commands via Python**: By maintaining a persistent REPL with a background reader and prompt detection, `)help`, `)summary`, `)what`, etc., execute reliably. The earlier “argument list is not valid” errors were artifacts of one-shot stdin approaches.
* **Output Cleaning**: Switching to minimal cleaning (remove only the trailing prompt and optional echoed line) prevents accidental loss of content.
* **Windows `system` Output**: We don’t rely on FriCAS to relay child stdout on Windows; we capture it directly via Python and print it.

### Remaining Limitations

* **None blocking the CLI**: With the persistent REPL approach and per-OS handling of `system`, the intended CLI functionality is stable on Windows.

## Alternative Approaches That Failed

### 1. Direct Executable Flags
**Attempted**: Using `--eval`, `--script`, and other command-line flags.
**Result**: Limited functionality, some commands still failed.

### 2. Temporary File Input
**Attempted**: Creating temporary input files and redirecting them to FriCAS.
**Result**: System commands still failed with "argument list not valid" errors.

### 3. PowerShell Advanced Process Management
**Attempted**: Using .NET ProcessStartInfo with various configurations.
**Result**: Same underlying issues with FriCAS system commands.

## Key Insights

### 1. Correct Architecture: Persistent REPL

FriCAS system commands require an interactive session. A persistent REPL with a background reader and prompt detection is the right abstraction; one-shot stdin redirection is not.

### 2. Windows-Specific Handling for `system`

On Windows, FriCAS doesn’t echo child stdout for `)system`. Capturing command output via Python is the pragmatic fix.

### 3. Quoting & Prompt Hygiene

Always quote Windows paths for `)read`. After startup, clear the residual banner bytes so the first command’s output isn’t polluted; thereafter, rely on prompt detection for framing.

## Recommendations for Future Attempts

1. **Keep the Persistent Design**: Maintain one FriCAS process with a background reader and explicit prompt detection.
2. **Per-OS `system` Strategy**: Continue to execute Windows shell commands via Python; defer to FriCAS `)system` elsewhere.
3. **Diagnostics First**: Preserve `--verbose` (implies `--debug` + `--raw`) and RAW block dumps for quick triage.
4. **Evolve Features Incrementally**: Consider `--init <file>` to auto-`)read` a startup script, `--cwd <path>` to `)cd` before running, and `--no-echo` to hide echoed inputs while keeping results.

## Final Assessment

The project demonstrated that while basic FriCAS mathematical operations can be wrapped programmatically, the full system command functionality requires approaches more sophisticated than simple subprocess management. The working ChatGPT solution used persistent session management with prompt detection, suggesting this is the correct architectural approach for a complete FriCAS CLI wrapper.
