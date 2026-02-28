import sys
import os
import asyncio
from pathlib import Path

# Add server directory to path
server_dir = Path("d:/github/pla_teplate/_blueprint_server")
sys.path.insert(0, str(server_dir))

from agent_tools import _search_rag

async def test_search():
    print("\n--- Testing Search (Query: 'clean architecture') ---")
    try:
        search_result = await _search_rag({"query": "clean architecture principles", "top_k": 3})
        print(f"Search Result:\n{search_result}")
    except Exception as e:
        print(f"Search Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())
