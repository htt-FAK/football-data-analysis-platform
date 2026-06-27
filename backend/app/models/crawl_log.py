"""爬取日志模型 — 爬虫运行日志"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CrawlLog(Base):
    """爬取日志表"""

    __tablename__ = "crawl_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=False, comment="数据源ID")
    target: Mapped[Optional[str]] = mapped_column(String(200), comment="爬取目标")
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="开始时间")
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="结束时间")
    fetched: Mapped[int] = mapped_column(Integer, default=0, comment="抓取数量")
    updated: Mapped[int] = mapped_column(Integer, default=0, comment="更新数量")
    failed: Mapped[int] = mapped_column(Integer, default=0, comment="失败数量")
    cost_ms: Mapped[int] = mapped_column(Integer, default=0, comment="耗时(毫秒)")
    status: Mapped[str] = mapped_column(String(20), default="running", comment="状态")
    error_msg: Mapped[Optional[str]] = mapped_column(Text, comment="错误信息")

    # 关联数据源
    data_source: Mapped["DataSource"] = relationship("DataSource")
