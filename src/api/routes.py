"""FastAPI 路由 - 标准化发布 API"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..models import (
    PlatformListResponse,
    PublishRequest,
    PublishResponse,
    TaskStatusResponse,
)
from ..publisher_hub import publisher_hub
from ..storage.database import get_publish_history

router = APIRouter(prefix="/api/v1", tags=["publisher"])


@router.post("/publish", response_model=PublishResponse, summary="发布内容到多平台")
async def publish(request: PublishRequest) -> PublishResponse:
    """
    发布内容到指定平台。

    - 接收 Markdown 格式内容
    - 自动路由到对应适配器（Wechatsync MCP / 官方 API / Playwright）
    - 并发发布，最多 3 个平台同时进行
    - 自动去重：相同内容不会重复发布，返回已有记录
    - 返回任务 ID 和各平台发布结果

    **调用方**: n8n Webhook / Dify 自定义工具 / 外部 HTTP 客户端
    """
    try:
        response = await publisher_hub.publish(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发布失败: {e}") from e


@router.get("/platforms", response_model=PlatformListResponse, summary="获取支持的平台列表")
async def list_platforms() -> PlatformListResponse:
    """
    获取所有支持的平台列表及认证状态。

    返回每个平台的:
    - 平台标识和显示名称
    - 发布方式（官方 API / Wechatsync MCP / Playwright）
    - 是否已认证
    - 支持的内容类型
    """
    return await publisher_hub.get_platforms()


@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="查询发布任务状态")
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    查询指定发布任务的状态。

    返回任务的整体状态和各平台的发布结果详情。
    """
    result = await publisher_hub.get_task_status(task_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return result


@router.get("/history", summary="分页查询发布历史")
async def publish_history(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    platform: Optional[str] = Query(None, description="按平台过滤"),
    status: Optional[str] = Query(None, description="按状态过滤"),
) -> dict:
    """
    分页查询发布历史记录。

    支持按平台和状态过滤。
    """
    records, total = get_publish_history(page=page, size=size, platform=platform, status=status)
    return {
        "records": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "platform": r.platform,
                "status": r.status,
                "post_url": r.post_url,
                "error": r.error,
                "retries": r.retries,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in records
        ],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("/retry/{task_id}", summary="重试失败的发布任务")
async def retry_task(task_id: str, platform: Optional[str] = None) -> dict:
    """
    重试失败的发布任务。

    - 不指定 platform: 重试该任务所有失败的平台
    - 指定 platform: 仅重试指定平台
    """
    result = await publisher_hub.retry_task(task_id, platform)
    if result is None:
        raise HTTPException(status_code=404, detail=f"任务不存在或无失败记录: {task_id}")

    retry_task_id, retry_platforms, fingerprint = result
    return {
        "task_id": retry_task_id,
        "retry_platforms": [p.value for p in retry_platforms],
        "message": f"已触发重试 {len(retry_platforms)} 个平台",
    }


@router.get("/health", summary="健康检查")
async def health_check() -> dict:
    """服务健康检查"""
    return {"status": "ok", "service": "ai-auto-publisher"}
