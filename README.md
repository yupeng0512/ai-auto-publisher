# AI Auto Publisher

> 一句话 Markdown 进，17 个平台出。AI 内容工作流的最后一公里。

AI Auto Publisher 是一个轻量级多平台发布中间件，接收 Markdown 内容，自动分发到知乎、掘金、CSDN、微信公众号、Twitter/X 等 17 个平台，并持久化追踪每一条发布记录的状态。

## 核心能力

- **一文多发** — 一次请求，并发推送到多个平台（最大并发 3）
- **三种发布通道** — Wechatsync Bridge（9 个图文平台）/ 官方 API（微信公众号、Twitter）/ Playwright 浏览器自动化（小红书、抖音等 6 个平台）
- **数据库级去重** — 相同内容不会重复发布，自动返回已有记录
- **全量状态追踪** — 每次发布落库，支持分页查询历史、失败重试
- **双协议接入** — REST API + MCP Server（stdio），Agent / Workflow / HTTP 客户端均可调用

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # 编辑填入平台凭证
python scripts/run.py --mode api
```

API 文档：http://localhost:8000/docs

## API 速览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/publish` | POST | 发布内容到多平台 |
| `/api/v1/platforms` | GET | 平台列表及认证状态 |
| `/api/v1/status/{task_id}` | GET | 查询任务状态 |
| `/api/v1/history` | GET | 分页查询发布历史（支持平台/状态过滤） |
| `/api/v1/retry/{task_id}` | POST | 重试失败的任务 |
| `/api/v1/health` | GET | 健康检查 |

## 架构定位

```
Workflow Agent（定时触发 + 生成内容）
    │ MCP / REST API
    ▼
AI Auto Publisher（本项目 — 编排 / 去重 / 落库 / 追踪）
    │ Bridge HTTP / 官方 API / Playwright
    ▼
Wechatsync + 各平台 API（最后一公里发布）
```

## 支持的平台（17 个）

**Wechatsync Bridge**: 知乎、掘金、CSDN、头条号、简书、微博、B站专栏、WordPress、语雀

**官方 API**: 微信公众号、Twitter/X

**Playwright**: 小红书、抖音、B站视频、YouTube、TikTok、快手

## 运行测试

```bash
pytest tests/ -v
```

## License

MIT
