---
name: ai-auto-publisher
description: 多平台内容发布中间件。接收 Markdown 文章或视频，自动分发到 16+ 个平台（公众号、知乎、掘金、小红书、抖音等），并追踪发布状态。当用户需要发布、同步、分发内容到多个平台时使用。
---

# AI Auto Publisher

多平台内容发布中间件 — 接收 Markdown 文章或视频内容，自动分发到 16+ 个平台，追踪发布进度与状态。

## 架构定位

```
Node Agent (Workflow 定时触发/生成文章)
        │ MCP 工具调用
        ▼
ai-auto-publisher (中间层平台)
  ├── 接收文章 (MCP Server / REST API)
  ├── 推送前处理 (格式转换/图片处理)
  ├── 分发到各 Publisher (路由/并发/重试)
  ├── 数据落库 (发布记录/进度/成败)
  └── Dashboard 展示 (发布历史/统计)
        │
        ├── 官方 API → 微信公众号、Twitter
        ├── Wechatsync Bridge → 知乎、掘金、CSDN 等 9+ 图文平台
        └── Playwright → 小红书、抖音、B站视频 等 6 个视频平台
```

## 前置条件

1. Python 3.12+
2. 安装项目：`cd ai-auto-publisher && pip install -e ".[dev]"`
3. 复制配置：`cp .env.example .env`，按需填写各平台凭证
4. Wechatsync 图文平台需要：Chrome Extension 运行 + MCP Server 启动
5. Playwright 视频平台需要：`playwright install chromium`

## 启动服务

```bash
# 仅启动 REST API（供 n8n/Dify/HTTP 调用）
python scripts/run.py --mode api

# 仅启动 MCP Server（供 AI Agent stdio 调用）
python scripts/run.py --mode mcp

# 同时启动两者
python scripts/run.py --mode all
```

## MCP 工具（4 个）

### publish_article — 发布文章到多平台

```json
{
  "name": "publish_article",
  "arguments": {
    "title": "文章标题",
    "content": "Markdown 格式正文",
    "platforms": ["zhihu", "juejin", "wechat_mp"],
    "tags": ["AI", "技术"],
    "draft_only": false
  }
}
```

**必需参数**：`title`、`content`、`platforms`
**可选参数**：`tags`（标签列表）、`draft_only`（仅保存草稿）

**返回示例**：
```
发布任务 task-abc123 完成:
✅ zhihu: published (https://zhuanlan.zhihu.com/p/xxx)
✅ juejin: published (https://juejin.cn/post/xxx)
📝 wechat_mp: draft_saved
```

### list_platforms — 查看所有平台及登录状态

```json
{ "name": "list_platforms", "arguments": {} }
```

### check_auth — 检查单个平台认证状态

```json
{ "name": "check_auth", "arguments": { "platform": "zhihu" } }
```

### get_publish_status — 查询任务进度

```json
{ "name": "get_publish_status", "arguments": { "task_id": "task-abc123" } }
```

## REST API（供 n8n/Dify/HTTP 调用）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/publish` | 发布内容到多平台 |
| GET | `/api/v1/platforms` | 获取平台列表及认证状态 |
| GET | `/api/v1/status/{task_id}` | 查询发布任务状态 |
| GET | `/api/v1/health` | 健康检查 |

**API 文档**：启动后访问 `http://localhost:8000/docs`

## 支持的平台（16 个）

| 平台 | 标识 | 发布方式 | 内容类型 |
|------|------|----------|----------|
| 微信公众号 | `wechat_mp` | 官方 API | 图文 |
| Twitter/X | `twitter` | 官方 API | 短文 |
| 知乎 | `zhihu` | Wechatsync | 图文 |
| 掘金 | `juejin` | Wechatsync | 图文 |
| CSDN | `csdn` | Wechatsync | 图文 |
| 头条号 | `toutiao` | Wechatsync | 图文 |
| 简书 | `jianshu` | Wechatsync | 图文 |
| 微博 | `weibo` | Wechatsync | 图文 |
| B站专栏 | `bilibili_article` | Wechatsync | 图文 |
| WordPress | `wordpress` | Wechatsync | 图文 |
| 语雀 | `yuque` | Wechatsync | 图文 |
| 小红书 | `xiaohongshu` | Playwright | 视频/图文 |
| 抖音 | `douyin` | Playwright | 视频 |
| B站视频 | `bilibili_video` | Playwright | 视频 |
| YouTube | `youtube` | Playwright | 视频 |
| TikTok | `tiktok` | Playwright | 视频 |
| 快手 | `kuaishou` | Playwright | 视频 |

## 数据持久化

- SQLite 数据库：`data/publisher.db`
- 三张表：`articles`（文章+指纹去重）、`publish_records`（发布记录）、`accounts`（账号状态）
- 内容指纹：标题+内容前 500 字 MD5，自动去重避免重复发布

## 用户意图 → 操作映射

| 用户说 | 操作 |
|--------|------|
| "把这篇文章发到知乎和掘金" | 调用 `publish_article`，platforms=["zhihu","juejin"] |
| "帮我看看哪些平台已经登录了" | 调用 `list_platforms` |
| "检查一下公众号认证状态" | 调用 `check_auth`，platform="wechat_mp" |
| "刚才那个发布任务进展如何" | 调用 `get_publish_status`，传入 task_id |
| "把文章同步到所有图文平台" | 调用 `publish_article`，platforms=["zhihu","juejin","csdn","toutiao","jianshu","weibo","bilibili_article","wordpress","yuque"] |
| "先存草稿不要直接发" | 调用 `publish_article`，draft_only=true |
| "把这个视频发到抖音和小红书" | 调用 `publish_article`，platforms=["douyin","xiaohongshu"]，需附 video_path |

## 全链路流程

```
1. Workflow Agent 定时触发（如每天 10:00）
2. Agent 生成/采集 Markdown 文章
3. Agent 调用 MCP publish_article → ai-auto-publisher
4. ai-auto-publisher 执行：
   a. 内容指纹计算 → 去重检查
   b. 路由到对应 Publisher（官方API / Wechatsync / Playwright）
   c. 并发调用各平台，失败自动重试（指数退避，最多 3 次）
   d. 结果落库（task_id + 各平台状态）
5. Agent 可轮询 get_publish_status 获取最终结果
6. Dashboard 展示历史发布记录和统计
```

## 故障排查

| 问题 | 排查 |
|------|------|
| Wechatsync 平台发布失败 | 检查 Chrome Extension 是否运行 + 该平台是否已登录 |
| "请求超时" | Wechatsync Bridge 可能未启动，执行 `curl http://localhost:9528/health` |
| 内容指纹重复 | 同标题+相同内容前 500 字会被视为重复，修改内容即可 |
| Playwright 平台失败 | 检查 `data/cookies/` 下对应平台 Cookie 是否过期 |
