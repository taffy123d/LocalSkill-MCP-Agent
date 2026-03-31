# 命令行界面
import os
import asyncio
import json
from collections import defaultdict
from dotenv import load_dotenv
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ===================== 基础配置 =====================
load_dotenv()
API_KEY = os.getenv("DOUBAO_API_KEY")
ENDPOINT_ID = os.getenv("DOUBAO_ENDPOINT_ID")
BASE_URL = os.getenv("DOUBAO_BASE_URL")
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# MCP 服务配置
MCP_SERVER = StdioServerParameters(
    command="python",
    args=["-u", os.path.join(ROOT_DIR, "mcp_server.py")],
    cwd=ROOT_DIR
)

# 全局缓存：仅缓存工具定义（不缓存会话，彻底解决异步崩溃）
CACHED_MCP_TOOLS = None

# 对话历史存储
chat_histories = defaultdict(list)
MAX_HISTORY = 20

# ===================== 工具调用（稳定版） =====================
async def run_mcp_tool(tool_name: str, arguments: dict):
    """每次调用新建临时MCP会话，100%无崩溃"""
    try:
        async with stdio_client(MCP_SERVER) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name=tool_name, arguments=arguments)
                return result.content[0].text
    except Exception as e:
        return f"工具调用失败：{str(e)}"

# ===================== 对话核心 =====================
async def chat_with_doubao(user_input: str, session_id: str = "default"):
    global CACHED_MCP_TOOLS
    http_client = httpx.AsyncClient(timeout=10)
    
    # 1. 首次运行：加载MCP工具（仅加载1次，无冗余日志）
    if CACHED_MCP_TOOLS is None:
        async with stdio_client(MCP_SERVER) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                CACHED_MCP_TOOLS = [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.inputSchema
                        }
                    } for t in tools.tools
                ]
        # print("✅ 本地技能加载完成（仅首次）")

    # 2. 构造请求
    messages = chat_histories.get(session_id, []).copy()
    messages.append({"role": "user", "content": user_input})
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        # 第一次请求：判断是否调用工具
        resp = await http_client.post(
            url=BASE_URL,
            json={
                "model": ENDPOINT_ID,
                "messages": messages,
                "tools": CACHED_MCP_TOOLS,
                "temperature": 0.1
            },
            headers=headers
        )
        data = resp.json()
        msg = data["choices"][0]["message"]

        # 3. 执行工具调用
        if "tool_calls" in msg:
            tool = msg["tool_calls"][0]
            tool_name = tool["function"]["name"]
            args = json.loads(tool["function"]["arguments"])
            
            # 调用本地技能
            tool_result = await run_mcp_tool(tool_name, args)
            
            # 拼接消息（修复：失败也能生成回答）
            messages.append(msg)
            messages.append({
                "role": "tool",
                "tool_call_id": tool["id"],
                "content": tool_result
            })

            # 第二次请求：生成最终回答
            final_resp = await http_client.post(
                url=BASE_URL,
                json={
                    "model": ENDPOINT_ID,
                    "messages": messages,
                    "temperature": 0.1
                },
                headers=headers
            )
            final_data = final_resp.json()
            final_msg = final_data["choices"][0]["message"]
            messages.append(final_msg)
            
            # 兜底：模型无输出时，直接返回工具结果
            final_answer = final_msg.get("content") or tool_result
            response = f"【调用了工具：{tool_name}】\n\n{final_answer}"
        else:
            # 普通对话直接返回
            messages.append(msg)
            response = msg["content"]
        
        # 更新历史
        chat_histories[session_id] = messages[-MAX_HISTORY:]
        return response

    except Exception as e:
        return f"处理失败：{str(e)}"
    finally:
        await http_client.aclose()

# ===================== 主程序入口 =====================
async def main():
    print("=" * 50)
    print("🤖 ToolKit本地技能Agent（稳定版）")
    print("✅ 计算器 | 🌤️ 天气查询")
    print("=" * 50)

    session_id = "default"
    
    while True:
        user_query = input("\n请输入你的问题：").strip()
        if not user_query:
            continue
        if user_query.lower() in ["exit", "quit", "退出"]:
            print("👋 再见！")
            break
        if user_query.lower() in ["clear", "清除历史"]:
            if session_id in chat_histories:
                del chat_histories[session_id]
            print("✅ 对话历史已清除")
            continue
        
        # 执行对话
        answer = await chat_with_doubao(user_query, session_id)
        print("\n" + "=" * 50)
        print("🤖 Agent回答：")
        print(answer)
        print("=" * 50)

if __name__ == "__main__":
    # 关闭异步异常抛送，Windows 完美运行
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见！")
    except Exception:
        pass