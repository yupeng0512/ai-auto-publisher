# 多平台接口参考文档

> 最后更新：2026-02-26

---

## 一、平台接口总览

| 平台 | 官方 API | 浏览器自动化 | 推荐方式 | 备注 |
|------|---------|-------------|---------|------|
| 微信公众号 | ✅ 草稿+发布接口 | ✅ Wechatsync | **官方 API** | 需认证服务号 |
| 知乎 | ✅ Draft API | ✅ Wechatsync | **Wechatsync** | 适配器已实现 |
| 掘金 | ❌ 无官方 API | ✅ Wechatsync | **Wechatsync** | 纯浏览器自动化 |
| CSDN | ❌ 无官方 API | ✅ Wechatsync | **Wechatsync** | 纯浏览器自动化 |
| 头条号 | ⚠️ 有限开放 | ✅ Wechatsync | **Wechatsync** | 适配器已实现 |
| 简书 | ❌ 无官方 API | ✅ Wechatsync | **Wechatsync** | 适配器已实现 |
| 微博 | ⚠️ 有限开放 | ✅ Wechatsync | **Wechatsync** | 适配器已实现 |
| B站专栏 | ⚠️ 有限开放 | ✅ Wechatsync | **Wechatsync** | 图文走 Wechatsync |
| 小红书 | ⚠️ 开放平台（需认证） | ✅ SAU/Playwright | **Playwright** | 笔记发布主要靠自动化 |
| 抖音 | ⚠️ 开放平台 | ✅ SAU/Playwright | **Playwright** | 审核严格，视频为主 |
| B站视频 | ⚠️ 有限开放 | ✅ SAU/Playwright | **Playwright** | 视频上传 |
| YouTube | ✅ Data API v3 | ✅ SAU | **官方 API** | 免费配额充足 |
| Twitter/X | ✅ API v2 | ✅ 可行 | **官方 API** | Free: 1500 posts/月 |
| TikTok | ⚠️ Content Posting API | ✅ SAU | **Playwright** | API 需申请 |
| 快手 | ⚠️ 有限开放 | ✅ SAU | **Playwright** | 视频为主 |
| WordPress | ✅ REST API | ✅ Wechatsync | **Wechatsync** | MetaWeblog 协议 |
| 语雀 | ✅ Open API | ✅ Wechatsync | **Wechatsync** | 适配器已实现 |

---

## 二、微信公众号 API

### 2.1 接口概述

微信公众号提供完整的图文发布 API 链路：获取 Token → 上传素材 → 创建草稿 → 发布。

> **注意**：2025年7月起，个人主体账号、企业主体未认证账号将被回收发布接口权限。仅认证服务号可用。

### 2.2 API 流程

```
1. 获取 access_token
   GET https://api.weixin.qq.com/cgi-bin/token
   ?grant_type=client_credential&appid=APPID&secret=APPSECRET

2. 上传永久素材（封面图）
   POST https://api.weixin.qq.com/cgi-bin/material/add_material
   ?access_token=ACCESS_TOKEN&type=image
   Content-Type: multipart/form-data
   Body: media=<图片文件>

3. 上传正文内插图
   POST https://api.weixin.qq.com/cgi-bin/media/uploadimg
   ?access_token=ACCESS_TOKEN
   Body: media=<图片文件>
   返回: {"url": "图片在微信服务器的URL"}

4. 创建草稿
   POST https://api.weixin.qq.com/cgi-bin/draft/add
   ?access_token=ACCESS_TOKEN
   Body: {
     "articles": [{
       "title": "标题",
       "author": "作者",
       "digest": "摘要",
       "content": "正文HTML",
       "content_source_url": "原文链接",
       "thumb_media_id": "封面图素材ID",
       "need_open_comment": 0,
       "only_fans_can_comment": 0
     }]
   }
   返回: {"media_id": "草稿的media_id"}

5. 发布草稿
   POST https://api.weixin.qq.com/cgi-bin/freepublish/submit
   ?access_token=ACCESS_TOKEN
   Body: {"media_id": "草稿的media_id"}
   返回: {"publish_id": "发布任务ID"}

6. 查询发布状态
   POST https://api.weixin.qq.com/cgi-bin/freepublish/get
   ?access_token=ACCESS_TOKEN
   Body: {"publish_id": "发布任务ID"}
```

### 2.3 关键限制

| 项目 | 限制 |
|------|------|
| access_token 有效期 | 2 小时，需缓存 + 自动刷新 |
| 每日群发次数 | 认证服务号：无限制（freepublish）|
| 素材大小 | 图片 ≤ 10MB，图文正文 ≤ 2MB |
| 标题长度 | ≤ 64 字符 |
| 正文图片 | 需通过 uploadimg 接口上传到微信服务器 |

---

## 三、Twitter/X API v2

### 3.1 接口概述

Twitter API v2 提供完整的推文发布能力。

### 3.2 API 流程

```
1. 发布推文
   POST https://api.twitter.com/2/tweets
   Authorization: Bearer <ACCESS_TOKEN>  (OAuth 2.0)
   或 OAuth 1.0a (Consumer Key + Access Token)
   Content-Type: application/json
   Body: {
     "text": "推文内容",
     "media": {"media_ids": ["媒体ID"]},
     "reply": {"in_reply_to_tweet_id": "回复的推文ID"}
   }

2. 上传媒体
   POST https://upload.twitter.com/1.1/media/upload.json
   Content-Type: multipart/form-data
   Body: media=<文件>
```

### 3.3 定价与配额

| 层级 | 价格 | 推文配额 | 读取配额 |
|------|------|---------|---------|
| Free | $0 | 1,500 posts/月 | 无 |
| Basic | $100/月 | 3,000 posts/月 | 10,000 reads/月 |
| Pro | $5,000/月 | 300,000 posts/月 | 1,000,000 reads/月 |

### 3.4 认证方式

- **OAuth 2.0 User Context**：代表用户操作（推荐）
- **OAuth 2.0 App-Only**：仅读取操作
- **OAuth 1.0a**：传统方式，部分端点仍需要

---

## 四、小红书

### 4.1 官方 API

小红书开放平台 (`open.xiaohongshu.com`) 提供内容发布 API，但需要：
1. 注册开发者账号 + 企业认证
2. 创建应用 + 审核
3. 申请「内容发布」API 权限

**现状**：API 审核严格，主要面向品牌商家和 MCN 机构，个人开发者难以获取发布权限。

### 4.2 推荐方案：Playwright 浏览器自动化

基于 Social-Auto-Upload 的方案：

```python
# 核心流程
1. 启动 Chromium（使用持久化 Cookie 保持登录态）
2. 导航到 https://creator.xiaohongshu.com/publish/publish
3. 上传图片/视频
4. 填写标题、正文、标签
5. 选择发布时间
6. 点击发布
```

**关键注意事项**：
- 随机延迟（2-5s）模拟人工操作
- Cookie 持久化管理，避免频繁登录
- 发布频率控制（建议 ≤ 5 篇/天）
- 内容需符合社区规范

---

## 五、抖音

### 5.1 官方 API

抖音开放平台 (`open.douyin.com`) 提供视频发布 API：

```
1. OAuth 2.0 授权
   GET https://open.douyin.com/platform/oauth/connect/
   ?client_key=APP_ID&response_type=code&scope=video.create&redirect_uri=...

2. 获取 AccessToken
   POST https://open.douyin.com/oauth/access_token/
   Body: {client_key, client_secret, code, grant_type: "authorization_code"}

3. 创建视频（上传方式）
   POST https://open.douyin.com/api/douyin/v1/video/upload_video/
   Authorization: Bearer ACCESS_TOKEN
   Content-Type: multipart/form-data
   Body: video=<视频文件>

4. 发布视频
   POST https://open.douyin.com/api/douyin/v1/video/create_video/
   Body: {video_id, text: "视频描述", ...}
```

**审核要求**：需企业认证 + 应用审核 + 接口权限申请，个人开发者门槛较高。

### 5.2 推荐方案：Playwright 浏览器自动化

与小红书类似，使用 SAU 的 Playwright 方案：

```python
# 核心流程
1. 启动 Chromium（持久化 Cookie）
2. 导航到抖音创作者中心
3. 上传视频文件
4. 填写标题、描述、标签
5. 设置封面
6. 点击发布
```

---

## 六、YouTube Data API v3

### 6.1 接口概述

YouTube 提供成熟的视频上传 API，配额相对充足。

### 6.2 API 流程

```
1. OAuth 2.0 授权
   范围: https://www.googleapis.com/auth/youtube.upload

2. 上传视频（分段上传）
   POST https://www.googleapis.com/upload/youtube/v3/videos
   ?uploadType=resumable&part=snippet,status
   Authorization: Bearer ACCESS_TOKEN
   Body: {
     "snippet": {
       "title": "视频标题",
       "description": "视频描述",
       "tags": ["标签1", "标签2"],
       "categoryId": "22"
     },
     "status": {
       "privacyStatus": "public",
       "selfDeclaredMadeForKids": false
     }
   }
```

### 6.3 配额

| 项目 | 限制 |
|------|------|
| 每日配额 | 10,000 units（1 次上传 = 1,600 units）|
| 每日上传 | ~6 个视频 |
| 视频大小 | ≤ 256GB |
| 视频时长 | ≤ 12 小时 |

---

## 七、B站

### 7.1 现状

B站开放平台主要面向游戏和直播场景，视频上传 API 不对外开放。

### 7.2 推荐方案

- **图文专栏**：通过 Wechatsync 浏览器自动化
- **视频上传**：通过 SAU Playwright 自动化

---

## 八、Wechatsync MCP 接口

### 8.1 MCP 工具列表

```json
{
  "tools": [
    {
      "name": "list_platforms",
      "description": "列出所有支持的平台及其登录状态",
      "params": {}
    },
    {
      "name": "sync_article",
      "description": "同步文章到指定平台",
      "params": {
        "title": "string - 文章标题",
        "markdown": "string - Markdown 格式正文",
        "platforms": "string[] - 目标平台列表"
      }
    }
  ]
}
```

### 8.2 通信链路

```
本项目 MCP Client ←--stdio/ws--→ Wechatsync MCP Server ←--WebSocket--→ Chrome Extension
```

### 8.3 并行控制

- `CONCURRENCY_LIMIT = 3`（最多同时 3 个平台）
- 指数退避重试（base=1s, max=32s）
- AbortController 支持任务取消

---

## 九、发布策略建议

### 9.1 平台优先级矩阵

| 优先级 | 平台 | 理由 |
|--------|------|------|
| P0 | 微信公众号 | 官方 API 稳定，国内第一内容平台 |
| P0 | 知乎 | Wechatsync 适配器成熟，技术内容首选 |
| P0 | 掘金 | Wechatsync 适配器成熟，开发者社区 |
| P1 | Twitter/X | 官方 API，国际影响力 |
| P1 | 小红书 | Playwright 自动化，年轻用户群 |
| P1 | CSDN | Wechatsync 适配器成熟，搜索权重高 |
| P2 | 抖音 | Playwright 自动化，视频内容 |
| P2 | YouTube | 官方 API，视频内容国际化 |
| P2 | B站 | Playwright 自动化，年轻用户 |

### 9.2 内容格式转换策略

```
输入：Markdown

→ 微信公众号：Markdown → HTML（需替换图片 URL 为微信服务器 URL）
→ 知乎：Markdown → Draft.js JSON（Wechatsync 自动处理）
→ 掘金/CSDN：Markdown 直接发布（原生支持）
→ Twitter：Markdown → 纯文本摘要（≤ 280 字符）
→ 小红书：Markdown → 纯文本 + 图片（笔记格式）
```
