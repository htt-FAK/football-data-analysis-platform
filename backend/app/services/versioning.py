"""版本控制服务层 — 基于 data_hash 的增量更新判断与 upsert"""

import hashlib
import json

from sqlalchemy.orm import Session


class VersioningService:
    """数据版本控制相关业务逻辑"""

    def __init__(self):
        """无参构造"""
        pass

    def compute_hash(self, data: dict) -> str:
        """计算数据字典的 SHA-256 哈希

        Args:
            data: 待计算的数据字典

        Returns:
            str: 16 进制哈希摘要
        """
        # 使用 sort_keys 保证字典顺序无关，ensure_ascii=False 保持可读性
        payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def should_update(self, db: Session, model_class, source_id: int, new_hash: str) -> bool:
        """判断是否需要更新

        比较数据库中现有记录的 data_hash 与新哈希，不同则需更新。

        Args:
            db: SQLAlchemy 会话
            model_class: 目标 Model 类
            source_id: 数据源侧 ID
            new_hash: 新计算的 data_hash

        Returns:
            bool: True 表示需要更新（哈希不同或记录不存在）
        """
        # TODO: 查询 model_class 中 source_id 对应记录的 data_hash
        #       existing = db.query(model_class).filter(model_class.source_id == source_id).first()
        #       if existing is None: return True
        #       return existing.data_hash != new_hash
        return True

    def upsert(self, db: Session, model_class, source_id: int, data: dict) -> dict:
        """增量更新（存在则更新，不存在则插入）

        Args:
            db: SQLAlchemy 会话
            model_class: 目标 Model 类
            source_id: 数据源侧 ID
            data: 新数据字典

        Returns:
            dict: 操作结果（action: created/updated/skipped, source_id, hash 等）
        """
        # TODO: 查询现有记录，对比 data_hash
        #       - 不存在 -> 创建新记录
        #       - 存在且 hash 不同 -> 更新记录
        #       - 存在且 hash 相同 -> 跳过（无变化）
        #       最后 db.commit()，返回操作结果字典
        new_hash = self.compute_hash(data)
        return {"action": "skipped", "source_id": source_id, "hash": new_hash}
