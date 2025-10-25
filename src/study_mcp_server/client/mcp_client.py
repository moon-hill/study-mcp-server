from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClient:
    """個別のMCPサーバーとの接続を管理するクラス"""

    def __init__(self, server_name: str):
        self.server_name = server_name
        self.session = None
        self.exit_stack = None
        self.tools = []
        self.tool_server_map = {}

    async def connect(self, server_path: str) -> str:
        """MCPサーバーに接続し、利用可能なツールを取得"""
        if self.exit_stack:
            await self.exit_stack.aclose()
        self.exit_stack = AsyncExitStack()
        server_params = StdioServerParameters(
            command="python",
            args=[server_path],
            env={"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        )

        # サーバープロセスを起動し、標準入出力経由でMCPサーバーと非同期に接続しセッションを初期化
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )
        await self.session.initialize()

        # サーバーから利用可能なツール一覧を取得
        response = await self.session.list_tools()
        self.tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        self.tool_server_map = {tool.name: self.server_name for tool in response.tools}
        tool_names = [tool["name"] for tool in self.tools]
        return f"{self.server_name}と接続しました。利用可能なツール: {', '.join(tool_names)}"