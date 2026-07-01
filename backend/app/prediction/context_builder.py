"""赛前数据采集 — 从数据库组装喂给 LLM 的比赛上下文。

采集内容（参照 football-match-analysis skill 的「信息采集清单」12类）：
  比赛基本信息、双方实力数据、赛季统计、近期战绩、核心球员、小组积分形势。
缺失的字段会记入 data_gaps，提示模型通过联网搜索补全。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.league import League
from app.models.match import Match
from app.models.player import Player
from app.models.player_stat import PlayerStat
from app.models.season import Season
from app.models.standings import Standings
from app.models.team import Team
from app.models.team_stat import TeamStat

logger = logging.getLogger(__name__)

RECENT_FORM_LIMIT = 8
KEY_PLAYER_LIMIT = 8


def _team_season_stat(db: Session, team_id: int, season_id: int | None) -> TeamStat | None:
    """取球队在该赛季的统计；若无 season_id 则取该球队最新一条。"""
    q = db.query(TeamStat).filter(TeamStat.team_id == team_id)
    if season_id:
        stat = q.filter(TeamStat.season_id == season_id).first()
        if stat:
            return stat
    # 兜底：取最新一条（按 id 倒序）
    return q.order_by(TeamStat.id.desc()).first()


def _recent_matches(db: Session, team_id: int, season_id: int | None, limit: int) -> list[Match]:
    """取该球队近 N 场已完赛比赛（主或客），按时间倒序。"""
    q = (
        db.query(Match)
        .filter(
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
            Match.status == "finished",
        )
    )
    if season_id:
        q = q.filter(Match.season_id == season_id)
    return (
        q.order_by(
            case((Match.match_date.is_(None), 1), else_=0),
            Match.match_date.desc(),
        )
        .limit(limit)
        .all()
    )


def _format_form(match: Match, team_id: int) -> str:
    """把一场已完赛比赛格式化为形如 W2-1 / L0-3 / D1-1 的状态标签。"""
    is_home = match.home_team_id == team_id
    our = match.home_score if is_home else match.away_score
    opp = match.away_score if is_home else match.home_score
    our = our if our is not None else 0
    opp = opp if opp is not None else 0
    if our > opp:
        tag = "W"
    elif our < opp:
        tag = "L"
    else:
        tag = "D"
    opp_name = ""
    opp_team = match.away_team if is_home else match.home_team
    if opp_team:
        opp_name = opp_team.name or ""
    return f"{tag}{our}-{opp}({opp_name})"


def _key_players(
    db: Session, team_id: int, season_id: int | None, limit: int
) -> list[dict]:
    """取球队核心球员（按进球+助攻倒序），附赛季统计。"""
    q = db.query(Player).filter(Player.team_id == team_id)
    players = q.all()
    if not players:
        return []
    player_ids = [p.id for p in players]
    stat_q = db.query(PlayerStat).filter(PlayerStat.player_id.in_(player_ids))
    if season_id:
        stat_q = stat_q.filter(PlayerStat.season_id == season_id)
    stats_by_player: dict[int, PlayerStat] = {
        s.player_id: s for s in stat_q.all()
    }
    # 如果指定赛季没有统计，回退取最新
    if not stats_by_player:
        fallback = (
            db.query(PlayerStat)
            .filter(PlayerStat.player_id.in_(player_ids))
            .all()
        )
        # 每个 player 取 id 最大（最新）一条
        latest: dict[int, PlayerStat] = {}
        for s in fallback:
            if s.player_id and (s.player_id not in latest or s.id > latest[s.player_id].id):
                latest[s.player_id] = s
        stats_by_player = latest

    enriched: list[dict] = []
    for p in players:
        s = stats_by_player.get(p.id)
        goals = s.goals if s and s.goals else 0
        assists = s.assists if s and s.assists else 0
        enriched.append({
            "name": p.name,
            "position": p.position,
            "nationality": p.nationality,
            "goals": goals,
            "assists": assists,
            "rating": round(s.rating, 2) if s and s.rating else None,
            "xg": round(s.xg, 2) if s and s.xg else None,
            "appearances": s.appearances if s else None,
            "score": goals + assists,
        })
    enriched.sort(key=lambda x: x.get("score", 0), reverse=True)
    return enriched[:limit]


def _standings_for_team(db: Session, team_id: int, season_id: int | None) -> dict:
    """取球队的小组/联赛积分形势。"""
    q = db.query(Standings).filter(Standings.team_id == team_id)
    if season_id:
        s = q.filter(Standings.season_id == season_id).first()
        if s:
            return _standings_to_dict(s)
    s = q.order_by(Standings.id.desc()).first()
    return _standings_to_dict(s) if s else {}


def _standings_to_dict(s: Standings) -> dict:
    return {
        "position": s.position,
        "played": s.played,
        "points": s.points,
        "won": s.won,
        "drawn": s.drawn,
        "lost": s.lost,
        "goals_for": s.goals_for,
        "goals_against": s.goals_against,
        "goal_diff": s.goal_diff,
        "form": s.form,
        "group_name": s.group_name,
        "qualification_status": s.qualification_status,
    }


def _group_standings(db: Session, season_id: int | None, group_name: str | None) -> list[dict]:
    """取同组其他球队积分形势（供出线推演）。"""
    if not season_id or not group_name:
        return []
    rows = (
        db.query(Standings)
        .filter(Standings.season_id == season_id, Standings.group_name == group_name)
        .order_by(
            case((Standings.position.is_(None), 1), else_=0),
            Standings.position.asc(),
        )
        .all()
    )
    result = []
    for s in rows:
        team = db.get(Team, s.team_id)
        result.append({
            "name": team.name if team else f"team#{s.team_id}",
            "position": s.position,
            "points": s.points,
            "played": s.played,
            "qualification_status": s.qualification_status,
        })
    return result


def _build_team_block(db: Session, team: Team, season_id: int | None) -> dict:
    """组装单支球队的上下文块。"""
    block: dict[str, Any] = {
        "name": team.name,
        "full_name": team.full_name,
        "country": team.country,
        "coach": team.coach,
        "stadium": team.stadium,
        "founded_year": team.founded_year,
        "rank": None,  # 暂无世界排名字段，留待联网补
        "stat": None,
        "recent_form": [],
        "key_players": [],
        "standings": {},
    }
    data_gaps: list[str] = []

    stat = _team_season_stat(db, team.id, season_id)
    if stat:
        block["stat"] = {
            "matches_played": stat.matches_played,
            "wins": stat.wins,
            "draws": stat.draws,
            "losses": stat.losses,
            "goals_for": stat.goals_for,
            "goals_against": stat.goals_against,
            "xg": round(stat.xg_for, 2) if stat.xg_for else None,
            "xga": round(stat.xg_against, 2) if stat.xg_against else None,
            "possession": round(stat.possession, 1) if stat.possession else None,
            "shots": stat.shots_total,
            "shots_on_target": stat.shots_on_target_total,
            "pass_accuracy": round(stat.pass_accuracy, 1) if stat.pass_accuracy else None,
            "corners": stat.corners,
            "clean_sheets": stat.clean_sheets,
            "attack_score": round(stat.attack_rating, 1) if stat.attack_rating else None,
            "defense_score": round(stat.defense_rating, 1) if stat.defense_rating else None,
            "overall_score": round(stat.overall_rating, 1) if stat.overall_rating else None,
        }
    else:
        data_gaps.append(f"{team.name}赛季统计")

    recent = _recent_matches(db, team.id, season_id, RECENT_FORM_LIMIT)
    block["recent_form"] = [_format_form(m, team.id) for m in recent]
    if not recent:
        data_gaps.append(f"{team.name}近期战绩")

    block["key_players"] = _key_players(db, team.id, season_id, KEY_PLAYER_LIMIT)
    if not block["key_players"]:
        data_gaps.append(f"{team.name}球员名单")

    block["standings"] = _standings_for_team(db, team.id, season_id)
    if not block["standings"]:
        data_gaps.append(f"{team.name}小组积分")

    block["data_gaps"] = data_gaps
    return block


def build_match_context(db: Session, match_id: int) -> dict:
    """组装完整比赛上下文，供 prompt 使用。

    返回结构：
      {
        match: {league, season, stage, group, kickoff, venue},
        home: {...team_block},
        away: {...team_block},
        group_standings: [...],
        data_gaps: [...],
        meta: {match_id, home_name, away_name, ...},
      }
    """
    match = db.get(Match, match_id)
    if not match:
        raise ValueError(f"比赛 {match_id} 不存在")

    league = db.get(League, match.league_id) if match.league_id else None
    season = db.get(Season, match.season_id) if match.season_id else None
    season_id = season.id if season else None
    season_name = season.name if season else None

    home_team = match.home_team
    away_team = match.away_team
    if not home_team or not away_team:
        raise ValueError(f"比赛 {match_id} 主客队信息不完整，无法预测")

    home_block = _build_team_block(db, home_team, season_id)
    away_block = _build_team_block(db, away_team, season_id)

    group_standings = _group_standings(db, season_id, match.group_name)

    data_gaps: list[str] = []
    data_gaps.extend(home_block.get("data_gaps", []))
    data_gaps.extend(away_block.get("data_gaps", []))
    # 全局缺失
    data_gaps.append("双方世界排名/身价/平均年龄（需联网查 FIFA 排名与德转身价）")
    data_gaps.append("赛前采访/天气/突发新闻（需联网搜索实时场外情报）")

    return {
        "match": {
            "match_id": match.id,
            "league": league.name if league else "未知",
            "season": season_name or "未知",
            "season_id": season_id,
            "stage": match.stage,
            "group": match.group_name,
            "matchday": match.matchday,
            "kickoff": match.match_date.strftime("%Y-%m-%d %H:%M") if match.match_date else "未知",
            "venue": match.venue,
            "status": match.status,
        },
        "home": home_block,
        "away": away_block,
        "group_standings": group_standings,
        "data_gaps": data_gaps,
        "meta": {
            "match_id": match.id,
            "home_name": home_team.name,
            "away_name": away_team.name,
            "home_team_id": home_team.id,
            "away_team_id": away_team.id,
            "kickoff": match.match_date,
            "stage": match.stage,
            "group": match.group_name,
            "venue": match.venue,
        },
    }
