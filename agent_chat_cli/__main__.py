#!/usr/bin/env python3

import click
import importlib.util
import sys
from pathlib import Path
import logging
from rich.console import Console
from rich.theme import Theme
from rich.prompt import Prompt
from rich.panel import Panel
from rich.align import Align
import os

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python < 3.11 fallback

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


def load_client_module(protocol):
    """Dynamically load the client module for the given protocol."""
    base_dir = Path(__file__).parent
    module_path = base_dir / f"{protocol}_client.py"

    if not module_path.exists():
        click.echo(f"❌ Error: {protocol}_client.py not found at {module_path}")
        sys.exit(1)

    try:
        spec = importlib.util.spec_from_file_location(f"{protocol}_client", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        click.echo(f"❌ Failed to load {protocol}_client: {e}")
        sys.exit(1)


def get_version():
    """
    Read version from multiple sources (in order of preference):
    1. Package metadata (works with pip/uvx installed packages)
    2. pyproject.toml (works in development/editable installs)
    3. Fallback to "0.0.0"
    """
    # Try package metadata first (works for installed packages via pip/uvx)
    try:
        from importlib.metadata import version

        return version("agent-chat-cli")
    except Exception:
        pass

    # Try reading from pyproject.toml (works in development/Docker)
    try:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)
        return pyproject_data["project"]["version"]
    except Exception:
        pass

    # Fallback
    return "0.0.0"


__version__ = get_version()


@click.group()
@click.version_option(version=__version__, prog_name="agent-chat-cli")
def cli():
    """Agent CLI Chat Client — Interact with chat agents using multiple protocols."""
    pass


# Theme for general-purpose agent UX
custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "agent": "green",
        "prompt": "magenta",
    }
)
console = Console(theme=custom_theme)


@cli.command()
@click.option("--host", "-h", default=None, help="Host/IP of the A2A agent")
@click.option("--port", "-p", default=None, type=int, help="Port to connect to")
@click.option("--token", "-t", default=None, help="Authentication token")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option(
    "--multi-input",
    is_flag=True,
    help="Enable multi-line input mode (read from stdin until EOF)",
)
@click.option(
    "--no-history",
    is_flag=True,
    help="Disable readline history (do not load or save chat history)",
)
@click.option(
    "--l9router",
    default=None,
    help="L9Router/Dispatcher URL (e.g., http://localhost:8888 or http://localhost:9000). If not provided, uses L9ROUTER_URL environment variable or L9ROUTER_MODE flag.",
)
@click.option("--agent-name", default=None, help="Target agent name (L9Router mode)")
@click.option("--user-id", default=None, help="User identifier (L9Router mode)")
def a2a(host, port, token, debug, multi_input, no_history, l9router, agent_name, user_id):
    """Run A2A protocol client."""

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine L9Router mode and URL
    l9router_url = None
    l9router_mode = False

    if l9router:
        # URL provided as parameter - use it directly
        l9router_url = l9router
        l9router_mode = True
    elif os.environ.get("L9ROUTER_MODE", "false").lower() in ["true", "1", "yes"]:
        # L9Router mode enabled via environment variable
        l9router_url = os.environ.get("L9ROUTER_URL", "http://localhost:9000")
        l9router_mode = True

    # L9Router mode: validate and configure
    if l9router_mode:
        console.print("🔀 [info]L9Router proxy mode enabled[/info]")
        deployment_id = os.environ.get("DEPLOYMENT_ID")

        # Get agent_name and user_id from CLI args or environment
        if not agent_name:
            agent_name = os.environ.get("L9ROUTER_AGENT_NAME")
        if not user_id:
            user_id = os.environ.get("L9ROUTER_USER_ID")

        # Validate required parameters
        if not deployment_id:
            console.print("[error]❌ DEPLOYMENT_ID environment variable is required for L9Router mode[/error]")
            console.print("[info]Set it to a UUID, e.g.: export DEPLOYMENT_ID=550e8400-e29b-41d4-a716-446655440000[/info]")
            sys.exit(1)

        if not agent_name:
            console.print("[error]❌ Agent name is required for L9Router mode[/error]")
            console.print("[info]Use --agent-name or set L9ROUTER_AGENT_NAME environment variable[/info]")
            sys.exit(1)

        if not user_id:
            console.print("[error]❌ User ID is required for L9Router mode[/error]")
            console.print("[info]Use --user-id or set L9ROUTER_USER_ID environment variable[/info]")
            sys.exit(1)

        # Set environment variables for a2a_client to use
        os.environ["L9ROUTER_MODE"] = "true"
        os.environ["L9ROUTER_URL"] = l9router_url
        os.environ["L9ROUTER_AGENT_NAME"] = agent_name
        os.environ["L9ROUTER_USER_ID"] = user_id
        os.environ["DEPLOYMENT_ID"] = deployment_id

        # Parse L9Router URL to get host and port
        from urllib.parse import urlparse
        parsed = urlparse(l9router_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 9000

        console.print(f"  📍 L9Router URL: {l9router_url}")
        console.print(f"  🎯 Target Agent: {agent_name}")
        console.print(f"  👤 User ID: {user_id}")
        console.print(f"  🆔 Deployment ID: {deployment_id}")
    else:
        # Read from environment if not provided (standard A2A mode)
        env_host = os.environ.get("A2A_HOST", "localhost")
        env_port = os.environ.get("A2A_PORT", "8000")
        env_token = os.environ.get("A2A_TOKEN", "")

    # Skip prompts in L9Router mode (already configured)
    if not l9router_mode:
        # Enhanced popup prompt
        def popup_input(prompt_text, default=None, password=False):
            panel = Panel(
                Align.left(prompt_text, vertical="middle"),
                title="💬 Input Required",
                border_style="prompt",
                padding=(1, 2),
            )
            console.print(panel)
            return Prompt.ask("👉", default=default, password=password)

        def simple_prompt(label: str, default: str = None, password: bool = False) -> str:
            console.print(f"💬 [prompt]{label}[/prompt]", end="")
            return Prompt.ask("", default=default, password=password)

        # Welcome banner with version and configuration prompt
        console.print(
            Panel(
                Align.center(
                    f"🚀 [agent]agent-chat-cli[/agent] v{__version__}\n\n"
                    f"🔧 A2A Client Setup\n"
                    f"Set your Auth Key (or press Enter to skip)",
                    vertical="middle",
                ),
                title="✨ Welcome",
                border_style="bold cyan",
                padding=(1, 2),
            )
        )

    if not l9router_mode and not host:
        if env_host:
            host = env_host
        else:
            host = simple_prompt("[info]Enter host[/info]", default=None)

    if not l9router_mode and not port:
        if env_port:
            try:
                port = int(env_port)
            except ValueError:
                port = None
        if not port:
            port_input = simple_prompt("[info]Enter port[/info]", default=None)
            try:
                port = int(port_input)
            except (ValueError, TypeError):
                console.print(
                    "[error]❌ Invalid port. Please provide a valid port.[/error]"
                )
                sys.exit(1)

    if not l9router_mode and token is None:
        if env_token:
            token = env_token
        else:
            token = simple_prompt(
                "[info]Enter token[/info] (optional)", default=None, password=True
            )

    console.print("🚀 [info]Launching A2A client...[/info]")
    if "A2A_HOST" not in os.environ:
        os.environ["A2A_HOST"] = str(host)
    if "A2A_PORT" not in os.environ:
        os.environ["A2A_PORT"] = str(port)

    if os.environ.get("A2A_TLS", "false").lower() in ["true", "1", "yes"]:
        tls = True
    else:
        tls = False

    client_module = load_client_module("a2a")
    client_module.main(
        host=host,
        port=port,
        token=token,
        tls=tls,
        multi_input_enabled=multi_input,
        no_history=no_history,
    )


@cli.command()
@click.option(
    "--endpoint",
    "-e",
    default=None,
    help="SLIM transport endpoint (e.g., 127.0.0.1:46357)",
)
@click.option(
    "--remote-card",
    "-c",
    default=None,
    help="Remote agent card (URL, JSON string, or file path)",
)
@click.option("--debug", is_flag=True, help="Enable debug logging")
def slim(endpoint, remote_card, debug):
    """Run SLIM protocol client."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("agent_chat_cli").setLevel(logging.DEBUG)
        logging.getLogger("agent_chat_cli.slim_client").setLevel(logging.DEBUG)
        logging.getLogger("agntcy_app_sdk").setLevel(logging.DEBUG)

    env_endpoint = os.environ.get("SLIM_ENDPOINT")
    env_remote_card = os.environ.get("SLIM_REMOTE_CARD")

    def simple_prompt(label: str, default: str = None, password: bool = False) -> str:
        console.print(f"💬 [prompt]{label}[/prompt]", end="")
        return Prompt.ask("", default=default, password=password)

    if not endpoint:
        endpoint = env_endpoint or simple_prompt(
            "[info]Enter SLIM endpoint (host:port)[/info]"
        )

    if not remote_card:
        remote_card = env_remote_card or simple_prompt(
            "[info]Enter remote Agent Card (URL or JSON or file path)[/info]"
        )

    # Ensure endpoint always contains scheme for SLIM transport
    if endpoint and not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"

    console.print("🚀 [info]Launching SLIM client...[/info]")
    client_module = load_client_module("slim")
    client_module.main(endpoint=endpoint, remote_card=remote_card, debug=debug)


if __name__ == "__main__":
    # Choose default subcommand from env when none is provided
    default_mode = os.environ.get("AGENT_CHAT_PROTOCOL", "").strip().lower() or "a2a"
    if len(sys.argv) == 1:
        if default_mode not in ("a2a", "slim"):
            default_mode = "a2a"
        sys.argv.insert(1, default_mode)
    cli()
