"""
Callback Server for L9Router Integration

This module provides a FastAPI-based HTTP server that receives callback messages
from L9Router when agents respond to user messages. The server puts incoming
messages into an asyncio queue for consumption by the chat interface.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class CallbackServer:
    """
    HTTP server that receives ResponseMessage callbacks from L9Router.

    The server runs in the background and puts incoming messages into a queue
    for the chat interface to consume and display.
    """

    def __init__(self, port: int, message_queue: asyncio.Queue):
        """
        Initialize callback server.

        Args:
            port: Port to listen on
            message_queue: Queue to put incoming messages into
        """
        self.port = port
        self.message_queue = message_queue
        self.server_task: asyncio.Task | None = None
        self.server: uvicorn.Server | None = None
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Create FastAPI application with callback endpoint."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Lifespan context manager for startup/shutdown."""
            logger.info(f"Callback server starting on port {self.port}")
            yield
            logger.info("Callback server shutting down")

        app = FastAPI(
            title="Agent Chat CLI Callback Server",
            description="Receives callbacks from L9Router",
            lifespan=lifespan,
        )

        @app.post("/callback")
        async def callback_endpoint(request: Request):
            """
            Receive ResponseMessage from L9Router.

            Expected format (ResponseMessage from L9Router):
            {
                "result": {
                    "status": "routed",
                    "message_id": "...",
                    "agent_name": "...",
                    "user_id": "...",
                    "direction": "agent_to_user",
                    "latency_ms": 42.5,
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
            """
            try:
                body = await request.json()
                logger.info(f"📥 Received callback message from L9Router")
                logger.debug(f"Callback body: {body}")

                # Put message into queue for chat interface to consume
                await self.message_queue.put(body)

                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "received",
                        "message": "Callback processed successfully",
                    },
                )

            except Exception as e:
                logger.error(f"Error processing callback: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return JSONResponse(
                status_code=200,
                content={
                    "status": "healthy",
                    "port": self.port,
                    "queue_size": self.message_queue.qsize(),
                },
            )

        return app

    async def start(self):
        """Start the callback server in the background."""
        if self.server_task is not None:
            logger.warning("Server already running")
            return

        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="warning",  # Reduce uvicorn logging noise
            access_log=False,  # Disable access logs
        )
        self.server = uvicorn.Server(config)

        # Run server in background task
        self.server_task = asyncio.create_task(self.server.serve())
        logger.info(f"Callback server started on http://0.0.0.0:{self.port}")

        # Give server a moment to start
        await asyncio.sleep(0.1)

    async def stop(self):
        """Stop the callback server gracefully."""
        if self.server_task is None:
            logger.warning("Server not running")
            return

        logger.info("Stopping callback server...")

        # Signal server to shutdown
        if self.server:
            self.server.should_exit = True

        # Wait for server task to complete (with timeout)
        try:
            await asyncio.wait_for(self.server_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Server shutdown timeout, cancelling task")
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass

        self.server_task = None
        self.server = None
        logger.info("Callback server stopped")

    def get_callback_url(self, host: str = "localhost") -> str:
        """
        Get the callback URL for L9Router registration.

        Args:
            host: Hostname to use in URL (default: localhost)

        Returns:
            Full callback URL (e.g., http://localhost:8080/callback)
        """
        return f"http://{host}:{self.port}/callback"


def find_available_port(start_port: int = 8080, max_attempts: int = 100) -> int:
    """
    Find an available port for the callback server.

    Args:
        start_port: Port to start searching from
        max_attempts: Maximum number of ports to try

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found
    """
    import socket

    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", port))
                return port
        except OSError:
            continue

    raise RuntimeError(
        f"No available port found in range {start_port}-{start_port + max_attempts}"
    )
