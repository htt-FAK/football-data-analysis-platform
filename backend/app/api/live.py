from fastapi import APIRouter, Depends, HTTPException, Query
from app.redis_client import get_redis

router = APIRouter(prefix="/live", tags=["live"])


@router.get("/")
async def list_live_matches(redis=Depends(get_redis)):
    """获取进行中比赛列表（从 Redis 缓存读）"""
    # TODO: 从 Redis 读取进行中比赛列表
    return []


@router.get("/{match_id}")
async def get_live_match(match_id: int, redis=Depends(get_redis)):
    """获取单场比赛实时数据"""
    # TODO: 从 Redis 读取指定比赛的实时数据
    return {}
