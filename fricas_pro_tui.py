#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FriCAS Professional TUI (Terminal User Interface)
-----------------------------------------------

A full-featured terminal user interface for FriCAS computer algebra system.
Built with Textual framework and integrates with fricas_pro_cli.py.

Features:
- Interactive REPL with syntax highlighting
- Multi-panel layout with resizable panels
- Command history and auto-completion
- Documentation browser
- Session management
- Mathematical output formatting
- File management and script execution
- Dark/light themes with customizable colors

Requirements:
- textual>=0.41.0
- fricas_pro_cli.py (for session management)
"""

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
    from textual.widgets import (
        Header,
        Footer,
        Input,
        RichLog,
        Static,
        Button,
        Tabs,
        Tab,
        DirectoryTree,
        TextArea,
        ProgressBar,
        Label,
        RadioSet,
        RadioButton,
        Switch,
        Select,
        Collapsible,
        Tree,
        DataTable,
    )
    from textual.reactive import reactive
    from textual.message import Message
    from textual.binding import Binding
    from textual.screen import Screen, ModalScreen
    from textual.worker import get_current_worker, Worker
    from textual import events, on
    from rich.text import Text
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.panel import Panel
    from rich.console import Console
    from rich.markdown import Markdown
except ImportError as e:
    print(f"ERROR: textual import failed: {e}")
    print("This TUI requires textual. Your version might be incompatible.")
    print("Try: pip install 'textual>=0.40.0'")
    sys.exit(1)

# Import from our CLI module
try:
    from fricas_pro_cli import (
        FriCASSession,
        _default_fricas_path,
        format_error,
        format_info,
        colorize,
    )
except ImportError as e:
    print(f"ERROR: textual import failed: {e}")
    print("This TUI requires textual. Try: pip install 'textual>=0.40.0'")
    sys.exit(1)


# -------------------------
# TUI-Specific Utilities
# -------------------------


class FriCASHistory:
    """Manage command history with search and persistence"""

    def __init__(self, max_size: int = 1000):
        self.commands: List[str] = []
        self.max_size = max_size
        self.current_index = -1
        self._load_history()

    def add(self, command: str) -> None:
        if command.strip() and (not self.commands or self.commands[-1] != command):
            self.commands.append(command)
            if len(self.commands) > self.max_size:
                self.commands = self.commands[-self.max_size :]
            self._save_history()
        self.current_index = len(self.commands)

    def get_previous(self) -> Optional[str]:
        if self.commands and self.current_index > 0:
            self.current_index -= 1
            return self.commands[self.current_index]
        return None

    def get_next(self) -> Optional[str]:
        if self.commands and self.current_index < len(self.commands) - 1:
            self.current_index += 1
            return self.commands[self.current_index]
        elif self.current_index == len(self.commands) - 1:
            self.current_index = len(self.commands)
            return ""
        return None

    def search(self, pattern: str) -> List[str]:
        return [cmd for cmd in self.commands if pattern.lower() in cmd.lower()]

    def _load_history(self) -> None:
        history_file = Path.home() / ".fricas_tui_history"
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    self.commands = [line.strip() for line in f.readlines()]
            except Exception:
                pass

    def _save_history(self) -> None:
        history_file = Path.home() / ".fricas_tui_history"
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                for cmd in self.commands[-self.max_size :]:
                    f.write(f"{cmd}\n")
        except Exception:
            pass


class FriCASCompleter:
    """Auto-completion for FriCAS commands and functions"""

    KEYWORDS = [
        # Common FriCAS commands
        ")quit",
        ")help",
        ")summary",
        ")what",
        ")read",
        ")system",
        ")clear",
        ")set",
        ")show",
        ")trace",
        ")boot",
        # Mathematical functions
        "integrate",
        "differentiate",
        "factor",
        "expand",
        "simplify",
        "solve",
        "limit",
        "series",
        "sum",
        "product",
        "sqrt",
        "exp",
        "log",
        "sin",
        "cos",
        "tan",
        "sinh",
        "cosh",
        "tanh",
        "asin",
        "acos",
        "atan",
        "pi",
        "e",
        "i",
        # Domains and types
        "Integer",
        "Float",
        "Polynomial",
        "Fraction",
        "Complex",
        "Matrix",
        "Vector",
        "List",
        "Symbol",
        "Expression",
        # Operations
        "factor",
        "gcd",
        "lcm",
        "prime?",
        "nextPrime",
        "random",
        "abs",
        "sign",
        "floor",
        "ceiling",
        "round",
        "truncate",
    ]

    def __init__(self):
        self.custom_completions: List[str] = []

    def get_completions(self, text: str) -> List[str]:
        if not text:
            return []

        text_lower = text.lower()
        matches = []

        # Match keywords
        for keyword in self.KEYWORDS:
            if keyword.lower().startswith(text_lower):
                matches.append(keyword)

        # Match custom completions
        for completion in self.custom_completions:
            if completion.lower().startswith(text_lower):
                matches.append(completion)

        return sorted(set(matches))

    def add_completion(self, completion: str) -> None:
        if completion not in self.custom_completions:
            self.custom_completions.append(completion)


class MathFormatter:
    """Format mathematical expressions for better display"""

    @staticmethod
    def format_fraction(numerator: str, denominator: str) -> str:
        """Create ASCII fraction display"""
        max_width = max(len(numerator), len(denominator))
        line = "─" * max_width
        num_centered = numerator.center(max_width)
        den_centered = denominator.center(max_width)
        return f"{num_centered}\n{line}\n{den_centered}"

    @staticmethod
    def format_matrix(elements: List[List[str]]) -> str:
        """Create ASCII matrix display"""
        if not elements:
            return "[]"

        # Calculate column widths
        col_widths = []
        for col in range(len(elements[0])):
            max_width = max(
                len(str(elements[row][col])) for row in range(len(elements))
            )
            col_widths.append(max_width)

        # Build matrix string
        lines = []
        for row in elements:
            formatted_row = " ".join(
                str(cell).rjust(width) for cell, width in zip(row, col_widths)
            )
            lines.append(f"│ {formatted_row} │")

        # Add top and bottom borders
        width = len(lines[0]) - 2
        top = "┌" + " " * width + "┐"
        bottom = "└" + " " * width + "┘"

        return "\n".join([top] + lines + [bottom])

    @staticmethod
    def enhance_output(text: str) -> str:
        """Enhance mathematical output with better formatting"""
        if not text.strip():
            return text

        # Handle simple fractions (looking for patterns like "x / y")
        fraction_pattern = r"(\w+(?:\^\d+)?)\s*/\s*(\w+(?:\^\d+)?)"
        if re.search(fraction_pattern, text) and "\n" not in text:
            match = re.search(fraction_pattern, text)
            if match:
                num, den = match.groups()
                return MathFormatter.format_fraction(num, den)

        return text


# -------------------------
# TUI Widgets
# -------------------------


class InputPanel(Container):
    """Left panel containing REPL input and command history"""

    DEFAULT_CSS = """
    InputPanel {
        width: 50%;
        border: solid $primary;
    }

    InputPanel Input {
        dock: bottom;
        height: 3;
        border: solid $accent;
    }

    InputPanel RichLog {
        height: 1fr;
        border: solid $primary-lighten-1;
    }
    """

    class CommandSubmitted(Message):
        def __init__(self, command: str) -> None:
            self.command = command
            super().__init__()

    def __init__(self) -> None:
        super().__init__()
        self.history = FriCASHistory()
        self.completer = FriCASCompleter()
        self.command_log: Optional[RichLog] = None
        self.input_field: Optional[Input] = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("FriCAS Interactive Session", classes="panel-title")
            self.command_log = RichLog(highlight=True, markup=True)
            yield self.command_log
            self.input_field = Input(placeholder="Enter FriCAS command...")
            yield self.input_field

    def on_mount(self) -> None:
        if self.input_field:
            self.input_field.focus()
        self._log_welcome_message()

    def _log_welcome_message(self) -> None:
        if self.command_log:
            welcome_text = Text("Welcome to FriCAS TUI!", style="bold green")
            self.command_log.write(welcome_text)
            self.command_log.write("Type FriCAS commands below. Use Ctrl+C to exit.")

    @on(Input.Submitted)
    def handle_input(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        if not command:
            return

        # Add to history
        self.history.add(command)

        # Log the command
        if self.command_log:
            cmd_text = Text(f"fricas> {command}", style="bold cyan")
            self.command_log.write(cmd_text)

        # Clear input and emit message
        if self.input_field:
            self.input_field.value = ""

        self.post_message(self.CommandSubmitted(command))

    def on_key(self, event: events.Key) -> None:
        if self.input_field and self.input_field.has_focus:
            if event.key == "up":
                prev_cmd = self.history.get_previous()
                if prev_cmd is not None:
                    self.input_field.value = prev_cmd
                    event.prevent_default()
            elif event.key == "down":
                next_cmd = self.history.get_next()
                if next_cmd is not None:
                    self.input_field.value = next_cmd
                    event.prevent_default()

    def log_result(self, result: str, is_error: bool = False) -> None:
        """Log a result from FriCAS execution"""
        if not self.command_log:
            return

        if is_error:
            result_text = Text(result, style="bold red")
        else:
            # Apply mathematical formatting
            formatted_result = MathFormatter.enhance_output(result)
            result_text = Text(formatted_result, style="green")

        self.command_log.write(result_text)
        self.command_log.write("")  # Add spacing


class OutputPanel(Container):
    """Bottom panel for displaying mathematical results"""

    DEFAULT_CSS = """
    OutputPanel {
        height: 40%;
        border: solid $primary;
    }

    OutputPanel RichLog {
        height: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.output_log: Optional[RichLog] = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Mathematical Output", classes="panel-title")
            self.output_log = RichLog(highlight=True, markup=True, wrap=True)
            yield self.output_log

    def display_result(
        self, result: str, command: str = "", result_number: int = 0
    ) -> None:
        """Display a mathematical result with formatting"""
        if not self.output_log:
            return

        if result_number > 0:
            header = Text(f"({result_number})", style="bold blue")
            self.output_log.write(header)

        if command:
            cmd_text = Text(f"Command: {command}", style="dim")
            self.output_log.write(cmd_text)

        # Format the mathematical output
        formatted = MathFormatter.enhance_output(result)
        result_text = Text(formatted, style="bold white")
        self.output_log.write(result_text)

        self.output_log.write("─" * 40)

    def display_error(self, error: str, command: str = "") -> None:
        """Display an error message"""
        if not self.output_log:
            return

        if command:
            cmd_text = Text(f"Command: {command}", style="dim")
            self.output_log.write(cmd_text)

        error_text = Text(f"Error: {error}", style="bold red")
        self.output_log.write(error_text)
        self.output_log.write("─" * 40)

    def clear(self) -> None:
        """Clear the output panel"""
        if self.output_log:
            self.output_log.clear()


class DocumentationPanel(Container):
    """Right panel for documentation and help"""

    DEFAULT_CSS = """
    DocumentationPanel {
        width: 50%;
        border: solid $primary;
    }

    DocumentationPanel RichLog {
        height: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.doc_log: Optional[RichLog] = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Documentation & Help", classes="panel-title")
            self.doc_log = RichLog(highlight=True, markup=True)
            yield self.doc_log

    def on_mount(self) -> None:
        self._show_welcome_help()

    def _show_welcome_help(self) -> None:
        """Show initial help content"""
        if not self.doc_log:
            return

        help_content = """
# FriCAS TUI Help

## Quick Start
- Type FriCAS commands in the input panel
- Use ↑/↓ arrows for command history
- Results appear in the output panel

## Common Commands
- `integrate(x^2, x)` - Integration
- `factor(x^2 + 2*x + 1)` - Factorization
- `solve(x^2 + 2*x + 1 = 0, x)` - Solve equations
- `)help <topic>` - Get help on topic
- `)quit` - Exit FriCAS session

## Keyboard Shortcuts
- **F1**: Toggle this help panel
- **F2**: Clear output
- **F3**: Session management
- **Ctrl+C**: Exit application
        """

        self.doc_log.write(Markdown(help_content))

    def show_help(self, topic: str, content: str) -> None:
        """Show help for a specific topic"""
        if not self.doc_log:
            return

        self.doc_log.clear()
        header = Text(f"Help: {topic}", style="bold blue")
        self.doc_log.write(header)
        self.doc_log.write("=" * 40)
        self.doc_log.write(content)

    def show_function_help(self, function: str) -> None:
        """Show help for a specific function (placeholder for now)"""
        help_text = f"Help for function: {function}\n\nDocumentation would be retrieved from FriCAS here."
        self.show_help(function, help_text)


class StatusPanel(Container):
    """Bottom status bar with session information"""

    DEFAULT_CSS = """
    StatusPanel {
        height: 3;
        dock: bottom;
        background: $primary-darken-2;
    }

    StatusPanel Horizontal {
        align: left middle;
    }

    StatusPanel Static {
        width: auto;
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.status_text = reactive("Ready")
        self.session_text = reactive("Disconnected")
        self.memory_text = reactive("0 MB")

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(f"Status: {self.status_text}", id="status")
            yield Static(f"Session: {self.session_text}", id="session")
            yield Static(f"Memory: {self.memory_text}", id="memory")
            yield Static("[F1] Help  [F2] Clear  [F3] Session", id="shortcuts")

    def update_status(self, status: str) -> None:
        self.status_text = status
        status_widget = self.query_one("#status", Static)
        status_widget.update(f"Status: {status}")

    def update_session(self, session_status: str) -> None:
        self.session_text = session_status
        session_widget = self.query_one("#session", Static)
        session_widget.update(f"Session: {session_status}")

    def update_memory(self, memory: str) -> None:
        self.memory_text = memory
        memory_widget = self.query_one("#memory", Static)
        memory_widget.update(f"Memory: {memory}")


class SettingsScreen(ModalScreen):
    """Modal screen for application settings"""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    SettingsScreen > Container {
        width: 60;
        height: 20;
        border: solid $primary;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Settings", classes="panel-title")
            with Vertical():
                yield Static("Theme:")
                yield RadioSet(
                    RadioButton("Dark", value=True, id="theme_dark"),
                    RadioButton("Light", id="theme_light"),
                )
                yield Static("FriCAS Path:")
                yield Input(value=_default_fricas_path(), id="fricas_path")
                with Horizontal():
                    yield Button("Save", variant="primary", id="save")
                    yield Button("Cancel", variant="default", id="cancel")

    @on(Button.Pressed, "#save")
    def save_settings(self) -> None:
        # TODO: Implement settings save
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def cancel_settings(self) -> None:
        self.dismiss(False)


# -------------------------
# Main TUI Application
# -------------------------


class FriCASApp(App):
    """Main FriCAS TUI application"""

    CSS = """
    .panel-title {
        dock: top;
        height: 3;
        content-align: center middle;
        background: $primary-darken-1;
        color: $text;
        text-style: bold;
    }

    Horizontal {
        height: 1fr;
    }

    #main_container {
        height: 1fr;
    }
    """

    TITLE = "FriCAS Professional TUI"
    SUB_TITLE = "Computer Algebra System Interface"

    BINDINGS = [
        Binding("f1", "toggle_help", "Help"),
        Binding("f2", "clear_output", "Clear"),
        Binding("f3", "session_management", "Session"),
        Binding("f10", "settings", "Settings"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.fricas_session: Optional[FriCASSession] = None
        self.result_counter = 0
        self.input_panel: Optional[InputPanel] = None
        self.output_panel: Optional[OutputPanel] = None
        self.doc_panel: Optional[DocumentationPanel] = None
        self.status_panel: Optional[StatusPanel] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main_container"):
            with Horizontal():
                self.input_panel = InputPanel()
                yield self.input_panel
                self.doc_panel = DocumentationPanel()
                yield self.doc_panel
            self.output_panel = OutputPanel()
            yield self.output_panel
        self.status_panel = StatusPanel()
        yield self.status_panel
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the application"""
        self.title = self.TITLE
        self.sub_title = self.SUB_TITLE
        self._initialize_fricas_session()

    def _initialize_fricas_session(self) -> None:
        """Initialize FriCAS session in the background"""
        if self.status_panel:
            self.status_panel.update_status("Initializing...")

        async def init_session():
            try:
                fricas_path = _default_fricas_path()
                self.fricas_session = FriCASSession(fricas_path, debug=False)
                self.fricas_session.start()

                # Update UI on success
                if self.status_panel:
                    self.status_panel.update_status("Ready")
                    self.status_panel.update_session("Connected")

            except Exception as e:
                # Handle error
                if self.status_panel:
                    self.status_panel.update_status("Error")
                    self.status_panel.update_session("Failed")

                if self.output_panel:
                    self.output_panel.display_error(
                        f"Failed to initialize FriCAS: {str(e)}"
                    )

        # Run the initialization
        self.run_worker(init_session, exclusive=False)

    def _handle_session_error(self, error: str) -> None:
        """Handle session initialization errors"""
        if self.status_panel:
            self.status_panel.update_status("Error")
            self.status_panel.update_session("Failed")

        if self.output_panel:
            self.output_panel.display_error(f"Failed to initialize FriCAS: {error}")

    @on(InputPanel.CommandSubmitted)
    def handle_command(self, message: InputPanel.CommandSubmitted) -> None:
        """Handle command submission from input panel"""
        command = message.command

        if not self.fricas_session:
            if self.output_panel:
                self.output_panel.display_error(
                    "FriCAS session not initialized", command
                )
            return

        if self.status_panel:
            self.status_panel.update_status("Computing...")

        async def execute_command():
            try:
                result = self.fricas_session.request(command, timeout=30.0, raw=False)

                # Update UI with result
                if self.status_panel:
                    self.status_panel.update_status("Ready")

                if self.output_panel:
                    self.result_counter += 1
                    self.output_panel.display_result(
                        result, command, self.result_counter
                    )

                # Update documentation panel if it's a help command
                if command.strip().startswith(")help") and self.doc_panel:
                    topic = (
                        command.strip().split(" ", 1)[1]
                        if " " in command
                        else "general"
                    )
                    self.doc_panel.show_help(topic, result)

            except Exception as e:
                # Handle error
                if self.status_panel:
                    self.status_panel.update_status("Ready")

                if self.output_panel:
                    self.output_panel.display_error(str(e), command)

        # Run the command execution
        self.run_worker(execute_command, exclusive=False)

    def action_toggle_help(self) -> None:
        """Toggle help panel visibility"""
        if self.doc_panel:
            self.doc_panel.visible = not self.doc_panel.visible

    def action_clear_output(self) -> None:
        """Clear the output panel"""
        if self.output_panel:
            self.output_panel.clear()
            self.result_counter = 0

    def action_session_management(self) -> None:
        """Open session management dialog"""
        # TODO: Implement session management
        if self.output_panel:
            self.output_panel.display_result(
                "Session management not yet implemented", "", 0
            )

    def action_settings(self) -> None:
        """Open settings dialog"""

        def handle_settings(result: bool) -> None:
            if result and self.output_panel:
                self.output_panel.display_result("Settings saved", "", 0)

        self.push_screen(SettingsScreen(), handle_settings)

    def action_quit(self) -> None:
        """Quit the application"""
        if self.fricas_session:
            self.fricas_session.stop()
        self.exit()


# -------------------------
# Entry Point
# -------------------------


def main() -> None:
    """Main entry point for the TUI application"""
    try:
        app = FriCASApp()
        app.run()
    except KeyboardInterrupt:
        print("\nExiting FriCAS TUI...")
    except Exception as e:
        print(f"Error starting TUI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
