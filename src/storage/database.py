"""SQLAlchemy 数据层 - 发布记录持久化"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import Platform, settings
from ..models import PublishStatus

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class ArticleRecord(Base):
    """文章记录表"""

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, index=True)
    content_fingerprint = Column(String(32), nullable=False, unique=True, index=True)
    content_type = Column(String(20), default="article")
    tags = Column(Text, default="")  # JSON 序列化的标签列表
    created_at = Column(DateTime, default=datetime.now)


class PublishRecord(Base):
    """发布记录表"""

    __tablename__ = "publish_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(12), nullable=False, index=True)
    article_fingerprint = Column(String(32), nullable=False, index=True)
    platform = Column(String(30), nullable=False)
    status = Column(String(20), default="pending")
    post_url = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    retries = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AccountRecord(Base):
    """平台账号记录表"""

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(30), nullable=False, unique=True)
    display_name = Column(String(100), nullable=True)
    is_authenticated = Column(Integer, default=0)  # 0=否, 1=是
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


# 创建引擎和会话工厂
engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """初始化数据库（创建表）"""
    Base.metadata.create_all(engine)
    logger.info("数据库初始化完成: %s", settings.database_url)


def get_session() -> Session:
    """获取数据库会话"""
    return SessionLocal()


# ============================================================
# CRUD 操作
# ============================================================


def save_article(title: str, fingerprint: str, content_type: str = "article", tags: str = "[]") -> bool:
    """保存文章记录，返回是否为新文章（去重）"""
    with get_session() as session:
        existing = session.query(ArticleRecord).filter_by(content_fingerprint=fingerprint).first()
        if existing:
            logger.info("文章已存在（指纹: %s），跳过", fingerprint)
            return False

        article = ArticleRecord(
            title=title,
            content_fingerprint=fingerprint,
            content_type=content_type,
            tags=tags,
        )
        session.add(article)
        session.commit()
        return True


def save_publish_record(
    task_id: str,
    fingerprint: str,
    platform: str,
    status: str,
    post_url: Optional[str] = None,
    error: Optional[str] = None,
    retries: int = 0,
) -> int:
    """保存发布记录"""
    with get_session() as session:
        record = PublishRecord(
            task_id=task_id,
            article_fingerprint=fingerprint,
            platform=platform,
            status=status,
            post_url=post_url,
            error=error,
            retries=retries,
        )
        session.add(record)
        session.commit()
        return record.id


def update_publish_record_status(
    record_id: int,
    status: str,
    post_url: Optional[str] = None,
    error: Optional[str] = None,
    retries: int = 0,
):
    """更新发布记录状态"""
    with get_session() as session:
        record = session.query(PublishRecord).filter_by(id=record_id).first()
        if record:
            record.status = status
            record.updated_at = datetime.now()
            if post_url is not None:
                record.post_url = post_url
            if error is not None:
                record.error = error
            if retries:
                record.retries = retries
            session.commit()


def get_publish_records(task_id: str) -> list[PublishRecord]:
    """查询任务的所有发布记录"""
    with get_session() as session:
        records = session.query(PublishRecord).filter_by(task_id=task_id).all()
        # Detach from session to avoid lazy loading issues
        session.expunge_all()
        return records


def get_existing_task_id(fingerprint: str) -> Optional[str]:
    """根据内容指纹查找最近一次的 task_id"""
    with get_session() as session:
        record = (
            session.query(PublishRecord)
            .filter_by(article_fingerprint=fingerprint)
            .order_by(PublishRecord.created_at.desc())
            .first()
        )
        return record.task_id if record else None


def get_article_by_fingerprint(fingerprint: str) -> Optional[ArticleRecord]:
    """根据指纹查找文章"""
    with get_session() as session:
        article = session.query(ArticleRecord).filter_by(content_fingerprint=fingerprint).first()
        if article:
            session.expunge(article)
        return article


def get_publish_history(
    page: int = 1,
    size: int = 20,
    platform: Optional[str] = None,
    status: Optional[str] = None,
) -> tuple[list[PublishRecord], int]:
    """分页查询发布历史"""
    with get_session() as session:
        query = session.query(PublishRecord)
        if platform:
            query = query.filter_by(platform=platform)
        if status:
            query = query.filter_by(status=status)

        total = query.count()
        records = (
            query.order_by(PublishRecord.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        session.expunge_all()
        return records, total


def is_duplicate(fingerprint: str) -> bool:
    """检查内容是否已发布（去重）"""
    with get_session() as session:
        return session.query(ArticleRecord).filter_by(content_fingerprint=fingerprint).first() is not None


def update_account_auth(platform: str, is_authenticated: bool, display_name: Optional[str] = None):
    """更新平台账号认证状态"""
    with get_session() as session:
        account = session.query(AccountRecord).filter_by(platform=platform).first()
        if account:
            account.is_authenticated = 1 if is_authenticated else 0
            account.last_checked_at = datetime.now()
            if display_name:
                account.display_name = display_name
        else:
            account = AccountRecord(
                platform=platform,
                is_authenticated=1 if is_authenticated else 0,
                display_name=display_name,
                last_checked_at=datetime.now(),
            )
            session.add(account)
        session.commit()
