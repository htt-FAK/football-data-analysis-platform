"""联赛分析模块 — 竞争度、争冠保级集团、射手榜"""

import statistics


class LeagueAnalysis:
    """联赛多维度分析"""

    def calculate_competitiveness(self, standings: list) -> float:
        """联赛竞争度：基于各队积分差的标准差"""
        if len(standings) < 2:
            return 0.0
        points = [row.get("points", 0) for row in standings]
        stdev = statistics.pstdev(points)
        # 标准差越小竞争越激烈；转换为 0-100 分值（标准差越大得分越低）
        # 经验上 30 分以上的标准差对应极不平衡的联赛
        score = max(0.0, 100.0 - stdev * 3.3)
        return round(score, 2)

    def get_title_race(self, standings: list, gap: int = 8) -> list:
        """争冠集团：与榜首积分差不超过 gap 的球队"""
        if not standings:
            return []
        sorted_table = sorted(standings, key=lambda r: r.get("points", 0), reverse=True)
        top_points = sorted_table[0].get("points", 0)
        title_race = [
            r for r in sorted_table
            if top_points - r.get("points", 0) <= gap
        ]
        return title_race

    def get_relegation_battle(self, standings: list) -> list:
        """保级集团：积分榜末尾 3 名及与之积分差不超过 5 分的球队"""
        if not standings:
            return []
        sorted_table = sorted(standings, key=lambda r: r.get("points", 0))
        # 末尾 3 名视为降级区
        relegation_zone = sorted_table[:3]
        if not relegation_zone:
            return []
        # 降级区最高分作为基准，向上扩展 5 分内的球队均纳入保级集团
        threshold = relegation_zone[-1].get("points", 0) + 5
        return [r for r in sorted_table if r.get("points", 0) <= threshold]

    def get_top_scorers_chart(self, player_stats: list) -> list:
        """射手榜：按进球数降序排列（进球相同时按助攻数排序）"""
        scorer_rows = [p for p in player_stats if p.get("goals", 0) > 0]
        scorer_rows.sort(
            key=lambda p: (p.get("goals", 0), p.get("assists", 0)),
            reverse=True,
        )
        return scorer_rows
