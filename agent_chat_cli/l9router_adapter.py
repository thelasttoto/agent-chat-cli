"""
L9Router Message Adapter for agent_chat_cli

This module provides conversion functions between agent_chat_cli's message format
and L9Router's USER_MSG format for A2A communication through L9Router proxy.

The L9Router expects messages in USER_MSG format with specific fields including
type, agent_name, user_id, direction, deployment_id, conversation_id, and turn_id.
"""

import json
import logging
from typing import Any
from uuid import uuid4

from a2a.types import Message, Part, TextPart, Role

logger = logging.getLogger(__name__)


def create_user_msg_payload(
    text: str,
    agent_name: str,
    user_id: str,
    deployment_id: str,
    conversation_id: str,
    turn_id: int,
) -> dict[str, Any]:
    """
    Create USER_MSG payload for L9Router.

    This creates the payload structure expected by L9Router for user-to-agent messages.
    The payload follows the DISPATCHER-API.md specification for send_user_message().

    Args:
        text: User's message text
        agent_name: Target agent name
        user_id: User identifier
        deployment_id: Deployment UUID (mandatory)
        conversation_id: Conversation identifier for tracking
        turn_id: Turn number in the conversation

    Returns:
        Dictionary with USER_MSG structure ready to be sent to L9Router

    Example:
        >>> payload = create_user_msg_payload(
        ...     text="Hello, agent!",
        ...     agent_name="finance_agent",
        ...     user_id="alice",
        ...     deployment_id="550e8400-e29b-41d4-a716-446655440000",
        ...     conversation_id="conv-123",
        ...     turn_id=1
        ... )
    """
    logger.info(
        "Creating USER_MSG payload for agent '%s', user '%s', conversation '%s', turn %d",
        agent_name, user_id, conversation_id, turn_id
    )
    return {
        "type": "USER_MSG",
        "agent_name": agent_name,
        "user_id": user_id,
        "direction": "user_to_agent",
        "message": text,
        "deployment_id": deployment_id,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
    }


def wrap_as_a2a_message(payload: dict) -> Message:
    """
    Wrap USER_MSG payload as A2A Message for transport.

    The L9Router receives messages via A2A protocol, but the actual USER_MSG
    payload is embedded in the message parts as JSON text.

    Args:
        payload: USER_MSG payload dictionary

    Returns:
        A2A Message object with payload embedded as JSON text

    Example:
        >>> payload = create_user_msg_payload(...)
        >>> a2a_msg = wrap_as_a2a_message(payload)
    """
    payload_json = json.dumps(payload)
    context_id = payload.get("conversation_id")

    logger.info(f"Wrapping payload as A2A message. conversation_id from payload: {context_id}, setting as context_id")
    logger.debug(f"Payload: {payload_json[:100]}...")

    return Message(
        role=Role.user,
        context_id=context_id,
        message_id=uuid4().hex,
        parts=[Part(root=TextPart(text=payload_json))],
        metadata={},
    )


def extract_agent_response(a2a_response) -> tuple[str, dict | None]:
    """
    Extract USER_MSG (agent_to_user) from A2A response.

    L9Router sends back a USER_MSG with direction="agent_to_user" containing
    the agent's response and optional detective analysis.

    Args:
        a2a_response: A2A response object from L9Router

    Returns:
        Tuple of (message_text, detective_analysis_dict)
        - message_text: The agent's response text
        - detective_analysis_dict: Detective analysis if present, None otherwise

    Raises:
        ValueError: If response format is invalid or not a USER_MSG

    Example:
        >>> text, analysis = extract_agent_response(response)
        >>> print(f"Agent says: {text}")
        >>> if analysis and analysis.get("verdict") == "block":
        ...     print("Message was blocked!")
    """
    try:
        # Convert response to dictionary format
        if hasattr(a2a_response, "model_dump"):
            response_data = a2a_response.model_dump()
        elif hasattr(a2a_response, "dict"):
            response_data = a2a_response.dict()
        else:
            response_data = a2a_response

        logger.debug(f"Extracting from response: {type(a2a_response)}")

        # Extract text from response parts (the response contains USER_MSG as JSON)
        text_content = ""

        if isinstance(response_data, dict):
            # Try to get task status message parts
            if "task" in response_data:
                task = response_data["task"]
                if "status" in task and task["status"]:
                    status = task["status"]
                    if "message" in status and status["message"]:
                        message = status["message"]
                        if "parts" in message:
                            for part in message["parts"]:
                                if isinstance(part, dict):
                                    if part.get("type") == "text" and "text" in part:
                                        text_content += part["text"]
                                    elif "root" in part and isinstance(part["root"], dict):
                                        if part["root"].get("text"):
                                            text_content += part["root"]["text"]

        # If we got text content, try to parse it as USER_MSG JSON
        if text_content:
            try:
                user_msg = json.loads(text_content)

                # Validate it's a USER_MSG with agent_to_user direction
                if user_msg.get("type") != "USER_MSG":
                    logger.warning(f"Response is not USER_MSG, got: {user_msg.get('type')}")
                    return text_content, None

                if user_msg.get("direction") != "agent_to_user":
                    logger.warning(
                        f"Expected direction=agent_to_user, got: {user_msg.get('direction')}"
                    )

                # Extract message text
                message_text = user_msg.get("message", "")

                # Extract detective analysis if present
                detective_analysis = user_msg.get("detective_analysis_request")

                logger.debug(f"Extracted message: {message_text[:100]}...")
                if detective_analysis:
                    logger.debug(f"Detective analysis present: {detective_analysis}")

                return message_text, detective_analysis

            except json.JSONDecodeError:
                logger.warning("Could not parse response as JSON, returning raw text")
                return text_content, None

        # Fallback: return empty if no text found
        logger.warning("No text content found in response")
        return "", None

    except Exception as e:
        logger.error(f"Error extracting agent response: {e}")
        raise ValueError(f"Failed to extract agent response: {e}") from e


# DEPRECATED: Callback-based communication removed
# Responses now come via A2A streaming, not callbacks
# This function is kept for reference but should not be used
def extract_response_from_callback(response_message: dict) -> tuple[str, int | None, dict | None]:
    """
    DEPRECATED: Extract agent response from L9Router ResponseMessage callback.

    This function is deprecated as L9Router no longer uses callbacks.
    Responses now come directly via A2A streaming.

    Kept for reference only - do not use.
    """
    raise DeprecationWarning(
        "extract_response_from_callback is deprecated. "
        "L9Router now uses A2A push architecture - responses come via A2A streaming."
    )


def format_detective_analysis(analysis: dict) -> str:
    """
    Format detective analysis for display.

    Args:
        analysis: Detective analysis dictionary

    Returns:
        Formatted string for display

    Example:
        >>> analysis = {"verdict": "allow", "tier_reached": 1}
        >>> print(format_detective_analysis(analysis))
        🛡️ Security Analysis: ALLOWED (Tier 1)
    """
    if not analysis:
        return ""

    verdict = analysis.get("verdict", "unknown").upper()
    tier = analysis.get("tier_reached", 0)

    emoji_map = {
        "ALLOW": "✅",
        "BLOCK": "🚫",
        "REWRITE": "✏️",
    }

    emoji = emoji_map.get(verdict, "🛡️")

    return f"{emoji} Security Analysis: {verdict} (Tier {tier})"
