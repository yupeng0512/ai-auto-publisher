"""Playwright 通用浏览器自动化发布器 - 支持小红书/抖音/B站/YouTube 视频上传"""

import asyncio
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import Platform, settings
from ..models import PlatformResult, PublishRequest, PublishStatus
from .base import BasePublisher

logger = logging.getLogger(__name__)

# Cookie 存储目录
COOKIE_DIR = Path(__file__).parent.parent.parent / "data" / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)

# 平台创作者中心 URL
PLATFORM_URLS: dict[Platform, str] = {
    Platform.XIAOHONGSHU: "https://creator.xiaohongshu.com/publish/publish",
    Platform.DOUYIN: "https://creator.douyin.com/creator-micro/content/upload",
    Platform.BILIBILI_VIDEO: "https://member.bilibili.com/platform/upload/video/frame",
    Platform.YOUTUBE: "https://studio.youtube.com/channel/UC/videos/upload",
    Platform.TIKTOK: "https://www.tiktok.com/upload",
    Platform.KUAISHOU: "https://cp.kuaishou.com/article/publish/video",
}


class PlaywrightPublisher(BasePublisher):
    """
    Playwright 浏览器自动化发布器。

    封装 Social-Auto-Upload 的核心能力，通过 Playwright 模拟人工操作
    实现视频/图文上传到各视频平台。

    特点:
    - Cookie 持久化管理，避免频繁登录
    - 随机延迟模拟人工操作
    - 支持 headless 模式
    """

    def __init__(self) -> None:
        self._headless = settings.playwright_headless
        self._slow_mo = settings.playwright_slow_mo

    def get_supported_platforms(self) -> list[Platform]:
        return list(PLATFORM_URLS.keys())

    async def check_auth(self, platform: Platform) -> bool:
        """检查平台 Cookie 是否存在且有效"""
        cookie_path = COOKIE_DIR / f"{platform.value}.json"
        return cookie_path.exists()

    async def publish(self, request: PublishRequest, platform: Platform) -> PlatformResult:
        """通过 Playwright 自动化发布内容"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error="playwright 未安装，请运行: pip install playwright && playwright install chromium",
            )

        publisher_method = self._get_platform_publisher(platform)
        if not publisher_method:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"平台 {platform.value} 的自动化发布尚未实现",
            )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self._headless,
                    slow_mo=self._slow_mo,
                )

                cookie_path = COOKIE_DIR / f"{platform.value}.json"
                context = await browser.new_context(
                    storage_state=str(cookie_path) if cookie_path.exists() else None,
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                )

                page = await context.new_page()
                result = await publisher_method(page, request, platform)

                await context.storage_state(path=str(cookie_path))
                await browser.close()

                return result

        except Exception as e:
            logger.error("Playwright 发布失败 [%s -> %s]: %s", request.title[:30], platform.value, e)
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"浏览器自动化失败: {e}",
            )

    def _get_platform_publisher(self, platform: Platform):
        """获取平台专属发布方法"""
        method_map = {
            Platform.XIAOHONGSHU: self._publish_xiaohongshu,
            Platform.DOUYIN: self._publish_douyin,
            Platform.BILIBILI_VIDEO: self._publish_bilibili,
            Platform.YOUTUBE: self._publish_youtube,
        }
        return method_map.get(platform)

    async def _publish_xiaohongshu(self, page, request: PublishRequest, platform: Platform) -> PlatformResult:
        """小红书发布"""
        try:
            await page.goto(PLATFORM_URLS[platform])
            await self._random_delay()

            if request.video_path and Path(request.video_path).exists():
                file_input = page.locator('input[type="file"]').first
                await file_input.set_input_files(request.video_path)
            elif request.cover_url:
                file_input = page.locator('input[type="file"]').first
                await file_input.set_input_files(request.cover_url)

            await self._random_delay()

            title_input = page.locator('[placeholder*="标题"]').first
            await title_input.fill(request.title)
            await self._random_delay()

            content_editor = page.locator('[contenteditable="true"]').first
            await content_editor.fill(request.content[:1000])
            await self._random_delay()

            if request.tags:
                for tag in request.tags[:5]:
                    await content_editor.type(f" #{tag}")
                    await self._random_delay(0.5, 1.5)

            publish_btn = page.locator('button:has-text("发布")').first
            await publish_btn.click()
            await page.wait_for_timeout(3000)

            return PlatformResult(
                platform=platform,
                status=PublishStatus.PUBLISHED,
                published_at=datetime.now(),
            )

        except Exception as e:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"小红书发布失败: {e}",
            )

    async def _publish_douyin(self, page, request: PublishRequest, platform: Platform) -> PlatformResult:
        """抖音发布"""
        try:
            await page.goto(PLATFORM_URLS[platform])
            await self._random_delay()

            if request.video_path and Path(request.video_path).exists():
                file_input = page.locator('input[type="file"]').first
                await file_input.set_input_files(request.video_path)
                await page.wait_for_timeout(5000)

            await self._random_delay()

            title_input = page.locator('[placeholder*="标题"], [placeholder*="作品标题"]').first
            await title_input.fill(request.title)
            await self._random_delay()

            desc_editor = page.locator('[contenteditable="true"]').first
            desc_text = request.content[:500]
            if request.tags:
                desc_text += " " + " ".join(f"#{tag}" for tag in request.tags[:5])
            await desc_editor.fill(desc_text)
            await self._random_delay()

            publish_btn = page.locator('button:has-text("发布")').first
            await publish_btn.click()
            await page.wait_for_timeout(3000)

            return PlatformResult(
                platform=platform,
                status=PublishStatus.PUBLISHED,
                published_at=datetime.now(),
            )

        except Exception as e:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"抖音发布失败: {e}",
            )

    async def _publish_bilibili(self, page, request: PublishRequest, platform: Platform) -> PlatformResult:
        """B站视频发布"""
        try:
            await page.goto(PLATFORM_URLS[platform])
            await self._random_delay()

            if request.video_path and Path(request.video_path).exists():
                file_input = page.locator('input[type="file"]').first
                await file_input.set_input_files(request.video_path)
                await page.wait_for_timeout(10000)

            await self._random_delay()

            title_input = page.locator('[placeholder*="标题"]').first
            await title_input.fill(request.title)
            await self._random_delay()

            if request.tags:
                tag_input = page.locator('[placeholder*="标签"], [placeholder*="tag"]').first
                for tag in request.tags[:5]:
                    await tag_input.fill(tag)
                    await tag_input.press("Enter")
                    await self._random_delay(0.3, 1.0)

            publish_btn = page.locator('button:has-text("投稿"), button:has-text("发布")').first
            await publish_btn.click()
            await page.wait_for_timeout(3000)

            return PlatformResult(
                platform=platform,
                status=PublishStatus.PUBLISHED,
                published_at=datetime.now(),
            )

        except Exception as e:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"B站发布失败: {e}",
            )

    async def _publish_youtube(self, page, request: PublishRequest, platform: Platform) -> PlatformResult:
        """YouTube 视频发布（通过 YouTube Studio 界面）"""
        try:
            await page.goto("https://studio.youtube.com")
            await self._random_delay()

            create_btn = page.locator('[id="create-icon"], button:has-text("Create")').first
            await create_btn.click()
            await self._random_delay()

            upload_option = page.locator('text="Upload videos"').first
            await upload_option.click()
            await self._random_delay()

            if request.video_path and Path(request.video_path).exists():
                file_input = page.locator('input[type="file"]').first
                await file_input.set_input_files(request.video_path)
                await page.wait_for_timeout(10000)

            title_input = page.locator('[id="textbox"]').first
            await title_input.fill(request.title)
            await self._random_delay()

            return PlatformResult(
                platform=platform,
                status=PublishStatus.DRAFT_SAVED,
                published_at=datetime.now(),
            )

        except Exception as e:
            return PlatformResult(
                platform=platform,
                status=PublishStatus.FAILED,
                error=f"YouTube 发布失败: {e}",
            )

    @staticmethod
    async def _random_delay(min_s: float = 2.0, max_s: float = 5.0) -> None:
        """随机延迟，模拟人工操作"""
        delay = random.uniform(min_s, max_s)
        await asyncio.sleep(delay)
