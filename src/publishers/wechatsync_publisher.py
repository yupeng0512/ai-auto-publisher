"""Wechatsync MCP 发布器 - 通过 Bridge HTTP API 调用 Chrome Extension 实现 20+ 图文平台同步"""

import json
import logging
import re
from datetime import datetime

import httpx

from ..config import Platform, WECHATSYNC_PLATFORM_MAP, settings
from ..models import PlatformResult, PublishRequest, PublishStatus
from .base import BasePublisher

logger = logging.getLogger(__name__)

# Bridge HTTP API 端口 = WebSocket 端口 + 1，默认 9528
BRIDGE_HTTP_URL = "http://localhost:9528"


class WechatsyncPublisher(BasePublisher):
    """
    Wechatsync 发布器。

    通过 Bridge HTTP API（POST /request）直接与 Chrome Extension 通讯，
    实现知乎、掘金、CSDN、头条号等 20+ 图文平台的一键同步。

    架构：
      ai-auto-publisher → Bridge HTTP API (9528) → WebSocket → Chrome Extension → 各平台 API
    """

    def __init__(self) -> None:
        self._bridge_url = BRIDGE_HTTP_URL

    def get_supported_platforms(self) -> list[Platform]:
        return list(WECHATSYNC_PLATFORM_MAP.keys())

    async def _bridge_request(self, method: str, params: dict | None = None, timeout: float = 60) -> dict:
        """向 Bridge HTTP API 发送请求"""
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self._bridge_url}/request",
                json={"method": method, "params": params or {}},
            )
            data = response.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data.get("result", {})

    async def check_auth(self, platform: Platform) -> bool:
        """通过 Bridge 的 listPlatforms 检查登录状态"""
        try:
            platforms_data = await self._bridge_request("listPlatforms", {"forceRefresh": True}, timeout=15)
            ws_name = WECHATSYNC_PLATFORM_MAP.get(platform, "")
            if isinstance(platforms_data, list):
                for p in platforms_data:
                    if p.get("id") == ws_name or p.get("name") == ws_name:
                        return p.get("isAuthenticated", False)
        except Exception as e:
            logger.warning("检查 Wechatsync 认证状态失败: %s", e)
        return False

    async def publish(self, request: PublishRequest, platform: Platform) -> PlatformResult:
        """通过 Bridge 的 syncArticle 发布文章"""
        ws_platform = WECHATSYNC_PLATFORM_MAP.get(platform)
        if not ws_platform:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"平台 {platform.value} 不在 Wechatsync 支持列表中",
            )

        try:
            result = await self._bridge_request(
                "syncArticle",
                {
                    "platforms": [ws_platform],
                    "article": {
                        "title": request.title,
                        "markdown": request.content,
                        "content": request.content,
                    },
                },
                timeout=120,
            )

            # 解析同步结果
            results = result.get("results", []) if isinstance(result, dict) else result
            if isinstance(results, list):
                for r in results:
                    if r.get("success"):
                        return PlatformResult(
                            platform=platform,
                            status=PublishStatus.PUBLISHED,
                            post_url=r.get("postUrl"),
                            published_at=datetime.now(),
                        )
                    else:
                        return PlatformResult(
                            platform=platform,
                            status=PublishStatus.FAILED,
                            error=r.get("error", "同步失败"),
                        )

            # 兜底：尝试从文本结果中判断
            result_str = json.dumps(result) if isinstance(result, dict) else str(result)
            if "success" in result_str.lower():
                return PlatformResult(
                    platform=platform,
                    status=PublishStatus.PUBLISHED,
                    post_url=self._extract_url(result_str),
                    published_at=datetime.now(),
                )

            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"Wechatsync 返回未知结果: {result_str[:200]}",
            )

        except httpx.TimeoutException:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error="Wechatsync 请求超时（120s）",
            )
        except Exception as e:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"Wechatsync 发布异常: {e}",
            )

    @staticmethod
    def _extract_url(text: str) -> str | None:
        """从响应文本中提取文章 URL"""
        match = re.search(r"https?://[^\s\)\"']+", text)
        return match.group(0) if match else None
