"""数据源模型 — 爬虫数据源配置"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DataSource(Base):
    """数据源配置表"""

    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="来源代码")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="数据源名称")
    type: Mapped[str] = mapped_column(String(20), default="html", comment="类型")
    base_url: Mapped[Optional[str]] = mapped_column(String(255), comment="基础URL")
    api_key: Mapped[Optional[str]] = mapped_column(String(255), comment="API密钥")
    priority: Mapped[int] = mapped_column(Integer, default=0, comment="优先级")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    status: Mapped[str] = mapped_column(String(20), default="idle", comment="状态")
    last_crawl_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后爬取时间")
    error_count: Mapped[int] = mapped_column(Integer, default=0, comment="错误次数")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="描述")
