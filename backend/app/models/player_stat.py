"""球员统计模型 — 球员赛季统计数据"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlayerStat(Base):
    """球员统计表"""

    __tablename__ = "player_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"), comment="球员ID")
    season_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("seasons.id"), comment="赛季ID")
    appearances: Mapped[int] = mapped_column(Integer, default=0, comment="出场次数")
    goals: Mapped[int] = mapped_column(Integer, default=0, comment="进球数")
    assists: Mapped[int] = mapped_column(Integer, default=0, comment="助攻数")
    yellow_cards: Mapped[int] = mapped_column(Integer, default=0, comment="黄牌数")
    red_cards: Mapped[int] = mapped_column(Integer, default=0, comment="红牌数")
    minutes_played: Mapped[int] = mapped_column(Integer, default=0, comment="上场时间")
    shots: Mapped[int] = mapped_column(Integer, default=0, comment="射门数")
    shots_on_target: Mapped[int] = mapped_column(Integer, default=0, comment="射正数")
    xg: Mapped[float] = mapped_column(Float, default=0, comment="预期进球")
    xa: Mapped[float] = mapped_column(Float, default=0, comment="预期助攻")
    passes: Mapped[int] = mapped_column(Integer, default=0, comment="传球数")
    pass_accuracy: Mapped[float] = mapped_column(Float, default=0, comment="传球成功率")
    tackles: Mapped[int] = mapped_column(Integer, default=0, comment="抢断数")
    interceptions: Mapped[int] = mapped_column(Integer, default=0, comment="拦截数")
    rating: Mapped[float] = mapped_column(Float, default=0, comment="评分")
    data_source: Mapped[Optional[str]] = mapped_column(String(50), comment="来源标识")
    source_id: Mapped[Optional[str]] = mapped_column(String(100), comment="源端ID")
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后更新时间")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    data_hash: Mapped[Optional[str]] = mapped_column(String(64), comment="内容指纹")

    # 关联关系
    player: Mapped[Optional["Player"]] = relationship("Player")
    season: Mapped[Optional["Season"]] = relationship("Season")
