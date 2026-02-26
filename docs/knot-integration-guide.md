# Knot 集成指南

> 本文档说明如何将 ai-auto-publisher 与 Knot 工作流式智能体集成。

---

## 一、架构概览

```
Knot 工作流式智能体
├── 触发器: 定时 Cron / 事件驱动
├── LLM 节点: 内容生成（deepseek-v3/claude-4.5-sonnet）
├── 知识检索: RSS 数据源 / 自定义知识库
├── 条件分支: 根据内容类型选择平台
└── MCP 工具调用: ai-auto-publisher
    ├── publish_article → 多平台发布
    ├── list_platforms → 查看平台状态
    └── check_auth → 检查认证
```

---

## 二、MCP Server 接入配置

### 2.1 部署 ai-auto-publisher MCP Server

```bash
# 1. 安装依赖
cd ai-auto-publisher
pip install -e .

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入各平台凭证

# 3. 启动 API 服务（供 n8n/Dify 调用）
python scripts/run.py --mode api --port 8000

# 4. MCP Server 以 stdio 模式运行（供 Knot 调用）
python scripts/run.py --mode mcp
```

### 2.2 Knot 智能体配置 MCP Server

在 Knot 平台创建智能体时，添加 MCP Server 配置：

```json
{
  "mcpServers": {
    "ai-auto-publisher": {
      "command": "python",
      "args": ["/path/to/ai-auto-publisher/scripts/run.py", "--mode", "mcp"],
      "env": {
        "WECHAT_MP_APP_ID": "your_app_id",
        "WECHAT_MP_APP_SECRET": "your_app_secret",
        "TWITTER_API_KEY": "your_api_key"
      }
    }
  }
}
```

如果部署为 HTTP 服务（streamable-http），配置为：

```json
{
  "mcpServers": {
    "ai-auto-publisher": {
      "url": "http://<your-host>:8080/mcp",
      "transport": "streamable-http"
    }
  }
}
```

---

## 三、工作流编排示例

### 3.1 定时发布技术文章

```yaml
工作流名称: 每日技术文章自动发布
触发器: Cron 每天 09:00

节点:
  1. RSS 数据采集:
     - 从 RSS.app 获取最新技术资讯
     - 输出: 原始文章列表

  2. LLM 内容加工:
     - 模型: deepseek-v3.2
     - Prompt: "基于以下技术资讯，撰写一篇 xxx 字的技术解读文章..."
     - 输出: Markdown 文章

  3. 条件分支:
     - 如果内容类型 == "技术文章" → 发布到知乎+掘金+CSDN
     - 如果内容类型 == "短资讯" → 发布到 Twitter+微博

  4. MCP 工具调用 (publish_article):
     - title: {{step2.title}}
     - content: {{step2.content}}
     - platforms: {{step3.platforms}}
     - tags: {{step2.tags}}
```

### 3.2 多平台内容矩阵

```yaml
工作流名称: 一文多发矩阵运营
触发器: 手动触发 / AG-UI 调用

节点:
  1. 输入: 用户提供原始 Markdown 文章

  2. LLM 平台适配:
     - 生成知乎长文版（2000+ 字，专业术语）
     - 生成小红书版（500 字，emoji 丰富）
     - 生成 Twitter 版（280 字，英文摘要）

  3. 并行 MCP 调用:
     - publish_article(知乎版, ["zhihu"])
     - publish_article(小红书版, ["xiaohongshu"])
     - publish_article(Twitter 版, ["twitter"])

  4. 结果汇总: 输出各平台发布 URL
```

---

## 四、AG-UI 协议调用

通过 AG-UI 协议直接调用 Knot 智能体：

```python
import httpx

async def trigger_publish_workflow(article: dict):
    """通过 AG-UI 协议触发 Knot 发布工作流"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://knot.woa.com/apigw/api/v1/agents/agui/{agent_id}",
            headers={
                "x-knot-api-token": "your_token",
                "Content-Type": "application/json",
            },
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": f"请将以下文章发布到知乎和掘金：\n\n标题: {article['title']}\n\n{article['content']}",
                    }
                ],
            },
        )
        # 流式读取事件
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:])
                print(event)
```

---

## 五、Knot CLI 集成

使用 Knot CLI 在命令行中触发发布：

```bash
# 发布文章到知乎和掘金
knot-cli chat -a {agent_id} \
  -p "帮我把以下文章发布到知乎和掘金：$(cat article.md)" \
  -o json

# 查看平台状态
knot-cli chat -a {agent_id} \
  -p "列出所有发布平台的认证状态" \
  -o stream-json
```

---

## 六、n8n 集成

### 6.1 Webhook 触发发布

```
n8n Webhook 节点:
  URL: http://<publisher-host>:8000/api/v1/publish
  Method: POST
  Body:
    {
      "title": "{{$json.title}}",
      "content": "{{$json.content}}",
      "platforms": ["zhihu", "juejin", "csdn"],
      "tags": ["AI", "技术"]
    }
```

### 6.2 n8n 工作流示例

```
Schedule Trigger (每天 9:00)
  → RSS Feed Read (获取技术资讯)
  → AI Agent (LLM 内容加工)
  → HTTP Request (POST /api/v1/publish)
  → Slack Notification (发布结果通知)
```

---

## 七、Dify 集成

### 7.1 自定义工具导入

1. 在 Dify 中进入「工具」→「自定义」→「创建自定义工具」
2. 导入 OpenAPI Schema：`http://<publisher-host>:8000/openapi.json`
3. 配置认证（如需要）
4. 在工作流中添加「AI Auto Publisher」工具节点

### 7.2 工作流节点

```
开始 → LLM 内容生成 → AI Auto Publisher (publish) → 结束
```
