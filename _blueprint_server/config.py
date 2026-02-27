"""
config.py — Configuration for the Blueprint MCP Server.
Set BLUEPRINT_ROOT to point to the _blueprint/ directory in your repository.
"""

from pathlib import Path

# Adjust this path if the server is run from a different working directory.
# By default we resolve relative to the repo root (one level up from this file).
BLUEPRINT_ROOT: Path = Path(__file__).parent.parent / "_blueprint"

# MCP server name displayed to clients
SERVER_NAME = "blueprint-server"
SERVER_VERSION = "0.1.0"
