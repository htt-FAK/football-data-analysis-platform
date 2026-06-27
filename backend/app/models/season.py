"""赛季模型 — 联赛赛季信息"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Season(Base):
    """赛季表"""

    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=False, comment="联赛ID")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="赛季名称")
    start_date: Mapped[Optional[date]] = mapped_column(Date, comment="开始日期")
    end_date: Mapped[Optional[date]] = mapped_column(Date, comment="结束日期")
    current_matchday: Mapped[Optional[int]] = mapped_column(Integer, comment="当前比赛日")
    data_source: Mapped[Optional[str]] = mapped_column(String(50), comment="来源标识")
    source_id: Mapped[Optional[str]] = mapped_column(String(100), comment="源端ID")
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后更新时间")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    data_hash: Mapped[Optional[str]] = mapped_column(String(64), comment="内容指纹")

    # 关联联赛
    league: Mapped["League"] = relationship("League")
