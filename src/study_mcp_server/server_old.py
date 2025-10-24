"""
最小限のMCPサーバー実装
"""
from mcp.server.fastmcp import FastMCP

# サーバーインスタンス作成
mcp = FastMCP("minimal-mcp-server")

# エコーツール定義
@mcp.tool()
def echo(message: str) -> str:
    """入力されたメッセージをそのまま返す簡単なツール"""
    return f"Echo: {message}"

# 日時ツール追加
@mcp.tool()
def get_current_time() -> str:
    """現在の日時を取得するツール"""
    from datetime import datetime
    now = datetime.now()
    return f"現在の日時: {now.strftime('%Y-%m-%d %H:%M:%S')}"

# リソース定義の例
@mcp.resource("info://server")
def server_info() -> str:
    """サーバーに関する情報を提供するリソース"""
    return "これは最小限の設定で作られたMCPサーバーです。"

# 動的リソースの例
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """名前に基づいた挨拶を返すリソース"""
    return f"こんにちは、{name}さん！"

# プロンプト定義の例
@mcp.prompt()
def simple_prompt(text: str) -> str:
    """単純なプロンプトテンプレート"""
    return f"以下のテキストについて考えてください: {text}"


# メイン実行部分（直接実行する場合）
if __name__ == "__main__":
    mcp.run()


