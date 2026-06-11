#!/bin/bash
# Demo script for agent-chat-cli in L9Router mode
#
# This script demonstrates how to use agent-chat-cli to communicate with
# agents through the L9Router proxy, which provides observability, security
# analysis via detective agent, and message routing.
#
# Prerequisites:
# - L9Router must be running on localhost:9000
# - Target agent must be registered and running
# - DEPLOYMENT_ID must be set to a UUID
#
# Usage:
#   ./demo_l9router_chat.sh

# Enable L9Router proxy mode
export L9ROUTER_MODE=true

# L9Router configuration
export L9ROUTER_URL=http://localhost:9000

# Target agent configuration
# Change these to match your setup
export L9ROUTER_AGENT_NAME=travel_agent
export L9ROUTER_USER_ID=alice

# Deployment ID (must be a UUID - required for L9Router)
# This should match the DEPLOYMENT_ID used by your agents/dispatcher
export DEPLOYMENT_ID=550e8400-e29b-41d4-a716-446655440000

# Optional: Deployment name
export DEPLOYMENT_NAME=demo_deployment

# Optional: Enable debug logging
# export A2A_DEBUG_CLIENT=true

echo "=========================================="
echo "🔀 L9Router Chat Demo"
echo "=========================================="
echo "L9Router URL:    $L9ROUTER_URL"
echo "Target Agent:    $L9ROUTER_AGENT_NAME"
echo "User ID:         $L9ROUTER_USER_ID"
echo "Deployment ID:   $DEPLOYMENT_ID"
echo "=========================================="
echo ""
echo "Starting agent-chat-cli in L9Router mode..."
echo "All messages will be routed through L9Router for:"
echo "  - Observability (logging)"
echo "  - Security analysis (detective agent)"
echo "  - Message routing and tracking"
echo ""

# Run the chat client with L9Router mode
cd "$(dirname "$0")"
uv run python -m agent_chat_cli a2a --l9router
