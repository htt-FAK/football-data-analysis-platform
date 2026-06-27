"""比赛模型 — 比赛基础信息"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Match(Base):
    """比赛表"""

    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("seasons.id"), comment="赛季ID")
    league_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("leagues.id"), comment="联赛ID")
    matchday: Mapped[Optional[int]] = mapped_column(Integer, comment="比赛日")
    home_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), comment="主队ID")
    away_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), comment="客队ID")
    home_score: Mapped[Optional[int]] = mapped_column(Integer, comment="主队得分")
    away_score: Mapped[Optional[int]] = mapped_column(Integer, comment="客队得分")
    home_score_ht: Mapped[Optional[int]] = mapped_column(Integer, comment="主队半场得分")
    away_score_ht: Mapped[Optional[int]] = mapped_column(Integer, comment="客队半场得分")
    status: Mapped[str] = mapped_column(String(20), default="scheduled", comment="比赛状态")
    match_date: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="比赛时间")
    venue: Mapped[Optional[str]] = mapped_column(String(100), comment="比赛场地")

    # 增量字段
    data_source: Mapped[Optional[str]] = mapped_column(String(50), comment="来源标识")
    source_id: Mapped[Optional[str]] = mapped_column(String(100), comment="源端ID")
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后更新时间")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    data_hash: Mapped[Optional[str]] = mapped_column(String(64), comment="内容指纹")

    # 关联关系（主客队均为 teams 表，需通过 foreign_keys 消歧）
    season: Mapped[Optional["Season"]] = relationship("Season")
    league: Mapped[Optional["League"]] = relationship("League")
    home_team: Mapped[Optional["Team"]] = relationship("Team", foreign_keys=[home_team_id])
    away_team: Mapped[Optional["Team"]] = relationship("Team", foreign_keys=[away_team_id])
