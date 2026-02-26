# AI Auto Publisher API Reference

## Base URL

```
http://localhost:8000/api/v1
```

## Endpoints

### POST /publish

Publish content to multiple platforms.

**Request Body:**

```json
{
  "title": "string (required, max 200 chars)",
  "content": "string (required, Markdown format)",
  "platforms": ["string (required, min 1 item)"],
  "content_type": "article | short_post | video (default: article)",
  "tags": ["string (optional)"],
  "cover_url": "string (optional, cover image URL)",
  "draft_only": "boolean (default: false)",
  "video_path": "string (optional, for video type)"
}
```

**Response:**

```json
{
  "task_id": "string",
  "content_fingerprint": "string (MD5)",
  "results": [
    {
      "platform": "string",
      "status": "pending | processing | published | draft_saved | failed",
      "post_url": "string | null",
      "error": "string | null",
      "retries": 0,
      "published_at": "datetime | null"
    }
  ],
  "created_at": "datetime"
}
```

### GET /platforms

List all supported platforms and authentication status.

**Response:**

```json
{
  "platforms": [
    {
      "platform": "string",
      "display_name": "string",
      "publish_method": "official_api | wechatsync_mcp | playwright",
      "is_authenticated": true,
      "content_types": ["article", "video"]
    }
  ],
  "total": 17
}
```

### GET /status/{task_id}

Query publish task status.

**Response:**

```json
{
  "task_id": "string",
  "status": "pending | processing | published | failed",
  "results": [...],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### GET /health

Health check endpoint.

**Response:** `{"status": "ok", "service": "ai-auto-publisher"}`

## Platform Identifiers

```
wechat_mp, twitter, zhihu, juejin, csdn, toutiao, jianshu,
weibo, bilibili_article, wordpress, yuque, xiaohongshu,
douyin, bilibili_video, youtube, tiktok, kuaishou
```

## MCP Tools

When running in MCP mode (`--mode mcp`), the following tools are available:

| Tool | Description |
|------|-------------|
| `publish_article` | Publish content to specified platforms |
| `list_platforms` | List all platforms with auth status |
| `check_auth` | Check authentication for a specific platform |
| `get_publish_status` | Query task status by task_id |
