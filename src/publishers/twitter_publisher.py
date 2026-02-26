"""Twitter/X API v2 发布器"""

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from datetime import datetime
from typing import Optional
from uuid import uuid4

import httpx

from ..config import Platform, settings
from ..models import PlatformResult, PublishRequest, PublishStatus
from .base import BasePublisher

logger = logging.getLogger(__name__)

TWITTER_API_BASE = "https://api.twitter.com/2"
TWITTER_UPLOAD_BASE = "https://upload.twitter.com/1.1"


class TwitterPublisher(BasePublisher):
    """
    Twitter/X API v2 发布器。

    使用 OAuth 1.0a 认证，支持发送推文和媒体上传。
    Free tier: 1500 posts/月
    """

    def __init__(self) -> None:
        self._api_key = settings.twitter_api_key
        self._api_secret = settings.twitter_api_secret
        self._access_token = settings.twitter_access_token
        self._access_token_secret = settings.twitter_access_token_secret

    def get_supported_platforms(self) -> list[Platform]:
        return [Platform.TWITTER]

    async def check_auth(self, platform: Platform) -> bool:
        """验证 Twitter API 凭证"""
        if not all([self._api_key, self._api_secret, self._access_token, self._access_token_secret]):
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = self._build_oauth_headers("GET", f"{TWITTER_API_BASE}/users/me")
                response = await client.get(f"{TWITTER_API_BASE}/users/me", headers=headers)
                return response.status_code == 200
        except Exception:
            return False

    async def publish(self, request: PublishRequest, platform: Platform) -> PlatformResult:
        """发送推文"""
        try:
            tweet_text = self._format_tweet(request)

            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{TWITTER_API_BASE}/tweets"
                headers = self._build_oauth_headers("POST", url)
                headers["Content-Type"] = "application/json"

                payload = {"text": tweet_text}

                response = await client.post(url, headers=headers, json=payload)
                data = response.json()

                if response.status_code in (200, 201):
                    tweet_data = data.get("data", {})
                    tweet_id = tweet_data.get("id", "")
                    return PlatformResult(
                        platform=platform,
                        status=PublishStatus.PUBLISHED,
                        post_url=f"https://twitter.com/i/status/{tweet_id}" if tweet_id else None,
                        published_at=datetime.now(),
                    )

                error_detail = data.get("detail") or data.get("title") or str(data)
                return PlatformResult(
                    platform=platform,
                    status=PublishStatus.FAILED,
                    error=f"Twitter API 错误 ({response.status_code}): {error_detail}",
                )

        except Exception as e:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"Twitter 发布异常: {e}",
            )

    def _format_tweet(self, request: PublishRequest) -> str:
        """将内容格式化为推文（≤280 字符）"""
        tags_text = " ".join(f"#{tag}" for tag in request.tags[:3]) if request.tags else ""

        max_content_len = 280 - len(request.title) - len(tags_text) - 10
        content_preview = request.content[:max_content_len].replace("\n", " ").strip()
        if len(request.content) > max_content_len:
            content_preview = content_preview[: max_content_len - 3] + "..."

        parts = [request.title, "", content_preview]
        if tags_text:
            parts.append("")
            parts.append(tags_text)

        tweet = "\n".join(parts)
        return tweet[:280]

    def _build_oauth_headers(self, method: str, url: str, params: Optional[dict] = None) -> dict:
        """构建 OAuth 1.0a 认证头"""
        oauth_params = {
            "oauth_consumer_key": self._api_key,
            "oauth_nonce": uuid4().hex,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self._access_token,
            "oauth_version": "1.0",
        }

        all_params = {**oauth_params}
        if params:
            all_params.update(params)

        sorted_params = sorted(all_params.items())
        param_string = "&".join(f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_params)

        base_string = f"{method.upper()}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(param_string, safe='')}"
        signing_key = f"{urllib.parse.quote(self._api_secret, safe='')}&{urllib.parse.quote(self._access_token_secret, safe='')}"

        signature = base64.b64encode(
            hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
        ).decode()

        oauth_params["oauth_signature"] = signature

        auth_header = "OAuth " + ", ".join(
            f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        )

        return {"Authorization": auth_header}
