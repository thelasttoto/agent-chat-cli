# L9Router Mode Documentation

## Overview

agent-chat-cli now supports **L9Router mode**, which enables communication with agents through the L9Router proxy. This provides enhanced observability, security analysis via detective agent, and centralized message routing.

## What is L9Router?

L9Router is an Agent-to-Agent (A2A) message routing proxy that:
- **Routes messages** between users and agents with observability
- **Analyzes messages** using a detective agent for security
- **Logs all interactions** for audit and debugging
- **Tracks conversations** with conversation_id and turn_id
- **Supports USER_MSG format** for user-agent communication

## Architecture

```
User → agent-chat-cli → L9Router → Detective Agent → Target Agent
                            ↓
                        Logging & Observability
```

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DEPLOYMENT_ID` | UUID identifying the deployment (**mandatory**) | `550e8400-e29b-41d4-a716-446655440000` |
| `L9ROUTER_AGENT_NAME` | Name of the target agent | `travel_agent` |
| `L9ROUTER_USER_ID` | User identifier | `alice` |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `L9ROUTER_MODE` | Enable L9Router mode | `false` |
| `L9ROUTER_URL` | L9Router server URL | `http://localhost:9000` |
| `DEPLOYMENT_NAME` | Logical deployment name | `demo_deployment` |
| `A2A_DEBUG_CLIENT` | Enable debug logging | `false` |

## Usage

### Method 1: Using Environment Variables

```bash
# Set required variables
export DEPLOYMENT_ID=550e8400-e29b-41d4-a716-446655440000
export L9ROUTER_AGENT_NAME=finance_agent
export L9ROUTER_USER_ID=alice
export L9ROUTER_MODE=true

# Run the client
uv run python -m agent_chat_cli a2a
```

### Method 2: Using CLI Flags

```bash
export DEPLOYMENT_ID=550e8400-e29b-41d4-a716-446655440000

uv run python -m agent_chat_cli a2a \
  --l9router \
  --agent-name finance_agent \
  --user-id alice
```

### Method 3: Using Demo Script

```bash
# Edit demo_l9router_chat.sh to configure your settings
./demo_l9router_chat.sh
```

### Method 4: Docker

```bash
docker run -it --network=host \
  -e L9ROUTER_MODE=true \
  -e L9ROUTER_URL=http://localhost:9000 \
  -e L9ROUTER_AGENT_NAME=travel_agent \
  -e L9ROUTER_USER_ID=alice \
  -e DEPLOYMENT_ID=550e8400-e29b-41d4-a716-446655440000 \
  ghcr.io/cnoe-io/agent-chat-cli:latest a2a --l9router
```

## Message Format

### User to Agent (user_to_agent)

When you send a message in L9Router mode, agent-chat-cli creates a `USER_MSG` payload:

```json
{
  "type": "USER_MSG",
  "agent_name": "finance_agent",
  "user_id": "alice",
  "direction": "user_to_agent",
  "message": "Can I spend $500?",
  "deployment_id": "550e8400-e29b-41d4-a716-446655440000",
  "conversation_id": "conv-abc123",
  "turn_id": 1
}
```

### Agent to User (agent_to_user)

L9Router sends back a `USER_MSG` with the agent's response:

```json
{
  "type": "USER_MSG",
  "agent_name": "finance_agent",
  "user_id": "alice",
  "direction": "agent_to_user",
  "message": "Yes, you can spend $500. Budget approved.",
  "deployment_id": "550e8400-e29b-41d4-a716-446655440000",
  "conversation_id": "conv-abc123",
  "turn_id": 1,
  "detective_analysis_request": {
    "verdict": "allow",
    "tier_reached": 1,
    "message_id": "msg_xyz"
  }
}
```

## Security Features

### Detective Agent Analysis

All messages are analyzed by the detective agent. The analysis result includes:

- **`verdict`**: `"allow"`, `"block"`, or `"rewrite"`
- **`tier_reached`**: Analysis depth (0=skipped, 1=OPA, 2=embedding, 3=LLM)
- **`message_id`**: Detective message identifier

### Blocked Messages

If the detective agent blocks a message (verdict: "block"), you'll see:

```
🚫 Message was blocked by security analysis
```

### Security Display

agent-chat-cli displays security analysis for each message:

```
✅ Security Analysis: ALLOWED (Tier 1)
🚫 Security Analysis: BLOCKED (Tier 2)
✏️ Security Analysis: REWRITTEN (Tier 1)
```

## Conversation Management

### Conversation ID

- Automatically managed using a session context ID
- Persists across all messages in the same session
- Allows L9Router to track conversation flow

### Turn ID

- Automatically incremented for each message sent
- Starts at 1 for the first message
- Used for request/response correlation

## Troubleshooting

### Error: DEPLOYMENT_ID is required

```
❌ DEPLOYMENT_ID environment variable is required for L9Router mode
Set it to a UUID, e.g.: export DEPLOYMENT_ID=550e8400-e29b-41d4-a716-446655440000
```

**Solution**: Set the `DEPLOYMENT_ID` environment variable to a valid UUID.

### Error: Agent name is required

```
❌ Agent name is required for L9Router mode
Use --agent-name or set L9ROUTER_AGENT_NAME environment variable
```

**Solution**: Specify the target agent name using `--agent-name` flag or `L9ROUTER_AGENT_NAME` env var.

### Error: User ID is required

```
❌ User ID is required for L9Router mode
Use --user-id or set L9ROUTER_USER_ID environment variable
```

**Solution**: Specify a user ID using `--user-id` flag or `L9ROUTER_USER_ID` env var.

### Connection Failed

If you can't connect to L9Router:

1. **Check L9Router is running**: `curl http://localhost:9000/health`
2. **Verify URL**: Ensure `L9ROUTER_URL` matches your L9Router instance
3. **Check network**: Ensure agent-chat-cli can reach L9Router (use `--network=host` with Docker)

### No Response from Agent

If L9Router receives the message but you get no response:

1. **Check agent registration**: Verify the target agent is registered with L9Router
2. **Check agent is running**: Ensure the target agent is active and responding
3. **Check detective agent**: Verify the detective agent isn't blocking messages
4. **Enable debug mode**: Set `A2A_DEBUG_CLIENT=true` to see detailed logs

## Comparison: Standard vs L9Router Mode

| Feature | Standard A2A Mode | L9Router Mode |
|---------|------------------|---------------|
| Connection | Direct to agent | Via L9Router proxy |
| Message Format | Standard A2A | USER_MSG format |
| Security Analysis | None | Detective agent |
| Observability | Limited | Full logging |
| Message Tracking | Basic | conversation_id + turn_id |
| Deployment ID | Not required | **Required** (UUID) |

## Example Session

```bash
$ export DEPLOYMENT_ID=550e8400-e29b-41d4-a716-446655440000
$ export L9ROUTER_AGENT_NAME=travel_agent
$ export L9ROUTER_USER_ID=alice
$ uv run python -m agent_chat_cli a2a --l9router

🔀 L9Router proxy mode enabled
  📍 L9Router URL: http://localhost:9000
  🎯 Target Agent: travel_agent
  👤 User ID: alice
  🆔 Deployment ID: 550e8400-e29b-41d4-a716-446655440000

🚀 Launching A2A client...

> Hello, I'd like to book a flight to Paris

✅ Security Analysis: ALLOWED (Tier 1)

╭─ Agent Response ────────────────╮
│ I'd be happy to help you book   │
│ a flight to Paris! Let me check │
│ available options...            │
╰─────────────────────────────────╯
```

## Advanced Usage

### Custom L9Router Deployment

```bash
# Production L9Router instance
export L9ROUTER_URL=https://l9router.prod.example.com
export DEPLOYMENT_ID=prod-550e8400-e29b-41d4-a716-446655440000
export L9ROUTER_AGENT_NAME=production_agent
export L9ROUTER_USER_ID=user123

uv run python -m agent_chat_cli a2a --l9router
```

### Multiple Agents

Switch between agents by changing the agent name:

```bash
# Talk to finance agent
export L9ROUTER_AGENT_NAME=finance_agent
uv run python -m agent_chat_cli a2a --l9router

# Talk to travel agent (new session)
export L9ROUTER_AGENT_NAME=travel_agent
uv run python -m agent_chat_cli a2a --l9router
```

## See Also

- [DISPATCHER-API.md](../DISPATCHER-API.md) - L9Router dispatcher API specification
- [README.md](README.md) - Main agent-chat-cli documentation
- [demo_l9router_chat.sh](demo_l9router_chat.sh) - Demo script
