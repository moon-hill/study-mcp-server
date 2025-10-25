import asyncio
from typing import Any
from anthropic import Anthropic
from study_mcp_server.client.mcp_client import MCPClient

from gradio.components.chatbot import ChatMessage
import gradio as gr


loop = asyncio.new_event_loop()

class MultiMCPManager:
    def __init__(self):
        self.os_client = MCPClient("mcp_os_name")
        self.disk_client = MCPClient("mcp_disk_usage")
        self.anthropic = Anthropic()
        self.all_tools = []
        self.tool_to_client = {}
        self.model_name = "claude-3-7-sonnet-20250219"

    def initialize_servers(self) -> str:
        """全サーバーへの接続"""
        return loop.run_until_complete(self._initialize_servers())

    async def _initialize_servers(self) -> str:
        servers = [
            (self.os_client, "server/mcp_os_name.py"),
            (self.disk_client, "server/mcp_disk_usage.py")
        ]
        tasks = [
            self._connect_client(client, path)
            for client, path in servers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return "\n".join(str(result) for result in results)

    async def _connect_client(self, client: MCPClient, server_path: str) -> str:
        """個別のクライアント接続処理"""
        try:
            result = await client.connect(server_path)
            self.all_tools.extend(client.tools)
            for tool_name in client.tool_server_map:
                self.tool_to_client[tool_name] = client
            return result
        except Exception as e:
            return f"Failed to connect to {server_path} server: {str(e)}"

    def process_message(
            self,
            message: str,
            history: list[dict[str, Any] | ChatMessage]
    ) -> tuple:
        new_messages = loop.run_until_complete(self._process_query(message, history))
        # チャット履歴を更新
        updated_history = history + [{"role": "user", "content": message}] + new_messages
        textbox_reset = gr.Textbox(value="")
        return updated_history, textbox_reset

    async def _process_query(
            self,
            message: str,
            history: list[dict[str, Any] | ChatMessage]
    ) -> list[dict[str, Any]]:
        claude_messages = []
        for msg in history:
            if isinstance(msg, ChatMessage):
                role, content = msg.role, msg.content
            else:
                role, content = msg.get("role"), msg.get("content")

            if role in ["user", "assistant", "system"]:
                claude_messages.append({"role": role, "content": content})

        claude_messages.append({"role": "user", "content": message})

        # ユーザーからの質問を使用可能なツール情報を含めて、Claude API用の形式に変換して送信
        response = self.anthropic.messages.create(
            model=self.model_name,
            max_tokens=1024,
            messages=claude_messages,
            tools=self.all_tools
        )
        result_messages = []

        # Claude APIからの応答を処理
        for content in response.content:
            if content.type == 'text':
                result_messages.append({
                    "role": "assistant",
                    "content": content.text
                })
            elif content.type == 'tool_use':
                tool_name = content.name
                tool_args = content.input
                client = self.tool_to_client.get(tool_name)

                # Claude API から使用を提示されたツールを実行
                client = self.tool_to_client.get(tool_name)
                result = await client.session.call_tool(tool_name, tool_args)
                result_text = str(result.content)
                result_messages.append({
                    "role": "assistant",
                    "content": "```\n" + result_text + "\n```",
                    "metadata": {
                        "parent_id": f"result_{tool_name}",
                        "id": f"raw_result_{tool_name}",
                        "title": "Raw Output"
                    }
                })

                # ツールの実行結果を含めて再度Claude API 呼び出し
                claude_messages.append({
                    "role": "user",
                    "content": (
                        f"Tool result for {tool_name}:\n"
                        f"{result_text}"
                    )
                })
                next_response = self.anthropic.messages.create(
                    model=self.model_name,
                    max_tokens=1024,
                    messages=claude_messages,
                )
                if next_response.content and next_response.content[0].type == 'text':
                    result_messages.append({
                        "role": "assistant",
                        "content": next_response.content[0].text
                    })

        return result_messages