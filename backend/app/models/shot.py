"""射门事件模型 — 射门坐标及结果"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Shot(Base):
    """射门事件表"""

    __tablename__ = "shots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("matches.id"), comment="比赛ID")
    player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"), comment="球员ID")
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), comment="球队ID")
    minute: Mapped[Optional[int]] = mapped_column(Integer, comment="分钟")
    x_coord: Mapped[Optional[float]] = mapped_column(Float, comment="X坐标")
    y_coord: Mapped[Optional[float]] = mapped_column(Float, comment="Y坐标")
    result: Mapped[Optional[str]] = mapped_column(String(20), comment="射门结果")
    shot_type: Mapped[Optional[str]] = mapped_column(String(20), comment="射门类型")
    situation: Mapped[Optional[str]] = mapped_column(String(20), comment="射门情境")
    xg: Mapped[Optional[float]] = mapped_column(Float, comment="预期进球")
    data_source: Mapped[Optional[str]] = mapped_column(String(50), comment="来源标识")
    source_id: Mapped[Optional[str]] = mapped_column(String(100), comment="源端ID")
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后更新时间")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    data_hash: Mapped[Optional[str]] = mapped_column(String(64), comment="内容指纹")

    # 关联关系
    match: Mapped[Optional["Match"]] = relationship("Match")
    player: Mapped[Optional["Player"]] = relationship("Player")
    team: Mapped[Optional["Team"]] = relationship("Team")
