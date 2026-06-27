"""字段映射模块 — 不同数据源字段标准化"""

# 标准字段名定义（不同数据源的字段统一映射到此）
STANDARD_FIELDS = [
    "player_id", "name", "team", "position", "age", "height", "weight",
    "nationality", "goals", "assists", "shots", "shots_on_target",
    "passes", "pass_accuracy", "minutes_played", "xg", "xa",
    "rating", "league", "season", "matchday", "date",
    "home_team", "away_team", "home_score", "away_score",
    "possession", "match_id",
]

# 各数据源字段 -> 标准字段映射
FIELD_MAP = {
    # 懂球帝：中文命名风格
    "dongqiudi": {
        "球员ID": "player_id",
        "姓名": "name",
        "球队": "team",
        "位置": "position",
        "年龄": "age",
        "身高": "height",
        "体重": "weight",
        "国籍": "nationality",
        "进球": "goals",
        "助攻": "assists",
        "射门": "shots",
        "射正": "shots_on_target",
        "传球": "passes",
        "传球成功率": "pass_accuracy",
        "出场时间": "minutes_played",
        "评分": "rating",
        "联赛": "league",
        "赛季": "season",
        "比赛日": "matchday",
        "日期": "date",
        "主队": "home_team",
        "客队": "away_team",
        "主队比分": "home_score",
        "客队比分": "away_score",
        "比赛ID": "match_id",
    },
    # FBref：英文小写带下划线，部分有前缀
    "fbref": {
        "player": "name",
        "squad": "team",
        "pos": "position",
        "age": "age",
        "height": "height",
        "weight": "weight",
        "nation": "nationality",
        "gls": "goals",
        "ast": "assists",
        "sh": "shots",
        "sot": "shots_on_target",
        "passes_total": "passes",
        "passes_pct": "pass_accuracy",
        "min": "minutes_played",
        "xg": "xg",
        "xa": "xa",
        "rating": "rating",
        "comp": "league",
        "season": "season",
        "round": "matchday",
        "date": "date",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "match_id": "match_id",
    },
    # Understat：侧重 xG/xA 与射门
    "understat": {
        "id": "player_id",
        "player_name": "name",
        "team_title": "team",
        "position": "position",
        "goals": "goals",
        "assists": "assists",
        "shots": "shots",
        "xG": "xg",
        "xA": "xa",
        "time": "minutes_played",
        "position": "position",
        "league": "league",
        "season": "season",
        "date": "date",
        "id": "match_id",
    },
    # football-data.org：API 风格
    "football_data": {
        "id": "match_id",
        "utcDate": "date",
        "matchday": "matchday",
        "competition": "league",
        "season": "season",
        "homeTeam": "home_team",
        "awayTeam": "away_team",
        "score_home": "home_score",
        "score_away": "away_score",
        "homeTeam_name": "home_team",
        "awayTeam_name": "away_team",
        "score_fullTime_home": "home_score",
        "score_fullTime_away": "away_score",
    },
    # API-Football v3：JSON 嵌套结构（爬虫已展平一层）
    "api_football": {
        "fixture_id": "match_id",
        "date": "date",
        "league_name": "league",
        "league_season": "season",
        "round": "matchday",
        "home_team_name": "home_team",
        "away_team_name": "away_team",
        "goals_home": "home_score",
        "goals_away": "away_score",
        "status": "status",
        # 球员统计
        "player_name": "name",
        "team_name": "team",
        "position": "position",
        "games_appearences": "appearances",
        "games_minutes": "minutes_played",
        "goals_total": "goals",
        "goals_assists": "assists",
        "shots_total": "shots",
        "shots_on": "shots_on_target",
        "passes_total": "passes",
        "passes_accuracy": "pass_accuracy",
        "tackles_total": "tackles",
        "duels_won": "interceptions",
    },
    # TheSportsDB：免费 API，元信息为主
    "thesportsdb": {
        "idLeague": "league_id",
        "strLeague": "league",
        "idTeam": "team_id",
        "strTeam": "team",
        "strTeamShort": "team",
        "strStadium": "stadium",
        "strManager": "coach",
        "intFormedYear": "founded_year",
        "strCountry": "country",
        # 球员
        "idPlayer": "player_id",
        "strPlayer": "name",
        "strTeam": "team",
        "strPosition": "position",
        "strNationality": "nationality",
        "dateBorn": "birth_date",
    },
    # OpenLigaDB：德甲为主，XML/JSON
    "openligadb": {
        "matchID": "match_id",
        "matchDateTime": "date",
        "groupOrderID": "matchday",
        "league_name": "league",
        "team1_teamName": "home_team",
        "team2_teamName": "away_team",
        "matchResults_resultName": "result_type",
        # 事件
        "goalMatchMinute": "minute",
        "goalPlayerName": "player",
        "goalTeamID": "team",
    },
    # TeamRankings：评分/概率
    "teamrankings": {
        "team": "team",
        "rating": "overall_rating",
        "win_pct": "win_rate",
        "rank": "position",
        "league": "league",
    },
}


def map_fields(data: dict, source: str) -> dict:
    """将指定数据源的字段映射为标准字段

    Args:
        data: 原始数据字典
        source: 数据源名称（dongqiudi/fbref/understat/football_data）

    Returns:
        dict: 标准化后的数据字典（仅保留映射命中的字段）
    """
    mapping = FIELD_MAP.get(source, {})
    if not mapping:
        # 未知数据源：原样返回（不做映射）
        return dict(data)

    result = {}
    for src_field, value in data.items():
        std_field = mapping.get(src_field)
        if std_field:
            result[std_field] = value
    return result
