"""数据模型 - FastAPI 和 MCP Server 共享"""

import hashlib
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from .config import ContentType, Platform


class PublishStatus(str, Enum):
    """发布状态"""

    PENDING = "pending"
    PROCESSING = "processing"
    DRAFT_SAVED = "draft_saved"
    PUBLISHED = "published"
    FAILED = "failed"


# ============================================================
# 请求模型
# ============================================================


class PublishRequest(BaseModel):
    """统一发布请求"""

    title: str = Field(..., max_length=200, description="内容标题")
    content: str = Field(..., description="Markdown 格式正文")
    platforms: list[Platform] = Field(..., min_length=1, description="目标平台列表")
    content_type: ContentType = Field(default=ContentType.ARTICLE, description="内容类型")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    cover_url: Optional[str] = Field(default=None, description="封面图 URL")
    draft_only: bool = Field(default=False, description="是否仅保存草稿")
    video_path: Optional[str] = Field(default=None, description="视频文件路径（视频类型时必填）")

    @computed_field
    @property
    def content_fingerprint(self) -> str:
        """内容指纹（标题+摘要 MD5），用于去重"""
        raw = f"{self.title}:{self.content[:500]}"
        return hashlib.md5(raw.encode()).hexdigest()


# ============================================================
# 响应模型
# ============================================================


class PlatformResult(BaseModel):
    """单平台发布结果"""

    platform: Platform
    status: PublishStatus = PublishStatus.PENDING
    post_url: Optional[str] = None
    error: Optional[str] = None
    retries: int = 0
    published_at: Optional[datetime] = None


class PublishResponse(BaseModel):
    """发布任务响应"""

    task_id: str = Field(..., description="任务 ID")
    content_fingerprint: str = Field(..., description="内容指纹")
    results: list[PlatformResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class PlatformInfo(BaseModel):
    """平台信息"""

    platform: Platform
    display_name: str
    publish_method: str
    is_authenticated: bool = False
    content_types: list[ContentType] = Field(default_factory=list)


class PlatformListResponse(BaseModel):
    """平台列表响应"""

    platforms: list[PlatformInfo]
    total: int


class TaskStatusResponse(BaseModel):
    """任务状态响应"""

    task_id: str
    status: PublishStatus
    results: list[PlatformResult]
    created_at: datetime
    updated_at: Optional[datetime] = None


# ============================================================
# 平台显示名称
# ============================================================

PLATFORM_DISPLAY_NAMES: dict[Platform, str] = {
    Platform.WECHAT_MP: "微信公众号",
    Platform.TWITTER: "Twitter/X",
    Platform.ZHIHU: "知乎",
    Platform.JUEJIN: "掘金",
    Platform.CSDN: "CSDN",
    Platform.TOUTIAO: "头条号",
    Platform.JIANSHU: "简书",
    Platform.WEIBO: "微博",
    Platform.BILIBILI_ARTICLE: "B站专栏",
    Platform.WORDPRESS: "WordPress",
    Platform.YUQUE: "语雀",
    Platform.XIAOHONGSHU: "小红书",
    Platform.DOUYIN: "抖音",
    Platform.BILIBILI_VIDEO: "B站视频",
    Platform.YOUTUBE: "YouTube",
    Platform.TIKTOK: "TikTok",
    Platform.KUAISHOU: "快手",
}
