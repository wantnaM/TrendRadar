# coding=utf-8
"""
FastAPI 应用工厂
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from webserver.routers import (
    dashboard, news, rss, config, schedule, actions, system
)


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="TrendRadar Admin",
        description="TrendRadar 管理仪表盘 API",
        version="6.7.0",
        docs_url="/api/docs" if __import__('os').environ.get("DEBUG") else None,
        redoc_url=None,
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "data": None,
                "error": str(exc),
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }
        )
    
    # 注册路由
    app.include_router(dashboard.router)
    app.include_router(news.router)
    app.include_router(rss.router)
    app.include_router(config.router)
    app.include_router(schedule.router)
    app.include_router(actions.router)
    app.include_router(system.router)
    
    # 静态文件
    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/assets", StaticFiles(directory=static_dir), name="static")
    
    # 根路由 - 返回前端 SPA
    @app.get("/")
    async def root():
        index_file = os.path.join(static_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "TrendRadar Admin API", "docs": "/api/docs"}
    
    # API 根路由
    @app.get("/api")
    async def api_root():
        return {
            "success": True,
            "data": {
                "version": "6.7.0",
                "endpoints": [
                    "/api/dashboard",
                    "/api/news",
                    "/api/rss",
                    "/api/config",
                    "/api/schedule",
                    "/api/actions",
                    "/api/system/info"
                ]
            },
            "error": None,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
    
    return app
