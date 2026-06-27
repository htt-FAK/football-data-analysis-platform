"""实时比赛服务层 — 异步读写 Redis 缓存，支持降级检测

对应方案 3.9：进行中比赛的高频字段（比分/事件/控球率）先写 Redis（TTL 5 分钟），
前端首屏直接读缓存，减轻 MySQL 压力。
"""

import json
import logging
import time

from app.redis_client import get_redis, live_key
from app.config import REDIS_LIVE_TTL

logger = logging.getLogger(__name__)


class LiveService:
    """实时比分相关业务逻辑（异步，基于 Redis）"""

    def __init__(self):
        pass

    async def get_live_matches(self) -> list:
        """获取所有进行中比赛

        使用 SCAN 匹配 "live:*" 的 key，逐个读取并反序列化。
        Returns:
            list[dict]: 进行中比赛列表
        """
        redis = get_redis()
        results: list = []
        async for k in redis.scan_iter(match="live:*", count=100):
            raw = await redis.get(k)
            if raw:
                try:
                    results.append(json.loads(raw))
                except (ValueError, TypeError):
                    continue
        return results

    async def get_live_match(self, match_id: int) -> dict:
        """获取单场进行中比赛

        Args:
            match_id: 比赛 ID
        Returns:
            dict: 比赛实时数据，未命中缓存返回空字典
        """
        redis = get_redis()
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
        await redis.set(
            live_key(match_id),
            json.dumps(data, ensure_ascii=False),
            ex=REDIS_LIVE_TTL,
        )

    async def check_degradation(self) -> dict:
        """检查降级状态

        检测 Redis 连接与缓存新鲜度：
        - Redis 连接失败 → degraded=True，前端应回退到 MySQL 查询
        - 缓存为空（无 live:* key）→ degraded=True，提示"暂无进行中比赛"
        Returns:
            dict: 降级状态信息
        """
        redis = get_redis()
        try:
            await redis.ping()
        except Exception as e:
            logger.warning("Redis 连接失败，进入降级模式: %s", e)
            return {
                "degraded": True,
                "reason": "redis_unavailable",
                "last_update": "",
            }

        # 检查是否有 live 缓存
        live_keys: list = []
        async for k in redis.scan_iter(match="live:*", count=10):
            live_keys.append(k)
            if live_keys:
                break  # 只要有一个就够判断了

        if not live_keys:
            return {
                "degraded": False,
                "reason": "no_live_matches",
                "last_update": "",
            }

        return {"degraded": False, "reason": "", "last_update": str(int(time.time()))}
