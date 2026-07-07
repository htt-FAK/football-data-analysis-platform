"""爬虫基类 — 提供反爬、重试、延迟、data_hash、HDFS 写入、日志记录"""

import hashlib
import json
import time
import random
import logging
import warnings as _warnings

# Suppress urllib3/chardet version-mismatch warning emitted by `requests`:
#   RequestsDependencyWarning: urllib3 (2.x) or chardet (...) doesn't match...
# This happens when requests 2.31+ is paired with a newer urllib3 than it
# officially pins.  The actual HTTP/TLS behaviour is unaffected.
_warnings.filterwarnings("ignore", message=".*urllib3.*doesn't match.*", category=DeprecationWarning)
# `requests` emits its own subclass that doesn't always get caught above:
try:
    from requests.exceptions import RequestsDependencyWarning as _RDW
    _warnings.filterwarnings("ignore", category=_RDW)
except ImportError:
    pass

# Silence InsecureRequestWarning globally — we deliberately pass verify=False
# for a handful of FIFA endpoints whose TLS chain causes UNEXPECTED_EOF errors.
from urllib3.exceptions import InsecureRequestWarning as _IRW
_warnings.filterwarnings("ignore", category=_IRW)

import requests
from abc import ABC, abstractmethod
from app.config import CRAWL_DELAY_MIN, CRAWL_DELAY_MAX
from app.hdfs_client import hdfs_client

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """所有爬虫的抽象基类，统一处理请求、延迟、去重与 HDFS 落盘"""

    def __init__(self, source_code: str, base_url: str = ""):
        self.source_code = source_code
        self.base_url = base_url
        self.session = requests.Session()
        # 设置完整浏览器请求头，应对 FBref/Understat 等严格反爬网站
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,image/apng,*/*;q=0.8,"
                      "application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": self.base_url,
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })

    def _delay(self):
        """在请求之间添加随机延迟，避免触发反爬"""
        time.sleep(random.uniform(CRAWL_DELAY_MIN, CRAWL_DELAY_MAX))

    def _fetch(self, url: str, retries: int = 3, **kwargs) -> requests.Response:
        """带重试机制的 HTTP 请求

        Args:
            url: 目标 URL
            retries: 最大重试次数（默认 3）
            **kwargs: 透传给 requests.Session.request 的参数

        Returns:
            requests.Response 对象

        Raises:
            requests.RequestException: 所有重试均失败后抛出
        """
        method = kwargs.pop("method", "GET")
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                self._delay()
                logger.info("[%s] 请求第 %d/%d 次: %s", self.source_code, attempt, retries, url)
                resp = self.session.request(method, url, timeout=30, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                last_exc = e
                logger.warning("[%s] 请求失败(%d/%d): %s | 错误: %s",
                               self.source_code, attempt, retries, url, e)
                # 指数退避，最大 30 秒
                backoff = min(2 ** attempt, 30)
                time.sleep(backoff)
        logger.error("[%s] 请求彻底失败: %s", self.source_code, url)
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _data_hash(data: dict) -> str:
        """对数据生成 SHA256 摘要，用于去重"""
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def _save_raw_to_hdfs(self, data, hdfs_path: str):
        """将原始数据以 JSON 形式写入 HDFS

        Args:
            data: 待保存的数据（dict 或 list）
            hdfs_path: HDFS 上的目标路径
        """
        payload = json.dumps(data, ensure_ascii=False)
        hdfs_client.write_json(payload, hdfs_path)
        logger.info("[%s] 原始数据已写入 HDFS: %s", self.source_code, hdfs_path)

    @abstractmethod
    def crawl(self, target: str, **kwargs):
        """子类实现具体采集逻辑"""
        raise NotImplementedError
