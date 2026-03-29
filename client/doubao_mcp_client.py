"""豆包 Ark 平台 + MCP 工具完整调用客户端"""
import os
import asyncio
import json
from dotenv import load_dotenv
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 加载环境变量
load_dotenv()

# 从环境变量读取 OpenAI SDK 格式配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

# 自动获取项目根目录（解决路径问题）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# MCP 服务配置【绝对路径+兼容所有Windows】
MCP_SERVER_CONFIG = StdioServerParameters(
    command="python",
    args=["-u", os.path.join(PROJECT_ROOT, "mcp_server.py")],
    cwd=PROJECT_ROOT
)

async def call_doubao_ark_with_mcp(user_query: str) -> str:
    async with stdio_client(MCP_SERVER_CONFIG) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            available_tools = tools_result.tools
            print(f"已加载本地 MCP 工具：{[tool.name for tool in available_tools]}")

            # 构造消息
            messages = [{"role": "user", "content": user_query}]
            
            # 转换 MCP 工具为兼容格式
            tools = []
            for mcp_tool in available_tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": mcp_tool.name,
                        "description": mcp_tool.description,
                        "parameters": mcp_tool.inputSchema
                    }
                })

            # 创建 OpenAI 客户端
            client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

            try:
                # 第一次请求：判断是否调用工具
                response = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    tools=tools,
                    temperature=0.1
                )
                
                message = response.choices[0].message

                # 核心修复：工具调用
                if message.tool_calls:
                    tool_call = message.tool_calls[0]
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    print(f"\n模型调用本地工具：{tool_name}，参数：{tool_args}")

                    # 调用工具
                    tool_result = await session.call_tool(
                        name=tool_name,
                        arguments=tool_args
                    )
                    
                    # 打印工具原始返回
                    tool_content = tool_result.content[0].text
                    print(f"\n工具返回结果：\n{tool_content}")

                    # 拼接工具返回消息
                    messages.append(message)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_content
                    })

                    # 第二次请求：生成最终回答
                    final_response = client.chat.completions.create(
                        model=OPENAI_MODEL,
                        messages=messages,
                        temperature=0.1
                    )
                    
                    return final_response.choices[0].message.content
                
                # 无需调用工具，直接返回
                return message.content

            except Exception as e:
                print(f"\n【错误详情】：{str(e)}")
                return f"调用失败：{str(e)}"

# ====================== 测试区 ======================
if __name__ == "__main__":
    # 优先测试计算器（无网络依赖）
    query = "帮我计算 100 + 200 * 3 等于多少"
    
    # 如需测试天气，取消下面注释
    # query = "帮我查一下北京的天气"
    
    result = asyncio.run(call_doubao_ark_with_mcp(query))
    print("\n" + "="*50)
    print("🤖 豆包最终回答：")
    print(result)
