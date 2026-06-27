"""实时比赛服务层 — 异步读写 Redis 缓存，支持降级检测"""

import json

from sqlalchemy.orm import Session  # noqa: F401  保留类型引用以保持一致性

from app.redis_client import get_redis, live_key
from app.config import REDIS_LIVE_TTL


class LiveService:
    """实时比分相关业务逻辑（异步，基于 Redis）"""

    def __init__(self):
        """无参构造"""
        pass

    async def get_live_matches(self) -> list:
        """获取所有进行中比赛

        从 Redis 读取所有 live:* key，返回比赛数据列表。

        Returns:
            list[dict]: 进行中比赛列表
        """
        redis = get_redis()
        # TODO: 使用 SCAN 匹配 "live:*" 的 key，逐个读取并反序列化
        # 示例:
        #   keys = []
        #   async for k in redis.scan_iter(match="live:*", count=100):
        #       keys.append(k)
        #   results = []
        #   for k in keys:
        #       raw = await redis.get(k)
        #       if raw:
        #           results.append(json.loads(raw))
        #   return results
        return []

    async def get_live_match(self, match_id: int) -> dict:
        """获取单场进行中比赛

        Args:
            match_id: 比赛 ID

        Returns:
            dict: 比赛实时数据，未命中缓存返回空字典
        """
        redis = get_redis()
        # TODO: 读取 live:{match_id} 并反序列化
        raw = await redis.get(live_key(match_id))
        if raw:
            return json.loads(raw)
        return {}

    async def update_live_cache(self, match_id: int, data: dict) -> None:
        """更新实时比赛缓存

        将比赛数据写入 Redis，并设置 TTL（REDIS_LIVE_TTL）。

        Args:
            match_id: 比赛 ID
            data: 比赛实时数据字典
        """
        redis = get_redis()
        # TODO: 序列化 data 写入 live:{match_id}，设置过期时间 REDIS_LIVE_TTL
        await redis.set(
            live_key(match_id),
            json.dumps(data, ensure_ascii=False),
            ex=REDIS_LIVE_TTL,
        )

    async def check_degradation(self) -> dict:
        """检查降级状态

        检测 Redis 连接与缓存新鲜度，返回降级状态信息。

        Returns:
            dict: 降级状态（degraded: bool, reason: str, last_update: str 等）
        """
        # TODO: 探测 Redis 连通性（PING），检查是否有 live:* 缓存
        #       若连接失败或缓存为空，标记为降级并给出原因
        return {"degraded": False, "reason": "", "last_update": ""}
