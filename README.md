# ToolKit本地技能Agent

一个基于 MCP (Model Context Protocol) 协议的本地技能助手，支持计算器、天气查询等自定义技能，提供 Web 界面和 API 接口。

## 项目结构

```
..
├── .env                    # 大模型 API 配置
├── chat_history.db         # SQLite 对话历史数据库（自动生成）
├── index.html              # 前端 Web 界面
├── main.py                 # 主入口（命令行界面）
├── mcp_server.py          # MCP 服务端（核心）
├── server.py               # Flask 后端服务
├── requirements.txt        # 依赖清单
├── README.md               # 项目说明
├── tree.txt                # 目录结构
├── client/                 # 客户端目录
│   ├── doubao_mcp_client.py  # 豆包 API 客户端
│   └── __init__.py
├── config/                 # 配置目录
│   ├── settings.py         # 全局配置
│   └── __init__.py
└── skills/                 # 技能实现目录
    ├── calculator.py       # 计算器技能
    ├── weather.py          # 天气查询技能
    ├── web_search/         # 网络搜索技能目录
    │   └── web_search.py   # DuckDuckGo搜索实现
    |   └── SKILL.md  # skill描述
    |   └── _init_.py   
    └── __init__.py
```

## 技术栈
**后端框架**：Python + Flask 构建 Web 服务，提供 RESTful API 与 SSE 流式输出接口

**AI 协议与模型调用**：基于 OpenAI 兼容 SDK 对接大模型 API，支持豆包等 OpenAI 格式模型接入

**核心协议**：MCP（Model Context Protocol）实现工具调用标准化，统一技能注册与调度

**异步架构**：asyncio 异步处理 + 线程池隔离，解决 Flask 同步环境下异步调用阻塞问题

**数据持久化**：SQLite 实现多会话对话上下文存储，支持会话管理与历史加载

**技能插件化**：模块化技能系统，支持计算器、天气、网络搜索等可插拔工具扩展

**前端**：原生 HTML/JS 实现 Web 交互界面，支持 Markdown 渲染、流式打字效果、思维链展示

**工程化** ：api变量配置（.env）、依赖管理（uv/pip）、错误重试与降级机制、工具调用缓存
## 核心功能

✅ **稳定的异步处理** - 修复了Flask路由中直接使用asyncio.run()的问题，使用线程池执行异步函数

✅ **对话历史持久化** - 使用 SQLite 存储对话历史，服务重启不丢失，支持多会话管理

✅ **工具调用容错** - 自动重试机制，工具调用失败时降级到模型直接回答

✅ **MCP 工具缓存** - 首次获取工具列表后缓存，减少重复初始化开销

✅ **流式输出** - 实现了完整的SSE流式接口，支持逐字输出体验

✅ **工具调用提示** - 当调用技能时，会显示"【调用了工具：{工具名称}】"的提示信息

✅ **多端支持** - 提供Web界面和命令行界面两种交互方式

✅ **丰富的技能** - 内置计算器、天气查询和网络搜索技能

✅ **技能管理** - 前端可视化技能管理，可自由开关技能

✅ **Markdown渲染** - 支持Markdown格式的回复，支持代码高亮、表格、列表、数学公式等

✅ **思维链展示** - 可折叠的AI思考过程展示，便于理解推理逻辑

✅ **多会话管理** - 支持创建多个独立对话，每个对话独立保存历史

✅ **历史对话加载** - 切换会话时自动加载历史对话，完整记录交互过程


## 环境要求

- Python 3.11+
- openaiSDK(api)
- uv 包管理工具（推荐）或 pip

## 安装

### 方法一：使用 uv 包管理工具（推荐）

1. **安装 uv**
   ```bash
   # Windows
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser 
   irm https://astral.sh/uv/install.ps1 | iex
   
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **克隆项目**
   ```bash
   git clone https://github.com/taffy123d/Doubao-MCP-agent
   cd <项目目录>
   ```

3. **创建虚拟环境**
   ```bash
   uv venv
   ```

4. **安装依赖**
   ```bash
   uv sync
   ```

### 方法二：使用 pip

1. **克隆项目**
   ```bash
   git clone https://github.com/taffy123d/Doubao-MCP-agent
   cd <项目目录>
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   ```

3. **激活虚拟环境**
   ```bash
   # Windows
   venv\Scripts\activate
   
   # macOS / Linux
   source venv/bin/activate
   ```

4. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

## 配置

- ##### 在前端配置api密钥
- ##### 或在 `.env` 文件中填写 API 密钥：

```env
# OpenAI 兼容格式的 API 配置
OPENAI_API_KEY=你的API密钥
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
OPENAI_MODEL=你的模型ID
```



## 运行

### 方法一：完整启动（推荐）

```bash
uv run server.py
#或者
python server.py
```

- 前端访问：`http://localhost:5000`
- API 接口：`http://localhost:5000/api/*`

### 方法二：命令行界面

```bash
uv run main.py
#或者
python main.py
```

- 直接在终端中进行对话
- 支持多轮对话和历史记录
- 输入 `clear` 或 `清除历史` 可以清除对话历史
- 输入 `exit`、`quit` 或 `退出` 可以退出程序

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端页面 |
| `/api/health` | GET | 健康检查 |
| `/api/tools` | GET | 获取技能列表 |
| `/api/config` | GET | 获取配置 |
| `/api/config` | POST | 保存配置 |
| `/api/test-connection` | POST | 测试 API 连接 |
| `/api/chat` | POST | 聊天（支持对话历史） |
| `/api/chat/stream` | POST | 流式聊天（SSE） |
| `/api/chat/clear` | POST | 清除对话历史 |
| `/api/sessions` | GET | 获取所有会话列表 |
| `/api/sessions/<id>` | DELETE | 删除指定会话 |
| `/api/sessions/<id>/history` | GET | 获取会话历史记录 |

### API 请求示例

#### 聊天接口

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "你的API密钥",
    "model": "你的模型ID",
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "message": "北京天气",
    "session_id": "default"
  }'
```

#### 流式聊天接口

```bash
curl -X POST http://localhost:5000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "你的API密钥",
    "model": "你的模型ID",
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "message": "北京天气",
    "session_id": "default"
  }'
```

#### 清除历史接口

```bash
curl -X POST http://localhost:5000/api/chat/clear \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "default"
  }'
```

## 如何使用

### Web 界面

1. **配置 API**
   - 在左侧配置面板填写 API Key 和 Endpoint ID
   - 点击「测试」按钮验证连接

2. **聊天**
   - 在输入框中输入问题
   - 支持的技能：
     - 计算器：`计算 123+456`
     - 天气查询：`北京天气`
     - 网络搜索：`搜索 最新AI新闻`

3. **技能管理**
   - 点击左侧「🔧 技能管理」展开面板
   - 查看所有可用技能及其描述
   - 点击开关按钮启用/禁用技能
   - 只有启用的技能才会被调用

4. **多会话管理**
   - 点击左侧「💬 对话管理」展开面板
   - 点击「➕ 新建对话」创建新会话
   - 点击会话列表项切换到对应对话
   - 点击🗑️删除不需要的对话
   - 每个会话独立保存历史记录

5. **查看结果**
   - 系统会自动调用相应的技能并返回结果
   - 支持Markdown格式的回复（代码高亮、表格、列表等）
   - 可点击「🧠 思考过程」查看AI的推理逻辑
   - 支持多轮对话

### 命令行界面

1. **运行程序**
   ```bash
   python main.py
   ```

2. **输入问题**
   - 直接在终端中输入你的问题
   - 支持的技能：
     - 计算器：`计算 123+456`
     - 天气查询：`北京天气`

3. **查看结果**
   - 系统会自动调用相应的技能并返回结果
   - 支持多轮对话
   - 输入 `clear` 或 `清除历史` 可以清除对话历史

## 如何增加新技能

### 步骤 1：创建技能文件

在 `skills/` 目录下创建新的技能文件，例如 `my_skill.py`：

```python
"""我的自定义技能"""
from mcp.server.fastmcp import FastMCP

def register_my_skill(mcp: FastMCP):
    """注册技能到 MCP 服务"""
    
    @mcp.tool()
    def my_skill(param1: str, param2: int = 1) -> str:
        """
        我的自定义技能描述
        示例：my_skill(param1="值", param2=2)
        
        Args:
            param1: 参数1描述
            param2: 参数2描述（默认值）
        Returns:
            技能执行结果
        """
        try:
            # 技能逻辑实现
            result = f"处理结果: {param1} - {param2}"
            return result
        except Exception as e:
            return f"处理失败: {str(e)}"
```

### 步骤 2：注册技能

编辑 `skills/__init__.py`，添加新技能的注册函数：

```python
from .calculator import register_calculator_tool
from .weather import register_weather_tool
from .my_skill import register_my_skill

__all__ = [
    "register_calculator_tool", 
    "register_weather_tool",
    "register_my_skill"
]
```

### 步骤 3：更新 MCP 服务

编辑 `mcp_server.py`，添加新技能的注册：

```python
from skills import register_calculator_tool, register_weather_tool, register_my_skill

# 注册所有技能工具
register_calculator_tool(mcp)
register_weather_tool(mcp)
register_my_skill(mcp)  # 添加这一行
```

### 步骤 4：重启服务

重新启动 MCP 服务和后端服务，新技能即可使用。

## 技能开发规范

1. **文件命名**：使用小写字母和下划线
2. **函数命名**：`register_xxx_tool` 格式
3. **工具装饰器**：使用 `@mcp.tool()` 装饰
4. **文档字符串**：包含功能描述、示例和参数说明
5. **错误处理**：捕获异常并返回友好提示
6. **参数类型**：使用类型注解

## 如何创建复杂 Skill（带 SKILL.md）

对于功能较复杂的技能，建议创建独立的 skill 目录，包含技能实现和 SKILL.md 描述文件。

### 目录结构

```
skills/
└── my_complex_skill/          # skill 目录
    ├── __init__.py            # 导出配置（必选）
    ├── my_skill.py            # 技能实现（必选）
    └── SKILL.md               # skill 描述文档（必选）
```

### 步骤 1：创建 skill 目录和实现文件

在 `skills/` 目录下创建新的 skill 目录，例如 `skills/my_complex_skill/`

#### 1.1 创建技能实现文件 `my_skill.py`

```python
"""我的复杂技能实现"""
from mcp.server.fastmcp import FastMCP
from duckduckgo_search import AsyncDuckDuckGoSearcher  # 示例依赖

def register_my_complex_skill(mcp: FastMCP):
    """注册复杂技能到 MCP 服务"""
    
    @mcp.tool()
    async def my_complex_skill(query: str, limit: int = 5) -> str:
        """
        我的复杂技能描述
        
        Args:
            query: 查询关键词
            limit: 返回结果数量，默认5
        
        Returns:
            格式化的搜索结果
        """
        try:
            async with AsyncDuckDuckGoSearcher() as searcher:
                results = await searcher.atext(query, max_results=limit)
                # 处理并返回结果
                return f"找到 {len(results)} 条结果..."
        except Exception as e:
            return f"搜索失败: {str(e)}"
```

#### 1.2 创建 `__init__.py` 导出配置

```python
"""my_complex_skill - 我的复杂技能"""
from .my_skill import register_my_complex_skill

__all__ = ["register_my_complex_skill"]
```

#### 1.3 创建 `SKILL.md` 描述文档

```markdown
# 我的复杂技能

## 功能描述
一句话描述技能功能...

## 使用场景
### ✅ 适用场景
- 场景1
- 场景2

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | - | 查询关键词 |

## 使用示例
```python
# 示例1
my_complex_skill(query="关键词")
```

## 返回结果格式
- 结果1：xxx
- 结果2：xxx

## 异常处理
| 错误类型 | 处理方式 |
|----------|----------|
| 网络错误 | 返回友好的错误提示 |

## 注意事项
1. 注意事项1
2. 注意事项2
```

### 步骤 2：更新 skills/__init__.py

```python
from .calculator import register_calculator_tool
from .weather import register_weather_tool
from .web_search import register_web_search_tool
from .my_complex_skill import register_my_complex_skill  # 新增

__all__ = [
    "register_calculator_tool", 
    "register_weather_tool",
    "register_web_search_tool",
    "register_my_complex_skill"  # 新增
]
```

### 步骤 3：更新 mcp_server.py

```python
from skills import (
    register_calculator_tool, 
    register_weather_tool, 
    register_web_search_tool,
    register_my_complex_skill  # 新增
)

# 注册所有技能工具
register_calculator_tool(mcp)
register_weather_tool(mcp)
register_web_search_tool(mcp)
register_my_complex_skill(mcp)  # 新增
```

### 步骤 4：安装额外依赖（如需要）

如果新 skill 需要额外的 Python 包，在使用 `uv add`  导入或`requirements.txt` 中添加：

```text
uv add 包名称
或
包名称 >=版本号 #requirements.txt
```

然后运行：
```bash
uv sync
# 或
pip install 包名称
```

### 步骤 5：重启服务

重新启动服务，新技能即可使用。

### SKILL.md 规范

| 字段 | 必填 | 说明 |
|------|------|------|
| # 标题 | 是 | 技能名称 |
| ## 功能描述 | 是 | 一句话说明技能作用 |
| ## 使用场景 | 建议 | 列出适用场景 |
| ## 参数说明 | 建议 | 表格形式说明参数 |
| ## 使用示例 | 建议 | 代码和对话示例 |
| ## 返回结果格式 | 建议 | 说明返回内容结构 |
| ## 异常处理 | 建议 | 错误处理方式 |
| ## 注意事项 | 建议 | 使用注意点 |

## 示例技能

### 计算器技能
- **功能**：支持加减乘除、括号、幂运算
- **调用**：`计算 (10+5)*2`

### 天气查询技能
- **功能**：查询城市天气和预报
- **调用**：`上海天气` 或 `北京天气 3天`

### 网络搜索技能
- **功能**：使用DuckDuckGo搜索最新资讯
- **调用**：`搜索 Python最新版本` 或 `搜索 今天科技新闻`
- **依赖**：`ddgs` 库（pip install duckduckgo-search）

## 技术亮点

1. **异步处理优化** - 使用线程池执行异步函数，避免了每次请求创建新事件循环的问题
2. **对话历史持久化** - 基于 SQLite 的持久化存储，服务重启不丢失，支持多会话隔离
3. **工具调用容错** - 失败自动重试 2 次，降级到模型直接回答，提升鲁棒性
4. **MCP 工具缓存** - 减少重复初始化开销，提升响应速度
5. **流式输出实现** - 完整的 SSE 流式接口，提供更好的用户体验
6. **工具调用提示** - 清晰的工具调用提示，提升用户体验
7. **多端支持** - 同时提供 Web 界面和命令行界面
8. **技能管理系统** - 前端可视化技能管理，支持灵活开关
9. **Markdown渲染** - 完整的Markdown支持，包括代码高亮、表格等
10. **思维链展示** - 可折叠的AI推理过程展示
11. **多会话管理** - 完整的会话创建、切换、删除功能
12. **历史对话加载** - 自动加载和展示会话历史

## 注意事项

1. **API 密钥安全**：不要将 API 密钥提交到版本控制
2. **技能安全性**：避免在技能中执行危险操作
3. **性能优化**：对于耗时操作，考虑使用异步处理
4. **错误处理**：确保技能能优雅处理异常情况

## 故障排除

- **连接失败**：检查 API 密钥和网络连接
- **技能不响应**：检查 MCP 服务是否正常运行
- **前端不显示**：检查浏览器控制台是否有错误
- **流式接口问题**：确保网络连接稳定，避免中途断开
- **数据库错误**：检查 `chat_history.db` 文件权限，确保可读写

## 数据存储

项目使用 SQLite 数据库持久化对话历史：

- **数据库文件**：`chat_history.db`（项目根目录，首次运行自动生成）
- **表结构**：
  ```sql
  CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,    -- 会话ID，支持多会话隔离
    role TEXT NOT NULL,           -- 角色（user/assistant/tool）
    content TEXT NOT NULL,        -- 消息内容
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
  )
  ```
- **查询历史**：使用 SQLite 工具或命令行查看
  ```bash
  sqlite3 chat_history.db "SELECT * FROM messages ORDER BY timestamp DESC LIMIT 10;"
  ```

## 扩展建议

1. **更多技能**：添加翻译、股票查询、新闻等技能
2. **多语言支持**：添加多语言界面
3. **部署优化**：使用 Docker 容器化部署
4. **技能市场**：创建技能市场，支持用户分享和下载技能
5. **模型切换**：支持切换不同的大语言模型

## 更新日志

### 2026-03-29 重大更新

#### API 调用方式升级
- **httpx → OpenAI SDK**：所有 API 调用从 `httpx` 直接 HTTP 请求改为 `openai>=1.0.0` SDK 方式
- **配置字段重命名**：
  - `DOUBAO_API_KEY` → `OPENAI_API_KEY`
  - `DOUBAO_ENDPOINT_ID` → `OPENAI_MODEL`
  - `DOUBAO_BASE_URL` → `OPENAI_BASE_URL`（去掉了 `/chat/completions` 后缀）

#### 工具调用优化
- **Schema 清理**：自动移除 `title`、`default` 等豆包 API 不支持的字段
- **Description 清理**：压缩多余空白字符，优化格式
- **消息转换**：添加 `_msg_to_dict()` 函数，正确处理 OpenAI SDK 返回的 `ChatCompletionMessage` 对象
- **第二次调用**：修复工具调用后二次请求的消息格式问题

#### Bug 修复
- ✅ 修复 "Object of type ChatCompletionMessage is not JSON serializable" 错误
- ✅ 修复消息历史保存时的类型转换问题
- ✅ 添加详细的异常堆栈跟踪，便于调试

#### 架构改进
- 添加 `_msg_to_dict()` 辅助函数，统一消息格式转换
- 添加 API 类型检测（讯飞 API 自动跳过 tools 参数）
- 优化 `chat()` 路由的异常处理和日志输出

---
