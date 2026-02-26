"""数据库层单元测试"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# 使用内存数据库避免污染
os.environ["DATABASE_URL"] = "sqlite:///./data/test_publisher.db"


class TestDatabase:
    """数据库 CRUD 测试"""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """每个测试使用独立的临时数据库"""
        db_path = tmp_path / "test.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

        # 重新加载模块以使用新的数据库路径
        from src.storage import database as db_module
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        db_module.engine = engine
        db_module.SessionLocal = sessionmaker(bind=engine)
        db_module.Base.metadata.create_all(engine)

        yield db_module

        # 清理
        engine.dispose()

    def test_save_article_new(self, setup_db):
        """保存新文章"""
        db = setup_db
        result = db.save_article("测试标题", "abc123", "article", '["AI"]')
        assert result is True

    def test_save_article_duplicate(self, setup_db):
        """保存重复文章返回 False"""
        db = setup_db
        db.save_article("测试标题", "abc123", "article", '["AI"]')
        result = db.save_article("测试标题2", "abc123", "article", '["AI"]')
        assert result is False

    def test_is_duplicate(self, setup_db):
        """去重检查"""
        db = setup_db
        assert db.is_duplicate("abc123") is False
        db.save_article("测试", "abc123")
        assert db.is_duplicate("abc123") is True

    def test_save_and_get_publish_records(self, setup_db):
        """保存和查询发布记录"""
        db = setup_db
        record_id = db.save_publish_record(
            task_id="task001",
            fingerprint="abc123",
            platform="zhihu",
            status="published",
            post_url="https://example.com/1",
        )
        assert record_id > 0

        records = db.get_publish_records("task001")
        assert len(records) == 1
        assert records[0].platform == "zhihu"
        assert records[0].status == "published"
        assert records[0].post_url == "https://example.com/1"

    def test_update_publish_record_status(self, setup_db):
        """更新发布记录状态"""
        db = setup_db
        record_id = db.save_publish_record(
            task_id="task002",
            fingerprint="def456",
            platform="juejin",
            status="processing",
        )

        db.update_publish_record_status(
            record_id=record_id,
            status="published",
            post_url="https://juejin.cn/post/123",
        )

        records = db.get_publish_records("task002")
        assert records[0].status == "published"
        assert records[0].post_url == "https://juejin.cn/post/123"

    def test_get_existing_task_id(self, setup_db):
        """根据指纹查找已有 task_id"""
        db = setup_db
        db.save_publish_record(
            task_id="task003",
            fingerprint="ghi789",
            platform="csdn",
            status="published",
        )

        task_id = db.get_existing_task_id("ghi789")
        assert task_id == "task003"

        assert db.get_existing_task_id("nonexistent") is None

    def test_get_article_by_fingerprint(self, setup_db):
        """根据指纹查找文章"""
        db = setup_db
        db.save_article("我的文章", "fp001", "article", '["test"]')

        article = db.get_article_by_fingerprint("fp001")
        assert article is not None
        assert article.title == "我的文章"

        assert db.get_article_by_fingerprint("nonexistent") is None

    def test_get_publish_history(self, setup_db):
        """分页查询发布历史"""
        db = setup_db
        for i in range(5):
            db.save_publish_record(
                task_id=f"task{i:03d}",
                fingerprint=f"fp{i:03d}",
                platform="zhihu" if i % 2 == 0 else "juejin",
                status="published" if i % 3 == 0 else "failed",
            )

        # 查全部
        records, total = db.get_publish_history(page=1, size=10)
        assert total == 5
        assert len(records) == 5

        # 按平台过滤
        records, total = db.get_publish_history(page=1, size=10, platform="zhihu")
        assert total == 3

        # 按状态过滤
        records, total = db.get_publish_history(page=1, size=10, status="failed")
        assert total == 3

        # 分页
        records, total = db.get_publish_history(page=1, size=2)
        assert total == 5
        assert len(records) == 2

    def test_update_account_auth(self, setup_db):
        """更新平台账号认证状态"""
        db = setup_db
        db.update_account_auth("zhihu", True, "测试用户")
        db.update_account_auth("zhihu", False)  # 更新同一平台


class TestHistoryAPI:
    """发布历史 API 测试"""

    @pytest.fixture(autouse=True)
    def setup_db_for_api(self, tmp_path):
        """为 API 测试准备数据库"""
        db_path = tmp_path / "test_api.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

        from src.storage import database as db_module
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        db_module.engine = engine
        db_module.SessionLocal = sessionmaker(bind=engine)
        db_module.Base.metadata.create_all(engine)

        yield db_module

        engine.dispose()

    def test_history_endpoint(self, setup_db_for_api):
        """测试历史查询端点"""
        from fastapi.testclient import TestClient
        from scripts.run import create_app

        db = setup_db_for_api
        db.save_publish_record("t001", "fp001", "zhihu", "published", "https://example.com")

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/history")
        assert response.status_code == 200
        data = response.json()
        assert "records" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_history_filter_by_platform(self, setup_db_for_api):
        """测试按平台过滤"""
        from fastapi.testclient import TestClient
        from scripts.run import create_app

        db = setup_db_for_api
        db.save_publish_record("t001", "fp001", "zhihu", "published")
        db.save_publish_record("t001", "fp001", "juejin", "failed")

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/history?platform=zhihu")
        data = response.json()
        assert data["total"] == 1
        assert data["records"][0]["platform"] == "zhihu"

    def test_retry_nonexistent_task(self, setup_db_for_api):
        """测试重试不存在的任务"""
        from fastapi.testclient import TestClient
        from scripts.run import create_app

        app = create_app()
        client = TestClient(app)

        response = client.post("/api/v1/retry/nonexistent")
        assert response.status_code == 404
