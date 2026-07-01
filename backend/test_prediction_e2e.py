"""AI 预测端到端联调脚本。

用法（在项目根目录或 backend 目录均可）:
    python backend/test_prediction_e2e.py
    python backend/test_prediction_e2e.py 1598
    python backend/test_prediction_e2e.py --status
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path
from typing import Iterable

from sqlalchemy import inspect, text
from sqlalchemy.orm import joinedload

# 允许从 backend/ 目录直接运行
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import DEEPSEEK_API_KEY, ENABLE_AI_PREDICTION, STEPFUN_API_KEY
from app.database import Base, SessionLocal, engine
from app.models.match import Match
from app.models.match_prediction import MatchPrediction
from app.services.prediction_service import (
    get_matches_due_for_prediction,
    serialize_prediction,
)


LINE_WIDTH = 72


def safe_text(value: object) -> str:
    text_value = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text_value.encode(encoding, errors="replace").decode(encoding, errors="replace")


def console_print(*parts: object, sep: str = " ", end: str = "\n") -> None:
    text_value = sep.join(safe_text(part) for part in parts)
    print(text_value, end=end)


def line(char: str = "=") -> str:
    return char * LINE_WIDTH


def section(title: str) -> None:
    console_print()
    console_print(line())
    console_print(title)
    console_print(line())


def item(status: str, message: str) -> None:
    console_print(f"[{status}] {message}")


def summarize_exception(prefix: str, exc: Exception) -> None:
    item("FAIL", f"{prefix}: {type(exc).__name__}: {exc}")


def check_requests_dependency() -> bool:
    section("1. 依赖与环境检查")
    has_requests = importlib.util.find_spec("requests") is not None
    if has_requests:
        item("OK", "requests 依赖已安装")
    else:
        item("FAIL", "未找到 requests 依赖，请先安装 requirements.txt")
        return False

    item("OK", f"ENABLE_AI_PREDICTION = {ENABLE_AI_PREDICTION}")
    item("OK" if STEPFUN_API_KEY else "FAIL", f"STEPFUN_API_KEY {'已配置' if STEPFUN_API_KEY else '未配置'}")
    item("OK" if DEEPSEEK_API_KEY else "FAIL", f"DEEPSEEK_API_KEY {'已配置' if DEEPSEEK_API_KEY else '未配置'}")

    if not STEPFUN_API_KEY or not DEEPSEEK_API_KEY:
        item("FAIL", "缺少模型 API Key，终止联调")
        return False

    return True


def check_db_and_table() -> bool:
    section("2. 远程 MySQL 与 match_predictions 表检查")
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
            current_db = conn.execute(text("SELECT DATABASE()")).scalar()
            item("OK", f"MySQL 连接成功，版本 {version}，当前库 {current_db}")
    except Exception as exc:  # noqa: BLE001
        summarize_exception("数据库连接失败", exc)
        return False

    try:
        tables = inspect(engine).get_table_names()
    except Exception as exc:  # noqa: BLE001
        summarize_exception("读取表列表失败", exc)
        return False

    if "match_predictions" in tables:
        item("OK", "match_predictions 表已存在")
        return True

    item("WARN", "match_predictions 表不存在，尝试通过 ORM 自动建表")
    try:
        Base.metadata.create_all(bind=engine, tables=[MatchPrediction.__table__])
        item("OK", "ORM 自动建表成功")
        return True
    except Exception as exc:  # noqa: BLE001
        summarize_exception("ORM 自动建表失败", exc)
        return False


def query_candidate_matches(limit: int = 10) -> list[Match]:
    db = SessionLocal()
    try:
        matches = (
            db.query(Match)
            .options(joinedload(Match.home_team), joinedload(Match.away_team))
            .filter(
                Match.status == "scheduled",
                Match.home_team_id.isnot(None),
                Match.away_team_id.isnot(None),
                Match.match_date.isnot(None),
            )
            .order_by(Match.match_date.asc())
            .limit(limit)
            .all()
        )
        return matches
    finally:
        db.close()


def print_candidate_matches(limit: int = 10) -> list[Match]:
    section("3. 候选比赛列表")
    matches = query_candidate_matches(limit=limit)
    if not matches:
        item("WARN", "没有找到 status=scheduled 且主客队完整的候选比赛")
        return []

    for match in matches:
        home_name = match.home_team.name if match.home_team else "?"
        away_name = match.away_team.name if match.away_team else "?"
        kickoff = match.match_date.strftime("%Y-%m-%d %H:%M") if match.match_date else "?"
        stage = match.stage or match.group_name or "-"
        console_print(f"  - id={match.id:<4} {home_name} vs {away_name} @ {kickoff} [{stage}]")
    return matches


def pick_match(match_arg: str | None) -> int | None:
    section("4. 比赛选择结果")
    db = SessionLocal()
    try:
        if match_arg and match_arg != "--status":
            if not match_arg.isdigit():
                item("FAIL", f"非法 match_id 参数: {match_arg}")
                return None
            match_id = int(match_arg)
            match = db.get(Match, match_id)
            if not match:
                item("FAIL", f"指定比赛不存在: match_id={match_id}")
                return None
            item("OK", f"使用指定比赛: match_id={match_id}")
            return match_id

        due_matches = get_matches_due_for_prediction(db)
        if due_matches:
            match = due_matches[0]
            home_name = match.home_team.name if match.home_team else "?"
            away_name = match.away_team.name if match.away_team else "?"
            kickoff = match.match_date.strftime("%Y-%m-%d %H:%M") if match.match_date else "?"
            item("OK", f"命中赛前窗口比赛: match_id={match.id} {home_name} vs {away_name} @ {kickoff}")
            return match.id

        nearest = (
            db.query(Match)
            .filter(
                Match.status == "scheduled",
                Match.home_team_id.isnot(None),
                Match.away_team_id.isnot(None),
                Match.match_date.isnot(None),
            )
            .order_by(Match.match_date.asc())
            .first()
        )
        if nearest:
            home_name = nearest.home_team.name if nearest.home_team else "?"
            away_name = nearest.away_team.name if nearest.away_team else "?"
            kickoff = nearest.match_date.strftime("%Y-%m-%d %H:%M") if nearest.match_date else "?"
            item("WARN", f"赛前窗口内无待预测比赛，回退到最近一场: match_id={nearest.id} {home_name} vs {away_name} @ {kickoff}")
            return nearest.id

        item("FAIL", "没有找到可用于预测的比赛")
        return None
    finally:
        db.close()


def load_orchestrator():
    try:
        from app.prediction.orchestrator import PredictionOrchestrator
    except ModuleNotFoundError as exc:
        if exc.name == "requests":
            raise RuntimeError("缺少 requests 依赖，无法加载预测编排器") from exc
        raise
    return PredictionOrchestrator


def preview_text(text: str | None, limit: int = 180) -> str:
    if not text:
        return ""
    one_line = " ".join(text.split())
    if len(one_line) <= limit:
        return one_line
    return one_line[:limit] + "..."


def print_search_sources(results: Iterable[dict], limit: int = 3) -> None:
    shown = 0
    for result in results:
        if shown >= limit:
            break
        title = result.get("title") or result.get("url") or "(无标题来源)"
        url = result.get("url") or ""
        if url:
            console_print(f"      - {preview_text(title, 80)} | {preview_text(url, 120)}")
        else:
            console_print(f"      - {preview_text(title, 80)}")
        shown += 1


def run_prediction(match_id: int) -> MatchPrediction | None:
    section("5. 四轮预测执行过程")
    item("OK", "执行顺序: StepFun 战术联网 -> StepFun 场外联网 -> DeepSeek 推理 -> DeepSeek 裁决")
    item("OK", "reasoning_effort=high，单次真实运行通常需要 1 到 3 分钟")

    try:
        PredictionOrchestrator = load_orchestrator()
    except Exception as exc:  # noqa: BLE001
        summarize_exception("加载 PredictionOrchestrator 失败", exc)
        return None

    db = SessionLocal()
    try:
        orchestrator = PredictionOrchestrator()
        prediction = orchestrator.run_full_prediction(db, match_id)
        item("OK", f"预测执行完成，status={prediction.status}")
        return prediction
    except Exception as exc:  # noqa: BLE001
        summarize_exception("预测执行异常", exc)
        console_print(preview_text(traceback.format_exc(), 500))
        return None
    finally:
        db.close()


def print_rounds(rounds: list[dict]) -> None:
    for round_data in rounds:
        round_idx = round_data.get("round")
        focus = round_data.get("focus") or "-"
        model = round_data.get("model") or "-"
        status = round_data.get("status") or "-"
        tokens = round_data.get("tokens") or 0
        cost_ms = round_data.get("cost_ms") or 0
        repaired_json = bool(round_data.get("repaired_json"))
        semantic_issues = round_data.get("semantic_issues") or []
        source_quality = round_data.get("source_quality") or {}
        console_print()
        console_print(f"  第 {round_idx} 轮 | {focus}")
        console_print(f"    模型: {model}")
        console_print(f"    状态: {status}")
        console_print(f"    JSON修复: {'是' if repaired_json else '否'}")
        if semantic_issues:
            console_print(f"    语义问题: {', '.join(str(item) for item in semantic_issues)}")
        if source_quality:
            console_print(
                "    来源质量: "
                f"{source_quality.get('level')} "
                f"(count={source_quality.get('count')}, "
                f"valid_url={source_quality.get('valid_url_count')}, "
                f"domains={len(source_quality.get('unique_domains') or [])}, "
                f"penalty={source_quality.get('confidence_penalty')})"
            )
        console_print(f"    tokens: {tokens}")
        console_print(f"    耗时: {cost_ms} ms")

        conservative = round_data.get("conservative_verdict")
        aggressive = round_data.get("aggressive_verdict")
        if conservative:
            console_print(f"    保守结论: {preview_text(conservative, 160)}")
        if aggressive:
            console_print(f"    激进结论: {preview_text(aggressive, 160)}")

        search_results = round_data.get("search_results") or []
        if search_results:
            console_print(f"    联网来源（前 {min(3, len(search_results))} 条）:")
            print_search_sources(search_results, limit=3)

        reasoning = round_data.get("reasoning") or round_data.get("thinking") or ""
        if reasoning:
            console_print(f"    思考预览: {preview_text(reasoning, 220)}")

        error = round_data.get("error")
        if error:
            console_print(f"    错误: {preview_text(error, 220)}")


def print_prediction_result(prediction: MatchPrediction) -> None:
    section("6. 最终预测结果与来源摘要")
    console_print(f"状态: {prediction.status}")
    console_print(f"总 tokens: {prediction.total_tokens}")
    console_print(f"总耗时: {prediction.total_cost_ms} ms")
    if prediction.generated_at:
        console_print(f"生成时间: {prediction.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")

    if prediction.status != "completed":
        error_message = prediction.error_msg or "无额外错误信息"
        item("FAIL", f"预测未完成: {error_message}")
        rounds = prediction.rounds or []
        if rounds:
            print_rounds(rounds)
        return

    console_print(f"预测比分: {prediction.predicted_home_score} - {prediction.predicted_away_score}")
    if (
        prediction.home_win_prob is not None
        and prediction.draw_prob is not None
        and prediction.away_win_prob is not None
    ):
        console_print(
            "胜平负概率: "
            f"主胜 {prediction.home_win_prob:.1f}% / "
            f"平局 {prediction.draw_prob:.1f}% / "
            f"客胜 {prediction.away_win_prob:.1f}%"
        )
    else:
        console_print("胜平负概率: 无")

    console_print(f"置信度: {prediction.confidence}" if prediction.confidence is not None else "置信度: 无")
    console_print(f"保守结论: {prediction.conservative_verdict or '无'}")
    console_print(f"激进结论: {prediction.aggressive_verdict or '无'}")

    reasons = prediction.key_reasons or []
    if reasons:
        console_print("关键依据:")
        for idx, reason in enumerate(reasons[:8], start=1):
            console_print(f"  {idx}. {preview_text(str(reason), 180)}")
    else:
        console_print("关键依据: 无")

    rounds = prediction.rounds or []
    if rounds:
        console_print()
        console_print("各轮摘要:")
        print_rounds(rounds)


def verify_persistence(match_id: int) -> MatchPrediction | None:
    section("7. 落库与序列化校验")
    db = SessionLocal()
    try:
        prediction = (
            db.query(MatchPrediction)
            .filter(MatchPrediction.match_id == match_id)
            .first()
        )
        if not prediction:
            item("FAIL", f"match_predictions 中未找到 match_id={match_id} 的记录")
            return None

        rounds = prediction.rounds or []
        item("OK", f"已落库: id={prediction.id}, status={prediction.status}, rounds={len(rounds)}")
        item("OK", f"total_tokens={prediction.total_tokens}, total_cost_ms={prediction.total_cost_ms}")
        item("OK", f"generated_at={prediction.generated_at}")

        serialized = serialize_prediction(prediction, db)
        if not serialized:
            item("FAIL", "serialize_prediction 返回空结果")
            return prediction

        round_count = len(serialized.get("rounds") or [])
        key_reason_count = len(serialized.get("key_reasons") or [])
        item("OK", f"API 序列化校验通过: rounds={round_count}, key_reasons={key_reason_count}")
        return prediction
    except Exception as exc:  # noqa: BLE001
        summarize_exception("落库或序列化校验失败", exc)
        return None
    finally:
        db.close()


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    if not check_requests_dependency():
        return 1
    if not check_db_and_table():
        return 1

    print_candidate_matches()
    if arg == "--status":
        section("完成")
        item("OK", "状态检查完成，未触发任何 LLM 调用")
        return 0

    match_id = pick_match(arg)
    if match_id is None:
        return 1

    prediction = run_prediction(match_id)
    if prediction is None:
        return 1

    print_prediction_result(prediction)
    verify_persistence(match_id)

    section("完成")
    item("OK", f"E2E 脚本执行结束，match_id={match_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
