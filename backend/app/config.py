"""配置管理模块 — 从 .env 文件读取所有环境变量"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── MySQL 数据库 ──
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "sports_analytics")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ── HDFS ──
HDFS_HOST = os.getenv("HDFS_HOST", "localhost")
HDFS_PORT = int(os.getenv("HDFS_PORT", 9870))
HDFS_USER = os.getenv("HDFS_USER", "root")
HDFS_URL = f"http://{HDFS_HOST}:{HDFS_PORT}"

# ── FastAPI ──
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# ── Redis ──
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

# ── WebSocket ──
WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", 25))
WS_LIVE_POLL_INTERVAL = int(os.getenv("WS_LIVE_POLL_INTERVAL", 30))
REDIS_LIVE_TTL = int(os.getenv("REDIS_LIVE_TTL", 300))

# ── 爬虫 ──
CRAWL_DELAY_MIN = float(os.getenv("CRAWL_DELAY_MIN", 2))
CRAWL_DELAY_MAX = float(os.getenv("CRAWL_DELAY_MAX", 5))
LIVE_CRAWL_INTERVAL = int(os.getenv("LIVE_CRAWL_INTERVAL", 30))

# ── Excel 导出 ──
EXPORT_DIR = os.getenv("EXPORT_DIR", "./export")
EXPORT_CRON = os.getenv("EXPORT_CRON", "0 2 * * *")
EXPORT_INCLUDE_ANOMALY = os.getenv("EXPORT_INCLUDE_ANOMALY", "True") == "True"
EXPORT_INCLUDE_COMPARISON = os.getenv("EXPORT_INCLUDE_COMPARISON", "True") == "True"

# ── API-Football（可选）──
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_FOOTBALL_BASE = os.getenv("API_FOOTBALL_BASE", "https://v3.football.api-sports.io")
