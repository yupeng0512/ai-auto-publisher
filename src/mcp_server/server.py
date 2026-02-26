"""MCP Server 实现 - streamable-http 传输，供 Knot 智能体调用"""

import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ..config import Platform
from ..models import PublishRequest
from ..publisher_hub import publisher_hub

logger = logging.getLogger(__name__)

# 创建 MCP Server 实例
mcp_server = Server("ai-auto-publisher")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """注册 MCP 工具"""
    return [
        Tool(
            name="publish_article",
            description="发布文章/内容到指定平台。支持 Markdown 格式输入，自动转换各平台格式。",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "文章标题",
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown 格式的文章正文",
                    },
                    "platforms": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [p.value for p in Platform],
                        },
                        "description": "目标平台列表，如 ['zhihu', 'juejin', 'wechat_mp']",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签列表（可选）",
                        "default": [],
                    },
                    "draft_only": {
                        "type": "boolean",
                        "description": "是否仅保存为草稿（可选，默认 false）",
                        "default": False,
                    },
                },
                "required": ["title", "content", "platforms"],
            },
        ),
        Tool(
            name="list_platforms",
            description="列出所有支持的发布平台及其登录状态。返回平台名称、发布方式、认证状态等信息。",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="check_auth",
            description="检查指定平台的认证/登录状态。",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": [p.value for p in Platform],
                        "description": "要检查的平台标识",
                    },
                },
                "required": ["platform"],
            },
        ),
        Tool(
            name="get_publish_status",
            description="查询发布任务的状态和结果。",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "发布任务 ID",
                    },
                },
                "required": ["task_id"],
            },
        ),
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理 MCP 工具调用"""

    if name == "publish_article":
        return await _handle_publish(arguments)
    elif name == "list_platforms":
        return await _handle_list_platforms()
    elif name == "check_auth":
        return await _handle_check_auth(arguments)
    elif name == "get_publish_status":
        return await _handle_get_status(arguments)
    else:
        return [TextContent(type="text", text=f"未知工具: {name}")]


async def _handle_publish(args: dict) -> list[TextContent]:
    """处理 publish_article 工具调用"""
    try:
        platforms = [Platform(p) for p in args["platforms"]]
        request = PublishRequest(
            title=args["title"],
            content=args["content"],
            platforms=platforms,
            tags=args.get("tags", []),
            draft_only=args.get("draft_only", False),
        )

        response = await publisher_hub.publish(request)

        results_text = []
        for r in response.results:
            status_emoji = "✅" if r.status.value == "published" else "📝" if r.status.value == "draft_saved" else "❌"
            line = f"{status_emoji} {r.platform.value}: {r.status.value}"
            if r.post_url:
                line += f" ({r.post_url})"
            if r.error:
                line += f" - {r.error}"
            results_text.append(line)

        summary = f"发布任务 {response.task_id} 完成:\n" + "\n".join(results_text)
        return [TextContent(type="text", text=summary)]

    except Exception as e:
        return [TextContent(type="text", text=f"发布失败: {e}")]


async def _handle_list_platforms() -> list[TextContent]:
    """处理 list_platforms 工具调用"""
    try:
        platforms_response = await publisher_hub.get_platforms()
        lines = [f"支持 {platforms_response.total} 个平台:\n"]

        for p in platforms_response.platforms:
            auth_status = "✅ 已认证" if p.is_authenticated else "❌ 未认证"
            types = ", ".join(ct.value for ct in p.content_types)
            lines.append(f"- {p.display_name} ({p.platform.value}): {auth_status} | 方式: {p.publish_method} | 类型: {types}")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"获取平台列表失败: {e}")]


async def _handle_check_auth(args: dict) -> list[TextContent]:
    """处理 check_auth 工具调用"""
    try:
        platform = Platform(args["platform"])
        platforms_response = await publisher_hub.get_platforms()

        for p in platforms_response.platforms:
            if p.platform == platform:
                status = "已认证 ✅" if p.is_authenticated else "未认证 ❌"
                return [TextContent(type="text", text=f"{p.display_name}: {status}")]

        return [TextContent(type="text", text=f"未找到平台: {args['platform']}")]

    except Exception as e:
        return [TextContent(type="text", text=f"检查认证失败: {e}")]


async def _handle_get_status(args: dict) -> list[TextContent]:
    """处理 get_publish_status 工具调用"""
    try:
        task_id = args["task_id"]
        status = await publisher_hub.get_task_status(task_id)

        if not status:
            return [TextContent(type="text", text=f"任务不存在: {task_id}")]

        result_data = {
            "task_id": status.task_id,
            "status": status.status.value,
            "results": [
                {
                    "platform": r.platform.value,
                    "status": r.status.value,
                    "post_url": r.post_url,
                    "error": r.error,
                }
                for r in status.results
            ],
        }

        return [TextContent(type="text", text=json.dumps(result_data, ensure_ascii=False, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"查询状态失败: {e}")]


async def run_mcp_server():
    """以 stdio 模式运行 MCP Server"""
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())
