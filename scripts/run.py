"""启动脚本 - 同时启动 FastAPI Server 和 MCP Server"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 将 src 加入 Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from fastapi import FastAPI

from src.api.routes import router
from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    from src.storage.database import init_db

    app = FastAPI(
        title="AI Auto Publisher",
        description="轻量级多平台发布中间件 - AI for Marketing 执行层",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(router)

    # 初始化数据库（创建表）
    init_db()

    return app


def main():
    parser = argparse.ArgumentParser(description="AI Auto Publisher 服务")
    parser.add_argument("--mode", choices=["api", "mcp", "all"], default="api", help="运行模式")
    parser.add_argument("--host", default=settings.api_host, help="API 服务主机")
    parser.add_argument("--port", type=int, default=settings.api_port, help="API 服务端口")
    parser.add_argument("--mcp-port", type=int, default=settings.mcp_port, help="MCP 服务端口")
    args = parser.parse_args()

    if args.mode == "api":
        logger.info("启动 FastAPI Server @ %s:%d", args.host, args.port)
        app = create_app()
        uvicorn.run(app, host=args.host, port=args.port)

    elif args.mode == "mcp":
        logger.info("启动 MCP Server (stdio mode)")
        from src.mcp_server.server import run_mcp_server
        asyncio.run(run_mcp_server())

    elif args.mode == "all":
        logger.info("启动 FastAPI Server @ %s:%d + MCP Server", args.host, args.port)
        app = create_app()
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
