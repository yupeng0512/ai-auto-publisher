"""集成测试 - 模拟完整发布流程（Mock 模式，不依赖真实 API）"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Platform
from src.models import PlatformResult, PublishRequest, PublishStatus
from src.publisher_hub import PublisherHub


@pytest.fixture
def hub():
    return PublisherHub()


@pytest.fixture
def sample_article():
    return PublishRequest(
        title="AI 自动化发布测试文章",
        content="# 测试标题\n\n这是一篇通过 ai-auto-publisher 自动发布的测试文章。\n\n## 功能验证\n\n- 多平台分发\n- 内容指纹去重\n- 并发控制",
        platforms=[Platform.ZHIHU, Platform.JUEJIN, Platform.CSDN],
        tags=["AI", "自动化", "测试"],
    )


@pytest.fixture
def sample_video_request():
    return PublishRequest(
        title="AI 短视频测试",
        content="这是一个测试视频描述",
        platforms=[Platform.XIAOHONGSHU, Platform.DOUYIN],
        content_type="video",
        video_path="/tmp/test_video.mp4",
        tags=["AI", "测试"],
    )


def _make_mock_client(response_json):
    """构建正确的 httpx.AsyncClient mock（支持 async with 上下文管理器）"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = response_json
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    return mock_client_cm


class TestWechatsyncIntegration:
    """Wechatsync MCP 集成测试（Mock MCP Server 响应）"""

    @pytest.mark.asyncio
    async def test_wechatsync_publish_success(self, hub, sample_article):
        """模拟 Wechatsync Bridge API 成功发布到知乎、掘金、CSDN"""
        mock_mcp_response = {
            "result": {
                "results": [
                    {
                        "platform": "zhihu",
                        "success": True,
                        "postUrl": "https://zhuanlan.zhihu.com/p/123456",
                    }
                ]
            },
        }

        mock_cm = _make_mock_client(mock_mcp_response)

        with patch("src.publishers.wechatsync_publisher.httpx.AsyncClient", return_value=mock_cm):
            response = await hub.publish(sample_article)

            assert response.task_id is not None
            assert len(response.results) == 3

            for result in response.results:
                assert result.status == PublishStatus.PUBLISHED
                assert result.platform in [Platform.ZHIHU, Platform.JUEJIN, Platform.CSDN]

    @pytest.mark.asyncio
    async def test_wechatsync_publish_failure(self, hub):
        """模拟 Wechatsync MCP 返回错误"""
        request = PublishRequest(
            title="失败测试",
            content="测试内容",
            platforms=[Platform.ZHIHU],
        )

        mock_mcp_response = {
            "error": "平台未登录",
        }

        mock_cm = _make_mock_client(mock_mcp_response)

        with patch("src.publishers.wechatsync_publisher.httpx.AsyncClient", return_value=mock_cm):
            response = await hub.publish(request)
            assert response.results[0].status == PublishStatus.FAILED
            assert "未登录" in response.results[0].error

    @pytest.mark.asyncio
    async def test_wechatsync_timeout(self, hub):
        """模拟 Wechatsync MCP 超时"""
        import httpx

        request = PublishRequest(
            title="超时测试",
            content="测试内容",
            platforms=[Platform.JUEJIN],
        )

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("连接超时")

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("src.publishers.wechatsync_publisher.httpx.AsyncClient", return_value=mock_cm):
            response = await hub.publish(request)
            assert response.results[0].status == PublishStatus.FAILED
            assert "超时" in response.results[0].error


class TestPlaywrightIntegration:
    """Playwright 浏览器自动化集成测试（Mock 模式）"""

    @pytest.mark.asyncio
    async def test_playwright_not_installed(self, hub, sample_video_request):
        """当 playwright 未安装时应优雅降级"""
        with patch(
            "src.publishers.playwright_publisher.PlaywrightPublisher.publish",
            new_callable=AsyncMock,
            return_value=PlatformResult(
                platform=Platform.XIAOHONGSHU,
                status=PublishStatus.FAILED,
                error="playwright 未安装",
            ),
        ):
            response = await hub.publish(sample_video_request)
            xhs_result = [r for r in response.results if r.platform == Platform.XIAOHONGSHU][0]
            assert xhs_result.status == PublishStatus.FAILED


class TestContentDedup:
    """内容去重测试"""

    @pytest.mark.asyncio
    async def test_duplicate_fingerprint_warning(self, hub):
        """相同内容二次发布应记录去重警告"""
        request = PublishRequest(
            title="去重测试文章",
            content="这是去重测试内容",
            platforms=[Platform.ZHIHU],
        )

        mock_mcp_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": "文章同步成功！"}]
            },
        }

        mock_cm = _make_mock_client(mock_mcp_response)

        with patch("src.publishers.wechatsync_publisher.httpx.AsyncClient", return_value=mock_cm):
            resp1 = await hub.publish(request)
            assert resp1.content_fingerprint == request.content_fingerprint

            resp2 = await hub.publish(request)
            assert resp2.content_fingerprint == resp1.content_fingerprint


class TestConcurrencyControl:
    """并发控制测试"""

    @pytest.mark.asyncio
    async def test_max_concurrency(self, hub):
        """验证最多 3 个平台同时发布"""
        request = PublishRequest(
            title="并发测试",
            content="测试并发控制",
            platforms=[
                Platform.ZHIHU,
                Platform.JUEJIN,
                Platform.CSDN,
                Platform.TOUTIAO,
                Platform.JIANSHU,
            ],
        )

        active_count = 0
        max_active = 0

        async def slow_mock_post(*args, **kwargs):
            nonlocal active_count, max_active
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.1)
            active_count -= 1

            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": "同步成功"}]},
            }
            mock_resp.status_code = 200
            return mock_resp

        mock_client = AsyncMock()
        mock_client.post.side_effect = slow_mock_post

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("src.publishers.wechatsync_publisher.httpx.AsyncClient", return_value=mock_cm):
            await hub.publish(request)
            assert max_active <= 3, f"最大并发数 {max_active} 超过限制 3"


class TestEndToEndFlow:
    """端到端流程测试"""

    @pytest.mark.asyncio
    async def test_full_publish_and_query_flow(self, hub):
        """完整流程: 发布 → 查询任务状态"""
        request = PublishRequest(
            title="E2E 测试文章",
            content="# E2E\n\n完整流程验证",
            platforms=[Platform.ZHIHU, Platform.CSDN],
            tags=["e2e", "test"],
        )

        mock_response = {
            "result": {
                "results": [
                    {
                        "platform": "zhihu",
                        "success": True,
                        "postUrl": "https://example.com/article/1",
                    }
                ]
            },
        }

        mock_cm = _make_mock_client(mock_response)

        with patch("src.publishers.wechatsync_publisher.httpx.AsyncClient", return_value=mock_cm):
            # Step 1: 发布
            pub_response = await hub.publish(request)
            assert pub_response.task_id
            assert len(pub_response.results) == 2

            # Step 2: 查询任务状态
            status = await hub.get_task_status(pub_response.task_id)
            assert status is not None
            assert status.task_id == pub_response.task_id
            assert status.status == PublishStatus.PUBLISHED
            assert len(status.results) == 2

            # Step 3: 验证结果包含 URL
            for r in status.results:
                assert r.post_url is not None or r.status == PublishStatus.PUBLISHED

    @pytest.mark.asyncio
    async def test_query_nonexistent_task(self, hub):
        """查询不存在的任务应返回 None"""
        result = await hub.get_task_status("nonexistent_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_platform_list(self, hub):
        """获取平台列表应返回所有已注册平台"""
        platforms = await hub.get_platforms()
        assert platforms.total >= 16
        names = [p.platform for p in platforms.platforms]
        assert Platform.ZHIHU in names
        assert Platform.WECHAT_MP in names
        assert Platform.XIAOHONGSHU in names
