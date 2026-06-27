"""球员服务层 — 球员列表、详情、统计、雷达、射手榜、对比、位置统计"""

from sqlalchemy.orm import Session


class PlayerService:
    """球员相关业务逻辑"""

    def __init__(self):
        """无参构造"""
        pass

    def get_players(self, db: Session, team_id: int = None, position: str = None) -> list:
        """获取球员列表，可按球队与位置过滤

        Args:
            db: SQLAlchemy 会话
            team_id: 球队 ID（可选过滤条件）
            position: 位置代码（可选过滤条件，如 GK/DF/MF/FW）

        Returns:
            list[dict]: 球员信息列表
        """
        # TODO: 查询 Player Model，按 team_id / position 过滤
        return []

    def get_player_detail(self, db: Session, player_id: int) -> dict:
        """获取球员详情

        Args:
            db: SQLAlchemy 会话
            player_id: 球员 ID

        Returns:
            dict: 球员基础信息（姓名、国籍、位置、身高体重等）
        """
        # TODO: 查询 Player Model，按 player_id 过滤，返回单条记录字典
        return {}

    def get_player_stats(self, db: Session, player_id: int) -> dict:
        """获取球员统计数据

        Args:
            db: SQLAlchemy 会话
            player_id: 球员 ID

        Returns:
            dict: 球员统计（进球、助攻、出场、xG、xA 等）
        """
        # TODO: 查询 PlayerStat Model，按 player_id 过滤，返回统计字典
        return {}

    def get_player_radar(self, db: Session, player_id: int, position: str = None) -> dict:
        """获取球员雷达数据，按位置返回不同维度

        Args:
            db: SQLAlchemy 会话
            player_id: 球员 ID
            position: 位置代码（可选，决定雷达维度选择）

        Returns:
            dict: 雷达图数据，不同位置使用不同维度集合（归一化 0-100）
        """
        # TODO: 按 position 选择维度集合
        #       GK: 扑救率、出击、高空球、传球
        #       DF: 抢断、拦截、解围、对抗、传球
        #       MF: 传球、关键传球、抢断、过人、射门
        #       FW: 进球、助攻、射门、过人、对抗
        #       各维度按位置均值/最大值归一化
        return {}

    def get_top_scorers(self, db: Session, limit: int = 10) -> list:
        """获取射手榜

        Args:
            db: SQLAlchemy 会话
            limit: 返回条数，默认 10

        Returns:
            list[dict]: 射手榜列表，按进球数降序
        """
        # TODO: 查询 PlayerStat，按 goals 降序排序，取前 limit 条
        #       关联 Player 表返回球员姓名、球队等
        return []

    def compare_players(self, db: Session, player_a: int, player_b: int) -> dict:
        """对比两名球员

        Args:
            db: SQLAlchemy 会话
            player_a: 球员 A 的 ID
            player_b: 球员 B 的 ID

        Returns:
            dict: 对比数据，包含两名球员的统计与雷达维度差值
        """
        # TODO: 分别查询两名球员的统计，按相同维度对齐返回
        #       可复用 get_player_stats / get_player_radar
        return {}

    def get_position_stats(self, db: Session, position: str) -> dict:
        """获取某位置的统计分布（箱线图数据）

        Args:
            db: SQLAlchemy 会话
            position: 位置代码

        Returns:
            dict: 箱线图数据，包含各维度的 min/q1/median/q3/max/outliers
        """
        # TODO: 查询该位置所有球员统计，按关键维度计算分位数
        #       返回箱线图所需的五数概括与异常值列表
        return {}

    def get_position_rank(self, db: Session, player_id: int) -> dict:
        """获取球员在同位置中的排名

        Args:
            db: SQLAlchemy 会话
            player_id: 球员 ID

        Returns:
            dict: 排名信息（位置、总人数、球员排名、各维度排名）
        """
        # TODO: 查询球员位置，统计同位置球员数量
        #       按核心维度（进球、助攻、xG 等）计算球员排名
        return {}
