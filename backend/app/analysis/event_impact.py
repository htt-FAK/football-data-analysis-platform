"""比赛事件影响度模块 — 进球/卡牌影响、动量曲线、关键事件"""


class EventImpact:
    """比赛事件影响度计算"""

    # 关键事件类型
    KEY_EVENT_TYPES = {"goal", "red_card", "penalty", "substitution"}

    # 事件强度映射（用于动量曲线）
    STRENGTH_MAP = {
        "goal": 5,
        "shot_on_target": 2,
        "shot_off_target": 1,
        "corner": 1,
        "yellow": -1,
        "red": -3,
    }

    def calculate_goal_impact(self, match_state: dict, goal_minute: int) -> float:
        """进球影响度：综合比分差、剩余时间"""
        home = match_state.get("home_score", 0)
        away = match_state.get("away_score", 0)
        total_minute = match_state.get("total_minutes", 90)
        # 当前比分差（绝对值越大影响越显著）
        diff = abs(home - away)
        # 剩余时间比例：越接近终场影响越大
        remaining_ratio = max(0.0, (total_minute - goal_minute) / total_minute)
        # 进球使比分扳平/反超时影响加成
        leverage = 1.0
        if diff == 0:
            leverage = 1.5  # 扳平
        elif diff == 1:
            leverage = 1.2  # 扩大或缩小到 1 球
        # 影响度 = 时间衰减 × 比分差权重 × 杠杆系数
        impact = (1.0 - remaining_ratio * 0.5) * (1.0 + diff * 0.2) * leverage
        return round(min(100.0, impact * 50.0), 2)

    def calculate_card_impact(self, match_state: dict, card_type: str) -> float:
        """卡牌影响度：黄牌 20、红牌 80"""
        if card_type == "red":
            base = 80.0
        elif card_type == "yellow":
            base = 20.0
        else:
            base = 10.0
        # 比分越接近，卡牌影响越大
        home = match_state.get("home_score", 0)
        away = match_state.get("away_score", 0)
        if abs(home - away) <= 1:
            base *= 1.2
        return round(min(100.0, base), 2)

    def get_momentum_curve(self, events: list) -> list:
        """比赛动量曲线：按分钟累加主客队事件强度"""
        if not events:
            return []
        sorted_events = sorted(events, key=lambda e: e.get("minute", 0))
        curve = []
        for event in sorted_events:
            minute = event.get("minute", 0)
            side = event.get("side", "home")
            etype = event.get("type", "")
            strength = self.STRENGTH_MAP.get(etype, 0)
            curve.append({
                "minute": minute,
                "side": side,
                "event": etype,
                "momentum": strength,
            })
        return curve

    def get_key_events(self, events: list) -> list:
        """关键事件筛选：进球、红牌、点球、换人"""
        return [
            e for e in events
            if e.get("type") in self.KEY_EVENT_TYPES
        ]
