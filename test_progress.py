import sys
import os
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

server_dir = Path("d:/github/pla_teplate/_blueprint_server")
sys.path.insert(0, str(server_dir))

from agent_tools import _index_knowledge

async def test_indexing_with_progress():
    print("\n--- Testing Indexing with Progress ---")
    
    # Create a mock session that prints progress
    mock_session = AsyncMock()
    async def mock_send_progress(progress_token, progress, total):
        print(f"[Progress] Token: {progress_token}, Progress: {progress}/{total}")
    
    mock_session.send_progress_notification.side_effect = mock_send_progress
    
    # Create a mock context
    mock_ctx = MagicMock()
    mock_ctx.meta.progressToken = "test_token_123"
    mock_ctx.session = mock_session
    
    # Create a mock server
    mock_server = MagicMock()
    mock_server.request_context.get.return_value = mock_ctx
    
    try:
        args = {"__server__": mock_server}
        result = await _index_knowledge(args)
        if result and len(result) > 0:
            # Note: The result might be a list of TextContent objects
            # Check if it has a 'text' attribute or just print
            print(f"\nResult: {getattr(result[0], 'text', result[0])}")
        else:
            print(f"\nEmpty result.")
    except Exception as e:
        print(f"Search Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_indexing_with_progress())
