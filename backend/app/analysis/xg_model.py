"""xG 模型模块 — 预期进球分析"""

import requests


class XGModel:
    """预期进球（xG）分析"""

    UNDERSTAT_BASE = "https://understat.com"

    def get_xg_from_understat(self, match_id: int) -> dict:
        """直接使用 Understat 现成 xG 值"""
        # Understat 通过 match 页面提供单场 xG
        url = f"{self.UNDERSTAT_BASE}/match/{match_id}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException:
            # 请求失败时返回占位结构，避免阻断流程
            return {
                "match_id": match_id,
                "home_xg": None,
                "away_xg": None,
                "source": "understat",
            }
        # Understat 页面中 xG 数据以 JSON-Like 形式内嵌于 scripts，
        # 真实场景需解析页面 scripts 中的 JSON 数据
        return {
            "match_id": match_id,
            "home_xg": None,
            "away_xg": None,
            "shots": [],
            "source": "understat",
        }

    def calculate_xg_timeline(self, shots: list) -> dict:
        """累计 xG 曲线：按分钟累积主客队 xG"""
        home_timeline = []
        away_timeline = []
        home_cum = 0.0
        away_cum = 0.0
        # 按分钟排序
        sorted_shots = sorted(shots, key=lambda s: s.get("minute", 0))
        for shot in sorted_shots:
            minute = shot.get("minute", 0)
            xg = shot.get("xg", 0.0)
            side = shot.get("side", "home")
            if side == "home":
                home_cum += xg
                home_timeline.append({"minute": minute, "cum_xg": round(home_cum, 3)})
            else:
                away_cum += xg
                away_timeline.append({"minute": minute, "cum_xg": round(away_cum, 3)})
        return {
            "home": home_timeline,
            "away": away_timeline,
            "final_home_xg": round(home_cum, 3),
            "final_away_xg": round(away_cum, 3),
        }

    def calculate_xg_performance(self, goals: int, xg: float) -> str:
        """超常发挥 / 正常 / 低于预期"""
        if xg <= 0:
            return "无数据" if goals == 0 else "超常发挥"
        diff = goals - xg
        # 阈值：超出预期 0.5 球视为超常发挥，低于预期 0.5 球视为低于预期
        if diff >= 0.5:
            return "超常发挥"
        if diff <= -0.5:
            return "低于预期"
        return "正常"
