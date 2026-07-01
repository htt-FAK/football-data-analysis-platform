"""球队统计模型 — 球队赛季统计数据"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TeamStat(Base):
    """球队统计表"""

    __tablename__ = "team_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), comment="球队ID")
    season_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("seasons.id"), comment="赛季ID")
    matches_played: Mapped[int] = mapped_column(Integer, default=0, comment="比赛场次")
    wins: Mapped[int] = mapped_column(Integer, default=0, comment="胜场")
    draws: Mapped[int] = mapped_column(Integer, default=0, comment="平场")
    losses: Mapped[int] = mapped_column(Integer, default=0, comment="负场")
    goals_for: Mapped[int] = mapped_column(Integer, default=0, comment="进球数")
    goals_against: Mapped[int] = mapped_column(Integer, default=0, comment="失球数")
    xg_for: Mapped[float] = mapped_column(Float, default=0, comment="预期进球")
    xg_against: Mapped[float] = mapped_column(Float, default=0, comment="预期失球")
    possession: Mapped[float] = mapped_column(Float, default=0, comment="控球率")
    shots_total: Mapped[int] = mapped_column(Integer, default=0, comment="总射门数")
    shots_on_target_total: Mapped[int] = mapped_column(Integer, default=0, comment="射正总数")
    passes_total: Mapped[int] = mapped_column(Integer, default=0, comment="总传球数")
    pass_accuracy: Mapped[float] = mapped_column(Float, default=0, comment="传球成功率")
    corners: Mapped[int] = mapped_column(Integer, default=0, comment="角球数")
    fouls: Mapped[int] = mapped_column(Integer, default=0, comment="犯规数")
    clean_sheets: Mapped[int] = mapped_column(Integer, default=0, comment="零封场次")
    attack_rating: Mapped[float] = mapped_column(Float, default=0, comment="进攻评分")
    defense_rating: Mapped[float] = mapped_column(Float, default=0, comment="防守评分")
    overall_rating: Mapped[float] = mapped_column(Float, default=0, comment="综合评分")
    data_source: Mapped[Optional[str]] = mapped_column(String(50), comment="来源标识")
    source_id: Mapped[Optional[str]] = mapped_column(String(100), comment="源端ID")
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后更新时间")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    data_hash: Mapped[Optional[str]] = mapped_column(String(64), comment="内容指纹")

    # 关联关系
    team: Mapped[Optional["Team"]] = relationship("Team")
    season: Mapped[Optional["Season"]] = relationship("Season")
