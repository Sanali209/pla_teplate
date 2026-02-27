"""
server.py — Blueprint MCP Server entry point.
Registers all resources, prompts, and agent tools, then starts the server via stdio transport.

Usage:
    cd _blueprint_server
    pip install -r requirements.txt
    python server.py
"""

from __future__ import annotations

import asyncio
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server

from config import SERVER_NAME, SERVER_VERSION
from resources import register_resources
from prompts import register_prompts
from agent_tools import register_agent_tools
from logger import server_start


def create_server() -> Server:
    server = Server(SERVER_NAME)
    register_resources(server)
    register_prompts(server)
    register_agent_tools(server)
    return server


async def main() -> None:
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    server_start(SERVER_NAME, SERVER_VERSION)
    asyncio.run(main())
