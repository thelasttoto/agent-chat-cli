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

    logger.debug(f"Wrapping payload as A2A message: {payload_json[:100]}...")

    return Message(
        role=Role.user,
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


def extract_response_from_callback(response_message: dict) -> tuple[str, int | None, dict | None]:
    """
    Extract agent response from L9Router ResponseMessage callback.

    This function processes the ResponseMessage sent to the callback endpoint
    by L9Router after routing a USER_MSG to an agent and receiving the response.

    Args:
        response_message: ResponseMessage dict from L9Router callback
            Expected structure:
            {
                "result": {
                    "status": "routed",
                    "message_id": "...",
                    "agent_name": "...",
                    "user_id": "...",
                    "direction": "agent_to_user",
                    "detective_analysis": {...}
                },
                "original_request": {
                    "type": "USER_MSG",
                    "message": "...",
                    "turn_id": 1,
                    ...
                },
                "request_id": "...",
                "timestamp": "..."
            }

    Returns:
        Tuple of (message_text, turn_id, detective_analysis)
        - message_text: The agent's response message
        - turn_id: Turn ID from original request (or None)
        - detective_analysis: Detective analysis dict (or None)

    Raises:
        ValueError: If response format is invalid

    Example:
        >>> callback_msg = {...}  # ResponseMessage from L9Router
        >>> text, turn_id, analysis = extract_response_from_callback(callback_msg)
        >>> print(f"Agent response (turn {turn_id}): {text}")
    """
    try:
        logger.info("📦 Extracting response from callback")

        # Extract result containing routing info
        result = response_message.get("result", {})
        logger.debug(f"Result: {result}")

        # Get detective analysis from result
        detective_analysis = result.get("detective_analysis")

        # Extract original request to get turn_id and message
        original_request = response_message.get("original_request", {})
        logger.debug(f"Original request keys: {list(original_request.keys())}")

        # Get turn_id from original request
        turn_id = original_request.get("turn_id")

        # Get the message from original request
        # In L9Router's ResponseMessage, the original_request contains the USER_MSG
        # that was sent to the agent. The actual agent response would come through
        # another callback when the agent responds back through L9Router.

        # However, based on the L9Router flow, when an agent responds, it sends
        # a USER_MSG with direction="agent_to_user" back through L9Router,
        # which then calls the user's callback with the ResponseMessage.

        # So we need to check if the original_request is the agent's response
        message_text = ""
        message_field = original_request.get("message")
        logger.debug(f"Message field type: {type(message_field)}, value: {message_field if isinstance(message_field, str) and len(message_field) < 200 else '(too long)'}")

        if isinstance(message_field, str):
            # Message is already a string, use directly
            message_text = message_field
        elif isinstance(message_field, dict):
            # Message is a dict, might be nested
            message_text = message_field.get("message", "")
        else:
            logger.warning(f"Unexpected message field type: {type(message_field)}")

        logger.info(f"✅ Extracted message from callback: turn_id={turn_id}, message_len={len(message_text)}, preview={message_text[:50] if message_text else '(empty)'}...")

        return message_text, turn_id, detective_analysis

    except Exception as e:
        logger.error(f"Error extracting callback response: {e}")
        raise ValueError(f"Failed to extract callback response: {e}") from e


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
