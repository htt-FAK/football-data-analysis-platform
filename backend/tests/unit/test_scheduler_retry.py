"""Scheduler retry / graceful-shutdown / structured-log 单元测试。

覆盖范围（P0-5 Track H）：
- tenacity @retry 装饰器的重试行为（成功、重试后成功、超过最大次数）
- 结构化 timing 日志（_log_job_start / _log_job_end）
- shutdown_scheduler(wait=True) 优雅关闭
- 辅助函数（_derive_crawl_status / _derive_source_status / _ingest_context / _mark_source_error）
- setup_jobs / _dispatch_crawl 路径覆盖

所有外部依赖均通过 mock 隔离，不依赖真实 MySQL / Redis / HTTP。
"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tenacity import RetryError

from app.scheduler.jobs import (
    _crawl_source_target,
    _derive_crawl_status,
    _derive_source_status,
    _dispatch_crawl,
    _ingest_context,
    _log_job_end,
    _log_job_start,
    _mark_source_error,
    crawl_live_matches,
    daily_full_crawl,
    export_daily_report,
    refresh_worldcup_match_xg,
    refresh_worldcup_schedule,
    scan_and_predict_matches,
    scheduler,
    setup_jobs,
    shutdown_scheduler,
)


# ── crawl_live_matches retry 行为 ─────────────────────────────────────────


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.refresh_player_stats_for_finished_matches", new_callable=AsyncMock)
@patch("app.scheduler.jobs.sort_sources_for_task", return_value=[])
@patch("app.scheduler.jobs.ensure_builtin_data_sources")
@patch("app.scheduler.jobs.SessionLocal")
async def test_crawl_live_matches_succeeds_first_try(
    mock_session_local,
    mock_ensure,
    mock_sort,
    mock_refresh,
    mock_sleep,
):
    """Mock 成功场景：只调用 ensure_builtin_data_sources 1 次。"""
    mock_session_local.return_value = MagicMock()
    await crawl_live_matches()
    assert mock_ensure.call_count == 1


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.refresh_player_stats_for_finished_matches", new_callable=AsyncMock)
@patch("app.scheduler.jobs.sort_sources_for_task", return_value=[])
@patch(
    "app.scheduler.jobs.ensure_builtin_data_sources",
    side_effect=[ConnectionError("transient-1"), ConnectionError("transient-2"), None],
)
@patch("app.scheduler.jobs.SessionLocal")
async def test_crawl_live_matches_retries_on_transient_failure(
    mock_session_local,
    mock_ensure,
    mock_sort,
    mock_refresh,
    mock_sleep,
):
    """前 2 次抛出 ConnectionError → tenacity 重试 → 第 3 次成功。"""
    mock_session_local.return_value = MagicMock()
    await crawl_live_matches()
    # 2 次失败 + 1 次成功 = 3 次调用
    assert mock_ensure.call_count == 3


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch(
    "app.scheduler.jobs.ensure_builtin_data_sources",
    side_effect=ConnectionError("always-fail"),
)
@patch("app.scheduler.jobs.SessionLocal")
async def test_crawl_live_matches_gives_up_after_max_attempts(
    mock_session_local,
    mock_ensure,
    mock_sleep,
):
    """3 次全部失败 → tenacity 耗尽重试 → 抛出 RetryError。"""
    mock_session_local.return_value = MagicMock()
    with pytest.raises(RetryError):
        await crawl_live_matches()
    # 最大尝试次数 = 3
    assert mock_ensure.call_count == 3


# ── 结构化日志辅助函数 ─────────────────────────────────────────────────────


def test_log_job_start_emits_structured_json(caplog):
    """_log_job_start 输出合法 JSON，含 event / job / ts 字段。"""
    with caplog.at_level(logging.INFO, logger="app.scheduler.jobs"):
        _log_job_start("crawl_live_matches")

    assert len(caplog.records) >= 1
    last = caplog.records[-1]
    payload = json.loads(last.getMessage())
    assert payload["event"] == "scheduler_job_start"
    assert payload["job"] == "crawl_live_matches"
    assert payload["ts"].endswith("Z")


def test_log_job_end_emits_elapsed_and_success(caplog):
    """_log_job_end 输出 elapsed_s（保留 3 位小数）+ success + error。"""
    with caplog.at_level(logging.INFO, logger="app.scheduler.jobs"):
        _log_job_end("daily_full_crawl", elapsed_s=1.23456, success=True)
        _log_job_end("daily_full_crawl", elapsed_s=0.5, success=False, error="boom")

    records = caplog.records
    assert len(records) >= 2

    ok_payload = json.loads(records[-2].getMessage())
    assert ok_payload["event"] == "scheduler_job_end"
    assert ok_payload["job"] == "daily_full_crawl"
    assert ok_payload["elapsed_s"] == 1.235  # round(1.23456, 3)
    assert ok_payload["success"] is True
    assert ok_payload["error"] is None

    fail_payload = json.loads(records[-1].getMessage())
    assert fail_payload["success"] is False
    assert fail_payload["error"] == "boom"
    assert fail_payload["elapsed_s"] == 0.5


# ── shutdown 优雅关闭 ────────────────────────────────────────────────────


@patch("app.scheduler.jobs.scheduler")
def test_shutdown_waits_for_running_jobs(mock_scheduler):
    """shutdown_scheduler 必须调用 scheduler.shutdown(wait=True)。"""
    mock_scheduler.running = True
    shutdown_scheduler()
    mock_scheduler.shutdown.assert_called_once_with(wait=True)


@patch("app.scheduler.jobs.scheduler")
def test_shutdown_noop_when_not_running(mock_scheduler):
    """scheduler 未运行时 shutdown_scheduler 为 no-op。"""
    mock_scheduler.running = False
    shutdown_scheduler()
    mock_scheduler.shutdown.assert_not_called()


# ── setup_jobs 注册路径 ─────────────────────────────────────────────────


@patch("app.scheduler.jobs.scheduler")
def test_setup_jobs_registers_all_periodic_jobs(mock_scheduler):
    """setup_jobs 至少注册 5 个 job（live, daily, worldcup, export, ai-prediction）。"""
    setup_jobs()
    added_ids = [call.kwargs.get("id") for call in mock_scheduler.add_job.call_args_list]
    assert "live_crawl" in added_ids
    assert "daily_crawl" in added_ids
    assert "worldcup_schedule_refresh" in added_ids
    assert "daily_export" in added_ids
    assert "ai_prediction_scan" in added_ids


# ── 辅助函数：_derive_crawl_status ────────────────────────────────────────


def test_derive_crawl_status_success():
    assert _derive_crawl_status(fetched=10, updated=5, failed=0) == "success"


def test_derive_crawl_status_partial_on_failure():
    assert _derive_crawl_status(fetched=10, updated=5, failed=2) == "partial"


def test_derive_crawl_status_partial_on_no_data():
    assert _derive_crawl_status(fetched=0, updated=0, failed=0) == "partial"


# ── 辅助函数：_derive_source_status ──────────────────────────────────────


def test_derive_source_status_success():
    assert _derive_source_status("success") == "active"


def test_derive_source_status_partial():
    assert _derive_source_status("partial") == "warning"


def test_derive_source_status_failed():
    assert _derive_source_status("failed") == "idle"


# ── 辅助函数：_ingest_context ────────────────────────────────────────────


def test_ingest_context_fifa_official():
    ctx = _ingest_context("fifa_official")
    assert ctx == {"league_name": "世界杯", "season_name": "2026"}


def test_ingest_context_other_source():
    assert _ingest_context("dongqiudi") == {}


# ── 辅助函数：_mark_source_error ─────────────────────────────────────────


def test_mark_source_error_increments_counter():
    source = MagicMock()
    source.error_count = 2
    db = MagicMock()
    _mark_source_error(source, db)
    assert source.error_count == 3
    assert source.status == "warning"
    db.commit.assert_called_once()


def test_mark_source_error_triggers_error_status():
    source = MagicMock()
    source.error_count = 4
    db = MagicMock()
    _mark_source_error(source, db)
    assert source.error_count == 5
    assert source.status == "error"


def test_mark_source_error_handles_none_counter():
    source = MagicMock()
    source.error_count = None
    db = MagicMock()
    _mark_source_error(source, db)
    assert source.error_count == 1
    assert source.status == "warning"


# ── _dispatch_crawl 路径覆盖 ─────────────────────────────────────────────


@patch("app.scheduler.jobs.DataSource", autospec=False)
async def test_dispatch_crawl_unknown_source(mock_ds_cls):
    """未知 source_code → 返回空列表 + logger.warning。"""
    source = MagicMock()
    source.source_code = "nonexistent_source"
    result = await _dispatch_crawl(source, "schedule")
    assert result == []


# ── export_daily_report / scan_and_predict_matches 路径覆盖 ──────────────


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.SessionLocal")
async def test_scan_and_predict_matches_disabled(mock_session_local, mock_sleep):
    """ENABLE_AI_PREDICTION=False 时 scan_and_predict_matches 直接返回。"""
    mock_session_local.return_value = MagicMock()
    with patch("app.config.ENABLE_AI_PREDICTION", False):
        await scan_and_predict_matches()
    # 无异常即为成功


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.SessionLocal")
async def test_scan_and_predict_matches_enabled_and_scans(mock_session_local, mock_sleep):
    """ENABLE_AI_PREDICTION=True 时调用 scan_and_predict_async 并记录日志。"""
    mock_session_local.return_value = MagicMock()
    mock_scan_result = {"scanned": 2, "predicted": 1, "failed": 0, "details": "ok"}
    with (
        patch("app.config.ENABLE_AI_PREDICTION", True),
        patch(
            "app.services.prediction_service.scan_and_predict_async",
            new_callable=AsyncMock,
            return_value=mock_scan_result,
        ),
    ):
        await scan_and_predict_matches()


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.SessionLocal")
async def test_export_daily_report_success(mock_session_local, mock_sleep):
    """export_daily_report 正常导出 Excel。"""
    mock_session_local.return_value = MagicMock()
    with (
        patch("app.config.EXPORT_DIR", "/tmp/test_export"),
        patch(
            "app.export.excel_exporter.ExcelExporter"
        ) as mock_exporter_cls,
    ):
        mock_exporter = MagicMock()
        mock_exporter.export_all.return_value = "/tmp/test_export/report.xlsx"
        mock_exporter_cls.return_value = mock_exporter
        await export_daily_report()
        mock_exporter.export_all.assert_called_once()


# ── _dispatch_crawl 全路径覆盖 ────────────────────────────────────────────


@pytest.mark.parametrize(
    "source_code,crawler_module,crawler_class",
    [
        ("fifa_official", "app.crawlers.fifa_official", "FIFAOfficialCrawler"),
        ("dongqiudi", "app.crawlers.dongqiudi", "DongqiudiCrawler"),
        ("fbref", "app.crawlers.fbref", "FBrefCrawler"),
        ("fotmob", "app.crawlers.fotmob", "FotmobCrawler"),
        ("understat", "app.crawlers.understat", "UnderstatCrawler"),
        ("api_football", "app.crawlers.api_football", "APIFootballCrawler"),
        ("thesportsdb", "app.crawlers.thesportsdb", "TheSportsDBCrawler"),
        ("openligadb", "app.crawlers.openligadb", "OpenLigaDBCrawler"),
        ("teamrankings", "app.crawlers.teamrankings", "TeamRankingsCrawler"),
        ("statsbomb", "app.crawlers.statsbomb", "StatsBombCrawler"),
        ("football_data", "app.crawlers.football_data", "FootballDataCrawler"),
    ],
)
async def test_dispatch_crawl_known_sources(source_code, crawler_module, crawler_class):
    """已知 source_code → 调用对应 crawler 并返回结果。"""
    source = MagicMock()
    source.source_code = source_code
    mock_crawler = MagicMock()
    mock_crawler.crawl.return_value = [{"match_id": 1}]
    with patch(f"{crawler_module}.{crawler_class}", return_value=mock_crawler):
        result = await _dispatch_crawl(source, "schedule")
    assert result == [{"match_id": 1}]
    mock_crawler.crawl.assert_called_once()


async def test_dispatch_crawl_api_football_live_target():
    """api_football 在 target=live 时映射为 fixtures。"""
    source = MagicMock()
    source.source_code = "api_football"
    mock_crawler = MagicMock()
    mock_crawler.crawl.return_value = []
    with patch(
        "app.crawlers.api_football.APIFootballCrawler", return_value=mock_crawler
    ):
        result = await _dispatch_crawl(source, "live")
    assert result == []
    mock_crawler.crawl.assert_called_once_with(target="fixtures")


# ── _bootstrap_data_sources ──────────────────────────────────────────────


@patch("app.scheduler.jobs.SessionLocal")
@patch("app.scheduler.jobs.ensure_builtin_data_sources", return_value=3)
def test_bootstrap_data_sources_success(mock_ensure, mock_session_local):
    """_bootstrap_data_sources 正常路径：创建 3 个 source 并 log。"""
    from app.scheduler.jobs import _bootstrap_data_sources

    mock_session_local.return_value = MagicMock()
    _bootstrap_data_sources()
    mock_ensure.assert_called_once()


@patch("app.scheduler.jobs.SessionLocal")
@patch(
    "app.scheduler.jobs.ensure_builtin_data_sources",
    side_effect=RuntimeError("db-down"),
)
def test_bootstrap_data_sources_handles_failure(mock_ensure, mock_session_local):
    """_bootstrap_data_sources 异常被吞掉（scheduler 仍然启动）。"""
    from app.scheduler.jobs import _bootstrap_data_sources

    mock_session_local.return_value = MagicMock()
    _bootstrap_data_sources()  # 不抛异常
    mock_ensure.assert_called_once()


# ── export_daily_report 失败路径 ─────────────────────────────────────────


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.SessionLocal")
async def test_export_daily_report_failure(mock_session_local, mock_sleep):
    """export_daily_report 导出失败时记录 error 但不崩溃。"""
    mock_session_local.return_value = MagicMock()
    with (
        patch("app.config.EXPORT_DIR", "/tmp/test_export"),
        patch(
            "app.export.excel_exporter.ExcelExporter"
        ) as mock_exporter_cls,
    ):
        mock_exporter_cls.return_value.export_all.side_effect = IOError("disk full")
        await export_daily_report()  # 不抛异常


# ── refresh_worldcup_schedule 路径覆盖 ────────────────────────────────────


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs._crawl_source_target", new_callable=AsyncMock)
@patch("app.scheduler.jobs.ensure_builtin_data_sources")
@patch("app.scheduler.jobs.SessionLocal")
async def test_refresh_worldcup_schedule_success(
    mock_session_local, mock_ensure, mock_crawl_target, mock_sleep
):
    """refresh_worldcup_schedule 正常路径：找到 fifa_official source 并刷新赛程。"""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_source = MagicMock()
    mock_source.source_code = "fifa_official"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_source

    await refresh_worldcup_schedule()
    mock_crawl_target.assert_called_once()


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.ensure_builtin_data_sources")
@patch("app.scheduler.jobs.SessionLocal")
async def test_refresh_worldcup_schedule_no_source(
    mock_session_local, mock_ensure, mock_sleep
):
    """refresh_worldcup_schedule: fifa_official 不存在时跳过。"""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_db.query.return_value.filter.return_value.first.return_value = None

    await refresh_worldcup_schedule()  # 不抛异常


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs._mark_source_error")
@patch(
    "app.scheduler.jobs._crawl_source_target",
    new_callable=AsyncMock,
    side_effect=ConnectionError("network-down"),
)
@patch("app.scheduler.jobs.ensure_builtin_data_sources")
@patch("app.scheduler.jobs.SessionLocal")
async def test_refresh_worldcup_schedule_failure_marks_error(
    mock_session_local, mock_ensure, mock_crawl_target, mock_mark_error, mock_sleep
):
    """refresh_worldcup_schedule 异常时调用 _mark_source_error。"""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_source = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_source

    await refresh_worldcup_schedule()
    mock_mark_error.assert_called_once_with(mock_source, mock_db)


# ── refresh_worldcup_match_xg 路径覆盖 ────────────────────────────────────


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.SessionLocal")
async def test_refresh_worldcup_match_xg_no_pending(mock_session_local, mock_sleep):
    """refresh_worldcup_match_xg: 无缺 xG 的比赛时直接跳过。"""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value = 0

    await refresh_worldcup_match_xg()  # 不抛异常


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs._crawl_source_target", new_callable=AsyncMock)
@patch("app.scheduler.jobs.ensure_builtin_data_sources")
@patch("app.scheduler.jobs.SessionLocal")
async def test_refresh_worldcup_match_xg_success(
    mock_session_local, mock_ensure, mock_crawl_target, mock_sleep
):
    """refresh_worldcup_match_xg 正常路径。"""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    # pending > 0
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value.filter.return_value.count.return_value = 3
    mock_source = MagicMock()
    mock_source.source_code = "fotmob"
    # second query for DataSource
    mock_query2 = MagicMock()
    mock_db.query.side_effect = [mock_query, mock_query2]
    mock_query2.filter.return_value.first.return_value = mock_source

    await refresh_worldcup_match_xg()
    mock_crawl_target.assert_called_once()


# ── _crawl_source_target 路径覆盖 ────────────────────────────────────────


@patch("app.scheduler.jobs._dispatch_crawl", new_callable=AsyncMock, return_value=[{"match_id": 1}])
@patch("app.scheduler.jobs.resolve_crawl_target", return_value="schedule")
def test_crawl_source_target_success(mock_resolve, mock_dispatch):
    """_crawl_source_target 正常路径：抓取 + ingest + 更新 log。"""
    mock_source = MagicMock()
    mock_source.source_code = "fifa_official"
    mock_source.id = 1
    mock_db = MagicMock()
    mock_ingest_fn = MagicMock(return_value={"created": 5, "updated": 3, "failed": 0})

    import asyncio

    asyncio.get_event_loop().run_until_complete(
        _crawl_source_target(mock_source, mock_db, "schedule", "schedule", mock_ingest_fn)
    )
    mock_ingest_fn.assert_called_once()
    mock_db.commit.assert_called()


@patch("app.scheduler.jobs.resolve_crawl_target", return_value=None)
def test_crawl_source_target_no_concrete_target(mock_resolve):
    """_crawl_source_target: 无具体 target 时跳过。"""
    mock_source = MagicMock()
    mock_source.source_code = "unknown"
    mock_db = MagicMock()
    mock_ingest_fn = MagicMock()

    import asyncio

    asyncio.get_event_loop().run_until_complete(
        _crawl_source_target(mock_source, mock_db, "schedule", "x", mock_ingest_fn)
    )
    mock_ingest_fn.assert_not_called()


# ── daily_full_crawl 路径覆盖 ─────────────────────────────────────────────


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.supports_task", return_value=True)
@patch("app.scheduler.jobs.sort_sources_for_task", return_value=[])
@patch("app.scheduler.jobs.ensure_builtin_data_sources")
@patch("app.scheduler.jobs.SessionLocal")
async def test_daily_full_crawl_no_sources(
    mock_session_local, mock_ensure, mock_sort, mock_supports, mock_sleep
):
    """daily_full_crawl: 无 enabled source 时不报错。"""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    await daily_full_crawl()  # 不抛异常


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs._crawl_source_target", new_callable=AsyncMock)
@patch("app.scheduler.jobs.supports_task", return_value=True)
@patch("app.scheduler.jobs.sort_sources_for_task")
@patch("app.scheduler.jobs.ensure_builtin_data_sources")
@patch("app.scheduler.jobs.SessionLocal")
async def test_daily_full_crawl_with_sources(
    mock_session_local, mock_ensure, mock_sort, mock_supports, mock_crawl_target, mock_sleep
):
    """daily_full_crawl with sources: 3 targets × 1 source = 3 _crawl_source_target calls。"""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_source = MagicMock()
    mock_source.source_code = "fifa_official"
    mock_source.enabled = True
    mock_source.error_count = 0
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_source]
    mock_sort.return_value = [mock_source]

    with (
        patch("app.services.worldcup_player_rating_service.WorldCupPlayerRatingService") as mock_rating,
        patch("app.services.ingest_service.ingest_matches", return_value={"created": 1, "updated": 0, "failed": 0}),
        patch("app.services.ingest_service.ingest_player_stats", return_value={"created": 1, "updated": 0, "failed": 0}),
        patch("app.services.ingest_service.ingest_standings", return_value={"created": 1, "updated": 0, "failed": 0}),
        patch("app.services.ingest_service.ingest_team_stats", return_value={"created": 1, "updated": 0, "failed": 0}),
    ):
        mock_rating.return_value.refresh.return_value = {"refreshed": 1}
        await daily_full_crawl()
        # schedule + standings + players + statistics (fifa_official) = at least 3 calls
        assert mock_crawl_target.call_count >= 3


# ── crawl_live_matches with sources ────────────────────────────────────


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.refresh_player_stats_for_finished_matches", new_callable=AsyncMock)
@patch("app.scheduler.jobs._mark_source_error")
@patch("app.scheduler.jobs._crawl_source_live", new_callable=AsyncMock, side_effect=ConnectionError("net"))
@patch("app.scheduler.jobs.sort_sources_for_task")
@patch("app.scheduler.jobs.ensure_builtin_data_sources")
@patch("app.scheduler.jobs.SessionLocal")
async def test_crawl_live_matches_with_failing_source(
    mock_session_local, mock_ensure, mock_sort, mock_crawl_live,
    mock_mark_error, mock_refresh, mock_sleep
):
    """crawl_live_matches: source 失败时调用 _mark_source_error。"""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_source = MagicMock()
    mock_source.source_code = "fifa_official"
    mock_sort.return_value = [mock_source]
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_source]

    await crawl_live_matches()
    mock_mark_error.assert_called_once()


# ── start_scheduler_async ────────────────────────────────────────────────


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.scheduler")
@patch("app.scheduler.jobs.setup_jobs")
@patch("app.scheduler.jobs._bootstrap_data_sources")
async def test_start_scheduler_async_success(mock_bootstrap, mock_setup, mock_scheduler, mock_sleep):
    """start_scheduler_async: 正常路径 — bootstrap + setup_jobs + scheduler.start。"""
    from app.scheduler.jobs import start_scheduler_async

    await start_scheduler_async()
    mock_setup.assert_called_once()
    mock_scheduler.start.assert_called_once()


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.scheduler.jobs.scheduler")
@patch("app.scheduler.jobs.setup_jobs", side_effect=RuntimeError("register fail"))
@patch("app.scheduler.jobs._bootstrap_data_sources")
async def test_start_scheduler_async_setup_failure(mock_bootstrap, mock_setup, mock_scheduler, mock_sleep):
    """start_scheduler_async: setup_jobs 异常被捕获，不崩溃。"""
    from app.scheduler.jobs import start_scheduler_async

    await start_scheduler_async()  # 不抛异常


# ── refresh_player_stats_for_finished_matches ──────────────────────────


@patch("app.scheduler.jobs.SessionLocal")
async def test_refresh_player_stats_no_finished_matches(mock_session_local):
    """无刚结束的比赛时，函数正常返回。"""
    from app.scheduler.jobs import refresh_player_stats_for_finished_matches

    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    with patch("app.crawlers.fifa_official.FIFAOfficialCrawler") as mock_cls:
        mock_crawler = MagicMock()
        mock_crawler.crawl.return_value = [{"status": "scheduled", "match_id": "m1"}]
        mock_cls.return_value = mock_crawler
        await refresh_player_stats_for_finished_matches()


@patch("app.scheduler.jobs.SessionLocal")
async def test_refresh_player_stats_schedule_crawl_fails(mock_session_local):
    """schedule crawl 失败时跳过球员刷新。"""
    from app.scheduler.jobs import refresh_player_stats_for_finished_matches

    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    with patch("app.crawlers.fifa_official.FIFAOfficialCrawler") as mock_cls:
        mock_crawler = MagicMock()
        mock_crawler.crawl.side_effect = RuntimeError("crawl failed")
        mock_cls.return_value = mock_crawler
        await refresh_player_stats_for_finished_matches()  # 不抛异常


@patch("app.scheduler.jobs.SessionLocal")
async def test_refresh_player_stats_empty_schedule(mock_session_local):
    """schedule 返回空时跳过。"""
    from app.scheduler.jobs import refresh_player_stats_for_finished_matches

    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    with patch("app.crawlers.fifa_official.FIFAOfficialCrawler") as mock_cls:
        mock_crawler = MagicMock()
        mock_crawler.crawl.return_value = []
        mock_cls.return_value = mock_crawler
        await refresh_player_stats_for_finished_matches()  # 不抛异常


@patch("app.scheduler.jobs.SessionLocal")
async def test_refresh_player_stats_with_finished_matches(mock_session_local):
    """有刚结束的比赛 + 球员数据 → ingest + rating refresh。"""
    from app.scheduler.jobs import (
        _REFRESHED_MATCH_SOURCE_IDS,
        refresh_player_stats_for_finished_matches,
    )

    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    # 清除去重集合
    _REFRESHED_MATCH_SOURCE_IDS.clear()

    schedule_data = [
        {"status": "finished", "match_id": "m_finished_1"},
        {"status": "scheduled", "match_id": "m_scheduled"},
    ]
    players_data = [{"player_id": "p1", "goals": 3}]

    with (
        patch("app.crawlers.fifa_official.FIFAOfficialCrawler") as mock_cls,
        patch("app.services.ingest_service.ingest_player_stats", return_value={"created": 1, "updated": 0}),
        patch("app.services.worldcup_player_rating_service.WorldCupPlayerRatingService") as mock_rating_cls,
    ):
        mock_crawler = MagicMock()
        mock_crawler.crawl.side_effect = [schedule_data, players_data]
        mock_cls.return_value = mock_crawler
        mock_rating_cls.return_value.refresh.return_value = {"refreshed": 1}

        await refresh_player_stats_for_finished_matches()

    assert "m_finished_1" in _REFRESHED_MATCH_SOURCE_IDS
    _REFRESHED_MATCH_SOURCE_IDS.clear()  # 清理

