"""球员评分模块 — 按位置加权计算综合评分与雷达图数据"""


class PlayerRating:
    """球员综合评分计算（基于位置权重）"""

    # 各位置维度权重
    POSITION_WEIGHTS = {
        "FW": {  # 前锋
            "atk": 0.4, "org": 0.2, "def": 0.1, "phy": 0.15, "dis": 0.15,
        },
        "MF": {  # 中场
            "atk": 0.25, "org": 0.35, "def": 0.2, "phy": 0.1, "dis": 0.1,
        },
        "DF": {  # 后卫
            "atk": 0.1, "org": 0.2, "def": 0.45, "phy": 0.15, "dis": 0.1,
        },
        "GK": {  # 门将
            "gk": 0.5, "org": 0.2, "phy": 0.15, "dis": 0.15,
        },
    }

    # 雷达图维度顺序
    RADAR_DIMENSIONS = {
        "FW": ["atk", "org", "def", "phy", "dis"],
        "MF": ["atk", "org", "def", "phy", "dis"],
        "DF": ["atk", "org", "def", "phy", "dis"],
        "GK": ["gk", "org", "phy", "dis"],
    }

    # 维度中文标签
    DIMENSION_LABELS = {
        "atk": "进攻", "org": "组织", "def": "防守",
        "phy": "身体", "dis": "纪律", "gk": "门将",
    }

    def calculate_overall(self, position: str, scores: dict) -> float:
        """按位置加权计算综合评分"""
        weights = self.POSITION_WEIGHTS.get(position)
        if weights is None:
            # 未知位置使用中场权重兜底
            weights = self.POSITION_WEIGHTS["MF"]
        total = 0.0
        for dim, weight in weights.items():
            total += scores.get(dim, 0.0) * weight
        return round(total, 2)

    def get_radar_data(self, position: str, scores: dict) -> dict:
        """返回雷达图维度数据"""
        dims = self.RADAR_DIMENSIONS.get(position, self.RADAR_DIMENSIONS["MF"])
        return {
            "dimensions": [self.DIMENSION_LABELS[d] for d in dims],
            "values": [scores.get(d, 0.0) for d in dims],
            "position": position,
            "overall": self.calculate_overall(position, scores),
        }
