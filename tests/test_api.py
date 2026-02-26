"""API 集成测试 - FastAPI TestClient"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run import create_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    return TestClient(app)


class TestHealthCheck:
    """健康检查测试"""

    def test_health(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "ai-auto-publisher"


class TestPlatformsAPI:
    """平台列表 API 测试"""

    def test_list_platforms(self, client):
        response = client.get("/api/v1/platforms")
        assert response.status_code == 200
        data = response.json()
        assert "platforms" in data
        assert "total" in data
        assert data["total"] > 0

        # 验证返回的平台包含核心平台
        platform_ids = [p["platform"] for p in data["platforms"]]
        assert "wechat_mp" in platform_ids
        assert "zhihu" in platform_ids
        assert "twitter" in platform_ids

    def test_platform_info_structure(self, client):
        response = client.get("/api/v1/platforms")
        data = response.json()
        platform = data["platforms"][0]
        assert "platform" in platform
        assert "display_name" in platform
        assert "publish_method" in platform
        assert "is_authenticated" in platform
        assert "content_types" in platform


class TestPublishAPI:
    """发布 API 测试"""

    def test_publish_request_validation(self, client):
        """测试请求参数校验"""
        # 缺少必填字段
        response = client.post("/api/v1/publish", json={})
        assert response.status_code == 422

    def test_publish_empty_platforms(self, client):
        """测试空平台列表"""
        response = client.post(
            "/api/v1/publish",
            json={
                "title": "Test",
                "content": "Hello",
                "platforms": [],
            },
        )
        assert response.status_code == 422

    def test_publish_valid_request(self, client):
        """测试有效发布请求（会因为平台未认证而部分失败，但 API 应返回 200）"""
        response = client.post(
            "/api/v1/publish",
            json={
                "title": "测试文章",
                "content": "# 测试\n\n这是一篇测试文章。",
                "platforms": ["zhihu"],
                "tags": ["测试"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "results" in data
        assert len(data["results"]) == 1


class TestTaskStatusAPI:
    """任务状态 API 测试"""

    def test_task_not_found(self, client):
        """测试查询不存在的任务"""
        response = client.get("/api/v1/status/nonexistent")
        assert response.status_code == 404

    def test_task_status_after_publish(self, client):
        """测试发布后查询任务状态"""
        # 先发布
        pub_response = client.post(
            "/api/v1/publish",
            json={
                "title": "状态测试文章",
                "content": "测试内容",
                "platforms": ["zhihu"],
            },
        )
        task_id = pub_response.json()["task_id"]

        # 再查询状态
        status_response = client.get(f"/api/v1/status/{task_id}")
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["task_id"] == task_id
        assert "results" in data
