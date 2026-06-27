"""球队评分模块 — 基于攻防数据计算综合评分"""


class TeamRating:
    """球队攻防评分计算"""

    # 进攻维度参考范围（用于归一化）
    ATTACK_RANGES = {
        "xg": (0.0, 3.0),       # 预期进球
        "shots": (0.0, 25.0),   # 射门数
        "goals": (0.0, 6.0),    # 实际进球
    }
    # 防守维度参考范围
    DEFENSE_RANGES = {
        "xga": (0.0, 3.0),      # 预期失球（越低越好）
        "tackles": (0.0, 30.0), # 抢断数
        "conceded": (0.0, 6.0), # 失球数（越低越好）
    }

    @staticmethod
    def normalize(value: float, min_val: float, max_val: float) -> float:
        """将数值归一化到 0-100 区间"""
        if max_val == min_val:
            return 50.0
        ratio = (value - min_val) / (max_val - min_val)
        ratio = max(0.0, min(1.0, ratio))
        return ratio * 100.0

    def calculate_attack_rating(self, stats: dict) -> float:
        """进攻评分: 综合 xG、射门、进球"""
        xg = stats.get("xg", 0.0)
        shots = stats.get("shots", 0)
        goals = stats.get("goals", 0)
        xg_lo, xg_hi = self.ATTACK_RANGES["xg"]
        shots_lo, shots_hi = self.ATTACK_RANGES["shots"]
        goals_lo, goals_hi = self.ATTACK_RANGES["goals"]
        # 权重: xG 0.4, 射门 0.2, 进球 0.4
        return (
            self.normalize(xg, xg_lo, xg_hi) * 0.4
            + self.normalize(shots, shots_lo, shots_hi) * 0.2
            + self.normalize(goals, goals_lo, goals_hi) * 0.4
        )

    def calculate_defense_rating(self, stats: dict) -> float:
        """防守评分: 综合 xGA、抢断、失球（失球与 xGA 越低越好）"""
        xga = stats.get("xga", 0.0)
        tackles = stats.get("tackles", 0)
        conceded = stats.get("conceded", 0)
        xga_lo, xga_hi = self.DEFENSE_RANGES["xga"]
        tackles_lo, tackles_hi = self.DEFENSE_RANGES["tackles"]
        conceded_lo, conceded_hi = self.DEFENSE_RANGES["conceded"]
        # 防守反向指标：越低得分越高
        xg_score = 100.0 - self.normalize(xga, xga_lo, xga_hi)
        tackle_score = self.normalize(tackles, tackles_lo, tackles_hi)
        conceded_score = 100.0 - self.normalize(conceded, conceded_lo, conceded_hi)
        # 权重: xGA 0.35, 抢断 0.25, 失球 0.4
        return xg_score * 0.35 + tackle_score * 0.25 + conceded_score * 0.4

    def calculate_overall(self, stats: dict) -> dict:
        """综合评分 = 0.5 * 进攻 + 0.5 * 防守"""
        attack = self.calculate_attack_rating(stats)
        defense = self.calculate_defense_rating(stats)
        overall = attack * 0.5 + defense * 0.5
        return {
            "attack": round(attack, 2),
            "defense": round(defense, 2),
            "overall": round(overall, 2),
        }
