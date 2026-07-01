"""懂球帝爬虫 — 采集赛程、积分榜、比赛详情、球员数据

页面结构分析：
- /match          赛程列表页（服务端渲染，按日期分组）
- /match/{id}     比赛详情页（含比分、事件、近期战绩）
- /team/{id}      球队信息页（含阵容、赛程、基本信息）
- /team/{id}/squad 球队阵容页
- /standing       积分榜页面（JS 渲染，需降级处理）
"""

import logging
import re
from datetime import datetime
from bs4 import BeautifulSoup

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class DongqiudiCrawler(BaseCrawler):
    """懂球帝数据爬虫"""

    # 联赛中文名到懂球帝 competition ID 的映射
    LEAGUE_IDS = {
        "英超": 1,
        "西甲": 2,
        "意甲": 3,
        "德甲": 4,
        "法甲": 5,
        "中超": 6,
        "世界杯": 7,
        "欧冠": 8,
        "欧联": 9,
    }

    # 联赛中文 -> 英文（用于数据标准化）
    LEAGUE_EN = {
        "英超": "Premier League",
        "西甲": "La Liga",
        "意甲": "Serie A",
        "德甲": "Bundesliga",
        "法甲": "Ligue 1",
        "中超": "CSL",
        "世界杯": "World Cup",
        "欧冠": "Champions League",
        "欧联": "Europa League",
    }

    def __init__(self):
        super().__init__(source_code="dongqiudi", base_url="https://www.dongqiudi.com/")
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.dongqiudi.com",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    def crawl(self, target: str, league: str = "英超", **kwargs) -> list[dict]:
        """采集入口

        Args:
            target: 采集目标，支持 schedule / standings / match_detail / player_stats / team_info
            league: 联赛中文名（如 "英超"、"世界杯"）
        """
        dispatch = {
            "schedule": self._crawl_schedule,
            "standings": self._crawl_standings,
            "match_detail": self._crawl_match_detail,
            "player_stats": self._crawl_player_stats,
            "team_info": self._crawl_team_info,
        }
        handler = dispatch.get(target)
        if not handler:
            logger.warning("不支持的目标: %s", target)
            return []
        return handler(league, **kwargs)

    # ──────────────────────────────────────────────────────
    # 1. 赛程采集
    # ──────────────────────────────────────────────────────

    def _crawl_schedule(self, league: str, **kwargs) -> list[dict]:
        """采集赛程列表

        从 /match 页面解析按日期分组的比赛列表。
        可选参数:
            date: 指定日期 (YYYYMMDD)，默认抓取当天
        """
        date = kwargs.get("date", datetime.now().strftime("%Y%m%d"))
        url = f"{self.base_url}match"
        if date:
            url = f"{url}?date={date}"

        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("赛程页请求失败: %s", e)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        results: list[dict] = []

        # 策略1: 尝试通过 CSS 选择器解析比赛卡片
        match_cards = soup.select("div.match-item, li.match-item, .schedule-list li, .match-card")
        if match_cards:
            results = self._parse_match_cards(match_cards, league)
        else:
            # 策略2: 降级为全文文本解析
            results = self._parse_schedule_text(resp.text, league)

        # 保存原始数据到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/dongqiudi/schedule/{date}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败，跳过: %s", e)

        logger.info("[dongqiudi] 赛程采集完成: %d 条 (league=%s, date=%s)", len(results), league, date)
        return results

    def _parse_match_cards(self, cards, league: str) -> list[dict]:
        """通过 CSS 选择器解析比赛卡片"""
        results = []
        current_date = ""
        for card in cards:
            # 尝试提取日期标题
            date_el = card.find_previous(string=re.compile(r"\d{4}-\d{2}-\d{2}"))
            if date_el:
                current_date = date_el.strip().split()[0]

            text = card.get_text(strip=True)
            match = self._parse_match_text(text, current_date, league)
            if match:
                results.append(match)
        return results

    def _parse_schedule_text(self, html: str, league: str) -> list[dict]:
        """降级策略：从页面纯文本中解析赛程

        文本格式：
            2019-09-21 今天
            完场 欧联 克卢日 2 - 1 拉齐奥 比赛集锦
            16:00 中甲 四川FC VS 南通支云
            2 ' 直播中 中甲 陕西长安竞技 0 - 0 贵州恒丰
        """
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator="\n")
        results = []
        current_date = ""

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # 匹配日期行: "2019-09-21 今天" 或 "2019-09-21"
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", line)
            if date_match:
                current_date = date_match.group(1)
                continue

            # 尝试解析比赛行
            match = self._parse_match_text(line, current_date, league)
            if match:
                results.append(match)

        return results

    @staticmethod
    def _parse_match_text(text: str, date_str: str, league_filter: str) -> dict | None:
        """从单行文本中解析比赛信息

        支持三种格式：
            完场 欧联 克卢日 2 - 1 拉齐奥 比赛集锦
            16:00 中甲 四川FC VS 南通支云
            2 ' 直播中 中甲 陕西长安竞技 0 - 0 贵州恒丰
        """
        # 已完场比赛: "完场 {联赛} {主队} {n} - {n} {客队}"
        m = re.match(
            r"完场\s+(\S+)\s+(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+?)(?:\s+比赛集锦)?$",
            text,
        )
        if m:
            league_name, home, hs, as_, away = m.groups()
            return {
                "date": date_str,
                "status": "finished",
                "league": league_name,
                "home_team": home.strip(),
                "away_team": away.strip(),
                "home_score": int(hs),
                "away_score": int(as_),
                "source": "dongqiudi",
            }

        # 直播中比赛: "2 ' 直播中 {联赛} {主队} {n} - {n} {客队}"
        m = re.match(
            r"(\d+)\s*'\s*直播中\s+(\S+)\s+(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+?)$",
            text,
        )
        if m:
            minute, league_name, home, hs, as_, away = m.groups()
            return {
                "date": date_str,
                "status": "playing",
                "minute": int(minute),
                "league": league_name,
                "home_team": home.strip(),
                "away_team": away.strip(),
                "home_score": int(hs),
                "away_score": int(as_),
                "source": "dongqiudi",
            }

        # 未开始比赛: "16:00 {联赛} {主队} VS {客队}"
        m = re.match(
            r"(\d{2}:\d{2})\s+(\S+)\s+(.+?)\s+VS\s+(.+?)$",
            text,
        )
        if m:
            time_str, league_name, home, away = m.groups()
            return {
                "date": date_str,
                "time": time_str,
                "status": "scheduled",
                "league": league_name,
                "home_team": home.strip(),
                "away_team": away.strip(),
                "home_score": None,
                "away_score": None,
                "source": "dongqiudi",
            }

        return None

    # ──────────────────────────────────────────────────────
    # 2. 积分榜采集
    # ──────────────────────────────────────────────────────

    def _crawl_standings(self, league: str, **kwargs) -> list[dict]:
        """采集积分榜

        懂球帝积分榜页面 (/standing) 为 JS 渲染，直接请求无数据。
        降级策略：尝试移动端 API → 降级为从赛程结果累计计算。
        """
        # 策略1: 尝试移动端 API
        results = self._try_standings_api(league)
        if results:
            return results

        # 策略2: 从已有赛程结果计算积分榜
        logger.info("[dongqiudi] 积分榜 API 不可用，降级为从赛程结果计算")
        results = self._compute_standings_from_schedule(league, **kwargs)

        # 保存原始数据到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/dongqiudi/standings/{league}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败，跳过: %s", e)

        return results

    def _try_standings_api(self, league: str) -> list[dict] | None:
        """尝试通过移动端 API 获取积分榜"""
        league_id = self.LEAGUE_IDS.get(league, 1)
        api_urls = [
            f"{self.base_url}api/standing/{league_id}",
            f"https://m.dongqiudi.com/api/standing/{league_id}",
        ]
        for url in api_urls:
            try:
                resp = self._fetch(url)
                data = resp.json()
                if data and isinstance(data, list):
                    return [
                        {
                            "position": item.get("rank", item.get("position")),
                            "team_name": item.get("team_name", item.get("name")),
                            "played": item.get("played", item.get("match_count")),
                            "won": item.get("won", item.get("win")),
                            "drawn": item.get("drawn", item.get("draw")),
                            "lost": item.get("lost", item.get("lose")),
                            "goals_for": item.get("goals_for", item.get("gf")),
                            "goals_against": item.get("goals_against", item.get("ga")),
                            "goal_diff": item.get("goal_diff", item.get("gd")),
                            "points": item.get("points", item.get("point")),
                            "source": "dongqiudi",
                        }
                        for item in data
                    ]
            except Exception:
                continue
        return None

    def _compute_standings_from_schedule(self, league: str, **kwargs) -> list[dict]:
        """从赛程结果计算积分榜（降级方案）"""
        matches = self._crawl_schedule(league, **kwargs)
        finished = [m for m in matches if m.get("status") == "finished"]
        if not finished:
            return []

        table: dict[str, dict] = {}
        for m in finished:
            for side, opp in [("home", "away"), ("away", "home")]:
                team = m[f"{side}_team"]
                opp_team = m[f"{opp}_team"]
                gf = m[f"{side}_score"]
                ga = m[f"{opp}_score"]
                if team not in table:
                    table[team] = {"team_name": team, "played": 0, "won": 0, "drawn": 0,
                                   "lost": 0, "goals_for": 0, "goals_against": 0, "points": 0}
                t = table[team]
                t["played"] += 1
                t["goals_for"] += gf
                t["goals_against"] += ga
                if gf > ga:
                    t["won"] += 1
                    t["points"] += 3
                elif gf == ga:
                    t["drawn"] += 1
                    t["points"] += 1
                else:
                    t["lost"] += 1

        # 排序并添加排名/净胜球
        results = sorted(table.values(),
                         key=lambda x: (-x["points"], -(x["goals_for"] - x["goals_against"])))
        for i, t in enumerate(results, 1):
            t["position"] = i
            t["goal_diff"] = t["goals_for"] - t["goals_against"]
            t["source"] = "dongqiudi"

        return results

    # ──────────────────────────────────────────────────────
    # 3. 比赛详情采集
    # ──────────────────────────────────────────────────────

    def _crawl_match_detail(self, league: str, **kwargs) -> list[dict]:
        """采集比赛详情

        从 /match/{id} 页面解析：
        - 比赛基本信息（联赛、日期、比分）
        - 比赛事件（进球、红黄牌、换人）
        - 近期战绩
        """
        match_id = kwargs.get("match_id")
        if not match_id:
            logger.warning("match_detail 需要提供 match_id 参数")
            return []

        url = f"{self.base_url}match/{match_id}"
        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("比赛详情页请求失败: %s", e)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(separator="\n")
        result: dict = {
            "match_id": match_id,
            "source": "dongqiudi",
            "events": [],
            "home_form": [],
            "away_form": [],
        }

        # 解析比赛头部信息
        # 格式: "荷甲·联赛2003-08-17 00:00"
        header_match = re.search(
            r"(\S+)[·•]\S*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", text
        )
        if header_match:
            result["league"] = header_match.group(1)
            result["match_date"] = header_match.group(2)

        # 解析比分: "维特斯  完  1 - 2  阿贾克斯"
        score_match = re.search(
            r"(.+?)\s+完\s+(\d+)\s*-\s*(\d+)\s+(.+?)(?:\n|$)", text
        )
        if score_match:
            result["home_team"] = score_match.group(1).strip()
            result["home_score"] = int(score_match.group(2))
            result["away_score"] = int(score_match.group(3))
            result["away_team"] = score_match.group(4).strip()
            result["status"] = "finished"

        # 解析比赛事件（从赛况分析页面）
        events = self._parse_match_events(soup, match_id)
        result["events"] = events

        # 解析近期战绩表
        form_tables = soup.find_all("table")
        if len(form_tables) >= 2:
            result["home_form"] = self._parse_form_table(form_tables[0])
            result["away_form"] = self._parse_form_table(form_tables[1])

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/dongqiudi/match_detail/{match_id}_{ts}.json"
        try:
            self._save_raw_to_hdfs(result, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败: %s", e)

        logger.info("[dongqiudi] 比赛详情采集完成: match_id=%s", match_id)
        return [result]

    def fetch_schedule_list_api(self, start_date: str) -> list[dict]:
        """Fetch schedule rows from the current Dongqiudi JSON API."""
        response = self._fetch(
            f"{self.base_url}magicball/v1/list/schedule_list",
            params={
                "language": "en-US",
                "cmp_type": "soccer",
                "tab_type": "schedule",
                "start": f"{start_date} 00:00:00",
            },
        )
        payload = response.json()
        matches = ((payload.get("data") or {}).get("matches") or [])
        logger.info("[dongqiudi] schedule_list API fetched %d matches for %s", len(matches), start_date)
        return matches

    def fetch_match_overview(self, match_id: str | int) -> dict:
        """Fetch the match overview payload that contains the event timeline."""
        response = self._fetch(f"{self.base_url}api/data/overview/match/{match_id}")
        payload = response.json()
        logger.info(
            "[dongqiudi] overview API fetched match_id=%s with %d minute buckets",
            match_id,
            len(payload.get("events") or {}),
        )
        return payload

    def normalize_overview_events(self, match_id: str | int, overview: dict) -> list[dict]:
        """Normalize Dongqiudi overview event buckets into key event rows."""
        normalized: list[dict] = []
        events_by_minute = overview.get("events") or {}

        for minute_key, bucket in events_by_minute.items():
            minute = self._parse_event_minute(minute_key)
            if minute is None:
                continue

            for side_key, team_side in (("teamAEvents", "home"), ("teamBEvents", "away")):
                entries = bucket.get(side_key) or []
                outgoing_queue = [entry for entry in entries if (entry.get("code") or "").upper() == "SO"]

                for entry in entries:
                    normalized_event = self._normalize_overview_entry(
                        match_id=match_id,
                        minute=minute,
                        minute_key=minute_key,
                        team_side=team_side,
                        entry=entry,
                        outgoing_queue=outgoing_queue,
                    )
                    if normalized_event:
                        normalized.append(normalized_event)

        return normalized

    @staticmethod
    def _parse_event_minute(minute_value: str | int | None) -> int | None:
        if minute_value is None:
            return None
        text = str(minute_value).strip()
        if not text:
            return None
        base = text.split("+", 1)[0]
        digits = "".join(ch for ch in base if ch.isdigit())
        return int(digits) if digits else None

    def _normalize_overview_entry(
        self,
        match_id: str | int,
        minute: int,
        minute_key: str,
        team_side: str,
        entry: dict,
        outgoing_queue: list[dict],
    ) -> dict | None:
        code = (entry.get("code") or "").upper()
        if code == "SO":
            return None

        event_type_map = {
            "G": "goal",
            "YC": "yellow_card",
            "RC": "red_card",
        }

        if code in event_type_map:
            event_type = event_type_map[code]
            return {
                "match_id": match_id,
                "minute": minute,
                "event_type": event_type,
                "team": team_side,
                "team_side": team_side,
                "player": entry.get("person"),
                "player_source_id": entry.get("person_id"),
                "detail": self._build_event_detail(code, entry),
                "data_source": "dongqiudi",
                "source_id": self._build_event_source_id(match_id, minute_key, team_side, event_type, entry),
            }

        if code == "SI":
            outgoing = outgoing_queue.pop(0) if outgoing_queue else {}
            return {
                "match_id": match_id,
                "minute": minute,
                "event_type": "substitution",
                "team": team_side,
                "team_side": team_side,
                "player": entry.get("person"),
                "player_source_id": entry.get("person_id"),
                "detail": self._build_substitution_detail(entry.get("person"), outgoing.get("person")),
                "data_source": "dongqiudi",
                "source_id": self._build_event_source_id(
                    match_id,
                    minute_key,
                    team_side,
                    "substitution",
                    entry,
                    extra=f"out:{outgoing.get('person_id') or outgoing.get('person') or 'unknown'}",
                ),
            }

        return None

    @staticmethod
    def _build_event_detail(code: str, entry: dict) -> str:
        player = entry.get("person") or "未知球员"
        reason = (entry.get("reason") or "").strip()
        score = (entry.get("score") or "").strip()

        if code == "G":
            return f"{player} 进球（{score}）" if score else f"{player} 进球"
        if code == "YC":
            return f"{player} 黄牌" + (f"：{reason}" if reason else "")
        if code == "RC":
            return f"{player} 红牌" + (f"：{reason}" if reason else "")
        return player

    @staticmethod
    def _build_substitution_detail(player_in: str | None, player_out: str | None) -> str:
        incoming = player_in or "未知球员"
        outgoing = player_out or "未知球员"
        return f"换人：{incoming} 上，{outgoing} 下"

    @staticmethod
    def _build_event_source_id(
        match_id: str | int,
        minute_key: str,
        team_side: str,
        event_type: str,
        entry: dict,
        extra: str | None = None,
    ) -> str:
        player_part = entry.get("person_id") or entry.get("person") or "unknown"
        parts = [str(match_id), str(minute_key), team_side, event_type, str(player_part)]
        if extra:
            parts.append(extra)
        return "-".join(parts)

    def _parse_match_events(self, soup: BeautifulSoup, match_id: str) -> list[dict]:
        """解析比赛事件（进球、卡牌、换人）

        懂球帝比赛详情页的事件通常在赛况分析子页面。
        这里先解析当前页面的文本，完整事件需单独请求赛况分析页。
        """
        events = []
        text = soup.get_text(separator="\n")

        # 尝试从文本中提取进球事件
        # 格式: "45' 球员名 进球" 或 "45+2' 球员名 (点球)"
        goal_pattern = re.compile(
            r"(\d+)('?|\+\d+'?)\s+(.+?)\s+(进球|点球|乌龙)", re.MULTILINE
        )
        for m in goal_pattern.finditer(text):
            events.append({
                "match_id": match_id,
                "minute": int(m.group(1)),
                "event_type": "goal",
                "player_name": m.group(3).strip(),
                "detail": m.group(4),
                "source": "dongqiudi",
            })

        # 尝试从文本中提取红黄牌
        card_pattern = re.compile(
            r"(\d+)('?|\+\d+'?)\s+(.+?)\s+(黄牌|红牌|两黄变红)", re.MULTILINE
        )
        for m in card_pattern.finditer(text):
            events.append({
                "match_id": match_id,
                "minute": int(m.group(1)),
                "event_type": "card",
                "player_name": m.group(3).strip(),
                "detail": m.group(4),
                "source": "dongqiudi",
            })

        # 尝试从文本中提取换人
        sub_pattern = re.compile(
            r"(\d+)('?|\+\d+'?)\s+换人\s+(.+?)\s+换下\s+(.+)", re.MULTILINE
        )
        for m in sub_pattern.finditer(text):
            events.append({
                "match_id": match_id,
                "minute": int(m.group(1)),
                "event_type": "substitution",
                "player_name": m.group(3).strip(),
                "detail": f"换下 {m.group(4).strip()}",
                "source": "dongqiudi",
            })

        return events

    @staticmethod
    def _parse_form_table(table) -> list[dict]:
        """解析近期战绩表

        表头: 赛事 | 日期 | 主队 | 比分 | 客队
        """
        results = []
        rows = table.find_all("tr")
        for row in rows[1:]:  # 跳过表头
            cells = row.find_all(["td", "th"])
            if len(cells) >= 5:
                results.append({
                    "competition": cells[0].get_text(strip=True),
                    "date": cells[1].get_text(strip=True),
                    "home_team": cells[2].get_text(strip=True),
                    "score": cells[3].get_text(strip=True),
                    "away_team": cells[4].get_text(strip=True),
                })
        return results

    # ──────────────────────────────────────────────────────
    # 4. 球员数据采集
    # ──────────────────────────────────────────────────────

    def _crawl_player_stats(self, league: str, **kwargs) -> list[dict]:
        """采集球员统计数据

        懂球帝球员数据页面结构：
        - /player 射手榜/助攻榜页面
        - /team/{id}/squad 球队阵容页

        可选参数:
            team_id: 指定球队 ID，获取该球队阵容
        """
        team_id = kwargs.get("team_id")

        if team_id:
            return self._crawl_team_squad(team_id)

        # 采集联赛射手榜
        url = f"{self.base_url}player"
        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("球员统计页请求失败: %s", e)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        results: list[dict] = []

        # 解析射手榜表格
        tables = soup.find_all("table")
        for table in tables:
            header_text = table.get_text()
            if "进球" in header_text or "射手" in header_text:
                results = self._parse_player_stats_table(table, "scorers")
                break
            elif "助攻" in header_text:
                results = self._parse_player_stats_table(table, "assists")
                break

        # 如果没有找到表格，尝试从文本解析
        if not results:
            results = self._parse_player_stats_text(soup.get_text(separator="\n"), league)

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/dongqiudi/player_stats/{league}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败: %s", e)

        logger.info("[dongqiudi] 球员统计采集完成: %d 条 (league=%s)", len(results), league)
        return results

    def _crawl_team_squad(self, team_id: int) -> list[dict]:
        """采集球队阵容

        从 /team/{id} 页面解析球员列表。
        """
        url = f"{self.base_url}team/{team_id}"
        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("球队页请求失败: %s", e)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        results: list[dict] = []

        # 查找阵容列表元素
        # 懂球帝球队页通常有球员卡片列表
        player_items = soup.select(
            ".player-item, .squad-list li, .player-card, .team-squad li"
        )

        for item in player_items:
            text = item.get_text(separator=" ", strip=True)
            # 尝试提取球员信息: 姓名 号码 位置 国籍
            m = re.match(
                r"(\d+)\s+(.+?)\s+(GK|DF|MF|FW|门将|后卫|中场|前锋)\s*(.*)",
                text,
            )
            if m:
                shirt, name, pos, nationality = m.groups()
                position_map = {"门将": "GK", "后卫": "DF", "中场": "MF", "前锋": "FW"}
                results.append({
                    "team_id": team_id,
                    "name": name.strip(),
                    "shirt_number": int(shirt),
                    "position": position_map.get(pos, pos),
                    "nationality": nationality.strip() if nationality else None,
                    "source": "dongqiudi",
                })

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/dongqiudi/squad/{team_id}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败: %s", e)

        logger.info("[dongqiudi] 球队阵容采集完成: %d 条 (team_id=%d)", len(results), team_id)
        return results

    @staticmethod
    def _parse_player_stats_table(table, stat_type: str) -> list[dict]:
        """解析球员统计表格"""
        results = []
        rows = table.find_all("tr")
        if not rows:
            return results

        # 解析表头
        header_cells = rows[0].find_all(["td", "th"])
        headers = [c.get_text(strip=True) for c in header_cells]

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            values = [c.get_text(strip=True) for c in cells]
            record = {"stat_type": stat_type, "source": "dongqiudi"}
            for i, h in enumerate(headers):
                key_map = {
                    "球员": "name", "姓名": "name", "球队": "team_name",
                    "进球": "goals", "助攻": "assists", "出场": "appearances",
                    "时间": "minutes_played", "射门": "shots", "射正": "shots_on_target",
                    "黄牌": "yellow_cards", "红牌": "red_cards",
                }
                key = key_map.get(h, h)
                val = values[i] if i < len(values) else None
                # 尝试转换为数字
                if val and val.replace(".", "").replace("-", "").isdigit():
                    try:
                        record[key] = float(val) if "." in val else int(val)
                    except ValueError:
                        record[key] = val
                else:
                    record[key] = val
            results.append(record)
        return results

    @staticmethod
    def _parse_player_stats_text(text: str, league: str) -> list[dict]:
        """从纯文本解析球员统计（降级方案）"""
        results = []
        # 匹配: "1. 球员名 球队名 15球"
        pattern = re.compile(
            r"(\d+)\.\s+(.+?)\s+(.+?)\s+(\d+)(?:球|个|次)", re.MULTILINE
        )
        for m in pattern.finditer(text):
            results.append({
                "rank": int(m.group(1)),
                "name": m.group(2).strip(),
                "team_name": m.group(3).strip(),
                "value": int(m.group(4)),
                "league": league,
                "source": "dongqiudi",
            })
        return results

    # ──────────────────────────────────────────────────────
    # 5. 球队信息采集
    # ──────────────────────────────────────────────────────

    def _crawl_team_info(self, league: str, **kwargs) -> list[dict]:
        """采集球队基本信息

        从 /team/{id} 页面解析球队信息。
        需要 team_id 参数。
        """
        team_id = kwargs.get("team_id")
        if not team_id:
            logger.warning("team_info 需要提供 team_id 参数")
            return []

        url = f"{self.base_url}team/{team_id}"
        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("球队页请求失败: %s", e)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(separator="\n")
        result: dict = {"team_id": team_id, "source": "dongqiudi"}

        # 解析球队名称（通常在页面最顶部）
        # 格式: "奥美多\nOlmedo"
        name_match = re.match(r"^\s*(.+?)\n(.+?)\n", text)
        if name_match:
            result["name"] = name_match.group(1).strip()
            result["full_name"] = name_match.group(2).strip()

        # 解析城市: "📍 Riobamba"
        city_match = re.search(r"[📍📁]\s*(.+?)(?:\n|$)", text)
        if city_match:
            result["country"] = city_match.group(1).strip()

        # 解析成立年份: "🗓 成立于 1919"
        founded_match = re.search(r"成立[于于]?\s*(\d{4})", text)
        if founded_match:
            result["founded_year"] = int(founded_match.group(1))

        # 解析主场: "🏟 Estadio Olímpico de Riobamba · 18936 座"
        stadium_match = re.search(r"[🏟⚽]\s*(.+?)(?:\s*·\s*(\d+)\s*座)?(?:\n|$)", text)
        if stadium_match:
            result["stadium"] = stadium_match.group(1).strip()
            if stadium_match.group(2):
                result["stadium_capacity"] = int(stadium_match.group(2))

        # 从球队信息表格中提取
        info_table = soup.find("table")
        if info_table:
            for row in info_table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    val = cells[1].get_text(strip=True)
                    key_map = {
                        "英文名": "full_name", "城市": "country", "成立": "founded_year",
                        "主场": "stadium", "容量": "stadium_capacity", "市值": "market_value",
                    }
                    field = key_map.get(key)
                    if field:
                        if field in ("founded_year", "stadium_capacity"):
                            try:
                                result[field] = int(re.search(r"\d+", val).group())
                            except (AttributeError, ValueError):
                                result[field] = val
                        else:
                            result[field] = val

        # 解析 logo URL
        logo_img = soup.find("img", src=re.compile(r"qunliao|doubaocdn|dongqiudi"))
        if logo_img:
            result["logo_url"] = logo_img.get("src", "")

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/dongqiudi/team/{team_id}_{ts}.json"
        try:
            self._save_raw_to_hdfs(result, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败: %s", e)

        logger.info("[dongqiudi] 球队信息采集完成: team_id=%d, name=%s",
                     team_id, result.get("name", "unknown"))
        return [result]
