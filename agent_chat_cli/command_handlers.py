"""Command handlers for agent_chat_cli.

This module contains handler functions for all built-in commands.
"""

import logging
import os
from typing import Any

from .commands import ChatExitException, get_all_commands

logger = logging.getLogger(__name__)


def handle_newsession(args: list[str], context: dict[str, Any]) -> str:
    """Start a new session with fresh context ID.

    This creates a new conversation context, effectively starting
    a clean slate with the agent. The previous conversation history
    is lost from the agent's perspective.

    Args:
        args: Command arguments (unused)
        context: Chat context (will use to reset turn counter)

    Returns:
        Confirmation message with new session ID
    """
    # Import here to avoid circular dependency
    try:
        from agent_chat_cli.a2a_client import (
            reset_session,
            get_session_context_id,
        )

        # Get old session ID for display
        old_session_id = get_session_context_id()

        # Reset session (generates new context_id)
        try:
            new_session_id = reset_session()
        except RuntimeError as e:
            # Edge case 1: Session reset during active processing
            return f"❌ {str(e)}"

        # Edge case 3: Reset turn counter if available (safe check)
        turn_tracker = context.get('turn_id')
        if turn_tracker and isinstance(turn_tracker, dict):
            turn_tracker['turn'] = 1
            logger.info("Turn counter reset to 1")

        output = "\n🔄 New Session Started\n"
        output += "=" * 50 + "\n"
        output += f"  Previous Session: {old_session_id[:16]}...\n"
        output += f"  New Session:      {new_session_id[:16]}...\n"
        output += f"  Turn Counter:     Reset to 1\n"
        output += "=" * 50 + "\n"
        output += "\n[dim]The agent will treat this as a brand new conversation.[/dim]"

        return output

    except ImportError as e:
        logger.error(f"Failed to import session management: {e}")
        return "❌ Session management not available in this mode"


def handle_sessioninfo(args: list[str], context: dict[str, Any]) -> str:
    """Display current session information.

    Args:
        args: Command arguments (unused)
        context: Chat context with turn tracking

    Returns:
        Formatted session information
    """
    try:
        from agent_chat_cli.a2a_client import get_session_info

        info = get_session_info()
        duration = info['duration']

        output = "\n📊 Current Session Information\n"
        output += "=" * 50 + "\n"
        output += f"  Session ID:  {info['context_id']}\n"
        output += f"  Started:     {info['started_at'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += f"  Duration:    {int(duration.total_seconds())}s\n"

        # Edge case 3: Safe check for turn tracker
        turn_tracker = context.get('turn_id')
        if turn_tracker and isinstance(turn_tracker, dict):
            current_turn = turn_tracker.get('turn', 0)
            output += f"  Current Turn: {current_turn}\n"

        output += "=" * 50

        return output

    except ImportError as e:
        logger.error(f"Failed to import session info: {e}")
        return "❌ Session information not available in this mode"


def handle_help(args: list[str], context: dict[str, Any]) -> str:
    """Display all available commands.

    Args:
        args: Command arguments (unused)
        context: Chat context (unused)

    Returns:
        Help text with all commands
    """
    commands = get_all_commands()

    output = "\n📋 Available Commands:\n"
    output += "=" * 50 + "\n"

    for cmd in commands:
        output += f"\n  /{cmd.name}\n"
        output += f"    {cmd.description}\n"
        if cmd.aliases:
            output += f"    Aliases: {', '.join('/' + a for a in cmd.aliases)}\n"

    output += "\n" + "=" * 50
    return output


def handle_exit(args: list[str], context: dict[str, Any]) -> str | None:
    """Exit the chat gracefully.

    Args:
        args: Command arguments (unused)
        context: Chat context (unused)

    Raises:
        ChatExitException: Always raised to signal exit
    """
    logger.info("Exit command received")
    raise ChatExitException()


def handle_clear(args: list[str], context: dict[str, Any]) -> str | None:
    """Clear the terminal screen.

    Args:
        args: Command arguments (unused)
        context: Chat context (unused)

    Returns:
        None (screen is cleared)
    """
    # Clear screen based on OS
    if os.name == 'nt':  # Windows
        os.system('cls')
    else:  # Unix/Linux/Mac
        os.system('clear')
    return None


def handle_status(args: list[str], context: dict[str, Any]) -> str:
    """Show connection status and current state.

    Args:
        args: Command arguments (unused)
        context: Chat context with connection info

    Returns:
        Status information as formatted string
    """
    l9router_url = context.get('l9router_url', 'N/A')
    user_id = context.get('user_id', 'N/A')
    agent_name = context.get('agent_name', 'N/A')
    callback_server = context.get('callback_server')

    output = "\n📡 Connection Status:\n"
    output += "=" * 50 + "\n"
    output += f"  L9Router URL:    {l9router_url}\n"
    output += f"  User ID:         {user_id}\n"
    output += f"  Agent Name:      {agent_name}\n"

    if callback_server:
        output += f"  Callback Server: Running on port {callback_server.port}\n"
    else:
        output += f"  Callback Server: Not running\n"

    # Add session info if available
    try:
        from agent_chat_cli.a2a_client import get_session_info

        session_info = get_session_info()
        duration = int(session_info['duration'].total_seconds())
        output += f"  Session ID:      {session_info['context_id'][:16]}...\n"
        output += f"  Session Duration: {duration}s\n"
    except ImportError:
        pass  # Session info not available

    # Edge case 3: Safe check for turn tracker
    turn_tracker = context.get('turn_id')
    if turn_tracker and isinstance(turn_tracker, dict):
        current_turn = turn_tracker.get('turn', 0)
        output += f"  Current Turn:    {current_turn}\n"

    output += "=" * 50

    return output


def handle_debug(args: list[str], context: dict[str, Any]) -> str:
    """Toggle debug logging on/off.

    Args:
        args: Command arguments (unused)
        context: Chat context (unused)

    Returns:
        Status message indicating new debug state
    """
    root_logger = logging.getLogger()
    current_level = root_logger.level

    if current_level == logging.DEBUG:
        root_logger.setLevel(logging.INFO)
        return "🔧 Debug logging disabled (level: INFO)"
    else:
        root_logger.setLevel(logging.DEBUG)
        return "🔧 Debug logging enabled (level: DEBUG)"


def handle_history(args: list[str], context: dict[str, Any]) -> str:
    """Show recent message history.

    Args:
        args: Command arguments (optional: number of messages to show)
        context: Chat context with message history

    Returns:
        Formatted message history
    """
    history = context.get('history', [])

    # Parse number of messages to show
    try:
        limit = int(args[0]) if args else 10
        limit = max(1, min(limit, 100))  # Clamp between 1 and 100
    except (ValueError, IndexError):
        limit = 10

    if not history:
        return "\n📜 No message history yet\n"

    # Get last N messages
    recent = history[-limit:]

    output = f"\n📜 Message History (last {len(recent)} messages):\n"
    output += "=" * 50 + "\n"

    for i, msg in enumerate(recent, 1):
        turn = msg.get('turn_id', '?')
        sender = msg.get('sender', 'unknown')
        text = msg.get('text', '')[:100]  # Truncate long messages

        if len(msg.get('text', '')) > 100:
            text += "..."

        output += f"\n[{i}] Turn {turn} - {sender}:\n"
        output += f"    {text}\n"

    output += "=" * 50

    return output


def register_default_commands() -> None:
    """Register all built-in commands."""
    from .commands import register_command

    register_command(
        name="help",
        description="Show this help message with all available commands",
        handler=handle_help,
        aliases=["?", "h"],
    )

    register_command(
        name="exit",
        description="Exit the chat gracefully",
        handler=handle_exit,
        aliases=["quit", "q"],
    )

    register_command(
        name="clear",
        description="Clear the terminal screen",
        handler=handle_clear,
        aliases=["cls"],
    )

    register_command(
        name="status",
        description="Show connection status and current state",
        handler=handle_status,
        aliases=["info"],
    )

    register_command(
        name="debug",
        description="Toggle debug logging on/off",
        handler=handle_debug,
    )

    register_command(
        name="history",
        description="Show recent message history (default: last 10 messages)",
        handler=handle_history,
        aliases=["hist"],
    )

    register_command(
        name="newsession",
        description="Start a new session with fresh conversation context",
        handler=handle_newsession,
        aliases=["ns", "new"],
    )

    register_command(
        name="sessioninfo",
        description="Display current session information",
        handler=handle_sessioninfo,
        aliases=["si", "session"],
    )

    logger.debug("Registered all default commands")
