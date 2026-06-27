"""数据源服务层 — 健康状态、爬取日志、源状态更新"""

from sqlalchemy.orm import Session


class DataSourceService:
    """数据源管理相关业务逻辑"""

    def __init__(self):
        """无参构造"""
        pass

    def get_health_status(self, db: Session) -> list:
        """获取各数据源健康状态

        Args:
            db: SQLAlchemy 会话

        Returns:
            list[dict]: 各数据源健康状态（源名称、状态、最近更新时间、成功率等）
        """
        # TODO: 查询 DataSource Model，返回各源的健康状态
        #       可关联最近一次 CrawlLog 统计成功率与延迟
        return []

    def get_crawl_logs(self, db: Session, source_id: int = None, limit: int = 50) -> list:
        """获取爬取日志

        Args:
            db: SQLAlchemy 会话
            source_id: 数据源 ID（可选过滤条件）
            limit: 返回条数，默认 50

        Returns:
            list[dict]: 爬取日志列表，按时间倒序
        """
        # TODO: 查询 CrawlLog Model，按 source_id 过滤
        #       按 created_at 倒序排序，取前 limit 条
        return []

    def update_source_status(self, db: Session, source_id: int, status: str) -> None:
        """更新数据源状态

        Args:
            db: SQLAlchemy 会话
            source_id: 数据源 ID
            status: 新状态（如 healthy/degraded/down）
        """
        # TODO: 查询 DataSource，更新 status 字段并提交
        #       db.query(DataSource).filter(DataSource.id == source_id).update({"status": status})
        #       db.commit()
        return None
