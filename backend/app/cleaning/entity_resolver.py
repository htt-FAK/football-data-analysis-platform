"""实体解析器 — 球队/联赛/球员名称到数据库 ID 的映射

爬虫返回的是业务名称（如 home_team="克卢日"、league="英超"），
数据库表需要 ID（home_team_id=5、league_id=2）。
本模块负责：
1. 按名称查现有实体，命中返回 ID
2. 未命中时自动创建实体（保证采集不中断），返回新 ID
3. 维护别名表处理"曼城 / Manchester City / Man City"等同名异写
"""

import logging

from sqlalchemy.orm import Session

from app.models.league import League
from app.models.team import Team
from app.models.player import Player
from app.models.season import Season

logger = logging.getLogger(__name__)

# 球队别名表：规范名 → 已知别名列表（解析时全部尝试匹配）
# 俱乐部规范名用中文（dongqiudi 习惯），国家队规范名用 FIFA 官方英文名
# （与 fifa_official 爬虫 _localized_text 抓取的 TeamName 一致），别名收录
# Fotmob 等第三方源常见的异写，避免精确匹配失败时新建重复球队。
TEAM_ALIASES = {
    "曼城": ["Manchester City", "Man City", "曼彻斯特城"],
    "阿森纳": ["Arsenal"],
    "利物浦": ["Liverpool"],
    "切尔西": ["Chelsea"],
    "热刺": ["Tottenham", "Spurs", "托特纳姆热刺"],
    "曼联": ["Manchester United", "Man United", "Man Utd", "曼彻斯特联"],
    "皇马": ["Real Madrid", "皇家马德里"],
    "巴萨": ["Barcelona", "巴塞罗那"],
    "拜仁": ["Bayern Munich", "拜仁慕尼黑"],
    "大巴黎": ["Paris Saint-Germain", "PSG", "巴黎圣日耳曼"],
    # ── 2026 世界杯国家队（canonical = FIFA 官方英文名）──
    # 仅收录已知会与第三方源（Fotmob 等）产生异写的队伍；
    # France/Argentina/Brazil 等常见英文名两端一致，靠精确匹配即可。
    "Korea Republic": ["South Korea", "Korea", "韩国"],
    "IR Iran": ["Iran", "Islamic Republic of Iran", "伊朗"],
    "USA": ["United States", "United States of America", "USMNT", "美国"],
    "Côte d'Ivoire": ["Ivory Coast", "科特迪瓦"],
    "Bosnia and Herzegovina": ["Bosnia", "波黑"],
    "Cape Verde Islands": ["Cape Verde", "佛得角"],
    "IRL": ["Ireland", "Republic of Ireland", "爱尔兰"],
    "North Macedonia": ["Macedonia", "北马其顿"],
    "Republic of Ireland": ["Ireland", "爱尔兰"],
}

# 联赛别名表
LEAGUE_ALIASES = {
    "英超": ["Premier League", "EPL", "PL"],
    "西甲": ["La Liga", "LL"],
    "意甲": ["Serie A"],
    "德甲": ["Bundesliga"],
    "法甲": ["Ligue 1", "L1"],
    "世界杯": ["World Cup", "WC", "FIFA World Cup", "FIFA World Cup™"],
    "欧冠": ["Champions League", "UCL"],
    "欧联": ["Europa League", "UEL"],
}

# 反向索引：任意别名 → 规范名（构建一次，查询用）
_ALIAS_TO_CANONICAL_TEAM: dict[str, str] = {}
for canonical, aliases in TEAM_ALIASES.items():
    _ALIAS_TO_CANONICAL_TEAM[canonical] = canonical
    for a in aliases:
        _ALIAS_TO_CANONICAL_TEAM[a.lower()] = canonical
        _ALIAS_TO_CANONICAL_TEAM[a] = canonical

_ALIAS_TO_CANONICAL_LEAGUE: dict[str, str] = {}
for canonical, aliases in LEAGUE_ALIASES.items():
    _ALIAS_TO_CANONICAL_LEAGUE[canonical] = canonical
    for a in aliases:
        _ALIAS_TO_CANONICAL_LEAGUE[a.lower()] = canonical
        _ALIAS_TO_CANONICAL_LEAGUE[a] = canonical


def resolve_league(db: Session, name: str, source: str = "dongqiudi") -> int | None:
    """联赛名称 → ID，未命中则创建

    Args:
        db: 数据库会话
        name: 联赛名称（中文或英文）
        source: 数据源编码（用于增量字段）
    Returns:
        int: 联赛 ID，解析失败返回 None
    """
    if not name:
        return None

    # 1. 先按规范名解析别名
    canonical = _ALIAS_TO_CANONICAL_LEAGUE.get(name) or _ALIAS_TO_CANONICAL_LEAGUE.get(name.strip())
    search_names = [canonical, name] if canonical and canonical != name else [name]

    # 2. 按名称（含别名）查现有联赛
    for sn in search_names:
        league = db.query(League).filter(League.name == sn).first()
        if league:
            return league.id

    # 3. 未命中 → 创建（用规范名或原名）
    create_name = canonical or name
    league = League(name=create_name, data_source=source, source_id=f"{source}:{create_name}")
    db.add(league)
    db.commit()
    db.refresh(league)
    logger.info("新建联赛: %s (id=%d)", create_name, league.id)
    return league.id


def resolve_team(db: Session, name: str, source: str = "dongqiudi") -> int | None:
    """球队名称 → ID，未命中则创建"""
    if not name:
        return None

    canonical = _ALIAS_TO_CANONICAL_TEAM.get(name) or _ALIAS_TO_CANONICAL_TEAM.get(name.strip())
    search_names = [canonical, name] if canonical and canonical != name else [name]

    for sn in search_names:
        team = db.query(Team).filter(Team.name == sn).first()
        if team:
            return team.id

    create_name = canonical or name
    team = Team(name=create_name, data_source=source, source_id=f"{source}:{create_name}")
    db.add(team)
    db.commit()
    db.refresh(team)
    logger.info("新建球队: %s (id=%d)", create_name, team.id)
    return team.id


def resolve_player(db: Session, name: str, team_id: int | None = None,
                   position: str | None = None, source: str = "dongqiudi") -> int | None:
    """球员名称 → ID，未命中则创建

    球员重名较多，优先按 (name, team_id) 联合定位。
    """
    if not name:
        return None

    query = db.query(Player).filter(Player.name == name)
    if team_id:
        query = query.filter(Player.team_id == team_id)
    player = query.first()
    if player:
        return player.id

    player = Player(name=name, team_id=team_id, position=position,
                    data_source=source, source_id=f"{source}:{name}")
    db.add(player)
    db.commit()
    db.refresh(player)
    logger.info("新建球员: %s (team_id=%s, id=%d)", name, team_id, player.id)
    return player.id


def resolve_season(db: Session, league_id: int, season_name: str,
                   source: str = "dongqiudi") -> int | None:
    """赛季 → ID，未命中则创建"""
    if not season_name or not league_id:
        return None

    season = db.query(Season).filter(
        Season.league_id == league_id, Season.name == season_name
    ).first()
    if season:
        return season.id

    season = Season(league_id=league_id, name=season_name,
                    data_source=source, source_id=f"{source}:{league_id}:{season_name}")
    db.add(season)
    db.commit()
    db.refresh(season)
    logger.info("新建赛季: %s (league_id=%d, id=%d)", season_name, league_id, season.id)
    return season.id
