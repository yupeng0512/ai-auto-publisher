"""PublisherHub - 发布调度中心"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from .config import PLATFORM_METHOD_MAP, ContentType, Platform, PublishMethod
from .models import (
    PLATFORM_DISPLAY_NAMES,
    PlatformInfo,
    PlatformListResponse,
    PlatformResult,
    PublishRequest,
    PublishResponse,
    PublishStatus,
    TaskStatusResponse,
)
from .publishers.base import BasePublisher
from .publishers.playwright_publisher import PlaywrightPublisher
from .publishers.twitter_publisher import TwitterPublisher
from .publishers.wechat_mp_publisher import WechatMPPublisher
from .publishers.wechatsync_publisher import WechatsyncPublisher
from .storage.database import (
    get_publish_records,
    get_session,
    is_duplicate,
    save_article,
    save_publish_record,
    update_publish_record_status,
    get_existing_task_id,
    get_publish_history,
)

logger = logging.getLogger(__name__)

# 最大并发发布数
MAX_CONCURRENCY = 3


class PublisherHub:
    """
    发布调度中心。

    职责:
    1. 接收发布请求，路由到对应适配器
    2. 并发控制（最多 3 个平台同时发布）
    3. 状态追踪和结果聚合
    4. 内容指纹去重（数据库级持久化）
    """

    def __init__(self) -> None:
        self._publishers: dict[PublishMethod, BasePublisher] = {
            PublishMethod.WECHATSYNC_MCP: WechatsyncPublisher(),
            PublishMethod.OFFICIAL_API: None,  # 按平台初始化
            PublishMethod.PLAYWRIGHT: PlaywrightPublisher(),
        }

        self._api_publishers: dict[Platform, BasePublisher] = {
            Platform.WECHAT_MP: WechatMPPublisher(),
            Platform.TWITTER: TwitterPublisher(),
        }

    async def publish(self, request: PublishRequest) -> PublishResponse:
        """
        执行多平台发布。

        1. 数据库级内容去重（重复时返回已有 task_id）
        2. 路由到对应适配器
        3. 并发发布（最多 MAX_CONCURRENCY 个）
        4. 结果持久化到数据库
        """
        fingerprint = request.content_fingerprint

        # 数据库级去重：检查是否已发布过
        if is_duplicate(fingerprint):
            existing_task_id = get_existing_task_id(fingerprint)
            if existing_task_id:
                logger.warning("内容已发布过（指纹: %s, task: %s），返回已有记录", fingerprint, existing_task_id)
                existing_status = await self.get_task_status(existing_task_id)
                if existing_status:
                    return PublishResponse(
                        task_id=existing_task_id,
                        content_fingerprint=fingerprint,
                        results=existing_status.results,
                        created_at=existing_status.created_at,
                    )

        task_id = uuid4().hex[:12]

        # 保存文章记录
        save_article(
            title=request.title,
            fingerprint=fingerprint,
            content_type=request.content_type.value if hasattr(request.content_type, 'value') else str(request.content_type),
            tags=json.dumps(request.tags, ensure_ascii=False),
        )

        response = PublishResponse(
            task_id=task_id,
            content_fingerprint=fingerprint,
            results=[],
            created_at=datetime.now(),
        )

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def publish_to_platform(platform: Platform) -> PlatformResult:
            async with semaphore:
                publisher = self._get_publisher(platform)
                if not publisher:
                    result = PlatformResult(
                        platform=platform,
                        status=PublishStatus.FAILED,
                        error=f"没有可用的发布器处理平台: {platform.value}",
                    )
                    save_publish_record(
                        task_id=task_id,
                        fingerprint=fingerprint,
                        platform=platform.value,
                        status=result.status.value,
                        error=result.error,
                    )
                    return result

                logger.info("开始发布 [%s] → %s", request.title[:30], platform.value)

                # 先写入 processing 状态
                record_id = save_publish_record(
                    task_id=task_id,
                    fingerprint=fingerprint,
                    platform=platform.value,
                    status=PublishStatus.PROCESSING.value,
                )

                result = await publisher.publish_with_retry(request, platform)

                # 更新最终状态
                update_publish_record_status(
                    record_id=record_id,
                    status=result.status.value,
                    post_url=result.post_url,
                    error=result.error,
                    retries=result.retries,
                )

                logger.info(
                    "发布完成 [%s] → %s: %s",
                    request.title[:30],
                    platform.value,
                    result.status.value,
                )
                return result

        tasks = [publish_to_platform(p) for p in request.platforms]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = PlatformResult(
                    platform=request.platforms[i],
                    status=PublishStatus.FAILED,
                    error=str(result),
                )
                save_publish_record(
                    task_id=task_id,
                    fingerprint=fingerprint,
                    platform=request.platforms[i].value,
                    status=PublishStatus.FAILED.value,
                    error=str(result),
                )
                response.results.append(error_result)
            else:
                response.results.append(result)

        return response

    async def get_platforms(self) -> PlatformListResponse:
        """获取所有支持的平台列表和认证状态"""
        platforms: list[PlatformInfo] = []

        for platform in Platform:
            method = PLATFORM_METHOD_MAP.get(platform)
            publisher = self._get_publisher(platform)

            is_authed = False
            if publisher:
                try:
                    is_authed = await publisher.check_auth(platform)
                except Exception:
                    pass

            content_types = self._get_platform_content_types(platform)

            platforms.append(
                PlatformInfo(
                    platform=platform,
                    display_name=PLATFORM_DISPLAY_NAMES.get(platform, platform.value),
                    publish_method=method.value if method else "unknown",
                    is_authenticated=is_authed,
                    content_types=content_types,
                )
            )

        return PlatformListResponse(platforms=platforms, total=len(platforms))

    async def get_task_status(self, task_id: str) -> Optional[TaskStatusResponse]:
        """从数据库查询任务状态"""
        records = get_publish_records(task_id)
        if not records:
            return None

        results = []
        for r in records:
            results.append(
                PlatformResult(
                    platform=Platform(r.platform),
                    status=PublishStatus(r.status),
                    post_url=r.post_url,
                    error=r.error,
                    retries=r.retries,
                )
            )

        all_statuses = [r.status for r in results]
        if all(s == PublishStatus.PUBLISHED for s in all_statuses):
            overall_status = PublishStatus.PUBLISHED
        elif any(s == PublishStatus.PROCESSING for s in all_statuses):
            overall_status = PublishStatus.PROCESSING
        elif all(s == PublishStatus.FAILED for s in all_statuses):
            overall_status = PublishStatus.FAILED
        else:
            overall_status = PublishStatus.PROCESSING

        created_at = records[0].created_at if records else datetime.now()
        updated_at = max((r.updated_at for r in records), default=datetime.now())

        return TaskStatusResponse(
            task_id=task_id,
            status=overall_status,
            results=results,
            created_at=created_at,
            updated_at=updated_at,
        )

    async def retry_task(self, task_id: str, platform: Optional[str] = None) -> Optional[PublishResponse]:
        """重试失败的发布任务"""
        records = get_publish_records(task_id)
        if not records:
            return None

        failed_records = [
            r for r in records
            if r.status == PublishStatus.FAILED.value
            and (platform is None or r.platform == platform)
        ]

        if not failed_records:
            logger.info("任务 %s 没有需要重试的失败记录", task_id)
            return None

        fingerprint = failed_records[0].article_fingerprint
        # 获取原始文章信息用于重新发布
        from .storage.database import get_article_by_fingerprint
        article = get_article_by_fingerprint(fingerprint)
        if not article:
            logger.error("找不到文章记录: %s", fingerprint)
            return None

        retry_platforms = [Platform(r.platform) for r in failed_records]
        logger.info("重试任务 %s，平台: %s", task_id, [p.value for p in retry_platforms])

        # 标记为 processing
        for r in failed_records:
            update_publish_record_status(r.id, PublishStatus.PROCESSING.value)

        return task_id, retry_platforms, fingerprint

    def _get_publisher(self, platform: Platform) -> Optional[BasePublisher]:
        """根据平台获取对应的发布器"""
        method = PLATFORM_METHOD_MAP.get(platform)
        if not method:
            return None

        if method == PublishMethod.OFFICIAL_API:
            return self._api_publishers.get(platform)

        return self._publishers.get(method)

    @staticmethod
    def _get_platform_content_types(platform: Platform) -> list[ContentType]:
        """获取平台支持的内容类型"""
        video_platforms = {
            Platform.DOUYIN,
            Platform.BILIBILI_VIDEO,
            Platform.YOUTUBE,
            Platform.TIKTOK,
            Platform.KUAISHOU,
        }
        article_platforms = {
            Platform.WECHAT_MP,
            Platform.ZHIHU,
            Platform.JUEJIN,
            Platform.CSDN,
            Platform.TOUTIAO,
            Platform.JIANSHU,
            Platform.BILIBILI_ARTICLE,
            Platform.WORDPRESS,
            Platform.YUQUE,
        }

        if platform in video_platforms:
            return [ContentType.VIDEO]
        elif platform in article_platforms:
            return [ContentType.ARTICLE]
        elif platform == Platform.XIAOHONGSHU:
            return [ContentType.ARTICLE, ContentType.VIDEO, ContentType.SHORT_POST]
        elif platform in (Platform.TWITTER, Platform.WEIBO):
            return [ContentType.SHORT_POST, ContentType.ARTICLE]
        return [ContentType.ARTICLE]


# 全局单例
publisher_hub = PublisherHub()
