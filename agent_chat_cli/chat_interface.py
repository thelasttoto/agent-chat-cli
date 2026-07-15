# SPDX-License-Identifier: Apache-2.0

import argparse
import asyncio
import itertools
import os
import re
import readline
import platform
import signal
import sys
from typing import Callable, Awaitable

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme

from .commands import ChatExitException, process_command
from .command_handlers import register_default_commands

# Theme for general-purpose agent
custom_theme = Theme(
    {"info": "cyan", "warning": "yellow", "error": "red", "agent": "green"}
)

console = Console(theme=custom_theme)

# Event to signal that streaming has started (set by protocol client)
_stream_start_event: asyncio.Event | None = None
_spinner_cleared_event: asyncio.Event | None = None


async def wait_spinner_cleared():
    global _spinner_cleared_event
    if _spinner_cleared_event is not None:
        await _spinner_cleared_event.wait()


def notify_streaming_started():
    global _stream_start_event
    if _stream_start_event is not None:
        _stream_start_event.set()


async def spinner(
    msg: str = "⏳ Waiting for agent...",
    stop_event: asyncio.Event | None = None,
    cleared_event: asyncio.Event | None = None,
):
    """
    Show an animated spinner in the terminal using ASCII, not Rich. No flush.
    """
    for frame in itertools.cycle(["|", "/", "-", "\\"]):
        if stop_event is not None and stop_event.is_set():
            # Replace spinner char with an arrow on the same line
            try:
                print(f"\r{msg} →")
            except Exception:
                pass
            if cleared_event is not None:
                cleared_event.set()
            break
        print(f"\r{msg} {frame}", end="")
        await asyncio.sleep(0.1)


def render_answer(answer: str, agent_name: str = "Agent", turn_id: str | None = None):
    """
    Render agent response in a formatted panel.

    Args:
        answer: The agent's response text
        agent_name: Name of the agent
        turn_id: Optional turn ID (kept for backward compatibility, not displayed)
    """
    answer = answer.strip()
    if re.match(r"^b?[\"']?\{.*\}['\"]?$", answer):
        console.print("[warning]⚠️  Skipping raw byte/dict output.[/warning]")
        return

    # Build title without turn_id (UUIDs are not user-friendly)
    title = f"[agent]{agent_name} Response[/agent]"

    console.print("\n")
    console.print(
        Panel(
            Markdown(answer),
            title=title,
            border_style="agent",
            padding=(1, 2),
        )
    )
    console.print("\n")


def clear_screen():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


def print_welcome_message(
    agent_name: str, skills_description: str = "", skills_examples: str = ""
):
    welcome_text = (
        f"[agent]🚀 Welcome to {agent_name} CLI[/agent]\n\n"
        "This agent helps you interact with tools dynamically.\n"
        "Type your question and hit enter.\n"
        "Type '/exit' or '/quit' to leave. Type '/clear' to clear the screen. Type '/history' to view chat history."
    )
    if skills_description:
        welcome_text += f"\n\n[info]Skills Description:[/info]\n{skills_description}"
    if skills_examples:
        # skills_examples is already a list
        bullets = "\n".join(f"- {ex}" for ex in skills_examples)
        welcome_text += f"\n\n[info]Example Skills:[/info]\n{bullets}"

    # Add command help
    welcome_text += "\n\n[dim]Type [bold]/help[/bold] for available commands[/dim]"

    console.print(
        Panel(
            welcome_text,
            title=f"[agent]{agent_name}[/agent]",
            border_style="agent",
            padding=(1, 2),
        )
    )
    console.print("\n")


async def run_chat_loop(
    handle_user_input: Callable[[str], Awaitable[None]],
    agent_name: str = "Agent",
    skills_description: str = "",
    skills_examples: str = "",
    history_key: str = "agent",
    multi_input_enabled: bool = False,
    no_history: bool = False,
    current_turn_tracker: dict | None = None,
):
    """
    Run the chat loop for agent interaction.

    Args:
        handle_user_input: Async function to handle user input
        agent_name: Name of the agent
        skills_description: Description of agent skills
        skills_examples: Example skills
        history_key: Key for history file
        multi_input_enabled: Enable multi-line input
        no_history: Disable history
        current_turn_tracker: Optional dict with 'turn' key for tracking turn IDs
    """
    # Register default commands on first run
    register_default_commands()

    print_welcome_message(agent_name, skills_description, skills_examples)

    if no_history:
        console.print(
            "[warning]⚠️  History is disabled (--no-history). Inputs will not be saved or recalled.[/warning]\n"
        )

    history_file = os.path.expanduser(f"~/.{history_key}_chat_history")

    if not no_history:
        try:
            if os.path.exists(history_file):
                readline.read_history_file(history_file)
        except Exception as e:
            console.print(f"[warning]⚠️  Could not load history file: {e}[/warning]")

    # Signal handler for graceful exit
    def signal_handler(signum, frame):
        if signum == signal.SIGTSTP:
            # Save history before suspending
            if not no_history:
                try:
                    readline.write_history_file(history_file)
                except Exception:
                    pass
            console.print(
                f"\n[agent]🛑 {agent_name} suspended. Use 'fg' to resume.[/agent]"
            )
            # Restore default handler and re-raise signal to actually suspend
            signal.signal(signal.SIGTSTP, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGTSTP)
        elif signum == signal.SIGQUIT:
            console.print(f"\n[agent]👋 {agent_name} terminated. Goodbye![/agent]")
            # Save history before exiting
            if not no_history:
                try:
                    readline.write_history_file(history_file)
                except Exception:
                    pass
            sys.exit(0)
        elif signum == signal.SIGCONT:
            # Re-register SIGTSTP handler after resuming from suspension
            signal.signal(signal.SIGTSTP, signal_handler)
            console.print(f"[agent]▶️  {agent_name} resumed.[/agent]")

    # Register signal handlers
    if platform.system() != "Windows":  # Signal handling works differently on Windows
        signal.signal(signal.SIGQUIT, signal_handler)  # Control+\ (quit)
        signal.signal(signal.SIGTSTP, signal_handler)  # Control+Z (suspend)
        signal.signal(signal.SIGCONT, signal_handler)  # Resume after suspension

    # Shared state for current prompt
    current_prompt = {"text": ""}

    try:
        while True:
            try:
                # Build prompt without turn_id (UUIDs are not user-friendly)
                prompt_prefix = "💬 [no-history] You: " if no_history else "💬 You: "

                # Store current prompt
                current_prompt["text"] = prompt_prefix

                if multi_input_enabled:
                    console.print(f"{prompt_prefix}(use ctrl+D to end input)")
                    # Use run_in_executor to make blocking stdin.read() non-blocking
                    loop = asyncio.get_event_loop()
                    user_input = await loop.run_in_executor(None, lambda: sys.stdin.read().strip())
                else:
                    # Use run_in_executor to make blocking input() non-blocking
                    loop = asyncio.get_event_loop()
                    user_input = await loop.run_in_executor(None, lambda: input(prompt_prefix).strip())

                # Clear current prompt since we got input
                current_prompt["text"] = ""

                # Check if it's a command
                if user_input.startswith('/'):
                    # Build command context
                    command_context = {
                        'l9router_url': os.environ.get('L9ROUTER_URL', 'N/A'),
                        'user_id': os.environ.get('L9ROUTER_USER_ID', 'N/A'),
                        'agent_name': agent_name,
                        'turn_id': current_turn_tracker if current_turn_tracker else {},
                        'history': [],  # Could be populated with actual message history
                    }

                    try:
                        handled, output = process_command(user_input, command_context)
                        if handled:
                            if output:
                                console.print(output)
                            continue
                        else:
                            # Unknown command
                            console.print(f"[error]❌ Unknown command: {user_input}[/error]")
                            console.print("[dim]Type [bold]/help[/bold] for available commands[/dim]")
                            continue
                    except ChatExitException:
                        console.print(
                            f"\n[agent]👋 Thank you for using {agent_name}. Goodbye![/agent]"
                        )
                        break

                if user_input:
                    if not no_history:
                        readline.add_history(user_input)
                    stop_event = asyncio.Event()
                    spinner_cleared_event = asyncio.Event()
                    global _stream_start_event, _spinner_cleared_event
                    _stream_start_event = stop_event
                    _spinner_cleared_event = spinner_cleared_event
                    spinner_task = asyncio.create_task(
                        spinner(
                            stop_event=stop_event, cleared_event=spinner_cleared_event
                        )
                    )
                    try:
                        await handle_user_input(user_input)
                    except Exception as e:
                        console.print(f"[error]⚠️  An error occurred: {e}[/error]")
                    finally:
                        stop_event.set()
                        spinner_task.cancel()
                        try:
                            await spinner_task
                        except asyncio.CancelledError:
                            pass
                        finally:
                            _stream_start_event = None
                            _spinner_cleared_event = None
            except (KeyboardInterrupt, EOFError):
                # KeyboardInterrupt: Control+C, EOFError: Control+D
                console.print("\n[agent]👋 Chat interrupted. Goodbye![/agent]")
                break
    finally:
        if not no_history:
            try:
                readline.write_history_file(history_file)
            except Exception as e:
                console.print(f"[warning]⚠️  Could not save history file: {e}[/warning]")


async def main():
    print("🚀 Starting Agent Chat CLI...")
    parser = argparse.ArgumentParser(description="Agent Chat CLI")
    parser.add_argument("agent_name_or_url", help="Agent name or base URL")
    parser.add_argument(
        "--multi-input",
        action="store_true",
        help="Enable multi-line input mode (read from stdin until EOF)",
    )
    args = parser.parse_args()

    agent_name_or_url = args.agent_name_or_url
    multi_input_enabled = args.multi_input

    # Example placeholder — inject your agent or A2A client logic here
    class MockChat:
        async def send_message(self, message: str):
            render_answer(f"Echo: {message}", agent_name=agent_name_or_url)

    chat = MockChat()

    await run_chat_loop(
        lambda message: chat.send_message(message),
        agent_name=agent_name_or_url,
        multi_input_enabled=multi_input_enabled,
    )


if __name__ == "__main__":
    asyncio.run(main())
