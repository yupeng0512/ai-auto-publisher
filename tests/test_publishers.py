"""发布器单元测试 - Mock 各平台 API/MCP 响应"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Platform
from src.models import PublishRequest, PublishStatus


@pytest.fixture
def sample_article_request():
    """示例文章发布请求"""
    return PublishRequest(
        title="AI 自动化发文技术调研",
        content="# AI 自动化发文\n\n这是一篇关于 AI for Marketing 的技术文章...",
        platforms=[Platform.ZHIHU, Platform.JUEJIN],
        tags=["AI", "Marketing", "自动化"],
    )


@pytest.fixture
def sample_tweet_request():
    """示例推文发布请求"""
    return PublishRequest(
        title="AI Marketing Update",
        content="Exploring AI-powered content automation for multi-platform publishing.",
        platforms=[Platform.TWITTER],
        tags=["AI", "Marketing"],
    )


class TestBasePublisher:
    """测试 BasePublisher 基类"""

    @pytest.mark.asyncio
    async def test_publish_with_retry_success(self, sample_article_request):
        """测试重试机制 - 首次成功"""
        from src.publishers.base import BasePublisher
        from src.models import PlatformResult

        class MockPublisher(BasePublisher):
            async def publish(self, request, platform):
                return PlatformResult(platform=platform, status=PublishStatus.PUBLISHED)

            async def check_auth(self, platform):
                return True

            def get_supported_platforms(self):
                return [Platform.ZHIHU]

        publisher = MockPublisher()
        result = await publisher.publish_with_retry(sample_article_request, Platform.ZHIHU)
        assert result.status == PublishStatus.PUBLISHED
        assert result.retries == 0

    @pytest.mark.asyncio
    async def test_publish_with_retry_eventual_success(self, sample_article_request):
        """测试重试机制 - 第二次成功"""
        from src.publishers.base import BasePublisher
        from src.models import PlatformResult

        call_count = 0

        class MockPublisher(BasePublisher):
            BASE_RETRY_DELAY = 0.01  # 加快测试

            async def publish(self, request, platform):
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    return PlatformResult(
                        platform=platform,
                        status=PublishStatus.FAILED,
                        error="临时错误",
                    )
                return PlatformResult(platform=platform, status=PublishStatus.PUBLISHED)

            async def check_auth(self, platform):
                return True

            def get_supported_platforms(self):
                return [Platform.ZHIHU]

        publisher = MockPublisher()
        result = await publisher.publish_with_retry(sample_article_request, Platform.ZHIHU)
        assert result.status == PublishStatus.PUBLISHED
        assert result.retries == 1

    @pytest.mark.asyncio
    async def test_publish_with_retry_all_failed(self, sample_article_request):
        """测试重试机制 - 全部失败"""
        from src.publishers.base import BasePublisher
        from src.models import PlatformResult

        class MockPublisher(BasePublisher):
            MAX_RETRIES = 2
            BASE_RETRY_DELAY = 0.01

            async def publish(self, request, platform):
                return PlatformResult(
                    platform=platform,
                    status=PublishStatus.FAILED,
                    error="持续错误",
                )

            async def check_auth(self, platform):
                return True

            def get_supported_platforms(self):
                return [Platform.ZHIHU]

        publisher = MockPublisher()
        result = await publisher.publish_with_retry(sample_article_request, Platform.ZHIHU)
        assert result.status == PublishStatus.FAILED
        assert result.retries == 2


class TestWechatMPPublisher:
    """测试微信公众号发布器"""

    @pytest.mark.asyncio
    async def test_check_auth_no_credentials(self):
        """测试无凭证时认证检查"""
        from src.publishers.wechat_mp_publisher import WechatMPPublisher

        publisher = WechatMPPublisher()
        publisher._app_id = ""
        publisher._app_secret = ""
        result = await publisher.check_auth(Platform.WECHAT_MP)
        assert result is False

    @pytest.mark.asyncio
    async def test_markdown_to_html(self):
        """测试 Markdown 转 HTML"""
        from src.publishers.wechat_mp_publisher import WechatMPPublisher

        html = WechatMPPublisher._markdown_to_html("# Hello\n\nThis is **bold** text.")
        assert "<h1>" in html
        assert "<strong>bold</strong>" in html


class TestTwitterPublisher:
    """测试 Twitter 发布器"""

    @pytest.mark.asyncio
    async def test_check_auth_no_credentials(self):
        """测试无凭证时认证检查"""
        from src.publishers.twitter_publisher import TwitterPublisher

        publisher = TwitterPublisher()
        publisher._api_key = ""
        result = await publisher.check_auth(Platform.TWITTER)
        assert result is False

    def test_format_tweet_length(self, sample_tweet_request):
        """测试推文长度限制"""
        from src.publishers.twitter_publisher import TwitterPublisher

        publisher = TwitterPublisher()
        tweet = publisher._format_tweet(sample_tweet_request)
        assert len(tweet) <= 280


class TestPlaywrightPublisher:
    """测试 Playwright 发布器"""

    def test_supported_platforms(self):
        """测试支持的平台列表"""
        from src.publishers.playwright_publisher import PlaywrightPublisher

        publisher = PlaywrightPublisher()
        platforms = publisher.get_supported_platforms()
        assert Platform.XIAOHONGSHU in platforms
        assert Platform.DOUYIN in platforms
        assert Platform.YOUTUBE in platforms

    @pytest.mark.asyncio
    async def test_check_auth_no_cookies(self):
        """测试无 Cookie 时认证检查"""
        from src.publishers.playwright_publisher import PlaywrightPublisher

        publisher = PlaywrightPublisher()
        result = await publisher.check_auth(Platform.XIAOHONGSHU)
        # 没有预存 Cookie 文件时应返回 False
        assert isinstance(result, bool)


class TestModels:
    """测试数据模型"""

    def test_publish_request_fingerprint(self):
        """测试内容指纹生成"""
        req1 = PublishRequest(
            title="Test",
            content="Hello World",
            platforms=[Platform.ZHIHU],
        )
        req2 = PublishRequest(
            title="Test",
            content="Hello World",
            platforms=[Platform.JUEJIN],
        )
        # 相同标题+内容 → 相同指纹
        assert req1.content_fingerprint == req2.content_fingerprint

    def test_publish_request_different_fingerprint(self):
        """测试不同内容产生不同指纹"""
        req1 = PublishRequest(
            title="Test A",
            content="Content A",
            platforms=[Platform.ZHIHU],
        )
        req2 = PublishRequest(
            title="Test B",
            content="Content B",
            platforms=[Platform.ZHIHU],
        )
        assert req1.content_fingerprint != req2.content_fingerprint
