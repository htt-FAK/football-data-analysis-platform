"""版本控制服务层 — 基于 data_hash 的增量更新判断与 upsert

对应方案 3.8（增量更新机制）与 6.4（增量变更检测）：
1. 计算每行字段的 data_hash（SHA256）
2. 与库中现有 data_hash 比对：
   - 不存在     → INSERT（created）
   - 存在但 hash 不同 → UPDATE + version+1（updated）
   - 存在且 hash 相同 → 跳过（skipped，不写库）
3. 幂等：依赖 MySQL 唯一键，避免并发脏写
"""

import hashlib
import json
import logging

from sqlalchemy import inspect
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class VersioningService:
    """数据版本控制：data_hash 比对 + 增量 upsert"""

    def __init__(self):
        pass

    @staticmethod
    def compute_hash(data: dict) -> str:
        """计算数据字典的 SHA-256 摘要

        使用 sort_keys 保证字段顺序无关，ensure_ascii=False 保持可读性。
        """
        payload = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _build_instance(self, model_class, data: dict, new_hash: str):
        """根据 data 字典构造一个 model_class 实例（填充存在的列）"""
        mapper = inspect(model_class)
        valid_columns = {c.key for c in mapper.columns}
        kwargs = {k: v for k, v in data.items() if k in valid_columns}
        kwargs["data_hash"] = new_hash
        # 新记录 version 从 1 开始
        if "version" in valid_columns and "version" not in data:
            kwargs["version"] = 1
        return model_class(**kwargs)

    def should_update(self, db: Session, model_class, source_id, new_hash: str) -> bool:
        """判断是否需要更新：记录不存在或 data_hash 不同则返回 True"""
        existing = (
            db.query(model_class)
            .filter(model_class.source_id == str(source_id))
            .first()
        )
        if existing is None:
            return True
        return (existing.data_hash or "") != new_hash

    def upsert(self, db: Session, model_class, source_id, data: dict) -> dict:
        """增量 upsert：存在则按 data_hash 决定更新/跳过，不存在则插入

        Args:
            db: SQLAlchemy 会话
            model_class: 目标 ORM 模型类
            source_id: 源端 ID（用于唯一定位记录）
            data: 新数据字典（字段名需与模型列名对应）

        Returns:
            dict: {"action": "created"|"updated"|"skipped", "source_id": ..., "hash": ...}
        """
        new_hash = self.compute_hash(data)
        existing = (
            db.query(model_class)
            .filter(model_class.source_id == str(source_id))
            .first()
        )

        if existing is None:
            # 新记录 → 插入
            instance = self._build_instance(model_class, data, new_hash)
            instance.source_id = str(source_id)  # 补上源端 ID，供后续 upsert 定位
            db.add(instance)
            db.commit()
            logger.info("[%s] 新增记录 source_id=%s", model_class.__tablename__, source_id)
            return {"action": "created", "source_id": source_id, "hash": new_hash}

        if (existing.data_hash or "") == new_hash:
            # 内容未变 → 跳过
            return {"action": "skipped", "source_id": source_id, "hash": new_hash}

        # 内容变化 → 更新字段 + version+1
        mapper = inspect(model_class)
        valid_columns = {c.key for c in mapper.columns}
        for key, value in data.items():
            if key in valid_columns and key != "id":
                setattr(existing, key, value)
        existing.data_hash = new_hash
        if "version" in valid_columns:
            existing.version = (existing.version or 1) + 1
        db.commit()
        logger.info(
            "[%s] 更新记录 source_id=%s version=%s",
            model_class.__tablename__, source_id, getattr(existing, "version", "?"),
        )
        return {"action": "updated", "source_id": source_id, "hash": new_hash}
