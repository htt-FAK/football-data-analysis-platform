"""Live match service backed by Redis with graceful degradation."""

from __future__ import annotations

import asyncio
import json
import logging
import time

from app.config import REDIS_DEGRADE_TIMEOUT, REDIS_LIVE_TTL
from app.redis_client import get_redis, live_key

logger = logging.getLogger(__name__)


class LiveService:
    """Async Redis helpers for live match cache and status reporting."""

    async def get_live_matches(self) -> list:
        redis = get_redis()

        async def _fetch_matches():
            results: list[dict] = []
            async for key in redis.scan_iter(match="live:*", count=100):
                raw = await redis.get(key)
                if not raw:
                    continue
                try:
                    results.append(self._normalize_live_payload(json.loads(raw)))
                except (ValueError, TypeError):
                    continue
            results.sort(
                key=lambda row: (
                    -int(row.get("cache_updated_at") or 0),
                    int(row.get("match_id") or 0),
                )
            )
            return results

        try:
            return await asyncio.wait_for(_fetch_matches(), timeout=REDIS_DEGRADE_TIMEOUT)
        except Exception as exc:
            logger.warning("Live list fallback to empty result because Redis is unavailable: %s", exc)
            return []

    async def get_live_match(self, match_id: int) -> dict:
        redis = get_redis()

        async def _fetch_match():
            raw = await redis.get(live_key(match_id))
            if raw:
                return self._normalize_live_payload(json.loads(raw))
            return {}

        try:
            return await asyncio.wait_for(_fetch_match(), timeout=REDIS_DEGRADE_TIMEOUT)
        except Exception as exc:
            logger.warning("Live match fallback to empty result because Redis is unavailable: %s", exc)
            return {}

    async def update_live_cache(self, match_id: int, data: dict) -> None:
        redis = get_redis()
        payload = self._normalize_live_payload({"match_id": match_id, **data})
        await redis.set(
            live_key(match_id),
            json.dumps(payload, ensure_ascii=False),
            ex=REDIS_LIVE_TTL,
        )

    async def clear_live_cache(self, match_id: int) -> None:
        redis = get_redis()
        await redis.delete(live_key(match_id))

    async def check_degradation(self) -> dict:
        redis = get_redis()
        try:
            await asyncio.wait_for(redis.ping(), timeout=REDIS_DEGRADE_TIMEOUT)
        except Exception as exc:
            logger.warning("Redis unavailable, entering degraded live mode: %s", exc)
            return {
                "degraded": True,
                "reason": "redis_unavailable",
                "last_update": "",
                "redis_available": False,
                "environment_ready": False,
                "cache_state": "unavailable",
                "live_match_count": 0,
                "active_match_ids": [],
            }

        async def _load_live_payloads():
            live_payloads: list[dict] = []
            async for key in redis.scan_iter(match="live:*", count=50):
                raw = await redis.get(key)
                if not raw:
                    continue
                try:
                    live_payloads.append(self._normalize_live_payload(json.loads(raw)))
                except (ValueError, TypeError):
                    continue
            return live_payloads

        try:
            live_payloads = await asyncio.wait_for(_load_live_payloads(), timeout=REDIS_DEGRADE_TIMEOUT)
        except Exception as exc:
            logger.warning("Redis live-key scan failed, entering degraded mode: %s", exc)
            return {
                "degraded": True,
                "reason": "redis_unavailable",
                "last_update": "",
                "redis_available": False,
                "environment_ready": False,
                "cache_state": "unavailable",
                "live_match_count": 0,
                "active_match_ids": [],
            }

        if not live_payloads:
            return {
                "degraded": False,
                "reason": "no_live_matches",
                "last_update": "",
                "redis_available": True,
                "environment_ready": True,
                "cache_state": "empty",
                "live_match_count": 0,
                "active_match_ids": [],
            }

        latest_update = max(int(payload.get("cache_updated_at") or 0) for payload in live_payloads)
        return {
            "degraded": False,
            "reason": "",
            "last_update": str(latest_update) if latest_update else str(int(time.time())),
            "redis_available": True,
            "environment_ready": True,
            "cache_state": "ready",
            "live_match_count": len(live_payloads),
            "active_match_ids": [payload.get("match_id") for payload in live_payloads if payload.get("match_id") is not None],
        }

    @staticmethod
    def _normalize_status(status: str | None) -> str | None:
        if status is None:
            return None
        normalized = str(status).strip().lower()
        return normalized or None

    def _normalize_live_payload(self, payload: dict) -> dict:
        normalized = dict(payload)
        normalized["status"] = self._normalize_status(normalized.get("status"))
        normalized["cache_updated_at"] = int(normalized.get("cache_updated_at") or time.time())
        normalized["cache_state"] = "live"
        return normalized
