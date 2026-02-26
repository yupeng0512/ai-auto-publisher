# 项目 Review 发现 & 待完善清单

**日期**: 2026-02-26
**状态**: 持续更新

---

## P0 — 必须修复（核心功能缺失）

### 1. 数据库层完全未被调用

**问题**: `src/storage/database.py` 定义了完整的 CRUD 方法，但 `publisher_hub.py` 全部使用内存 dict/set 存储。进程重启后所有发布记录丢失。

**影响**: 项目核心使命"追踪发布状态"形同虚设。

**修复**:
- `publisher_hub.py` 的 `publish()` 中接入 `save_article()` + `save_publish_record()`
- `scripts/run.py` 的 `create_app()` 中调用 `init_db()`
- `get_task_status()` 从数据库查询

### 2. 去重逻辑有缺陷

**问题**: `publisher_hub.py:71-72` 去重仅打日志警告，不阻止重复发布。`_published_fingerprints` 内存集合重启后清空。

**修复**: 
- 接入 `database.is_duplicate()`
- 重复时返回已有 task_id 而非重新发布

### 3. API 无认证保护

**问题**: 所有端点零认证，任何人可发布内容到已认证平台。

**修复**: 添加 API Key 中间件（`X-API-Key` header）

---

## P1 — 应该修复（功能完善）

### 4. `--mode all` 未同时启动两个服务

**问题**: `uvicorn.run()` 阻塞，MCP Server 永远不会启动。

**修复**: 使用 `asyncio.create_task` 或 multiprocessing 并行启动。

### 5. 缺少发布历史查询 API

**需求**: `GET /api/v1/history?page=1&size=20&platform=zhihu`

### 6. 缺少手动重试 API

**需求**: `POST /api/v1/retry/{task_id}` 和 `POST /api/v1/retry/{task_id}/{platform}`

### 7. 数据库层测试和 MCP Server 测试为零

**需求**: 补充 database CRUD 测试、MCP 4 个工具测试。

---

## P2 — 建议优化（生产就绪）

### 8. 同步数据库会阻塞事件循环

**问题**: `database.py` 是同步 SQLAlchemy，上层全 async。

**修复**: 改用 `sqlalchemy[asyncio]` + `aiosqlite`。

### 9. 缺少 Dockerfile 和 docker-compose

### 10. 缺少结构化日志和 Prometheus 指标

### 11. Playwright 发布结果验证不足

**问题**: 点击发布后仅 `wait_for_timeout(3000)` 就返回成功，未验证是否真正成功。

### 12. 健康检查过于简单

**需求**: 检查数据库连接、Wechatsync Bridge 可达性、Playwright 浏览器可用性。

---

## P3 — 长期优化

### 13. 缺少 Alembic 数据库迁移
### 14. 缺少 Webhook 回调（发布完成主动通知）
### 15. 缺少平台级 Rate Limiting
### 16. TikTok/快手 Playwright 实现缺失
### 17. 数据库 Schema 缺少外键和关系定义
### 18. PublishRecord 缺少 duration_ms / publisher_method 字段

---

## 数据库 Schema 完善建议

### 现有 Schema

```
articles          - id, title, content_fingerprint, content_type, tags, created_at
publish_records   - id, task_id, article_fingerprint, platform, status, post_url, error, retries, created_at, updated_at
accounts          - id, platform, display_name, is_authenticated, last_checked_at, created_at
```

### 建议新增

| 表/字段 | 说明 |
|---------|------|
| `articles.content_preview` | 内容前 500 字，便于回溯 |
| `articles.author` | 发布者标识 |
| `publish_records.publisher_method` | 使用的发布方式 |
| `publish_records.duration_ms` | 发布耗时 |
| `publish_tasks` 表 | 任务级元数据（触发来源、触发者） |
| ForeignKey 约束 | publish_records.article_fingerprint → articles.content_fingerprint |

---

## API 完善建议

| 端点 | 方法 | 优先级 | 说明 |
|------|------|--------|------|
| `/api/v1/history` | GET | P1 | 分页查询发布历史 |
| `/api/v1/retry/{task_id}` | POST | P1 | 重试失败任务 |
| `/api/v1/retry/{task_id}/{platform}` | POST | P1 | 仅重试指定平台 |
| `/api/v1/tasks/{task_id}` | DELETE | P2 | 取消/删除任务 |
| `/api/v1/stats` | GET | P2 | 发布统计 |
| `/api/v1/articles` | GET | P2 | 文章列表 |
