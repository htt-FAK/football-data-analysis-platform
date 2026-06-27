"""FastAPI 应用入口"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import APP_HOST, APP_PORT, DEBUG
from app.api import (
    leagues_router,
    teams_router,
    players_router,
    matches_router,
    live_router,
    data_sources_router,
    crawl_router,
)
from app.api.websocket import ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化调度器，关闭时清理"""
    from app.scheduler.jobs import start_scheduler, shutdown_scheduler
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="09 体育赛事数据采集与分析 API",
    description="自动化全域采集 · 数据清洗标准化 · 多维度价值分析 · 可视化报告输出",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(leagues_router, prefix="/api/v1/leagues", tags=["联赛"])
app.include_router(teams_router, prefix="/api/v1/teams", tags=["球队"])
app.include_router(players_router, prefix="/api/v1/players", tags=["球员"])
app.include_router(matches_router, prefix="/api/v1/matches", tags=["比赛"])
app.include_router(live_router, prefix="/api/v1/live", tags=["实时比赛"])
app.include_router(data_sources_router, prefix="/api/v1/data-sources", tags=["数据源"])
app.include_router(crawl_router, prefix="/api/v1/crawl", tags=["爬虫"])
app.include_router(ws_router, tags=["WebSocket"])


@app.get("/api/v1/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "sports-analytics", "version": "1.0.0"}


@app.get("/", tags=["系统"])
async def root():
    """根路径"""
    return {"message": "09 体育赛事数据采集与分析 API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=APP_HOST, port=APP_PORT, reload=DEBUG)
