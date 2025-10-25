import asyncio
import os

import gradio as gr
from dotenv import load_dotenv

from study_mcp_server.client.multi_mcp_manager_old import MultiMCPManager

load_dotenv()
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

manager = MultiMCPManager()

def gradio_interface():
    with gr.Blocks(title="MCP Host Demo") as demo:
        gr.Markdown("# MCP Host Demo")
        # MCPサーバーに接続し、接続状況を表示
        gr.Textbox(
            label="MCP Server 接続状況",
            value=manager.initialize_servers(),
            interactive=False
        )
        chatbot = gr.Chatbot(
            value=[],
            height=500,
            type="messages",
            show_copy_button=True,
            avatar_images=("images/m_.jpeg", "images/robo.jpg"),
        )
        with gr.Row(equal_height=True):
            msg = gr.Textbox(
                label="質問してください。",
                placeholder="Ask about OS information or disk usage",
                scale=4
            )
            clear_btn = gr.Button("Clear Chat", scale=1)

        msg.submit(manager.process_message, [msg, chatbot], [chatbot, msg])
        clear_btn.click(lambda: [], None, chatbot)
    return demo

if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Warning: ANTHROPIC_API_KEY を .env ファイルに設定してください。")

    interface = gradio_interface()
    interface.launch(debug=True)