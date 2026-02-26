---
name: ai-auto-publisher
description: >
  This skill enables multi-platform content publishing through a lightweight middleware.
  It should be used when the user wants to publish articles, short posts, or videos
  to platforms like WeChat, Zhihu, Juejin, CSDN, Twitter, Xiaohongshu, Douyin, YouTube, etc.
  This skill handles platform routing, format conversion, and concurrent publishing
  through a unified API. It integrates with Wechatsync MCP for 20+ article platforms,
  official APIs for WeChat MP and Twitter, and Playwright for video platforms.
---

# AI Auto Publisher Skill

## Overview

This skill provides multi-platform content publishing capabilities through the `ai-auto-publisher` middleware service. It transforms a single Markdown input into platform-specific formats and publishes to multiple platforms concurrently.

## When to Use

- When publishing articles to multiple platforms simultaneously (Zhihu, Juejin, CSDN, WeChat MP, etc.)
- When posting short content to Twitter or Weibo
- When uploading videos to Douyin, Xiaohongshu, Bilibili, or YouTube
- When checking platform authentication status
- When querying publish task results

## Architecture

```
User Request → AI Auto Publisher API → Platform Adapters → Target Platforms
                    ↓
            ┌───────┼───────┐
            ↓       ↓       ↓
      Wechatsync  Official  Playwright
       (20+ 图文)   API    (视频平台)
```

## Usage

### Prerequisites

Ensure the ai-auto-publisher service is running:

```bash
cd /Users/yupeng/ai-auto-publisher
source .venv/bin/activate
python scripts/run.py --mode api --port 8000
```

### Publishing Content

To publish an article to multiple platforms, send a POST request to the API:

```bash
curl -X POST http://localhost:8000/api/v1/publish \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Article Title",
    "content": "# Markdown Content\n\nYour article here...",
    "platforms": ["zhihu", "juejin", "csdn"],
    "tags": ["AI", "tech"]
  }'
```

### Checking Platform Status

To list all platforms and their auth status:

```bash
curl http://localhost:8000/api/v1/platforms
```

### Querying Task Status

After publishing, query the result using the returned task_id:

```bash
curl http://localhost:8000/api/v1/status/{task_id}
```

### Available Platforms

| Platform ID | Name | Method | Content Type |
|------------|------|--------|-------------|
| wechat_mp | 微信公众号 | Official API | article |
| zhihu | 知乎 | Wechatsync MCP | article |
| juejin | 掘金 | Wechatsync MCP | article |
| csdn | CSDN | Wechatsync MCP | article |
| twitter | Twitter/X | Official API | short_post |
| xiaohongshu | 小红书 | Playwright | article/video |
| douyin | 抖音 | Playwright | video |
| bilibili_video | B站视频 | Playwright | video |
| youtube | YouTube | Playwright | video |

### MCP Server Mode

For integration with Knot or Claude Code, run in MCP mode:

```bash
python scripts/run.py --mode mcp
```

This exposes MCP tools: `publish_article`, `list_platforms`, `check_auth`, `get_publish_status`.

## Bundled Resources

- `references/api_reference.md` — Detailed API endpoint documentation and request/response schemas
