"""比赛事件模型 — 进球/换人/红黄牌等事件"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MatchEvent(Base):
    """比赛事件表"""

    __tablename__ = "match_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("matches.id"), comment="比赛ID")
    minute: Mapped[Optional[int]] = mapped_column(Integer, comment="分钟")
    event_type: Mapped[Optional[str]] = mapped_column(String(20), comment="事件类型")
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), comment="球队ID")
    player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"), comment="球员ID")
    detail: Mapped[Optional[str]] = mapped_column(String(200), comment="事件详情")

    # 关联关系
    match: Mapped[Optional["Match"]] = relationship("Match")
    team: Mapped[Optional["Team"]] = relationship("Team")
    player: Mapped[Optional["Player"]] = relationship("Player")
