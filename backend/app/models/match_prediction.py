"""比赛 AI 预测模型 — 多轮分析的赛前前瞻预测结果"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MatchPrediction(Base):
    """比赛 AI 预测结果表

    一场比赛对应一条预测记录（由 match_id 唯一）。
    存储最终裁决结论 + 三轮思考过程 + 联网搜索来源 + 元数据。
    """

    __tablename__ = "match_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matches.id"), nullable=False, unique=True, index=True, comment="比赛ID"
    )

    # ── 最终裁决结论 ──
    home_win_prob: Mapped[Optional[float]] = mapped_column(Float, comment="主胜概率(0-100)")
    draw_prob: Mapped[Optional[float]] = mapped_column(Float, comment="平局概率(0-100)")
    away_win_prob: Mapped[Optional[float]] = mapped_column(Float, comment="客胜概率(0-100)")
    predicted_home_score: Mapped[Optional[int]] = mapped_column(Integer, comment="预测主队得分")
    predicted_away_score: Mapped[Optional[int]] = mapped_column(Integer, comment="预测客队得分")
    conservative_verdict: Mapped[Optional[str]] = mapped_column(String(500), comment="保守预测一句话")
    aggressive_verdict: Mapped[Optional[str]] = mapped_column(String(500), comment="激进预测一句话")
    key_reasons: Mapped[Optional[Any]] = mapped_column(JSON, comment="关键依据数组")
    confidence: Mapped[Optional[float]] = mapped_column(Float, comment="综合置信度(0-100)")
    mermaid_mindmap: Mapped[Optional[str]] = mapped_column(Text, comment="Mermaid 思维导图源码")

    # ── 思考过程（核心展示用）──
    # 结构: [{round, model, focus, reasoning, search_results, conclusion, tokens_ms, status}]
    rounds: Mapped[Optional[Any]] = mapped_column(JSON, comment="各轮分析思考过程")
    final_summary: Mapped[Optional[str]] = mapped_column(Text, comment="综合裁决全文")

    # ── 元数据 ──
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, comment="总token消耗")
    total_cost_ms: Mapped[int] = mapped_column(Integer, default=0, comment="总耗时(毫秒)")
    status: Mapped[str] = mapped_column(String(20), default="completed", comment="预测状态")
    error_msg: Mapped[Optional[str]] = mapped_column(Text, comment="错误信息(失败时)")
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="生成时间")

    # 增量字段
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后更新时间")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")

    # 关联关系
    match: Mapped[Optional["Match"]] = relationship("Match", backref="prediction")
