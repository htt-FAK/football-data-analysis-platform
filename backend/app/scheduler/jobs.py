"""定时调度任务 — APScheduler"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.config import LIVE_CRAWL_INTERVAL, EXPORT_CRON

scheduler = AsyncIOScheduler()

def setup_jobs():
    """注册所有定时任务"""
    
    # 实时比赛数据 — 每 30 秒
    scheduler.add_job(
        crawl_live_matches,
        IntervalTrigger(seconds=LIVE_CRAWL_INTERVAL),
        id="live_crawl",
        name="实时比赛抓取",
        replace_existing=True,
    )
    
    # 日常全量采集 — 每天 06:00
    scheduler.add_job(
        daily_full_crawl,
        CronTrigger(hour=6, minute=0),
        id="daily_crawl",
        name="日常全量采集",
        replace_existing=True,
    )
    
    # Excel 报告导出 — 每天凌晨 02:00
    scheduler.add_job(
        export_daily_report,
        CronTrigger.from_crontab(EXPORT_CRON),
        id="daily_export",
        name="日报导出",
        replace_existing=True,
    )


async def crawl_live_matches():
    """抓取进行中比赛数据"""
    # TODO: 调用爬虫 + 更新 Redis
    pass


async def daily_full_crawl():
    """日常全量采集"""
    # TODO: 遍历所有启用的数据源执行采集
    pass


async def export_daily_report():
    """导出每日数据报告"""
    # TODO: 调用 ExcelExporter
    pass
