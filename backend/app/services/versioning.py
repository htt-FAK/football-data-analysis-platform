"""版本控制服务层 — 基于 data_hash 的增量更新判断与 upsert

对应方案 3.8（增量更新机制）与 6.4（增量变更检测）：
1. 计算每行字段的 data_hash（SHA256）
2. 与库中现有 data_hash 比对：
   - 不存在     → INSERT（created）
   - 存在但 hash 不同 → UPDATE + version+1（updated）
   - 存在且 hash 相同 → 跳过（skipped，不写库）
3. 幂等：依赖 MySQL 唯一键，避免并发脏写
4. 并发安全：捕获 IntegrityError 并回退为 UPDATE（防 race condition）
"""

import hashlib
import json
import logging

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
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

    @staticmethod
    def _find_existing(db: Session, model_class, source_id: str, data_source: str | None = None):
        """按 (source_id, data_source) 查找现有记录。

        如果模型没有 data_source 列，则仅按 source_id 查找。
        当同时提供 data_source 时做精确匹配，防止不同源的 source_id 碰撞。
        """
        query = db.query(model_class).filter(model_class.source_id == str(source_id))
        mapper = inspect(model_class)
        has_data_source = any(c.key == "data_source" for c in mapper.columns)
        if has_data_source and data_source is not None:
            query = query.filter(model_class.data_source == data_source)
        return query.first()

    def should_update(self, db: Session, model_class, source_id, new_hash: str, data_source: str | None = None) -> bool:
        """判断是否需要更新：记录不存在或 data_hash 不同则返回 True"""
        existing = self._find_existing(db, model_class, source_id, data_source)
        if existing is None:
            return True
        return (existing.data_hash or "") != new_hash

    def upsert(self, db: Session, model_class, source_id, data: dict) -> dict:
        """增量 upsert：存在则按 data_hash 决定更新/跳过，不存在则插入

        并发安全：若 INSERT 因 (source_id, data_source) 唯一约束冲突（race condition），
        自动 rollback 并重试为 UPDATE。

        Args:
            db: SQLAlchemy 会话
            model_class: 目标 ORM 模型类
            source_id: 源端 ID（用于唯一定位记录）
            data: 新数据字典（字段名须与模型列名对应）

        Returns:
            dict: {"action": "created"|"updated"|"skipped", "source_id": ..., "hash": ...}
        """
        new_hash = self.compute_hash(data)
        data_source = data.get("data_source")
        existing = self._find_existing(db, model_class, source_id, data_source)

        if existing is None:
            # 新记录 → 插入
            instance = self._build_instance(model_class, data, new_hash)
            instance.source_id = str(source_id)
            db.add(instance)
            try:
                db.commit()
            except IntegrityError:
                # 并发写入：另一个进程已插入同一 (source_id, data_source)
                # 回滚当前事务，回退为 UPDATE
                db.rollback()
                existing = self._find_existing(db, model_class, source_id, data_source)
                if existing is None:
                    logger.warning(
                        "[%s] IntegrityError 回退但未能定位记录 source_id=%s data_source=%s",
                        model_class.__tablename__, source_id, data_source,
                    )
                    return {"action": "failed", "source_id": source_id, "hash": new_hash}
                logger.info(
                    "[%s] IntegrityError 回退为 UPDATE source_id=%s",
                    model_class.__tablename__, source_id,
                )
                # 继续走下面的 update 分支
            else:
                logger.info("[%s] 新增记录 source_id=%s", model_class.__tablename__, source_id)
                return {"action": "created", "source_id": source_id, "hash": new_hash}

        # 此处 existing 一定不为 None（要么原始查询命中，要么 IntegrityError 回退后命中）
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
