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
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", 1))
REDIS_CONNECT_TIMEOUT = float(os.getenv("REDIS_CONNECT_TIMEOUT", 1))
REDIS_DEGRADE_TIMEOUT = float(os.getenv("REDIS_DEGRADE_TIMEOUT", 1.5))

# ── WebSocket ──
WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", 25))
WS_LIVE_POLL_INTERVAL = int(os.getenv("WS_LIVE_POLL_INTERVAL", 30))
REDIS_LIVE_TTL = int(os.getenv("REDIS_LIVE_TTL", 300))

# ── 爬虫 ──
CRAWL_DELAY_MIN = float(os.getenv("CRAWL_DELAY_MIN", 2))
CRAWL_DELAY_MAX = float(os.getenv("CRAWL_DELAY_MAX", 5))
LIVE_CRAWL_INTERVAL = int(os.getenv("LIVE_CRAWL_INTERVAL", 30))
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "True").lower() == "true"

# ── Excel 导出 ──
EXPORT_DIR = os.getenv("EXPORT_DIR", "./export")
EXPORT_CRON = os.getenv("EXPORT_CRON", "0 2 * * *")
EXPORT_INCLUDE_ANOMALY = os.getenv("EXPORT_INCLUDE_ANOMALY", "True") == "True"
EXPORT_INCLUDE_COMPARISON = os.getenv("EXPORT_INCLUDE_COMPARISON", "True") == "True"

# ── API-Football（可选）──
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_FOOTBALL_BASE = os.getenv("API_FOOTBALL_BASE", "https://v3.football.api-sports.io")

# ── AI 预测（阶跃星辰 step-3.7-flash + DeepSeek V4 Flash）──
STEPFUN_API_KEY = os.getenv("STEPFUN_API_KEY", "")
STEPFUN_BASE_URL = os.getenv("STEPFUN_BASE_URL", "https://api.stepfun.com/v1")
STEPFUN_MODEL = os.getenv("STEPFUN_MODEL", "step-3.7-flash")
# 视觉/多模态模型：图片理解推荐 step-1o-turbo-vision，视频理解用 step-3.7-flash（原生支持）
STEPFUN_VISION_MODEL = os.getenv("STEPFUN_VISION_MODEL", "step-1o-turbo-vision")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://token.sensenova.cn/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
# 思考强度：low / medium / high / none
AI_REASONING_EFFORT = os.getenv("AI_REASONING_EFFORT", "high")
# 赛前多少小时触发自动预测
AI_PREDICTION_HOURS_BEFORE = float(os.getenv("AI_PREDICTION_HOURS_BEFORE", "5"))
# 调度器扫描间隔（秒）
AI_PREDICTION_SCAN_SECONDS = int(os.getenv("AI_PREDICTION_SCAN_SECONDS", "900"))
# 触发窗口容忍（小时），扫描 match_date ∈ [now + H - TOL, now + H + TOL]
AI_PREDICTION_WINDOW_TOLERANCE_HOURS = float(os.getenv("AI_PREDICTION_WINDOW_TOLERANCE_HOURS", "0.5"))
# 单轮 LLM 请求超时（秒）
AI_REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", "120"))
# 是否启用自动预测调度
ENABLE_AI_PREDICTION = os.getenv("ENABLE_AI_PREDICTION", "True").lower() == "true"

# ── 联网搜索 API（独立于阶跃原生 web_search，作为实时情报来源）──
# provider 选哪个：tavily / serper / none（none=禁用联网搜索）
WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "tavily").lower()
# Tavily（https://tavily.com，免费 1000 次/月）
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")
# Serper（https://serper.dev，免费 2500 次/月）
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_BASE_URL = os.getenv("SERPER_BASE_URL", "https://google.serper.dev")
# 每场比赛每轮搜索返回的最大结果数
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "6"))
WEB_SEARCH_TIMEOUT = int(os.getenv("WEB_SEARCH_TIMEOUT", "20"))
# 视觉/视频理解增强：是否对搜索到的图片/视频做视觉分析（需 step-1o-turbo-vision）
ENABLE_VISION_INTEL = os.getenv("ENABLE_VISION_INTEL", "True").lower() == "true"
# 每场比赛视觉分析最多处理的图片数（控制 token 与耗时）
VISION_MAX_IMAGES = int(os.getenv("VISION_MAX_IMAGES", "5"))
