import asyncio
from typing import Any
from study_mcp_server.client.mcp_client import MCPClient
from gradio.components.chatbot import ChatMessage
import gradio as gr
from openai import OpenAI
import re

# --- asyncioイベントループ作成 ---
loop = asyncio.new_event_loop()


class MultiMCPManager:
    """
    MCPを介して複数のサーバー・ツールと接続し、
    GPTを利用してチャットと自動ツール呼び出しを行うクラス
    """
    def __init__(self):
        # MCPクライアント初期化
        self.os_client = MCPClient("mcp_os_name")       # OS情報取得用
        self.disk_client = MCPClient("mcp_disk_usage")  # ディスク使用状況取得用

        # GPT初期化（社内GPTやOpenAI無料枠も利用可能）
        self.gpt = OpenAI(api_key="YOUR_API_KEY")
        self.model_name = "gpt-3.5-turbo"

        # ツール情報
        self.all_tools = []
        self.tool_to_client = {}

    def initialize_servers(self) -> str:
        """全サーバーへの接続を同期的に実行"""
        return loop.run_until_complete(self._initialize_servers())

    async def _initialize_servers(self) -> str:
        """各MCPクライアントに非同期接続"""
        servers = [
            (self.os_client, "server/mcp_os_name.py"),
            (self.disk_client, "server/mcp_disk_usage.py")
        ]
        tasks = [self._connect_client(client, path) for client, path in servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return "\n".join(str(result) for result in results)

    async def _connect_client(self, client: MCPClient, server_path: str) -> str:
        """個別クライアントの接続処理"""
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
        """
        ユーザー入力を処理し、チャット履歴とテキストボックスを返す
        """
        new_messages = loop.run_until_complete(self._process_query(message, history))
        updated_history = history + [{"role": "user", "content": message}] + new_messages
        textbox_reset = gr.Textbox(value="")
        return updated_history, textbox_reset

    async def _process_query(
            self,
            message: str,
            history: list[dict[str, Any] | ChatMessage]
    ) -> list[dict[str, Any]]:
        """
        GPTにユーザー入力と履歴を渡し、必要に応じてMCPツールを自動実行して応答を生成
        """
        chat_messages = []

        # 過去の履歴をGPT用フォーマットに変換
        for msg in history:
            if isinstance(msg, ChatMessage):
                role, content = msg.role, msg.content
            else:
                role, content = msg.get("role"), msg.get("content")
            if role in ["user", "assistant", "system"]:
                chat_messages.append({"role": role, "content": content})

        # GPTにツール情報と使い方をプロンプトで明示
        system_prompt = (
            "あなたはMCPツールを使えるアシスタントです。\n"
            "利用可能なツール:\n"
            "1. get_disk_usage: ディスク使用状況を取得\n"
            "2. get_os_info: OS情報を取得\n"
            "必要な場合はツールを使用してください。\n"
            "ツールを使う場合は必ず /tool_name 形式で返答してください。"
        )
        chat_messages.insert(0, {"role": "system", "content": system_prompt})

        # ユーザー入力を追加
        chat_messages.append({"role": "user", "content": message})

        # GPTに送信
        response = await self.gpt.chat.completions.create(
            model=self.model_name,
            messages=chat_messages,
            max_tokens=1024
        )

        gpt_reply = response.choices[0].message.content
        result_messages = []

        # GPTの返答がツール呼び出し形式か確認
        tool_call_match = re.match(r"/(\w+)", gpt_reply.strip())
        if tool_call_match:
            # GPTがツール呼び出しを指示した場合
            tool_name = tool_call_match.group(1)
            client = self.tool_to_client.get(tool_name)
            if client:
                # ツールを呼び出す
                result = await client.session.call_tool(tool_name, {})
                tool_result_text = str(result.content)

                # ツール結果をGPTに渡して自然な文章に変換
                chat_messages.append({
                    "role": "user",
                    "content": f"ツールの結果はこちらです:\n{tool_result_text}"
                })
                next_response = await self.gpt.chat.completions.create(
                    model=self.model_name,
                    messages=chat_messages,
                    max_tokens=1024
                )
                final_text = next_response.choices[0].message.content
                result_messages.append({"role": "assistant", "content": final_text})
            else:
                # クライアントが存在しない場合
                result_messages.append({"role": "assistant", "content": f"ツール {tool_name} は存在しません。"})
        else:
            # 通常のGPT応答として返す
            result_messages.append({"role": "assistant", "content": gpt_reply})

        return result_messages
