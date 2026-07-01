"""Player rating utilities for dimension scoring and radar readiness."""

from __future__ import annotations


class PlayerRating:
    """Compute position-aware player dimension scores on a 0-100 scale."""

    POSITION_WEIGHTS = {
        "FW": {"atk": 0.4, "org": 0.2, "def": 0.1, "phy": 0.15, "dis": 0.15},
        "MF": {"atk": 0.25, "org": 0.35, "def": 0.2, "phy": 0.1, "dis": 0.1},
        "DF": {"atk": 0.1, "org": 0.2, "def": 0.45, "phy": 0.15, "dis": 0.1},
        "GK": {"gk": 0.5, "org": 0.2, "phy": 0.15, "dis": 0.15},
    }

    RADAR_DIMENSIONS = {
        "FW": ["atk", "org", "def", "phy", "dis"],
        "MF": ["atk", "org", "def", "phy", "dis"],
        "DF": ["atk", "org", "def", "phy", "dis"],
        "GK": ["gk", "org", "phy", "dis"],
    }

    DIMENSION_LABELS = {
        "atk": "进攻",
        "org": "组织",
        "def": "防守",
        "phy": "身体",
        "dis": "纪律",
        "gk": "门将",
    }

    @staticmethod
    def normalize(value: float, min_val: float, max_val: float, *, inverse: bool = False) -> float:
        """Normalize to 0-100, optionally reversing the score direction."""
        if max_val <= min_val:
            return 50.0
        ratio = (float(value) - min_val) / (max_val - min_val)
        ratio = max(0.0, min(1.0, ratio))
        score = ratio * 100.0
        if inverse:
            score = 100.0 - score
        return round(score, 2)

    def calculate_dimension_scores(self, position: str | None, stats: dict) -> dict[str, float]:
        """Compute per-dimension scores using only currently available player stats."""
        pos = position if position in self.POSITION_WEIGHTS else "MF"

        goals = float(stats.get("goals") or 0)
        assists = float(stats.get("assists") or 0)
        xg = float(stats.get("xg") or 0)
        xa = float(stats.get("xa") or 0)
        shots = float(stats.get("shots") or 0)
        shots_on_target = float(stats.get("shots_on_target") or 0)
        passes = float(stats.get("passes") or 0)
        pass_accuracy = float(stats.get("pass_accuracy") or 0)
        tackles = float(stats.get("tackles") or 0)
        interceptions = float(stats.get("interceptions") or 0)
        rating = float(stats.get("rating") or 0)
        yellow_cards = float(stats.get("yellow_cards") or 0)
        red_cards = float(stats.get("red_cards") or 0)
        minutes_played = float(stats.get("minutes_played") or 0)
        appearances = float(stats.get("appearances") or 0)
        saves = float(stats.get("saves") or 0)
        save_rate = float(stats.get("save_rate") or 0)
        xcs = float(stats.get("xcs") or 0)
        sweeper_actions = float(stats.get("sweeper_actions") or 0)

        attack_score = (
            self.normalize(goals, 0, 6) * 0.34
            + self.normalize(xg, 0, 3) * 0.24
            + self.normalize(shots_on_target, 0, 10) * 0.20
            + self.normalize(shots, 0, 18) * 0.12
            + self.normalize(rating, 0, 10) * 0.10
        )
        organization_score = (
            self.normalize(assists, 0, 4) * 0.28
            + self.normalize(xa, 0, 2) * 0.18
            + self.normalize(passes, 0, 180) * 0.24
            + self.normalize(pass_accuracy, 40, 100) * 0.22
            + self.normalize(rating, 0, 10) * 0.08
        )
        defense_score = (
            self.normalize(tackles, 0, 15) * 0.42
            + self.normalize(interceptions, 0, 12) * 0.32
            + self.normalize(pass_accuracy, 40, 100) * 0.08
            + self.normalize(minutes_played, 0, 300) * 0.08
            + self.normalize(rating, 0, 10) * 0.10
        )
        physical_score = (
            self.normalize(minutes_played, 0, 300) * 0.40
            + self.normalize(appearances, 0, 4) * 0.20
            + self.normalize(shots + tackles + interceptions, 0, 25) * 0.16
            + self.normalize(pass_accuracy, 40, 100) * 0.08
            + self.normalize(rating, 0, 10) * 0.16
        )
        discipline_score = (
            self.normalize(yellow_cards, 0, 4, inverse=True) * 0.55
            + self.normalize(red_cards, 0, 1, inverse=True) * 0.35
            + self.normalize(pass_accuracy, 40, 100) * 0.05
            + self.normalize(rating, 0, 10) * 0.05
        )
        goalkeeping_score = (
            self.normalize(saves, 0, 20) * 0.34
            + self.normalize(save_rate, 40, 100) * 0.34
            + self.normalize(xcs, 0, 3) * 0.16
            + self.normalize(sweeper_actions, 0, 10) * 0.08
            + self.normalize(rating, 0, 10) * 0.08
        )

        scores = {
            "atk": round(attack_score, 2),
            "org": round(organization_score, 2),
            "def": round(defense_score, 2),
            "phy": round(physical_score, 2),
            "dis": round(discipline_score, 2),
            "gk": round(goalkeeping_score, 2),
        }

        if pos == "GK":
            scores["def"] = round((scores["def"] * 0.55 + scores["gk"] * 0.45), 2)

        return scores

    def calculate_overall(self, position: str | None, scores: dict[str, float]) -> float:
        """Calculate weighted overall rating from dimension scores."""
        pos = position if position in self.POSITION_WEIGHTS else "MF"
        weights = self.POSITION_WEIGHTS[pos]
        total = 0.0
        for dim, weight in weights.items():
            total += scores.get(dim, 0.0) * weight
        return round(total, 2)

    def get_radar_data(self, position: str | None, scores: dict[str, float]) -> dict:
        """Return radar labels and values for the given position."""
        pos = position if position in self.RADAR_DIMENSIONS else "MF"
        dims = self.RADAR_DIMENSIONS[pos]
        return {
            "dimensions": [self.DIMENSION_LABELS[d] for d in dims],
            "values": [scores.get(d, 0.0) for d in dims],
            "position": pos,
            "overall": self.calculate_overall(pos, scores),
        }
