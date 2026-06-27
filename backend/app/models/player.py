"""球员模型 — 球员基础信息及评分"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Player(Base):
    """球员表"""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), comment="所属球队ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="球员姓名")
    position: Mapped[Optional[str]] = mapped_column(String(20), comment="位置")
    shirt_number: Mapped[Optional[int]] = mapped_column(Integer, comment="球衣号码")
    nationality: Mapped[Optional[str]] = mapped_column(String(50), comment="国籍")
    birth_date: Mapped[Optional[date]] = mapped_column(Date, comment="出生日期")
    height: Mapped[Optional[int]] = mapped_column(Integer, comment="身高(cm)")
    weight: Mapped[Optional[int]] = mapped_column(Integer, comment="体重(kg)")
    photo_url: Mapped[Optional[str]] = mapped_column(String(255), comment="球员照片地址")

    # 门将专属字段
    saves: Mapped[int] = mapped_column(Integer, default=0, comment="扑救次数")
    save_rate: Mapped[float] = mapped_column(Float, default=0, comment="扑救成功率")
    xcs: Mapped[float] = mapped_column(Float, default=0, comment="预期失球")
    sweeper_actions: Mapped[int] = mapped_column(Integer, default=0, comment="清道夫动作次数")

    # 评分字段
    atk_score: Mapped[float] = mapped_column(Float, default=0, comment="进攻评分")
    org_score: Mapped[float] = mapped_column(Float, default=0, comment="组织评分")
    def_score: Mapped[float] = mapped_column(Float, default=0, comment="防守评分")
    gk_score: Mapped[float] = mapped_column(Float, default=0, comment="门将评分")
    phy_score: Mapped[float] = mapped_column(Float, default=0, comment="身体评分")
    dis_score: Mapped[float] = mapped_column(Float, default=0, comment="纪律评分")
    overall_rating: Mapped[float] = mapped_column(Float, default=0, comment="综合评分")

    # 增量字段
    data_source: Mapped[Optional[str]] = mapped_column(String(50), comment="来源标识")
    source_id: Mapped[Optional[str]] = mapped_column(String(100), comment="源端ID")
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后更新时间")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    data_hash: Mapped[Optional[str]] = mapped_column(String(64), comment="内容指纹")

    # 关联球队
    team: Mapped[Optional["Team"]] = relationship("Team")
