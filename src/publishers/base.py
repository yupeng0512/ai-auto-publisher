"""BasePublisher 抽象基类 - 所有平台适配器的基础"""

import asyncio
import logging
from abc import ABC, abstractmethod

from ..config import Platform
from ..models import PlatformResult, PublishRequest, PublishStatus

logger = logging.getLogger(__name__)


class BasePublisher(ABC):
    """
    平台发布器抽象基类。

    所有平台适配器需实现:
    - publish(): 执行实际发布
    - check_auth(): 检查认证状态
    - get_supported_platforms(): 返回支持的平台列表
    """

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0  # 秒
    MAX_RETRY_DELAY = 32.0  # 秒

    @abstractmethod
    async def publish(self, request: PublishRequest, platform: Platform) -> PlatformResult:
        """
        执行发布操作。

        Args:
            request: 发布请求
            platform: 目标平台

        Returns:
            PlatformResult: 发布结果
        """
        ...

    @abstractmethod
    async def check_auth(self, platform: Platform) -> bool:
        """
        检查指定平台的认证状态。

        Args:
            platform: 目标平台

        Returns:
            bool: 是否已认证
        """
        ...

    @abstractmethod
    def get_supported_platforms(self) -> list[Platform]:
        """返回此发布器支持的平台列表"""
        ...

    async def publish_with_retry(self, request: PublishRequest, platform: Platform) -> PlatformResult:
        """
        带指数退避重试的发布方法。

        重试策略: delay = min(base * 2^attempt, max_delay)
        """
        last_error: str | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                result = await self.publish(request, platform)
                if result.status in (PublishStatus.PUBLISHED, PublishStatus.DRAFT_SAVED):
                    result.retries = attempt
                    return result
                last_error = result.error
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "发布失败 [%s] 平台=%s 尝试=%d/%d 错误=%s",
                    request.title[:30],
                    platform.value,
                    attempt + 1,
                    self.MAX_RETRIES + 1,
                    last_error,
                )

            if attempt < self.MAX_RETRIES:
                delay = min(self.BASE_RETRY_DELAY * (2**attempt), self.MAX_RETRY_DELAY)
                logger.info("等待 %.1f 秒后重试...", delay)
                await asyncio.sleep(delay)

        return PlatformResult(
            platform=platform,
            status=PublishStatus.FAILED,
            error=f"达到最大重试次数({self.MAX_RETRIES}): {last_error}",
            retries=self.MAX_RETRIES,
        )
