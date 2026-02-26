"""全局配置 - Pydantic BaseSettings 加载 .env"""

from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings


class Platform(str, Enum):
    """支持的发布平台"""

    # 官方 API 直连
    WECHAT_MP = "wechat_mp"
    TWITTER = "twitter"

    # Wechatsync MCP（20+ 图文平台）
    ZHIHU = "zhihu"
    JUEJIN = "juejin"
    CSDN = "csdn"
    TOUTIAO = "toutiao"
    JIANSHU = "jianshu"
    WEIBO = "weibo"
    BILIBILI_ARTICLE = "bilibili_article"
    WORDPRESS = "wordpress"
    YUQUE = "yuque"

    # Playwright 浏览器自动化（视频平台）
    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"
    BILIBILI_VIDEO = "bilibili_video"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    KUAISHOU = "kuaishou"


class ContentType(str, Enum):
    """内容类型"""

    ARTICLE = "article"
    SHORT_POST = "short_post"
    VIDEO = "video"


class PublishMethod(str, Enum):
    """发布方式"""

    OFFICIAL_API = "official_api"
    WECHATSYNC_MCP = "wechatsync_mcp"
    PLAYWRIGHT = "playwright"


# 平台 → 发布方式映射
PLATFORM_METHOD_MAP: dict[Platform, PublishMethod] = {
    Platform.WECHAT_MP: PublishMethod.OFFICIAL_API,
    Platform.TWITTER: PublishMethod.OFFICIAL_API,
    Platform.ZHIHU: PublishMethod.WECHATSYNC_MCP,
    Platform.JUEJIN: PublishMethod.WECHATSYNC_MCP,
    Platform.CSDN: PublishMethod.WECHATSYNC_MCP,
    Platform.TOUTIAO: PublishMethod.WECHATSYNC_MCP,
    Platform.JIANSHU: PublishMethod.WECHATSYNC_MCP,
    Platform.WEIBO: PublishMethod.WECHATSYNC_MCP,
    Platform.BILIBILI_ARTICLE: PublishMethod.WECHATSYNC_MCP,
    Platform.WORDPRESS: PublishMethod.WECHATSYNC_MCP,
    Platform.YUQUE: PublishMethod.WECHATSYNC_MCP,
    Platform.XIAOHONGSHU: PublishMethod.PLAYWRIGHT,
    Platform.DOUYIN: PublishMethod.PLAYWRIGHT,
    Platform.BILIBILI_VIDEO: PublishMethod.PLAYWRIGHT,
    Platform.YOUTUBE: PublishMethod.PLAYWRIGHT,
    Platform.TIKTOK: PublishMethod.PLAYWRIGHT,
    Platform.KUAISHOU: PublishMethod.PLAYWRIGHT,
}

# Wechatsync 平台名称映射（与 Wechatsync Skill 保持一致）
WECHATSYNC_PLATFORM_MAP: dict[Platform, str] = {
    Platform.ZHIHU: "zhihu",
    Platform.JUEJIN: "juejin",
    Platform.CSDN: "csdn",
    Platform.TOUTIAO: "toutiao",
    Platform.JIANSHU: "jianshu",
    Platform.WEIBO: "weibo",
    Platform.BILIBILI_ARTICLE: "bilibili",
    Platform.WORDPRESS: "wordpress",
    Platform.YUQUE: "yuque",
}

# Wechatsync 支持的完整平台列表（来自 Skill 文档，用于扩展）
WECHATSYNC_ALL_PLATFORMS = [
    "zhihu", "juejin", "jianshu", "toutiao", "weibo", "bilibili",
    "baijiahao", "csdn", "yuque", "douban", "sohu", "xueqiu",
    "weixin", "woshipm", "dayu", "yidian", "51cto", "sohufocus",
    "imooc", "oschina", "segmentfault", "cnblogs", "x", "xiaohongshu",
]


class Settings(BaseSettings):
    """应用配置"""

    # 服务
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    mcp_port: int = 8080
    database_url: str = "sqlite:///./data/publisher.db"

    # 微信公众号
    wechat_mp_app_id: str = ""
    wechat_mp_app_secret: str = ""

    # Twitter/X
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_token_secret: str = ""

    # Wechatsync MCP
    wechatsync_mcp_url: str = "http://localhost:9529"
    wechatsync_token: str = ""

    # Knot
    knot_api_token: str = ""

    # Playwright
    playwright_headless: bool = True
    playwright_slow_mo: int = 1000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# 全局配置实例
settings = Settings()
