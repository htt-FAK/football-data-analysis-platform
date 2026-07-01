"""积分榜模型 — 联赛积分榜"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Standings(Base):
    """积分榜表"""

    __tablename__ = "standings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[int] = mapped_column(Integer, ForeignKey("seasons.id"), nullable=False, comment="赛季ID")
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False, comment="球队ID")
    position: Mapped[Optional[int]] = mapped_column(Integer, comment="排名")
    played: Mapped[int] = mapped_column(Integer, default=0, comment="已赛场次")
    won: Mapped[int] = mapped_column(Integer, default=0, comment="胜场")
    drawn: Mapped[int] = mapped_column(Integer, default=0, comment="平场")
    lost: Mapped[int] = mapped_column(Integer, default=0, comment="负场")
    goals_for: Mapped[int] = mapped_column(Integer, default=0, comment="进球数")
    goals_against: Mapped[int] = mapped_column(Integer, default=0, comment="失球数")
    goal_diff: Mapped[int] = mapped_column(Integer, default=0, comment="净胜球")
    points: Mapped[int] = mapped_column(Integer, default=0, comment="积分")
    form: Mapped[Optional[str]] = mapped_column(String(50), comment="近期状态")
    group_name: Mapped[Optional[str]] = mapped_column(String(50), comment="分组")
    stage: Mapped[Optional[str]] = mapped_column(String(50), comment="阶段")
    qualification_status: Mapped[Optional[str]] = mapped_column(String(50), comment="出线状态")
    data_source: Mapped[Optional[str]] = mapped_column(String(50), comment="来源标识")
    source_id: Mapped[Optional[str]] = mapped_column(String(100), comment="源端ID")
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后更新时间")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    data_hash: Mapped[Optional[str]] = mapped_column(String(64), comment="内容指纹")

    # 关联关系
    season: Mapped["Season"] = relationship("Season")
    team: Mapped["Team"] = relationship("Team")
