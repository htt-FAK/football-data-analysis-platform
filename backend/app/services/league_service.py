"""联赛服务层 — 联赛列表、积分榜、赛程、趋势"""

from sqlalchemy.orm import Session


class LeagueService:
    """联赛相关业务逻辑"""

    def __init__(self):
        """无参构造"""
        pass

    def get_leagues(self, db: Session, country: str = None) -> list:
        """获取联赛列表，可按国家过滤

        Args:
            db: SQLAlchemy 会话
            country: 国家名称（可选过滤条件）

        Returns:
            list[dict]: 联赛信息列表
        """
        # TODO: 导入 League Model，按 country 过滤查询
        # 示例: query = db.query(League)
        #       if country: query = query.filter(League.country == country)
        #       return [league.to_dict() for league in query.all()]
        return []

    def get_standings(self, db: Session, league_id: int, season_id: int = None) -> list:
        """获取联赛积分榜

        Args:
            db: SQLAlchemy 会话
            league_id: 联赛 ID
            season_id: 赛季 ID（可选，默认取最新赛季）

        Returns:
            list[dict]: 积分榜数据，按积分排序
        """
        # TODO: 查询 Standing Model，按 league_id + season_id 过滤
        #       若 season_id 为空，需先查询最新赛季 ID
        #       按 points 降序、goal_difference 降序排序
        return []

    def get_schedule(self, db: Session, league_id: int, matchday: int = None) -> list:
        """获取联赛赛程

        Args:
            db: SQLAlchemy 会话
            league_id: 联赛 ID
            matchday: 比赛日（可选过滤条件）

        Returns:
            list[dict]: 赛程列表，按比赛时间排序
        """
        # TODO: 查询 Match Model，按 league_id 过滤
        #       若 matchday 提供则进一步过滤
        #       按 matchday / kickoff_time 升序排序
        return []

    def get_trends(self, db: Session, league_id: int) -> list:
        """获取联赛趋势数据（多赛季冠军、进球趋势等）

        Args:
            db: SQLAlchemy 会话
            league_id: 联赛 ID

        Returns:
            list[dict]: 趋势数据列表
        """
        # TODO: 聚合多赛季数据，统计冠军球队、场均进球等趋势指标
        #       可关联 Standing / Match / Season 多表
        return []
