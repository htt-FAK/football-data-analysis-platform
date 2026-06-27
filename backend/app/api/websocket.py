from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from app.redis_client import get_redis

ws_router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """WebSocket 连接管理器：维护活跃连接并提供广播能力"""

    def __init__(self):
        # 活跃连接列表
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """接受新连接并加入活跃列表"""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """从活跃列表中移除指定连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """向所有活跃连接广播消息"""
        for connection in self.active_connections:
            await connection.send_json(message)


# 全局连接管理器实例
manager = ConnectionManager()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点：接收 subscribe/unsubscribe/ping 消息"""
    await manager.connect(websocket)
    try:
        while True:
            # 接收客户端发来的 JSON 消息
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "subscribe":
                # TODO: 处理订阅请求（记录客户端关注的频道/比赛）
                await websocket.send_json({"type": "ack", "action": "subscribe"})
            elif action == "unsubscribe":
                # TODO: 处理取消订阅请求
                await websocket.send_json({"type": "ack", "action": "unsubscribe"})
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "error", "message": "未知操作"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
