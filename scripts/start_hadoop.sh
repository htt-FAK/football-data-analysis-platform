#!/bin/bash
# 启动 Hadoop 伪分布式
start-dfs.sh
start-yarn.sh
echo "=== Hadoop 进程 ==="
jps
