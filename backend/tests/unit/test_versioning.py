"""Versioning Service 单元测试 — 覆盖 G race condition 处理 + 增量更新。

测试目标:
- VersioningService.compute_hash: 哈希计算确定性
- VersioningService.should_update: 新记录/变化/不变
- VersioningService.upsert: created/updated/skipped/IntegrityError fallback
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.versioning import VersioningService


def _make_mock_model(tablename="test_table", columns=None):
    """构造一个模拟 ORM 模型类。

    Args:
        tablename: 表名
        columns: 列名列表，默认包含常见字段
    """
    if columns is None:
        columns = ["id", "source_id", "data_source", "data_hash", "version", "name", "value"]

    model_cls = MagicMock()
    model_cls.__tablename__ = tablename

    # 模拟 sqlalchemy inspect 返回的 mapper
    mapper = MagicMock()
    mapper.columns = [MagicMock(key=col) for col in columns]

    return model_cls, mapper


def _make_chainable_query(first_return=None):
    """构造一个链式查询 mock，使得 .filter().filter().first() 返回指定值。

    _find_existing 可能链式调用多次 .filter()（取决于是否有 data_source 列），
    因此需要让 .filter() 返回自身。
    """
    query = MagicMock()
    query.filter.return_value = query  # .filter() 返回自身，支持链式调用
    query.first.return_value = first_return
    return query


class TestVersioningComputeHash:
    """compute_hash 哈希计算。"""

    def test_compute_hash_deterministic(self):
        """相同输入产出相同哈希。"""
        svc = VersioningService()
        data = {"name": "test", "value": 42}
        h1 = svc.compute_hash(data)
        h2 = svc.compute_hash(data)
        assert h1 == h2

    def test_compute_hash_order_independent(self):
        """字段顺序不影响哈希（sort_keys=True）。"""
        svc = VersioningService()
        h1 = svc.compute_hash({"a": 1, "b": 2})
        h2 = svc.compute_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_compute_hash_different_data(self):
        """不同数据产出不同哈希。"""
        svc = VersioningService()
        h1 = svc.compute_hash({"name": "test1"})
        h2 = svc.compute_hash({"name": "test2"})
        assert h1 != h2


class TestVersioningShouldUpdate:
    """should_update 更新判断逻辑。"""

    def test_should_update_new_record(self):
        """记录不存在 → 需要更新。"""
        svc = VersioningService()
        mock_db = MagicMock()
        model_cls, mapper = _make_mock_model()

        with patch("app.services.versioning.inspect", return_value=mapper):
            # _find_existing 返回 None（记录不存在）
            mock_db.query.return_value = _make_chainable_query(first_return=None)
            result = svc.should_update(mock_db, model_cls, "src_123", "new_hash")
            assert result is True

    def test_should_update_hash_changed(self):
        """记录存在但 hash 不同 → 需要更新。"""
        svc = VersioningService()
        mock_db = MagicMock()
        model_cls, mapper = _make_mock_model()

        existing = MagicMock()
        existing.data_hash = "old_hash"

        with patch("app.services.versioning.inspect", return_value=mapper):
            mock_db.query.return_value = _make_chainable_query(first_return=existing)
            result = svc.should_update(mock_db, model_cls, "src_123", "new_hash")
            assert result is True

    def test_should_update_hash_unchanged(self):
        """记录存在且 hash 相同 → 不需要更新。"""
        svc = VersioningService()
        mock_db = MagicMock()
        model_cls, mapper = _make_mock_model()

        existing = MagicMock()
        existing.data_hash = "same_hash"

        with patch("app.services.versioning.inspect", return_value=mapper):
            mock_db.query.return_value = _make_chainable_query(first_return=existing)
            result = svc.should_update(mock_db, model_cls, "src_123", "same_hash")
            assert result is False


class TestVersioningUpsert:
    """upsert 增量更新 + race condition 处理。"""

    def test_upsert_created_new_record(self):
        """新记录：INSERT 成功 → action=created。"""
        svc = VersioningService()
        mock_db = MagicMock()
        model_cls, mapper = _make_mock_model()

        with patch("app.services.versioning.inspect", return_value=mapper):
            # _find_existing 返回 None → 触发 INSERT 路径
            mock_db.query.return_value = _make_chainable_query(first_return=None)
            mock_db.commit = MagicMock()  # INSERT 不抛 IntegrityError

            result = svc.upsert(mock_db, model_cls, "src_123", {"name": "new", "data_source": "test"})

            assert result["action"] == "created"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_upsert_skipped_same_hash(self):
        """记录存在且 hash 未变 → action=skipped。"""
        svc = VersioningService()
        mock_db = MagicMock()
        model_cls, mapper = _make_mock_model()

        data = {"name": "test", "data_source": "src"}
        existing = MagicMock()
        existing.data_hash = svc.compute_hash(data)  # 相同 hash
        existing.version = 1

        with patch("app.services.versioning.inspect", return_value=mapper):
            mock_db.query.return_value = _make_chainable_query(first_return=existing)

            result = svc.upsert(mock_db, model_cls, "src_123", data)

            assert result["action"] == "skipped"
            mock_db.commit.assert_not_called()

    def test_upsert_updated_hash_changed(self):
        """记录存在且 hash 不同 → action=updated, version+1。"""
        svc = VersioningService()
        mock_db = MagicMock()
        model_cls, mapper = _make_mock_model()

        existing = MagicMock()
        existing.data_hash = "old_hash"
        existing.version = 1

        with patch("app.services.versioning.inspect", return_value=mapper):
            mock_db.query.return_value = _make_chainable_query(first_return=existing)
            mock_db.commit = MagicMock()

            result = svc.upsert(mock_db, model_cls, "src_123", {"name": "updated", "data_source": "src"})

            assert result["action"] == "updated"
            assert existing.version == 2  # version+1
            mock_db.commit.assert_called_once()

    def test_upsert_integrity_error_fallback_to_update(self):
        """INSERT 抛 IntegrityError（race condition） → rollback 后 UPDATE。"""
        svc = VersioningService()
        mock_db = MagicMock()
        model_cls, mapper = _make_mock_model()

        # INSERT 后 rollback，第二次 _find_existing 返回已存在的记录
        existing_after_race = MagicMock()
        existing_after_race.data_hash = "old_hash"
        existing_after_race.version = 1

        call_count = [0]

        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                # 第一次查询：无记录（触发 INSERT 路径）
                return _make_chainable_query(first_return=None)
            else:
                # 第二次查询（IntegrityError 后）：其他进程已插入
                return _make_chainable_query(first_return=existing_after_race)

        mock_db.query.side_effect = query_side_effect
        mock_db.rollback = MagicMock()

        with patch("app.services.versioning.inspect", return_value=mapper):
            # 第一次 commit（INSERT）抛 IntegrityError，第二次 commit（UPDATE）成功
            commit_call_count = [0]

            def commit_side_effect(*args, **kwargs):
                commit_call_count[0] += 1
                if commit_call_count[0] == 1:
                    raise IntegrityError("duplicate", None, None)
                # 第二次 commit 成功

            mock_db.commit.side_effect = commit_side_effect

            result = svc.upsert(mock_db, model_cls, "src_123", {"name": "race", "data_source": "src"})

            assert result["action"] == "updated"
            mock_db.rollback.assert_called_once()
            assert existing_after_race.version == 2

    def test_upsert_integrity_error_but_no_record_after_rollback(self):
        """INSERT 抛 IntegrityError，rollback 后仍找不到记录 → action=failed。"""
        svc = VersioningService()
        mock_db = MagicMock()
        model_cls, mapper = _make_mock_model()

        # 所有 _find_existing 都返回 None
        mock_db.query.return_value = _make_chainable_query(first_return=None)
        mock_db.commit.side_effect = IntegrityError("duplicate", None, None)
        mock_db.rollback = MagicMock()

        with patch("app.services.versioning.inspect", return_value=mapper):
            result = svc.upsert(mock_db, model_cls, "src_123", {"name": "orphan", "data_source": "src"})
            assert result["action"] == "failed"
