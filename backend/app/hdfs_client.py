"""HDFS 客户端封装 — Parquet 文件读写"""

import os
import tempfile
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from hdfs import InsecureClient
from app.config import HDFS_URL, HDFS_USER


class HDFSClient:
    """HDFS 操作封装，支持 DataFrame 读写"""

    def __init__(self):
        self.client = InsecureClient(HDFS_URL, user=HDFS_USER)

    def write_json(self, data: str, hdfs_path: str):
        """将 JSON 字符串写入 HDFS"""
        self.client.write(hdfs_path, data.encode("utf-8"), overwrite=True)

    def read_json(self, hdfs_path: str) -> str:
        """读取 HDFS 上的 JSON 文件"""
        with self.client.read(hdfs_path) as reader:
            return reader.read().decode("utf-8")

    def write_parquet(self, df: pd.DataFrame, hdfs_path: str):
        """将 DataFrame 写入 HDFS（Parquet 格式）"""
        table = pa.Table.from_pandas(df)
        tmp = os.path.join(tempfile.gettempdir(), os.path.basename(hdfs_path))
        pq.write_table(table, tmp)
        with open(tmp, "rb") as f:
            self.client.write(hdfs_path, f, overwrite=True)
        os.remove(tmp)

    def read_parquet(self, hdfs_path: str) -> pd.DataFrame:
        """读取 HDFS 上的 Parquet 文件为 DataFrame"""
        tmp = os.path.join(tempfile.gettempdir(), os.path.basename(hdfs_path))
        with self.client.read(hdfs_path) as reader:
            data = reader.read()
        with open(tmp, "wb") as f:
            f.write(data)
        df = pq.read_table(tmp).to_pandas()
        os.remove(tmp)
        return df

    def mkdirs(self, hdfs_path: str):
        """创建 HDFS 目录"""
        self.client.makedirs(hdfs_path)

    def exists(self, hdfs_path: str) -> bool:
        """检查路径是否存在"""
        return self.client.status(hdfs_path, strict=False) is not None

    def list_dir(self, hdfs_path: str) -> list:
        """列出目录内容"""
        return self.client.list(hdfs_path)


# 全局实例
hdfs_client = HDFSClient()
