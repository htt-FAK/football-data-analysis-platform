"""
FIFA世界杯数据独立爬虫 - 无需后端框架即可运行
使用说明：
1. 确保已安装 requests 库: pip install requests
2. 直接运行: python standalone_fifa_crawler.py
3. 数据将保存到当前目录的 output 文件夹
"""

import requests
import json
import time
import os
from datetime import datetime
from pathlib import Path


class SimpleFIFACrawler:
    """简化的FIFA爬虫，无需后端框架"""
    
    API_BASE_URL = "https://api.fifa.com/api/v3"
    COMPETITION_ID = "17"
    SEASON_ID = "285023"
    GROUP_STAGE_ID = "289273"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.fifa.com/",
        })
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
    
    def fetch_standings(self):
        """获取小组积分榜"""
        print("正在获取小组积分榜...")
        url = f"{self.API_BASE_URL}/calendar/{self.COMPETITION_ID}/{self.SEASON_ID}/{self.GROUP_STAGE_ID}/standing"
        params = {
            "language": "en",
            "count": 200,
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            standings = []
            for item in data.get("Results", []):
                team = item.get("Team") or {}
                standing = {
                    "team": self._get_localized_text(team.get("Name")),
                    "position": item.get("Position"),
                    "played": item.get("Played", 0),
                    "won": item.get("Won", 0),
                    "drawn": item.get("Drawn", 0),
                    "lost": item.get("Lost", 0),
                    "goals_for": item.get("For", 0),
                    "goals_against": item.get("Against", 0),
                    "goal_diff": item.get("GoalsDiference", 0),
                    "points": item.get("Points", 0),
                    "group": self._get_localized_text(item.get("Group")),
                }
                standings.append(standing)
            
            # 保存为JSON
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"standings_{timestamp}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(standings, f, ensure_ascii=False, indent=2)
            
            print(f"[OK] 成功获取 {len(standings)} 条积分榜数据")
            print(f"  保存至: {output_file}")
            return standings
            
        except Exception as e:
            print(f"[ERROR] 获取积分榜失败: {e}")
            return []
    
    def fetch_schedule(self):
        """获取赛程"""
        print("\n正在获取赛程...")
        url = f"{self.API_BASE_URL}/calendar/matches"
        params = {
            "count": 200,
            "from": "2026-06-11",
            "to": "2026-07-19",
            "idCompetition": self.COMPETITION_ID,
            "language": "en",
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            matches = []
            for item in data.get("Results", []):
                home = item.get("Home") or {}
                away = item.get("Away") or {}
                
                match = {
                    "match_id": item.get("IdMatch"),
                    "date": item.get("Date"),
                    "home_team": self._get_localized_text(home.get("TeamName")),
                    "away_team": self._get_localized_text(away.get("TeamName")),
                    "home_score": item.get("HomeTeamScore"),
                    "away_score": item.get("AwayTeamScore"),
                    "status": item.get("MatchStatus"),
                    "group": self._get_localized_text(item.get("GroupName")),
                }
                matches.append(match)
            
            # 保存为JSON
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"schedule_{timestamp}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(matches, f, ensure_ascii=False, indent=2)
            
            print(f"[OK] 成功获取 {len(matches)} 场比赛数据")
            print(f"  保存至: {output_file}")
            return matches
            
        except Exception as e:
            print(f"[ERROR] 获取赛程失败: {e}")
            return []
    
    def fetch_teams(self):
        """获取参赛球队列表"""
        print("\n正在获取参赛球队...")
        url = f"https://cxm-api.fifa.com/fifaplusweb/api/getAllTeamPages/{self.SEASON_ID}"
        params = {"locale": "en"}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            teams = response.json()
            
            if not isinstance(teams, list):
                print("[ERROR] 球队数据格式异常")
                return []
            
            team_list = []
            for team in teams:
                team_info = {
                    "team_id": team.get("teamPageId"),
                    "name": team.get("teamName"),
                    "country": team.get("country"),
                }
                team_list.append(team_info)
            
            # 保存为JSON
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"teams_{timestamp}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(team_list, f, ensure_ascii=False, indent=2)
            
            print(f"[OK] 成功获取 {len(team_list)} 支球队信息")
            print(f"  保存至: {output_file}")
            return team_list
            
        except Exception as e:
            print(f"[ERROR] 获取球队列表失败: {e}")
            return []
    
    def _get_localized_text(self, value):
        """从本地化对象中提取文本"""
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict) and entry.get("Description"):
                    return str(entry["Description"]).strip()
            return ""
        if isinstance(value, dict):
            description = value.get("Description")
            return str(description).strip() if description else ""
        if value is None:
            return ""
        return str(value).strip()
    
    def run_all(self):
        """运行所有爬取任务"""
        print("=" * 60)
        print("FIFA世界杯数据爬虫 - 独立版")
        print("=" * 60)
        
        self.fetch_standings()
        time.sleep(1)
        self.fetch_schedule()
        time.sleep(1)
        self.fetch_teams()
        
        print("\n" + "=" * 60)
        print("爬取完成！所有数据已保存至 output 文件夹")
        print("=" * 60)


if __name__ == "__main__":
    crawler = SimpleFIFACrawler()
    crawler.run_all()
