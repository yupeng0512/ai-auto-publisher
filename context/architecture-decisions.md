# 架构决策记录

## ADR-001: 三层架构定位

**日期**: 2026-02-26
**状态**: 已确定

### 架构

```
Node Agent (Workflow 定时触发/生成文章)    ← 触发层
        │ MCP 调用
        ▼
ai-auto-publisher (中间层平台)             ← 管理层
        │ Bridge HTTP / 官方API / Playwright
        ▼
Wechatsync + 各平台 API (能力层)           ← 执行层
```

### 各层职责边界

| 层 | 职责 | 不做什么 |
|---|---|---|
| **Agent（触发层）** | 定时触发、内容生成、格式适配、平台选择、图片处理 | 不管发布状态、不做重试、不做落库 |
| **ai-auto-publisher（管理层）** | 接收发布请求、路由分发、并发控制、重试策略、状态追踪、数据落库、历史查询 | 不生成内容、不做格式转换 |
| **Wechatsync/API（执行层）** | 操控浏览器/调用API完成实际发布 | 不管业务逻辑 |

### 核心定位

**ai-auto-publisher 的核心价值不是"发文章"，而是"管文章的发布"**：
- 谁发了
- 发到哪
- 成功没
- 什么时候发的
- 失败了怎么重试
- 历史记录怎么查

---

## ADR-002: 推送前处理（格式/图片）放 Agent 层

**日期**: 2026-02-26
**状态**: 已确定

### 决策

推送前的格式处理和图片处理放到 **Agent 层**（Node Agent），而非中间层。

### 理由

**核心原则：所有 AI 能介入的处理能力，都应放到 Agent 层。**

1. **格式适配是 AI 擅长的事**：不同平台需要不同风格（知乎专业、小红书活泼、Twitter 简短），这是 LLM 的强项
2. **图片处理可编排为 Agent 子任务**：图片压缩/格式转换/上传图床 → MCP 工具调用
3. **中间层保持"管道"角色**：只负责透传和管理，不篡改内容
4. **Agent 层有完整上下文**：知道文章主题、目标受众、平台特性，能做更好的适配
5. **复用性**：格式适配 Agent 可被其他 Workflow 复用

### 具体分工

| 处理项 | 归属 | 原因 |
|--------|------|------|
| Markdown → 各平台格式 | Agent 层 | AI 可做智能适配 |
| 本地图片 → 图床 URL | Agent 层 | 可编排为子任务 |
| 图片压缩/裁剪 | Agent 层 | 独立工具调用 |
| 标题/标签优化 | Agent 层 | AI 擅长 |
| HTML 转义/清理 | 中间层 | 纯技术处理，无需 AI |
| 发布请求校验 | 中间层 | 必要的数据校验 |

---

## ADR-003: Bridge HTTP API vs SSE/MCP 协议

**日期**: 2026-02-26
**状态**: 已确定

### 决策

ai-auto-publisher 的 WechatsyncPublisher 直接调用 Bridge HTTP API（`POST /request`），而非 SSE/MCP 协议层。

### 理由

**核心：选择最短通信路径。**

```
方案A (SSE/MCP):  publisher → SSE Client → MCP Protocol → MCP Server → Bridge → Extension
方案B (Bridge):   publisher → HTTP POST → Bridge → Extension
```

- SSE/MCP 是为"不知道有什么工具"的 AI 设计的（工具发现），我们的代码已明确知道要调什么
- 多一层协议 = 多一个故障点 + 多一份连接维护
- Bridge HTTP API 就是标准的 `POST /request`，简单可靠

### 端口分配

| 端口 | 用途 |
|------|------|
| 9527 | WebSocket — Chrome Extension 连接 |
| 9528 | Bridge HTTP API — `POST /request` |
| 9529 | SSE — 供 Claude Code 等 AI 工具使用 |

---

## ADR-004: 全链路数据流

**日期**: 2026-02-26
**状态**: 已确定

```
1. Workflow Agent 定时触发（如每天 10:00）
2. Agent 生成/采集 Markdown 文章
3. Agent 做格式适配（不同平台版本）
4. Agent 调用 MCP publish_article → ai-auto-publisher
5. ai-auto-publisher 执行：
   a. 内容指纹计算 → 去重检查
   b. 路由到对应 Publisher（官方API / Wechatsync / Playwright）
   c. 并发调用各平台，失败自动重试（指数退避，最多 3 次）
   d. 结果落库（task_id + 各平台状态）
6. Agent 可轮询 get_publish_status 获取最终结果
7. Dashboard 展示历史发布记录和统计
```
