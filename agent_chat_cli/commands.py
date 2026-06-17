"""Command processing system for agent_chat_cli.

This module provides a command registry and processor for handling
slash commands (e.g., /help, /exit) in the chat interface.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ChatExitException(Exception):
    """Raised when user wants to exit the chat."""
    pass


@dataclass
class Command:
    """Represents a chat command."""
    name: str
    description: str
    handler: Callable[[list[str], dict[str, Any]], str | None]
    aliases: list[str]


# Global command registry
_commands: dict[str, Command] = {}


def register_command(
    name: str,
    description: str,
    handler: Callable[[list[str], dict[str, Any]], str | None],
    aliases: list[str] | None = None,
) -> None:
    """Register a command in the global registry.

    Args:
        name: Command name (without /)
        description: Human-readable description
        handler: Function to execute command
        aliases: Alternative names for the command
    """
    if aliases is None:
        aliases = []

    command = Command(
        name=name,
        description=description,
        handler=handler,
        aliases=aliases,
    )
    _commands[name] = command
    logger.debug(f"Registered command: /{name} (aliases: {aliases})")


def parse_command(input_text: str) -> tuple[str, list[str]]:
    """Parse command input into command name and arguments.

    Args:
        input_text: User input starting with /

    Returns:
        (command_name, args): Tuple of command name and argument list

    Example:
        "/help" -> ("help", [])
        "/history 10" -> ("history", ["10"])
        "/unknown arg1 arg2" -> ("unknown", ["arg1", "arg2"])
    """
    # Remove leading "/" and split
    parts = input_text[1:].split()
    command_name = parts[0].lower() if parts else ""
    args = parts[1:] if len(parts) > 1 else []
    return command_name, args


def process_command(input_text: str, context: dict[str, Any]) -> tuple[bool, str | None]:
    """Process a command input.

    Args:
        input_text: User input (should start with /)
        context: Context dictionary with chat state

    Returns:
        (handled, output):
            - handled: True if command was recognized and executed
            - output: Message to display to user, or None

    Raises:
        ChatExitException: If exit command was executed
    """
    if not input_text.startswith('/'):
        return False, None

    command_name, args = parse_command(input_text)

    if not command_name:
        return False, None

    # Check main commands
    if command_name in _commands:
        try:
            logger.debug(f"Executing command: /{command_name} with args: {args}")
            output = _commands[command_name].handler(args, context)
            return True, output
        except ChatExitException:
            # Let exit exception bubble up
            raise
        except Exception as e:
            logger.error(f"Command /{command_name} failed: {e}", exc_info=True)
            return True, f"❌ Command failed: {e}"

    # Check aliases
    for cmd in _commands.values():
        if command_name in cmd.aliases:
            try:
                logger.debug(f"Executing command: /{command_name} (alias for /{cmd.name}) with args: {args}")
                output = cmd.handler(args, context)
                return True, output
            except ChatExitException:
                raise
            except Exception as e:
                logger.error(f"Command /{command_name} failed: {e}", exc_info=True)
                return True, f"❌ Command failed: {e}"

    # Not a recognized command
    return False, None


def get_all_commands() -> list[Command]:
    """Get all registered commands.

    Returns:
        List of Command objects sorted by name
    """
    return sorted(_commands.values(), key=lambda c: c.name)


def clear_commands() -> None:
    """Clear all registered commands (useful for testing)."""
    global _commands
    _commands = {}
