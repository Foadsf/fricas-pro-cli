#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FriCAS Professional CLI Wrapper (Windows)
----------------------------------------

Features
- Persistent REPL session under the hood; robust prompt detection.
- Subcommands: eval, file, help, summary, what, system, version, repl, pipe.
- Clean output (optional --raw to keep banner/echoes).
- Timeouts, exit codes, graceful shutdown.
- No third-party deps.

Tested design for FriCAS 1.3.x on Windows with Scoop layout.
"""

import argparse
import os
import queue
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

# -------------------------
# Defaults & Utilities
# -------------------------


def _default_fricas_path() -> str:
    # Respect explicit env var if you decide to set one later
    env_path = os.environ.get("FRICAS_EXE")
    if env_path:
        return env_path

    # Your Scoop path from the prompt
    userprofile = os.environ.get("USERPROFILE", r"C:\Users\Public")
    return str(Path(userprofile) / r"scoop\apps\fricas\1.3.12\bin\FRICASsys.exe")


PROMPT_RE = re.compile(rb"\(\d+\)\s*->\s*$")  # bytes regex; prompt usually ends a line
BANNER_STRIP_PATTERNS = [
    r"^Checking for foreign routines$",
    r"^FRICAS=.*$",
    r"^spad-lib=.*$",
    r"^foreign routines found$",
    r"^openServer result.*$",
    r"^\s*-{3,}\s*$",
    r"^\s*FriCAS Computer Algebra System\s*$",
    r"^\s*Version:.*$",
    r"^\s*Timestamp:.*$",
    r"^\s*Issue \)copyright.*$",
    r"^\s*Issue \)summary.*$",
    r"^\s*Issue \)quit.*$",
]
BANNER_RE_LIST = [re.compile(p) for p in BANNER_STRIP_PATTERNS]


def _clean_text_block(text: str) -> str:
    cleaned = []
    for ln in text.splitlines():
        if any(rx.match(ln) for rx in BANNER_RE_LIST):
            continue
        # Skip empty lines that are just banner spacing
        if not ln.strip():
            continue
        cleaned.append(ln.rstrip())
    return "\n".join(cleaned).strip()


def _debug(msg: str, enabled: bool):
    if enabled:
        print(f"[DEBUG] {msg}", file=sys.stderr)


# -------------------------
# FriCAS Session
# -------------------------


class _StreamReader(threading.Thread):
    """
    Asynchronously read bytes from a pipe and push into a Queue.
    Also keep a rolling buffer to detect REPL prompts reliably.
    """

    def __init__(self, stream, out_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.stream = stream
        self.q = out_queue
        self.stop_event = stop_event

    def run(self):
        try:
            while not self.stop_event.is_set():
                chunk = self.stream.read(1)
                if not chunk:
                    break
                self.q.put(chunk)
        except Exception:
            # On shutdown, pipe may close; that's fine.
            pass


class FriCASSession:
    def __init__(self, exe_path: str, debug: bool = False, encoding: str = "utf-8"):
        self.exe_path = exe_path
        self.debug = debug
        self.encoding = encoding
        self.proc: Optional[subprocess.Popen] = None
        self._q: Optional[queue.Queue] = None
        self._reader: Optional[_StreamReader] = None
        self._stop_event: Optional[threading.Event] = None
        self._buffer = bytearray()
        self.banner_text: str = ""

    def start(self, startup_timeout: float = 20.0) -> None:
        if self.proc and self.proc.poll() is None:
            return

        creationflags = 0
        if os.name == "nt":
            # New process group allows Ctrl+C handling without killing parent
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

        self.proc = subprocess.Popen(
            [self.exe_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            bufsize=0,  # unbuffered
        )
        if not self.proc.stdin or not self.proc.stdout:
            raise RuntimeError("Failed to start FriCAS: stdio not available")

        self._q = queue.Queue()
        self._stop_event = threading.Event()
        self._reader = _StreamReader(self.proc.stdout, self._q, self._stop_event)
        self._reader.start()

        # Drain banner until first prompt
        _debug("Waiting for initial prompt…", self.debug)
        ok, banner = self._wait_for_prompt(deadline=time.time() + startup_timeout)
        if not ok:
            raise TimeoutError("FriCAS did not present a prompt in time")

        # Clear banner bytes so the next command returns cleanly
        try:
            self.banner_text = banner.decode(self.encoding, errors="ignore")
        except Exception:
            self.banner_text = ""
        finally:
            self._buffer.clear()

    def _wait_for_prompt(self, deadline: float) -> Tuple[bool, bytes]:
        """
        Pull bytes from queue until we see a FriCAS prompt or deadline passes.
        Returns (found, collected_bytes)
        """
        collected = bytearray()
        while time.time() < deadline:
            try:
                b = self._q.get(timeout=0.05)  # type: ignore[union-attr]
                collected += b
                self._buffer += b
                # Prompt can appear without trailing newline, so test buffer end
                # We check last ~40 bytes for speed
                tail = bytes(self._buffer[-64:])
                if PROMPT_RE.search(tail):
                    return True, bytes(collected)
            except queue.Empty:
                continue
        return False, bytes(collected)

    def _write_line(self, line: str) -> None:
        assert self.proc and self.proc.stdin
        data = (line + "\n").encode(self.encoding, errors="ignore")
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def send(self, line: str, timeout: float = 30.0) -> str:
        """
        Send a single FriCAS line and capture output until the next prompt.
        Returns decoded text (utf-8 default).
        """
        if not self.proc or self.proc.poll() is not None:
            self.start()

        _debug(f"-> {line}", self.debug)
        self._write_line(line)
        # Collect until prompt
        ok, block = self._wait_for_prompt(deadline=time.time() + timeout)
        if not ok:
            raise TimeoutError(f"Timed out waiting for prompt after sending: {line}")

        # The returned block includes EVERYTHING since the last prompt.
        # We want just the output in response to THIS command:
        # Strategy: everything gathered AFTER the write, minus the final prompt echo.
        # Since we clear buffer ONLY at session start and between sends we don't,
        # we will compute delta by slicing from the end backwards until just before the prompt.
        # Simpler: keep a local capture starting now. We already have `block` as the delta.
        text = block.decode(self.encoding, errors="ignore")
        _debug(f"<- block size: {len(text)} chars", self.debug)
        if self.debug:
            sep = "=" * 30
            sys.stderr.write(
                f"\n[DEBUG] RAW BLOCK START\n{sep}\n{text}\n{sep}\n[DEBUG] RAW BLOCK END\n"
            )
            sys.stderr.flush()
        return text

    def request(self, line: str, timeout: float = 30.0, raw: bool = False) -> str:
        """High-level request with optional cleanup."""
        text = self.send(line, timeout=timeout)
        # Remove the trailing prompt itself, if present at the end of the block
        text = re.sub(r"\(\d+\)\s*->\s*$", "", text, flags=re.MULTILINE).rstrip()
        if raw:
            return text
        # Strip banner lines and echoed command lines that are common
        cleaned = _clean_text_block(text)
        # Often FriCAS echoes the command; if the very last line equals the input, drop it
        lines = cleaned.splitlines()
        if lines and lines[-1].strip() == line.strip():
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def stop(self, graceful_timeout: float = 5.0) -> None:
        if not self.proc:
            return
        try:
            if self.proc.poll() is None:
                # Try graceful )quit
                try:
                    self._write_line(")quit")
                except Exception:
                    pass
                # Wait briefly
                t0 = time.time()
                while time.time() - t0 < graceful_timeout:
                    if self.proc.poll() is not None:
                        break
                    time.sleep(0.05)
        finally:
            try:
                if self._stop_event:
                    self._stop_event.set()
                if self._reader and self._reader.is_alive():
                    self._reader.join(timeout=1.0)
            finally:
                if self.proc and self.proc.poll() is None:
                    # Hard kill as last resort
                    if os.name == "nt":
                        self.proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                        time.sleep(0.2)
                    self.proc.kill()
                self.proc = None


# -------------------------
# High-level operations
# -------------------------


def op_version(session: FriCASSession, timeout: float, raw: bool) -> str:
    """
    Report FriCAS version from the startup banner captured on session start.
    Only return the key three lines: title, Version, and Timestamp, and drop any advisory lines.
    """
    bt = session.banner_text or ""
    if not bt:
        return session.request(")summary", timeout=timeout, raw=raw)

    lines = [ln.strip() for ln in bt.splitlines() if ln.strip()]
    # Filter out advisory lines like "Issue )quit …"
    lines = [ln for ln in lines if not ln.startswith("Issue )")]

    # Find the title region and pick the core lines
    title_idx = None
    for i, ln in enumerate(lines):
        if re.search(r"\bFriCAS Computer Algebra System\b", ln):
            title_idx = i
            break

    if title_idx is not None:
        pick = []
        for ln in lines[title_idx : title_idx + 6]:
            if (
                ("FriCAS Computer Algebra System" in ln)
                or ln.startswith("Version:")
                or ln.startswith("Timestamp:")
            ):
                pick.append(ln)
        if pick:
            return "\n".join(pick)

    # Fallback: pick the first three core lines wherever they appear
    wanted = [
        ln
        for ln in lines
        if ("FriCAS Computer Algebra System" in ln)
        or ln.startswith("Version:")
        or ln.startswith("Timestamp:")
    ]
    return "\n".join(wanted[:3])


def op_help(
    session: FriCASSession, topic: Optional[str], timeout: float, raw: bool
) -> str:
    if topic:
        return session.request(f")help {topic}", timeout=timeout, raw=raw)
    return session.request(")help", timeout=timeout, raw=raw)


def op_summary(session: FriCASSession, timeout: float, raw: bool) -> str:
    return session.request(")summary", timeout=timeout, raw=raw)


def op_what(
    session: FriCASSession, category: str, patterns: list, timeout: float, raw: bool
) -> str:
    patt = " ".join(patterns) if patterns else ""
    return session.request(
        f")what {category} {patt}".rstrip(), timeout=timeout, raw=raw
    )


def op_eval(session: FriCASSession, expr: str, timeout: float, raw: bool) -> str:
    return session.request(expr, timeout=timeout, raw=raw)


def op_file(
    session: FriCASSession,
    path: str,
    quiet: bool,
    ifthere: bool,
    timeout: float,
    raw: bool,
) -> str:
    p = Path(path)
    if not p.exists():
        if ifthere:
            return ""  # silently do nothing per FriCAS semantics
        raise FileNotFoundError(f"Input file not found: {path}")
    opts = []
    if quiet:
        opts.append(")quiet")
    if ifthere:
        opts.append(")ifthere")
    opt_str = " " + " ".join(opts) if opts else ""
    # Quote the path so Windows backslashes/spaces are safe in FriCAS
    return session.request(f')read "{str(p)}"{opt_str}', timeout=timeout, raw=raw)


def op_system(session: FriCASSession, cmd: str, timeout: float, raw: bool) -> str:
    """
    On Windows, FriCAS `)system` does not relay child process stdout/stderr back
    to the REPL stream (you only get an exit status). To provide a useful CLI,
    we execute the system command in Python and return its captured output.

    On non-Windows, we defer to FriCAS `)system` so behavior matches the REPL.
    """
    if os.name == "nt":
        try:
            # Use shell=True to support built-ins like "dir"
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            out = proc.stdout or ""
            err = proc.stderr or ""
            text = out + (("\n" + err) if err and out else err)
            # Normalize newlines to match FriCAS style closely
            return text.rstrip("\n")
        except Exception as e:
            return f"[system error] {e}"
    else:
        # Unix-like: FriCAS generally prints the child output
        return session.request(f")system {cmd}", timeout=timeout, raw=raw)


def op_pipe(session: FriCASSession, timeout: float, raw: bool) -> str:
    """
    Read stdin fully and feed to FriCAS via a temp .input file,
    which is the most reliable way to execute a batch.
    """
    data = sys.stdin.read()
    if not data.strip():
        return ""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".input", delete=False, encoding="utf-8", newline="\n"
    ) as tf:
        tf.write(data)
        tmp = tf.name
    try:
        return op_file(
            session, tmp, quiet=False, ifthere=True, timeout=timeout, raw=raw
        )
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def interactive_repl(
    session: FriCASSession, prompt: str = "> ", timeout: float = 1e9, raw: bool = True
) -> int:
    """
    Lightweight interactive shell that proxies lines to FriCAS.
    We keep our own prompt to avoid re-emitting FriCAS's "(n) ->".
    """
    print("FriCAS CLI — type ')quit' or Ctrl+C to exit.")
    try:
        while True:
            try:
                line = input(prompt)
            except EOFError:
                break
            if not line.strip():
                continue
            out = session.request(line, timeout=timeout, raw=raw)
            if out:
                print(out)
            if line.strip().lower() in {")quit", ")pquit", ")fin", ")exit"}:
                break
    except KeyboardInterrupt:
        print()
    return 0


# -------------------------
# CLI
# -------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fricas",
        description="Professional CLI wrapper for FriCAS (Windows).",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument(
        "--fricas-path",
        default=_default_fricas_path(),
        help="Path to FRICASsys.exe (default: auto-detected Scoop path).",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Per-command timeout in seconds (default: 60).",
    )
    p.add_argument(
        "--raw",
        action="store_true",
        help="Do NOT clean banner/echo or strip prompts; print raw FriCAS output.",
    )
    p.add_argument("--debug", action="store_true", help="Enable debug logs to stderr.")
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose mode (implies --debug and --raw, dumps raw REPL blocks).",
    )

    sub = p.add_subparsers(dest="cmd", metavar="subcommand")

    # version
    sub.add_parser("version", help="Show FriCAS version info.")

    # help [topic]
    hp = sub.add_parser("help", help="Show FriCAS help or help about a specific topic.")
    hp.add_argument("topic", nargs="?", help="Topic, e.g., 'read', 'what', etc.")

    # summary
    sub.add_parser("summary", help="Show FriCAS command summary.")

    # what <category> [patterns...]
    wp = sub.add_parser(
        "what",
        help="Run ')what' (categories|commands|domains|operations|packages|synonym|things).",
    )
    wp.add_argument(
        "category",
        choices=[
            "categories",
            "commands",
            "domains",
            "operations",
            "packages",
            "synonym",
            "things",
        ],
    )
    wp.add_argument("patterns", nargs="*", help="Optional filter patterns.")

    # eval <expr>
    ev = sub.add_parser(
        "eval", help="Evaluate a FriCAS expression, e.g. 'integrate(x^2, x)'."
    )
    ev.add_argument("expr")

    # file <path> [--quiet] [--ifthere]
    fp = sub.add_parser("file", help="Read a .input file via ')read'.")
    fp.add_argument("path")
    fp.add_argument(
        "--quiet",
        action="store_true",
        help="Use )quiet to suppress output while reading.",
    )
    fp.add_argument(
        "--ifthere", action="store_true", help="Use )ifthere to skip if file missing."
    )

    # system <command>
    sp = sub.add_parser("system", help="Run a system command via ')system'.")
    sp.add_argument("command")

    # repl
    sub.add_parser("repl", help="Simple interactive shell that proxies to FriCAS.")

    # pipe (read stdin to a temp .input and execute)
    sub.add_parser(
        "pipe", help="Read FriCAS commands from STDIN and execute (via temp .input)."
    )

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if getattr(args, "verbose", False):
        args.debug = True
        args.raw = True

    exe = args.fricas_path

    if not Path(exe).exists():
        print(f"ERROR: FriCAS executable not found: {exe}", file=sys.stderr)
        return 2

    session = FriCASSession(exe_path=exe, debug=args.debug)

    try:
        # Ensure FriCAS is up and prompt ready
        session.start()

        if args.cmd == "version":
            out = op_version(session, timeout=args.timeout, raw=args.raw)
            print(out)
            return 0

        if args.cmd == "help":
            out = op_help(session, topic=args.topic, timeout=args.timeout, raw=args.raw)
            print(out)
            return 0

        if args.cmd == "summary":
            out = op_summary(session, timeout=args.timeout, raw=args.raw)
            print(out)
            return 0

        if args.cmd == "what":
            out = op_what(
                session,
                args.category,
                args.patterns,
                timeout=args.timeout,
                raw=args.raw,
            )
            print(out)
            return 0

        if args.cmd == "eval":
            out = op_eval(session, args.expr, timeout=args.timeout, raw=args.raw)
            print(out)
            return 0

        if args.cmd == "file":
            out = op_file(
                session,
                args.path,
                args.quiet,
                args.ifthere,
                timeout=args.timeout,
                raw=args.raw,
            )
            if out:
                print(out)
            return 0

        if args.cmd == "system":
            out = op_system(session, args.command, timeout=args.timeout, raw=args.raw)
            if out:
                print(out)
            return 0

        if args.cmd == "repl":
            return interactive_repl(
                session, prompt="fricas> ", timeout=args.timeout, raw=args.raw
            )

        if args.cmd == "pipe":
            out = op_pipe(session, timeout=args.timeout, raw=args.raw)
            if out:
                print(out)
            return 0

        # No subcommand: show help
        build_parser().print_help()
        return 0

    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except TimeoutError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 124  # common timeout code
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        session.stop()


if __name__ == "__main__":
    raise SystemExit(main())
