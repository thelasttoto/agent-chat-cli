"""Tests for command processing system."""

import pytest
from uuid import uuid4
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

    context = {
        'l9router_url': 'http://localhost:9000',
        'user_id': 'alice',
        'agent_name': 'root_agent',
        'turn_id': {'turn_id': str(uuid4())},
        'history': [],
    }

    handled, output = process_command("/status", context)
    assert handled is True
    assert output is not None
    assert "Connection Status" in output
    assert "alice" in output
    assert "root_agent" in output
    assert "http://localhost:9000" in output


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
            {'turn_id': str(uuid4()), 'sender': 'user', 'text': 'Hello'},
            {'turn_id': str(uuid4()), 'sender': 'agent', 'text': 'Hi there'},
        ],
    }

    # Test history command with argument
    handled, output = process_command("/history 1", context)
    assert handled is True
    assert output is not None
    assert "Message History" in output


def test_newsession_command():
    """Test /newsession creates new context ID."""
    try:
        from agent_chat_cli.a2a_client import get_session_context_id, reset_session

        # Get initial session ID
        initial_id = get_session_context_id()

        # Reset session
        new_id = reset_session()

        # Verify new ID is different
        assert new_id != initial_id
        assert get_session_context_id() == new_id
    except ImportError:
        pytest.skip("Session management not available")


def test_newsession_command_handler():
    """Test /newsession command handler."""
    register_default_commands()

    old_turn_id = str(uuid4())
    turn_tracker = {'turn_id': old_turn_id}

    context = {
        'l9router_url': 'test',
        'user_id': 'test',
        'agent_name': 'test',
        'turn_id': turn_tracker,
        'history': [],
    }

    handled, output = process_command('/newsession', context)

    assert handled is True
    assert output is not None
    assert "New Session Started" in output
    # Verify turn_id was reset to a new UUID (different from old one)
    assert 'turn_id' in turn_tracker
    assert turn_tracker['turn_id'] != old_turn_id
    # Verify it's a valid UUID format
    assert len(turn_tracker['turn_id']) == 36  # UUID string length


def test_newsession_aliases():
    """Test /newsession aliases work correctly."""
    register_default_commands()

    turn_tracker = {'turn_id': str(uuid4())}

    context = {
        'l9router_url': 'test',
        'user_id': 'test',
        'agent_name': 'test',
        'turn_id': turn_tracker,
        'history': [],
    }

    # Test /ns alias
    old_turn_id = turn_tracker['turn_id']
    handled, output = process_command('/ns', context)
    assert handled is True
    assert "New Session Started" in output
    assert turn_tracker['turn_id'] != old_turn_id
    assert len(turn_tracker['turn_id']) == 36

    # Test /new alias
    old_turn_id = turn_tracker['turn_id']
    handled, output = process_command('/new', context)
    assert handled is True
    assert "New Session Started" in output
    assert turn_tracker['turn_id'] != old_turn_id
    assert len(turn_tracker['turn_id']) == 36


def test_sessioninfo_command():
    """Test /sessioninfo command displays session information."""
    register_default_commands()

    test_turn_id = str(uuid4())
    turn_tracker = {'turn_id': test_turn_id}

    context = {
        'l9router_url': 'test',
        'user_id': 'test',
        'agent_name': 'test',
        'turn_id': turn_tracker,
        'history': [],
    }

    handled, output = process_command('/sessioninfo', context)

    assert handled is True
    assert output is not None
    assert "Session Information" in output
    assert "Session ID:" in output
    assert "Duration:" in output
    assert "Current Turn ID:" in output
    assert test_turn_id in output  # Full UUID should be displayed


def test_sessioninfo_aliases():
    """Test /sessioninfo aliases work correctly."""
    register_default_commands()

    context = {
        'l9router_url': 'test',
        'user_id': 'test',
        'agent_name': 'test',
        'turn_id': {'turn_id': str(uuid4())},
        'history': [],
    }

    # Test /si alias
    handled, output = process_command('/si', context)
    assert handled is True
    assert "Session Information" in output

    # Test /session alias
    handled, output = process_command('/session', context)
    assert handled is True
    assert "Session Information" in output


def test_status_includes_session_info():
    """Test /status command includes session information."""
    register_default_commands()

    class FakeCallbackServer:
        port = 8080

    test_turn_id = str(uuid4())
    context = {
        'l9router_url': 'http://localhost:9000',
        'user_id': 'alice',
        'agent_name': 'root_agent',
        'callback_server': FakeCallbackServer(),
        'turn_id': {'turn_id': test_turn_id},
        'history': [],
    }

    handled, output = process_command('/status', context)

    assert handled is True
    assert output is not None
    assert "Connection Status" in output
    assert "Session ID:" in output
    assert "Session Duration:" in output
    assert test_turn_id in output  # Full UUID should be displayed
