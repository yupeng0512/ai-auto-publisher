"""微信公众号 API 发布器 - 通过官方 API 草稿+发布"""

import logging
import time
from datetime import datetime
from typing import Optional

import httpx
import markdown

from ..config import Platform, settings
from ..models import PlatformResult, PublishRequest, PublishStatus
from .base import BasePublisher

logger = logging.getLogger(__name__)

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"


class WechatMPPublisher(BasePublisher):
    """
    微信公众号官方 API 发布器。

    流程: 获取 access_token → Markdown 转 HTML → 创建草稿 → 发布草稿
    注意: 仅认证服务号可用（2025.7 起个人号权限回收）
    """

    def __init__(self) -> None:
        self._app_id = settings.wechat_mp_app_id
        self._app_secret = settings.wechat_mp_app_secret
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def get_supported_platforms(self) -> list[Platform]:
        return [Platform.WECHAT_MP]

    async def check_auth(self, platform: Platform) -> bool:
        """检查微信公众号 API 认证状态"""
        if not self._app_id or not self._app_secret:
            return False
        try:
            token = await self._get_access_token()
            return token is not None
        except Exception:
            return False

    async def publish(self, request: PublishRequest, platform: Platform) -> PlatformResult:
        """发布文章到微信公众号"""
        try:
            token = await self._get_access_token()
            if not token:
                return PlatformResult(
                    platform=platform,
                    status=PublishStatus.FAILED,
                    error="获取 access_token 失败，请检查 AppID/AppSecret 配置",
                )

            html_content = self._markdown_to_html(request.content)

            media_id = await self._create_draft(
                token=token,
                title=request.title,
                content=html_content,
                digest=request.content[:120].replace("\n", " "),
            )

            if not media_id:
                return PlatformResult(
                    platform=platform,
                    status=PublishStatus.FAILED,
                    error="创建草稿失败",
                )

            if request.draft_only:
                return PlatformResult(
                    platform=platform,
                    status=PublishStatus.DRAFT_SAVED,
                    published_at=datetime.now(),
                )

            publish_id = await self._submit_publish(token, media_id)
            if publish_id:
                return PlatformResult(
                    platform=platform,
                    status=PublishStatus.PUBLISHED,
                    published_at=datetime.now(),
                )

            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error="发布草稿失败",
            )

        except Exception as e:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"微信公众号发布异常: {e}",
            )

    async def _get_access_token(self) -> Optional[str]:
        """获取 access_token，带缓存（2h 有效期）"""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{WECHAT_API_BASE}/token",
                params={
                    "grant_type": "client_credential",
                    "appid": self._app_id,
                    "secret": self._app_secret,
                },
            )
            data = response.json()

            if "access_token" in data:
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data.get("expires_in", 7200) - 300
                return self._access_token

            logger.error("获取 access_token 失败: %s", data.get("errmsg", "unknown"))
            return None

    async def _create_draft(
        self,
        token: str,
        title: str,
        content: str,
        digest: str,
    ) -> Optional[str]:
        """创建草稿，返回 media_id"""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{WECHAT_API_BASE}/draft/add",
                params={"access_token": token},
                json={
                    "articles": [
                        {
                            "title": title,
                            "content": content,
                            "digest": digest,
                            "need_open_comment": 0,
                            "only_fans_can_comment": 0,
                        }
                    ]
                },
            )
            data = response.json()

            if "media_id" in data:
                logger.info("草稿创建成功: media_id=%s", data["media_id"])
                return data["media_id"]

            logger.error("创建草稿失败: %s", data.get("errmsg", "unknown"))
            return None

    async def _submit_publish(self, token: str, media_id: str) -> Optional[str]:
        """提交发布，返回 publish_id"""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{WECHAT_API_BASE}/freepublish/submit",
                params={"access_token": token},
                json={"media_id": media_id},
            )
            data = response.json()

            if "publish_id" in data:
                logger.info("发布提交成功: publish_id=%s", data["publish_id"])
                return data["publish_id"]

            logger.error("发布提交失败: %s", data.get("errmsg", "unknown"))
            return None

    @staticmethod
    def _markdown_to_html(md_content: str) -> str:
        """Markdown 转 HTML（微信公众号正文格式）"""
        return markdown.markdown(
            md_content,
            extensions=["tables", "fenced_code", "codehilite"],
        )
