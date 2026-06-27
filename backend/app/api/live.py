"""实时比赛接口 — 从 Redis 缓存读取进行中比赛数据（降级轮询入口）"""

from fastapi import APIRouter

from app.redis_client import get_redis

router = APIRouter(prefix="/live", tags=["实时比赛"])


@router.get("/")
async def list_live_matches():
    """获取进行中比赛列表（从 Redis 缓存读，供 WS 断线时降级轮询）

    实际路径：GET /api/v1/live/
    """
    redis = get_redis()
    results: list = []
    # SCAN 匹配 "live:*" 的 key，逐个读取并反序列化
    async for k in redis.scan_iter(match="live:*", count=100):
        raw = await redis.get(k)
        if raw:
            import json
            try:
                results.append(json.loads(raw))
            except (ValueError, TypeError):
                continue
    return results


@router.get("/{match_id}")
async def get_live_match(match_id: int):
    """获取单场比赛实时数据

    实际路径：GET /api/v1/live/{match_id}
    """
    redis = get_redis()
    import json
    raw = await redis.get(f"live:{match_id}")
    if raw:
        return json.loads(raw)
    return {}
