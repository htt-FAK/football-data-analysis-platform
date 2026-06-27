"""WebSocket 实时推送 — 按联赛分组订阅、心跳检测、定向广播

设计要点（对应方案 3.9）：
- 客户端连接 /ws 后发送 {"action":"subscribe","league_ids":[39,140]} 订阅联赛
- 服务端按 league_id 分组维护连接，仅推送订阅联赛内的比赛/事件/积分变动
- 25s 无任何消息则视为断开，前端 useWebSocket 自动降级为 30s HTTP 轮询
- 爬虫 upsert 后通过 ConnectionManager.publish_to_league 广播，避免无差别全量推送
"""

import asyncio
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import WS_HEARTBEAT_INTERVAL

logger = logging.getLogger(__name__)
ws_router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """WebSocket 连接管理器：按联赛分组维护活跃连接

    数据结构：
        self.league_subs: {league_id: set[WebSocket]}  联赛 → 订阅该联赛的连接集合
        self.conn_leagues: {WebSocket: set[int]}       连接 → 该连接订阅的联赛集合
        self.last_active: {WebSocket: float}           连接 → 最近活跃时间戳（心跳用）
    """

    def __init__(self):
        self.league_subs: dict[int, set[WebSocket]] = {}
        self.conn_leagues: dict[WebSocket, set[int]] = {}
        self.last_active: dict[WebSocket, float] = {}

    async def connect(self, websocket: WebSocket):
        """接受新连接并初始化其订阅集合"""
        await websocket.accept()
        self.conn_leagues[websocket] = set()
        self.last_active[websocket] = time.time()
        logger.info("WebSocket 连接已建立，当前连接数: %d", len(self.conn_leagues))

    def subscribe(self, websocket: WebSocket, league_ids: list[int]):
        """将连接加入指定联赛的订阅集合"""
        for league_id in league_ids:
            self.league_subs.setdefault(league_id, set()).add(websocket)
            self.conn_leagues[websocket].add(league_id)
        self.last_active[websocket] = time.time()

    def unsubscribe(self, websocket: WebSocket, league_ids: list[int]):
        """将连接从指定联赛的订阅集合中移除"""
        for league_id in league_ids:
            if league_id in self.league_subs:
                self.league_subs[league_id].discard(websocket)
                if not self.league_subs[league_id]:
                    del self.league_subs[league_id]
            self.conn_leagues[websocket].discard(league_id)
        self.last_active[websocket] = time.time()

    def disconnect(self, websocket: WebSocket):
        """连接断开时清理其所有订阅关系"""
        for league_id in self.conn_leagues.get(websocket, set()):
            if league_id in self.league_subs:
                self.league_subs[league_id].discard(websocket)
                if not self.league_subs[league_id]:
                    del self.league_subs[league_id]
        self.conn_leagues.pop(websocket, None)
        self.last_active.pop(websocket, None)
        logger.info("WebSocket 连接已断开，当前连接数: %d", len(self.conn_leagues))

    def touch(self, websocket: WebSocket):
        """更新连接的最近活跃时间（收到任意消息时调用）"""
        self.last_active[websocket] = time.time()

    async def publish_to_league(self, league_id: int, message: dict):
        """向订阅了指定联赛的所有连接推送消息（定向广播）

        供爬虫 / live_service 在 upsert 后调用：
            await manager.publish_to_league(39, {"type": "match_update", "data": {...}})
        """
        subscribers = self.league_subs.get(league_id, set()).copy()
        dead: list[WebSocket] = []
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception as e:  # 连接已失效
                logger.warning("推送失败，清理失效连接: %s", e)
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast(self, message: dict):
        """向所有活跃连接广播消息（全局通知，谨慎使用）"""
        conns = list(self.conn_leagues.keys())
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)


# 全局连接管理器实例
manager = ConnectionManager()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点

    消息协议（方案 3.9）：
        客户端 → 服务端：
            {"action":"subscribe","league_ids":[39,140]}
            {"action":"unsubscribe","league_ids":[39]}
            {"action":"ping"}
        服务端 → 客户端：
            {"type":"ack","action":"subscribe"}
            {"type":"match_update","data":{...}}      比赛数据更新
            {"type":"event","data":{...}}             比赛事件（进球/红牌/换人）
            {"type":"standing_update","data":{...}}   积分榜变动
            {"type":"pong"}
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            manager.touch(websocket)

            if action == "subscribe":
                league_ids = data.get("league_ids", [])
                manager.subscribe(websocket, league_ids)
                await websocket.send_json(
                    {"type": "ack", "action": "subscribe", "league_ids": league_ids}
                )
            elif action == "unsubscribe":
                league_ids = data.get("league_ids", [])
                manager.unsubscribe(websocket, league_ids)
                await websocket.send_json(
                    {"type": "ack", "action": "unsubscribe", "league_ids": league_ids}
                )
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json(
                    {"type": "error", "message": f"未知操作: {action}"}
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
