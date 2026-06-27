"""Redis 客户端封装 — 异步缓存 + Pub/Sub + 实时比分"""

import redis.asyncio as aioredis
from app.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

_redis = aioredis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
)


def get_redis() -> aioredis.Redis:
    """获取 Redis 异步客户端"""
    return _redis


def live_key(match_id: int) -> str:
    """进行中比赛的缓存 key"""
    return f"live:{match_id}"


def standings_key(league_id: int, season_id: int) -> str:
    """积分榜缓存 key"""
    return f"standings:{league_id}:{season_id}"
