#!/usr/bin/env python3
import subprocess
import sys
import re
import argparse
import tempfile
import os
from pathlib import Path


def debug_log(message, debug_enabled=False):
    if debug_enabled:
        print(f"[DEBUG] {message}", file=sys.stderr)


class FriCASWrapper:
    def __init__(self, fricas_path=None):
        self.fricas_path = (
            fricas_path or r"C:\Users\FoadS\scoop\apps\fricas\1.3.12\bin\FRICASsys.exe"
        )

    def execute_command(self, fricas_command, timeout=15, debug=False):
        """Execute a FriCAS command and return cleaned output."""
        debug_log(f"Executing FriCAS command: {fricas_command}", debug)

        try:
            # Try direct input without echo/pipe
            process = subprocess.run(
                [self.fricas_path, "--eval", fricas_command, "--quit"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            debug_log(f"Process completed with exit code: {process.returncode}", debug)
            debug_log(f"Stdout length: {len(process.stdout)}", debug)

            if debug:
                debug_log("Raw stdout:", debug)
                debug_log(process.stdout[:300], debug)

            return self._clean_output(process.stdout, debug)

        except subprocess.TimeoutExpired:
            debug_log("Command timed out", debug)
            return "ERROR: Command timed out"
        except Exception as e:
            debug_log(f"Error: {e}", debug)
            return f"ERROR: {e}"

    def _clean_output(self, raw_output, debug=False):
        """Clean FriCAS output by removing REPL artifacts."""
        debug_log("Cleaning output", debug)

        lines = raw_output.split("\n")
        cleaned_lines = []
        skip_patterns = [
            r"^Checking for foreign routines$",
            r"^FRICAS=.*$",
            r"^spad-lib=.*$",
            r"^foreign routines found$",
            r"^openServer result.*$",
            r"^-{50,}$",
            r"^\s*FriCAS Computer Algebra System\s*$",
            r"^\s*Version:.*built with.*$",
            r"^\s*Timestamp:.*$",
            r"^\s*Issue \)copyright.*$",
            r"^\s*Issue \)summary.*$",
            r"^\s*Issue \)quit.*$",
            r"^\s*$",
            r"^2 \+ 3$",  # Remove echoed math command
            r"^\)summary$",  # Remove echoed system command
        ]

        for line in lines:
            should_skip = False
            for pattern in skip_patterns:
                try:
                    if re.match(pattern, line):
                        should_skip = True
                        if debug:
                            debug_log(
                                f"Skipping line (matched {pattern}): {line[:50]}", debug
                            )
                        break
                except re.error as e:
                    debug_log(f"Regex error with pattern '{pattern}': {e}", debug)
                    continue

            if not should_skip and line.strip():
                cleaned_lines.append(line.strip())

        result = "\n".join(cleaned_lines)
        debug_log(f"Cleaned output length: {len(result)}", debug)
        return result

    def get_version(self):
        """Get FriCAS version information."""
        try:
            # Use --version flag and parse the startup output
            process = subprocess.run(
                [self.fricas_path, "--version", "--quit"],
                capture_output=True,
                text=True,
                timeout=10,
                input=")quit\n",
            )

            output = process.stdout
            # Look for the version line in the startup banner
            for line in output.split("\n"):
                if "Version:" in line and "FriCAS" in line:
                    return line.strip()

            # Fallback: extract from any line containing version info
            for line in output.split("\n"):
                if "FriCAS" in line and ("built with" in line or "Version" in line):
                    return line.strip()

            return "Version information not found"

        except Exception as e:
            return f"ERROR: Could not get version - {e}"

    def get_help(self, topic=None, debug=False):
        """Get help information."""
        if topic:
            command = f")help {topic}"
        else:
            # Use )summary for general help since )help alone gives an error
            command = ")summary"
        return self.execute_command(command, debug=debug)

    def evaluate_expression(self, expression, debug=False):
        """Evaluate a mathematical expression."""
        return self.execute_command(expression, debug=debug)

    def execute_file(self, filepath):
        """Execute commands from a file."""
        if not os.path.exists(filepath):
            return f"ERROR: File {filepath} not found"
        return self.execute_command(f")read {filepath}")

    def system_command(self, cmd):
        """Execute system command through FriCAS."""
        return self.execute_command(f")system {cmd}")

    def show_summary(self, debug=False):
        """Show FriCAS command summary."""
        return self.execute_command(")summary", debug=debug)


def main():
    parser = argparse.ArgumentParser(
        description="FriCAS Command Line Interface Wrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fricas_cli.py --version
  python fricas_cli.py --help
  python fricas_cli.py --eval "2 + 3"
  python fricas_cli.py --eval "integrate(x^2, x)"
  python fricas_cli.py --help integrate
  python fricas_cli.py --file mycommands.fricas
  python fricas_cli.py --system "dir"
        """,
    )

    parser.add_argument(
        "--fricas-path",
        help="Path to FRICASsys.exe executable",
        default=r"C:\Users\FoadS\scoop\apps\fricas\1.3.12\bin\FRICASsys.exe",
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--version", action="store_true", help="Show FriCAS version")
    parser.add_argument("--help-topic", help="Show help for specific topic")
    parser.add_argument("--eval", help="Evaluate mathematical expression")
    parser.add_argument("--file", help="Execute commands from file")
    parser.add_argument("--system", help="Execute system command")
    parser.add_argument(
        "--summary", action="store_true", help="Show FriCAS command summary"
    )
    parser.add_argument(
        "--interactive", action="store_true", help="Start interactive FriCAS session"
    )

    parser.add_argument(
        "--help-general", action="store_true", help="Show general FriCAS help"
    )

    args = parser.parse_args()

    fricas = FriCASWrapper(args.fricas_path)

    try:
        if args.version:
            print(fricas.get_version())
        elif args.help_topic is not None:
            print(fricas.get_help(args.help_topic, args.debug))
        elif hasattr(args, "help") and args.help:
            print(fricas.get_help(None, args.debug))
        elif args.eval:
            result = fricas.evaluate_expression(args.eval, args.debug)
            print(result)
        elif args.file:
            result = fricas.execute_file(args.file)
            print(result)
        elif args.system:
            result = fricas.system_command(args.system)
            print(result)
        elif args.summary:
            print(fricas.show_summary(args.debug))
        elif args.interactive:
            subprocess.run([fricas.fricas_path])
        elif args.help_general:
            print(fricas.get_help(None, args.debug))
        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
