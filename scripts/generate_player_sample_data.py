"""生成球员层样本数据（与项目 players / player_stats 结构对齐）。

用途：
- 当前真实源稳定性不足时，为项目提供可展示的球员基础信息与基础统计样本
- 后续可替换为真实 API / 官方数据源，不影响字段结构
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = PROJECT_ROOT / "export" / "sample_players"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

TEAMS = [
    {"team_id": 1, "team_name": "阿根廷", "group": "A"},
    {"team_id": 2, "team_name": "法国", "group": "A"},
    {"team_id": 3, "team_name": "巴西", "group": "B"},
    {"team_id": 4, "team_name": "英格兰", "group": "B"},
]

PLAYERS = [
    {"team_id": 1, "name": "L. Messi", "position": "FW", "shirt_number": 10, "nationality": "阿根廷", "height": 170, "weight": 72, "overall_rating": 9.4, "atk_score": 9.8, "org_score": 9.6, "def_score": 5.2, "phy_score": 7.0, "dis_score": 8.7},
    {"team_id": 1, "name": "J. Álvarez", "position": "FW", "shirt_number": 9, "nationality": "阿根廷", "height": 170, "weight": 71, "overall_rating": 8.4, "atk_score": 8.8, "org_score": 7.5, "def_score": 5.8, "phy_score": 7.4, "dis_score": 8.0},
    {"team_id": 2, "name": "K. Mbappé", "position": "FW", "shirt_number": 10, "nationality": "法国", "height": 178, "weight": 75, "overall_rating": 9.3, "atk_score": 9.9, "org_score": 8.3, "def_score": 4.8, "phy_score": 8.6, "dis_score": 8.1},
    {"team_id": 2, "name": "A. Griezmann", "position": "MF", "shirt_number": 7, "nationality": "法国", "height": 176, "weight": 73, "overall_rating": 8.8, "atk_score": 8.4, "org_score": 9.1, "def_score": 6.4, "phy_score": 7.1, "dis_score": 8.6},
    {"team_id": 3, "name": "Vinícius Júnior", "position": "FW", "shirt_number": 7, "nationality": "巴西", "height": 176, "weight": 73, "overall_rating": 9.0, "atk_score": 9.5, "org_score": 8.0, "def_score": 4.9, "phy_score": 8.4, "dis_score": 7.9},
    {"team_id": 3, "name": "Rodrygo", "position": "FW", "shirt_number": 11, "nationality": "巴西", "height": 174, "weight": 64, "overall_rating": 8.5, "atk_score": 8.7, "org_score": 7.9, "def_score": 5.1, "phy_score": 7.2, "dis_score": 7.8},
    {"team_id": 4, "name": "H. Kane", "position": "FW", "shirt_number": 9, "nationality": "英格兰", "height": 188, "weight": 86, "overall_rating": 9.1, "atk_score": 9.6, "org_score": 8.2, "def_score": 4.7, "phy_score": 8.5, "dis_score": 8.4},
    {"team_id": 4, "name": "J. Bellingham", "position": "MF", "shirt_number": 10, "nationality": "英格兰", "height": 186, "weight": 75, "overall_rating": 9.0, "atk_score": 8.6, "org_score": 8.9, "def_score": 7.7, "phy_score": 8.8, "dis_score": 8.2},
]

PLAYER_STATS = [
    {"player_name": "L. Messi", "season": "2026", "appearances": 6, "goals": 4, "assists": 3, "yellow_cards": 1, "red_cards": 0, "minutes_played": 540, "shots": 24, "shots_on_target": 12, "xg": 3.6, "xa": 2.4, "passes": 312, "pass_accuracy": 0.87, "tackles": 4, "interceptions": 3, "rating": 9.4},
    {"player_name": "J. Álvarez", "season": "2026", "appearances": 6, "goals": 3, "assists": 1, "yellow_cards": 0, "red_cards": 0, "minutes_played": 498, "shots": 18, "shots_on_target": 9, "xg": 2.8, "xa": 1.1, "passes": 190, "pass_accuracy": 0.82, "tackles": 5, "interceptions": 2, "rating": 8.4},
    {"player_name": "K. Mbappé", "season": "2026", "appearances": 6, "goals": 5, "assists": 2, "yellow_cards": 0, "red_cards": 0, "minutes_played": 525, "shots": 28, "shots_on_target": 14, "xg": 4.2, "xa": 1.7, "passes": 205, "pass_accuracy": 0.84, "tackles": 3, "interceptions": 1, "rating": 9.3},
    {"player_name": "A. Griezmann", "season": "2026", "appearances": 6, "goals": 2, "assists": 4, "yellow_cards": 1, "red_cards": 0, "minutes_played": 530, "shots": 14, "shots_on_target": 7, "xg": 1.9, "xa": 3.2, "passes": 340, "pass_accuracy": 0.89, "tackles": 10, "interceptions": 7, "rating": 8.8},
    {"player_name": "Vinícius Júnior", "season": "2026", "appearances": 5, "goals": 3, "assists": 2, "yellow_cards": 1, "red_cards": 0, "minutes_played": 447, "shots": 21, "shots_on_target": 10, "xg": 3.1, "xa": 1.8, "passes": 180, "pass_accuracy": 0.83, "tackles": 2, "interceptions": 1, "rating": 9.0},
    {"player_name": "Rodrygo", "season": "2026", "appearances": 5, "goals": 2, "assists": 2, "yellow_cards": 0, "red_cards": 0, "minutes_played": 410, "shots": 16, "shots_on_target": 8, "xg": 2.1, "xa": 1.9, "passes": 155, "pass_accuracy": 0.81, "tackles": 2, "interceptions": 2, "rating": 8.5},
    {"player_name": "H. Kane", "season": "2026", "appearances": 6, "goals": 4, "assists": 1, "yellow_cards": 1, "red_cards": 0, "minutes_played": 540, "shots": 22, "shots_on_target": 11, "xg": 3.7, "xa": 1.2, "passes": 210, "pass_accuracy": 0.84, "tackles": 1, "interceptions": 1, "rating": 9.1},
    {"player_name": "J. Bellingham", "season": "2026", "appearances": 6, "goals": 2, "assists": 3, "yellow_cards": 1, "red_cards": 0, "minutes_played": 536, "shots": 13, "shots_on_target": 6, "xg": 1.8, "xa": 2.3, "passes": 355, "pass_accuracy": 0.9, "tackles": 11, "interceptions": 8, "rating": 9.0},
]


def build_players_df() -> pd.DataFrame:
    df = pd.DataFrame(PLAYERS)
    teams_df = pd.DataFrame(TEAMS)
    return df.merge(teams_df[["team_id", "team_name", "group"]], on="team_id", how="left")


def build_player_stats_df() -> pd.DataFrame:
    players_df = build_players_df()[["name", "team_id", "team_name", "position", "shirt_number", "nationality"]]
    stats_df = pd.DataFrame(PLAYER_STATS)
    return stats_df.merge(players_df, left_on="player_name", right_on="name", how="left")


def export_sample_files() -> tuple[Path, Path]:
    players_path = EXPORT_DIR / "worldcup_sample_players.xlsx"
    stats_path = EXPORT_DIR / "worldcup_sample_player_stats.xlsx"

    build_players_df().to_excel(players_path, index=False)
    build_player_stats_df().to_excel(stats_path, index=False)
    return players_path, stats_path


def export_json_bundle() -> Path:
    bundle = {
        "teams": TEAMS,
        "players": build_players_df().to_dict(orient="records"),
        "player_stats": build_player_stats_df().to_dict(orient="records"),
    }
    json_path = EXPORT_DIR / "worldcup_sample_players_bundle.json"
    json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


if __name__ == "__main__":
    players_path, stats_path = export_sample_files()
    json_path = export_json_bundle()
    print(f"PLAYERS={players_path}")
    print(f"PLAYER_STATS={stats_path}")
    print(f"BUNDLE={json_path}")
