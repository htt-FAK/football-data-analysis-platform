"""HDFS client helpers for JSON and Parquet persistence."""

import os
import tempfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from hdfs import InsecureClient

from app.config import HDFS_URL, HDFS_USER


class HDFSClient:
    """Small wrapper around WebHDFS operations used by the project."""

    def __init__(self):
        self.client = InsecureClient(HDFS_URL, user=HDFS_USER)

    def write_json(self, data: str, hdfs_path: str):
        """Write a UTF-8 JSON string to HDFS, creating parent dirs if needed."""
        parent = os.path.dirname(hdfs_path.rstrip("/"))
        if parent:
            self.client.makedirs(parent)
        with self.client.write(hdfs_path, overwrite=True, encoding="utf-8") as writer:
            writer.write(data)

    def read_json(self, hdfs_path: str) -> str:
        """Read a JSON file from HDFS as a UTF-8 string."""
        with self.client.read(hdfs_path, encoding="utf-8") as reader:
            return reader.read()

    def write_parquet(self, df: pd.DataFrame, hdfs_path: str):
        """Write a DataFrame to HDFS in Parquet format."""
        table = pa.Table.from_pandas(df)
        tmp = os.path.join(tempfile.gettempdir(), os.path.basename(hdfs_path))
        pq.write_table(table, tmp)
        parent = os.path.dirname(hdfs_path.rstrip("/"))
        if parent:
            self.client.makedirs(parent)
        with open(tmp, "rb") as f:
            self.client.write(hdfs_path, f, overwrite=True)
        os.remove(tmp)

    def read_parquet(self, hdfs_path: str) -> pd.DataFrame:
        """Read a Parquet file from HDFS into a DataFrame."""
        tmp = os.path.join(tempfile.gettempdir(), os.path.basename(hdfs_path))
        with self.client.read(hdfs_path) as reader:
            data = reader.read()
        with open(tmp, "wb") as f:
            f.write(data)
        df = pq.read_table(tmp).to_pandas()
        os.remove(tmp)
        return df

    def mkdirs(self, hdfs_path: str):
        """Create a directory on HDFS."""
        self.client.makedirs(hdfs_path)

    def exists(self, hdfs_path: str) -> bool:
        """Check whether a path exists on HDFS."""
        return self.client.status(hdfs_path, strict=False) is not None

    def list_dir(self, hdfs_path: str) -> list:
        """List one HDFS directory."""
        return self.client.list(hdfs_path)


hdfs_client = HDFSClient()
