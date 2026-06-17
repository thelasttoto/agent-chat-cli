"""Tests for command processing system."""

import pytest
from agent_chat_cli.commands import (
    ChatExitException,
    Command,
    clear_commands,
    get_all_commands,
    parse_command,
    process_command,
    register_command,
)
from agent_chat_cli.command_handlers import register_default_commands


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear command registry before each test."""
    clear_commands()
    yield
    clear_commands()


def test_register_command():
    """Test command registration."""
    def dummy_handler(args, context):
        return "test output"

    register_command("test", "Test command", dummy_handler, aliases=["t"])

    commands = get_all_commands()
    assert len(commands) == 1
    assert commands[0].name == "test"
    assert commands[0].description == "Test command"
    assert commands[0].aliases == ["t"]


def test_parse_command():
    """Test command parsing."""
    # Simple command
    name, args = parse_command("/help")
    assert name == "help"
    assert args == []

    # Command with arguments
    name, args = parse_command("/history 10")
    assert name == "history"
    assert args == ["10"]

    # Command with multiple arguments
    name, args = parse_command("/test arg1 arg2 arg3")
    assert name == "test"
    assert args == ["arg1", "arg2", "arg3"]

    # Empty command
    name, args = parse_command("/")
    assert name == ""
    assert args == []


def test_process_command_help():
    """Test /help command processing."""
    register_default_commands()

    context = {
        'l9router_url': 'http://localhost:9000',
        'user_id': 'test',
        'agent_name': 'test',
        'turn_id': {},
        'history': [],
    }

    handled, output = process_command("/help", context)
    assert handled is True
    assert output is not None
    assert "Available Commands" in output
    assert "/help" in output
    assert "/exit" in output


def test_process_command_status():
    """Test /status command processing."""
    register_default_commands()

    class FakeCallbackServer:
        port = 8080

    context = {
        'l9router_url': 'http://localhost:9000',
        'user_id': 'alice',
        'agent_name': 'root_agent',
        'callback_server': FakeCallbackServer(),
        'turn_id': {'turn': 5},
        'history': [],
    }

    handled, output = process_command("/status", context)
    assert handled is True
    assert output is not None
    assert "Connection Status" in output
    assert "alice" in output
    assert "root_agent" in output
    assert "8080" in output


def test_process_command_exit():
    """Test /exit command raises exception."""
    register_default_commands()

    context = {
        'l9router_url': 'test',
        'user_id': 'test',
        'agent_name': 'test',
        'turn_id': {},
        'history': [],
    }

    with pytest.raises(ChatExitException):
        process_command("/exit", context)


def test_process_command_aliases():
    """Test command aliases work correctly."""
    register_default_commands()

    context = {
        'l9router_url': 'test',
        'user_id': 'test',
        'agent_name': 'test',
        'turn_id': {},
        'history': [],
    }

    # Test help aliases
    handled, output = process_command("/h", context)
    assert handled is True
    assert "Available Commands" in output

    handled, output = process_command("/?", context)
    assert handled is True
    assert "Available Commands" in output

    # Test exit aliases
    with pytest.raises(ChatExitException):
        process_command("/quit", context)

    with pytest.raises(ChatExitException):
        process_command("/q", context)

    # Test status alias
    handled, output = process_command("/info", context)
    assert handled is True
    assert "Connection Status" in output


def test_process_command_unknown():
    """Test unknown command returns False."""
    register_default_commands()

    context = {
        'l9router_url': 'test',
        'user_id': 'test',
        'agent_name': 'test',
        'turn_id': {},
        'history': [],
    }

    handled, output = process_command("/unknown", context)
    assert handled is False
    assert output is None


def test_process_command_not_slash():
    """Test non-slash input returns False."""
    register_default_commands()

    context = {'l9router_url': 'test', 'user_id': 'test', 'agent_name': 'test', 'turn_id': {}, 'history': []}

    handled, output = process_command("regular message", context)
    assert handled is False
    assert output is None


def test_command_with_arguments():
    """Test command that accepts arguments."""
    register_default_commands()

    context = {
        'l9router_url': 'test',
        'user_id': 'test',
        'agent_name': 'test',
        'turn_id': {},
        'history': [
            {'turn_id': 1, 'sender': 'user', 'text': 'Hello'},
            {'turn_id': 2, 'sender': 'agent', 'text': 'Hi there'},
        ],
    }

    # Test history command with argument
    handled, output = process_command("/history 1", context)
    assert handled is True
    assert output is not None
    assert "Message History" in output
