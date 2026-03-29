"""
豆包本地技能助手 - Flask 后端服务
"""
import asyncio
import json
import os
import sqlite3
from collections import defaultdict
from flask import Flask, request, jsonify, send_from_directory, Response, g
from flask_cors import CORS
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# MCP 服务配置
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
MCP_SERVER = StdioServerParameters(
    command="python",
    args=["-u", os.path.join(ROOT_DIR, "mcp_server.py")],
    cwd=ROOT_DIR
)

# 缓存 MCP 工具列表
_cached_tools = None

# 数据库路径
DB_PATH = os.path.join(ROOT_DIR, "chat_history.db")
MAX_HISTORY = 20


# ====================== MCP 工具管理 ======================
def _clean_schema(schema):
    """清理 JSON Schema，只保留豆包 API 支持的最小字段"""
    if not isinstance(schema, dict):
        return schema
    result = {}
    if "properties" in schema:
        result["properties"] = {}
        for k, v in schema["properties"].items():
            # 只保留 type
            clean_prop = {}
            if "type" in v:
                clean_prop["type"] = v["type"]
            result["properties"][k] = clean_prop
    if "required" in schema:
        result["required"] = schema["required"]
    return result


def _clean_description(desc):
    """清理工具描述"""
    if not desc:
        return desc
    import re
    # 移除多余空白
    desc = re.sub(r'\s+', ' ', desc.strip())
    return desc


async def get_mcp_tools():
    """获取 MCP 工具列表（缓存）"""
    global _cached_tools
    if _cached_tools is not None:
        return _cached_tools
    
    async with stdio_client(MCP_SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            _cached_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": _clean_description(t.description),
                        "parameters": _clean_schema(t.inputSchema)
                    }
                }
                for t in tools_result.tools
            ]
            return _cached_tools


async def run_mcp_tool(tool_name: str, arguments: dict, max_retries: int = 2):
    """运行 MCP 工具（带重试和 fallback）"""
    for attempt in range(max_retries):
        try:
            async with stdio_client(MCP_SERVER) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name=tool_name, arguments=arguments)
                    return result.content[0].text
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ 工具调用失败，重试 {attempt + 1}/{max_retries}: {str(e)}")
                await asyncio.sleep(0.5)
                continue
            else:
                # 最后一次尝试也失败，返回 fallback 提示
                error_msg = f"工具 {tool_name} 调用失败：{str(e)}"
                print(f"⚠️ {error_msg}")
                return f"[工具调用失败] {error_msg}，请直接回答问题"


# ====================== SQLite 数据库 ======================
def get_db():
    """获取数据库连接"""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def init_db():
    """初始化数据库表"""
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
        db.commit()


def get_history(session_id: str, limit: int = MAX_HISTORY) -> list:
    """获取对话历史"""
    db = get_db()
    rows = db.execute("""
        SELECT role, content FROM messages
        WHERE session_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (session_id, limit)).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def save_message(session_id: str, role: str, content: str):
    """保存消息到数据库"""
    db = get_db()
    db.execute("""
        INSERT INTO messages (session_id, role, content)
        VALUES (?, ?, ?)
    """, (session_id, role, content))
    db.commit()


def trim_history(session_id: str, limit: int = MAX_HISTORY):
    """清理超过限制的历史记录"""
    db = get_db()
    db.execute("""
        DELETE FROM messages WHERE id IN (
            SELECT id FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT -1 OFFSET ?
        )
    """, (session_id, limit))
    db.commit()


def clear_history_db(session_id: str):
    """清空会话历史"""
    db = get_db()
    db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    db.commit()


def get_all_sessions():
    """获取所有会话列表"""
    db = get_db()
    rows = db.execute("""
        SELECT
            session_id,
            MIN(timestamp) as created_at,
            MAX(timestamp) as last_active,
            COUNT(*) as message_count
        FROM messages
        GROUP BY session_id
        ORDER BY MAX(timestamp) DESC
    """).fetchall()
    return [
        {
            "session_id": row["session_id"],
            "created_at": row["created_at"],
            "last_active": row["last_active"],
            "message_count": row["message_count"]
        }
        for row in rows
    ]



# ====================== 请求关闭时清理 ======================
@app.teardown_appcontext
def close_db(error):
    """关闭数据库连接"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


# ====================== 辅助函数 ======================
def _msg_to_dict(msg):
    """将消息对象转换为字典（用于 JSON 序列化）"""
    # 检查是否是 OpenAI SDK 的消息对象（更健壮的检查）
    if hasattr(msg, 'model') and hasattr(msg, 'finish_reason'):
        # ChatCompletionMessage 对象
        result = {"role": getattr(msg, 'role', 'assistant'), "content": msg.content or ""}
        # 添加 tool_calls 如果存在
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id if hasattr(tc, 'id') else str(tc),
                    "function": {
                        "name": tc.function.name if hasattr(tc.function, 'name') else "",
                        "arguments": tc.function.arguments if hasattr(tc.function, 'arguments') else "{}"
                    },
                    "type": "function"
                }
                for tc in msg.tool_calls
            ]
        return result
    elif isinstance(msg, dict):
        return msg
    else:
        return {"role": "assistant", "content": str(msg)}


def run_in_thread(func, *args, **kwargs):
    """在线程中运行异步函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(func(*args, **kwargs))
    finally:
        loop.close()


# ====================== 路由处理 ======================





@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({"status": "ok", "message": "服务正常运行"})


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置"""
    config = {}
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip().strip("'").strip('"')
    return jsonify(config)


@app.route('/api/config', methods=['POST'])
def save_config():
    """保存配置到 .env 文件"""
    data = request.json
    try:
        # 读取现有配置
        existing_config = {}
        if os.path.exists('.env'):
            with open('.env', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line:
                        key, value = line.split('=', 1)
                        existing_config[key.strip()] = value.strip()
        
        # 更新配置
        if 'OPENAI_API_KEY' in data:
            existing_config['OPENAI_API_KEY'] = f"'{data['OPENAI_API_KEY']}'"
        if 'OPENAI_MODEL' in data:
            existing_config['OPENAI_MODEL'] = f"'{data['OPENAI_MODEL']}'"
        if 'OPENAI_BASE_URL' in data:
            existing_config['OPENAI_BASE_URL'] = f"'{data['OPENAI_BASE_URL']}'"
        
        # 写入配置文件
        with open('.env', 'w', encoding='utf-8') as f:
            for key, value in existing_config.items():
                f.write(f"{key}={value}\n")
        
        return jsonify({"success": True, "message": "配置保存成功"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def get_tools_in_thread():
    """在线程中获取工具列表"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(get_mcp_tools())
    finally:
        loop.close()

@app.route('/api/tools', methods=['GET'])
def get_tools():
    """获取可用工具列表"""
    try:
        tools = run_in_thread(get_mcp_tools)
        return jsonify({"tools": tools})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def test_connection_in_thread(api_key, model, base_url):
    """在线程中测试连接"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def _test():
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "test"}],
                temperature=0.1
            )
            return True
        except Exception:
            return False
    
    try:
        return loop.run_until_complete(_test())
    finally:
        loop.close()

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """测试 API 连接"""
    data = request.json
    api_key = data.get('api_key', '')
    model = data.get('model', '')
    base_url = data.get('base_url', '')
    
    if not api_key or not model:
        return jsonify({"connected": False, "error": "缺少 API Key 或 Model"})
    
    try:
        is_connected = test_connection_in_thread(api_key, model, base_url)
        return jsonify({"connected": is_connected})
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)})


def chat_in_thread(api_key, model, base_url, message, history, tools=None):
    """在线程中执行异步聊天函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            _chat_async(api_key, model, base_url, message, history, tools)
        )
    finally:
        loop.close()

async def _chat_async(api_key, model, base_url, user_message, history, tools=None):
    """异步聊天函数"""
    # 检查是否是讯飞 API（不支持 tools 参数）
    is_xunfei = "xf-yun.com" in base_url or "xunfei" in base_url.lower()
    
    # 如果前端没有传入工具列表，则获取所有 MCP 工具
    if tools is None and not is_xunfei:
        tools = await get_mcp_tools()
    elif tools is not None and len(tools) > 0:
        print(f"DEBUG: 使用前端传入的工具，数量={len(tools)}")
    else:
        tools = []
    
    # 过滤历史消息：只保留 user 和 assistant 消息，去除 tool 消息
    messages = [msg for msg in history if msg["role"] in ["user", "assistant"]]
    messages.append({"role": "user", "content": user_message})

    # 创建 OpenAI 客户端
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    # 构造请求体（讯飞 API 不支持 tools）
    if is_xunfei or len(tools) == 0:
        request_body = {
            "model": model,
            "messages": messages,
            "temperature": 0.1
        }
        print(f"DEBUG: 讯飞 API 或无工具，跳过 tools 参数")
    else:
        request_body = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "temperature": 0.1
        }
        print(f"DEBUG: tools length = {len(tools)}")
    
    print(f"DEBUG: 请求 Body = {json.dumps(request_body, ensure_ascii=False, indent=2)}")
    
    try:
        if is_xunfei or len(tools) == 0:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                temperature=0.1
            )
    except Exception as e:
        print(f"DEBUG: API 调用失败: {str(e)}")
        return {"response": f"API 调用失败: {str(e)}", "messages": [_msg_to_dict(m) for m in messages]}
    
    msg = response.choices[0].message
    reasoning_content = getattr(msg, "reasoning_content", "") or ""
    
    # 检查是否需要调用工具
    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        
        # 调用 MCP 工具（带 fallback）
        tool_result = await run_mcp_tool(tool_name, tool_args)
        
        # 构建第二次调用的消息
        messages.append(msg)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": tool_result
        })
        
        # 第二次调用豆包 API（让模型处理工具调用失败的情况）
        # 先转换消息列表中的对象
        final_messages = [_msg_to_dict(m) for m in messages]
        final_request_body = {
            "model": model,
            "messages": final_messages,
            "temperature": 0.1
        }
        print(f"DEBUG: 第二次请求 Body = {json.dumps(final_request_body, ensure_ascii=False, indent=2)}")
        
        try:
            final_response = client.chat.completions.create(
                model=model,
                messages=final_messages,
                temperature=0.1
            )
            final_msg = final_response.choices[0].message
            messages.append(final_msg)
            response_content = final_msg.content or tool_result
            final_reasoning = getattr(final_msg, "reasoning_content", "") or ""
            return {
                "response": f"【调用了工具：{tool_name}】\n\n{response_content}",
                "reasoning": reasoning_content + ("\n\n" + final_reasoning if final_reasoning else ""),
                "messages": [_msg_to_dict(m) for m in messages]
            }
        except Exception:
            messages.append({"role": "assistant", "content": tool_result})
            return {
                "response": f"【调用了工具：{tool_name}】\n\n{tool_result}",
                "reasoning": reasoning_content,
                "messages": [_msg_to_dict(m) for m in messages]
            }
    
    messages.append(msg)
    return {
        "response": msg.content or "无响应内容",
        "reasoning": reasoning_content,
        "messages": [_msg_to_dict(m) for m in messages]
    }

@app.route('/api/chat', methods=['POST'])
def chat():
    """聊天接口 - 调用豆包 API 和 MCP 工具"""
    data = request.json
    api_key = data.get('api_key', '')
    model = data.get('model', '')
    base_url = data.get('base_url', '')
    user_message = data.get('message', '')
    session_id = data.get('session_id', 'default')
    tools = data.get('tools')  # 前端传入的已启用工具列表

    if not api_key or not model:
        return jsonify({"error": "缺少 API Key 或 Model"}), 400

    if not user_message:
        return jsonify({"error": "消息内容不能为空"}), 400

    # 获取会话历史（从数据库）
    messages_history = get_history(session_id)

    try:
        result = chat_in_thread(api_key, model, base_url, user_message, messages_history, tools)

        # 保存历史到数据库
        if "messages" in result:
            messages = result["messages"]
            # 保存最后 MAX_HISTORY 条
            for msg in messages[-MAX_HISTORY:]:
                # 处理 OpenAI SDK 返回的消息格式
                if hasattr(msg, 'model') and hasattr(msg, 'finish_reason'):
                    # ChatCompletionMessage 对象
                    content = msg.content or ""
                    role = getattr(msg, 'role', 'assistant')
                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                    role = msg.get("role", "assistant")
                else:
                    content = str(msg)
                    role = "assistant"
                
                save_message(session_id, role, content)
            # 清理旧数据
            trim_history(session_id)

        return jsonify({
            "response": result["response"],
            "reasoning": result.get("reasoning", ""),
            "session_id": session_id
        })
    except Exception as e:
        import traceback
        print(f"DEBUG: chat() 异常: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat/clear', methods=['POST'])
def clear_history():
    """清除对话历史"""
    data = request.json
    session_id = data.get('session_id', 'default')

    clear_history_db(session_id)

    return jsonify({"success": True, "message": "对话历史已清除"})


@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """获取所有会话列表"""
    try:
        sessions = get_all_sessions()
        return jsonify({"sessions": sessions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """删除会话"""
    try:
        clear_history_db(session_id)
        return jsonify({"success": True, "message": "会话已删除"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/sessions/<session_id>/history', methods=['GET'])
def get_session_history(session_id):
    """获取会话历史"""
    try:
        history = get_history(session_id, limit=100)  # 获取最近100条
        return jsonify({"history": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500




async def _stream_generator(api_key, endpoint_id, base_url, message, history):
    """异步流式生成器"""
    async for chunk in _chat_stream_async(api_key, endpoint_id, base_url, message, history):
        yield chunk

def stream_in_thread(api_key, model, base_url, message, history):
    """在线程中执行异步流式聊天函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        generator = _stream_generator(api_key, model, base_url, message, history)
        while True:
            try:
                chunk = loop.run_until_complete(generator.__anext__())
                yield chunk
            except StopAsyncIteration:
                break
    finally:
        loop.close()

async def _chat_stream_async(api_key, model, base_url, user_message, history):
    """异步流式聊天函数"""
    # 获取 MCP 工具
    tools = await get_mcp_tools()
    
    # 使用历史消息
    messages = history.copy()
    messages.append({"role": "user", "content": user_message})
    
    # 创建 OpenAI 客户端
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    # 第一次调用豆包 API
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            temperature=0.1,
            stream=True
        )
    except Exception as e:
        yield f"data: {{\"error\": \"API 调用失败: {str(e)}\"}}\n\n"
        return
    
    full_response = ""
    tool_calls = None
    tool_call_id = None
    tool_name = None
    
    # 处理流式响应
    for chunk in stream:
        if chunk.choices:
            choice = chunk.choices[0]
            if choice.delta:
                delta = choice.delta
                if delta.content:
                    content = delta.content
                    full_response += content
                    yield f"data: {{\"response\": \"{content.replace('\\n', '\\\\n')}\"}}\n\n"
                elif delta.tool_calls:
                    tool_calls = delta.tool_calls
    
    # 检查是否需要调用工具
    if tool_calls:
        tool_call = tool_calls[0]
        tool_call_id = tool_call.id
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        
        # 调用 MCP 工具（带 fallback）
        tool_result = await run_mcp_tool(tool_name, tool_args)
        
        # 构建第二次调用的消息
        messages.append({"role": "assistant", "tool_calls": [{"id": tool_call_id, "function": {"name": tool_call.function.name, "arguments": tool_call.function.arguments}, "type": "function"}]})
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": tool_result
        })
        
        # 发送工具调用提示
        yield f"data: {{\"response\": \"【调用了工具：{tool_name}】\\n\\n\"}}\n\n"
        
        # 第二次调用豆包 API
        try:
            final_stream = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                stream=True
            )
            
            for chunk in final_stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    if choice.delta and choice.delta.content:
                        content = choice.delta.content
                        yield f"data: {{\"response\": \"{content.replace('\\n', '\\\\n')}\"}}\n\n"
        except Exception:
            yield f"data: {{\"response\": \"{tool_result.replace('\\n', '\\\\n')}\"}}\n\n"
    
    yield "data: [DONE]\n\n"

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """流式聊天接口（SSE）"""
    data = request.json
    api_key = data.get('api_key', '')
    model = data.get('model', '')
    base_url = data.get('base_url', '')
    user_message = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    if not api_key or not model:
        return jsonify({"error": "缺少 API Key 或 Model"}), 400
    
    if not user_message:
        return jsonify({"error": "消息内容不能为空"}), 400
    
    # 获取会话历史（从数据库）
    messages_history = get_history(session_id)
    
    def generate():
        # 收集完整消息用于保存历史
        full_user_message = {"role": "user", "content": user_message}
        full_assistant_messages = []
        
        for chunk in stream_in_thread(api_key, model, base_url, user_message, messages_history):
            yield chunk
            
            # 尝试解析 chunk 并收集消息
            if chunk.startswith("data: ") and chunk.strip() != "data: [DONE]\n\n":
                try:
                    data_str = chunk[6:].strip()
                    if data_str.startswith("{") and data_str.endswith("}\n\n"):
                        data_obj = json.loads(data_str[:-2])
                        if "response" in data_obj:
                            response = data_obj["response"]
                            if not response.startswith("【"):
                                if not full_assistant_messages:
                                    full_assistant_messages.append({"role": "assistant", "content": response})
                                else:
                                    full_assistant_messages[0]["content"] += response
                except:
                    pass
        
        # 保存历史到数据库
        save_message(session_id, full_user_message["role"], full_user_message["content"])
        for msg in full_assistant_messages:
            save_message(session_id, msg["role"], msg["content"])
        trim_history(session_id)
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/')
def index():
    """返回前端页面"""
    return send_from_directory('.', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    """返回静态文件"""
    return send_from_directory('.', path)


if __name__ == '__main__':
    print("=" * 50)
    print("豆包本地技能助手 - Flask 后端服务")
    print("=" * 50)
    print("服务地址: http://localhost:5000")
    print("API 文档:")
    print("  GET  /api/health          - 健康检查")
    print("  GET  /api/tools           - 获取工具列表")
    print("  POST /api/test-connection - 测试连接")
    print("  POST /api/chat            - 聊天")
    print("=" * 50)
    
    # 确保 MCP 服务文件存在
    mcp_server_path = os.path.join(ROOT_DIR, "mcp_server.py")
    if not os.path.exists(mcp_server_path):
        print(f"\n警告: 未找到 MCP 服务文件: {mcp_server_path}")
        print("请先创建 mcp_server.py 文件\n")
    
    # 初始化数据库
    init_db()
    print("✅ 数据库已初始化")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
