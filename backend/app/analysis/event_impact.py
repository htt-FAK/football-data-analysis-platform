"""Match event impact helpers for timeline and presentation analysis."""

from __future__ import annotations


class EventImpact:
    """Compute event importance and a simple momentum timeline."""

    KEY_EVENT_TYPES = {
        "goal",
        "red",
        "red_card",
        "penalty",
        "substitution",
        "yellow",
        "yellow_card",
    }

    STRENGTH_MAP = {
        "goal": 5,
        "penalty": 4,
        "substitution": 1,
        "shot_on_target": 2,
        "shot_off_target": 1,
        "corner": 1,
        "yellow": -1,
        "yellow_card": -1,
        "red": -3,
        "red_card": -3,
    }

    def calculate_goal_impact(self, match_state: dict, goal_minute: int) -> float:
        """Estimate goal impact from score context and match minute."""

        home = match_state.get("home_score", 0)
        away = match_state.get("away_score", 0)
        total_minute = max(int(match_state.get("total_minutes", 90) or 90), 1)
        diff = abs(home - away)
        remaining_ratio = max(0.0, (total_minute - goal_minute) / total_minute)

        leverage = 1.0
        if diff == 0:
            leverage = 1.5
        elif diff == 1:
            leverage = 1.2

        impact = (1.0 - remaining_ratio * 0.5) * (1.0 + diff * 0.2) * leverage
        return round(min(100.0, impact * 50.0), 2)

    def calculate_card_impact(self, match_state: dict, card_type: str) -> float:
        """Estimate disciplinary impact with a stronger penalty for red cards."""

        normalized_type = self.normalize_event_type(card_type)
        if normalized_type in {"red", "red_card"}:
            base = 80.0
        elif normalized_type in {"yellow", "yellow_card"}:
            base = 20.0
        else:
            base = 10.0

        home = match_state.get("home_score", 0)
        away = match_state.get("away_score", 0)
        if abs(home - away) <= 1:
            base *= 1.2
        return round(min(100.0, base), 2)

    def get_momentum_curve(self, events: list[dict]) -> list[dict]:
        """Build a cumulative home-away momentum curve from ordered events."""

        if not events:
            return []

        sorted_events = sorted(events, key=lambda e: ((e.get("minute") or 0), e.get("id") or 0))
        home_momentum = 0
        away_momentum = 0
        curve = []
        for event in sorted_events:
            minute = event.get("minute", 0) or 0
            side = event.get("side", "neutral")
            event_type = self.normalize_event_type(event.get("type") or event.get("event_type"))
            strength = self.STRENGTH_MAP.get(event_type, 0)

            if side == "home":
                home_momentum += strength
            elif side == "away":
                away_momentum += strength

            curve.append(
                {
                    "minute": minute,
                    "side": side,
                    "event": event_type,
                    "swing": strength,
                    "home_momentum": home_momentum,
                    "away_momentum": away_momentum,
                    "net_momentum": home_momentum - away_momentum,
                }
            )
        return curve

    def get_key_events(self, events: list[dict]) -> list[dict]:
        """Keep only presentation-worthy key events."""

        return [
            event
            for event in events
            if self.normalize_event_type(event.get("type") or event.get("event_type")) in self.KEY_EVENT_TYPES
        ]

    @staticmethod
    def normalize_event_type(event_type: str | None) -> str:
        if not event_type:
            return ""
        lowered = str(event_type).strip().lower()
        aliases = {
            "yellow_card": "yellow_card",
            "yellow": "yellow_card",
            "red_card": "red_card",
            "red": "red_card",
            "goal": "goal",
            "penalty": "penalty",
            "substitution": "substitution",
        }
        return aliases.get(lowered, lowered)
