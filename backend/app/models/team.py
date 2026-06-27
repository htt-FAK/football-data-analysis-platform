"""球队模型 — 球队基础信息"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Team(Base):
    """球队表"""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="球队名称")
    full_name: Mapped[Optional[str]] = mapped_column(String(200), comment="球队全称")
    country: Mapped[Optional[str]] = mapped_column(String(50), comment="国家")
    logo_url: Mapped[Optional[str]] = mapped_column(String(255), comment="球队Logo地址")
    stadium: Mapped[Optional[str]] = mapped_column(String(100), comment="主场")
    coach: Mapped[Optional[str]] = mapped_column(String(100), comment="主教练")
    founded_year: Mapped[Optional[int]] = mapped_column(Integer, comment="成立年份")
    data_source: Mapped[Optional[str]] = mapped_column(String(50), comment="来源标识")
    source_id: Mapped[Optional[str]] = mapped_column(String(100), comment="源端ID")
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后更新时间")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    data_hash: Mapped[Optional[str]] = mapped_column(String(64), comment="内容指纹")
