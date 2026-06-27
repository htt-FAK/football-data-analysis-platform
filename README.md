# 09 体育赛事数据采集与分析

> 中国高科（CHINA HI-TECH GROUP）课程设计项目
>
> 聚焦海量体育赛事数据的自动化采集与深度解析，将非结构化赛事信息转化为标准化数据资产，通过多维度挖掘为战术复盘、媒体传播和竞技训练提供数据支撑。

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端 | FastAPI + SQLAlchemy | Python 3.9+ |
| 前端 | React + TypeScript + Vite | Node.js 18+ |
| 数据库 | MySQL | 8.0 |
| 大数据存储 | Hadoop HDFS | 3.3.6 (伪分布式) |
| 缓存 | Redis | 7.x |
| 可视化 | ECharts | - |
| 爬虫 | requests + BeautifulSoup + pandas | - |
| 分析 | pandas + scikit-learn | - |
| Excel 导出 | openpyxl + xlsxwriter | - |

## 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone <repo-url>
cd 09-sports-analytics

# 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入真实配置
```

### 2. 服务器部署

```bash
# 一键部署（安装 Python/Node.js/Redis + HDFS 初始化 + 前端创建）
bash deploy.sh
```

### 3. 数据库初始化

```bash
mysql -h <DB_HOST> -u <DB_USER> -p <DB_NAME> < init_database.sql
```

### 4. 启动服务

```bash
# 启动后端
bash scripts/start_backend.sh

# 启动前端（新终端）
bash scripts/start_frontend.sh
```

### 5. 访问

- 后端 API 文档: http://localhost:8000/docs
- 前端页面: http://localhost:5173

## 项目结构

```
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用入口
│   │   ├── config.py        # 配置管理
│   │   ├── database.py      # MySQL 连接
│   │   ├── redis_client.py  # Redis 客户端
│   │   ├── hdfs_client.py   # HDFS 客户端
│   │   ├── api/             # API 路由 (8 模块)
│   │   ├── crawlers/        # 爬虫模块 (8 数据源)
│   │   ├── models/          # SQLAlchemy 模型 (12 表)
│   │   ├── services/        # 业务逻辑层
│   │   ├── cleaning/        # 数据清洗管道
│   │   ├── analysis/        # 分析模型
│   │   ├── export/          # Excel 导出
│   │   └── scheduler/       # 定时调度
│   └── requirements.txt
├── frontend/                # React + TS 前端 (deploy.sh 生成)
├── scripts/                 # 启动脚本
├── deploy/                  # 部署脚本
├── deploy.sh                # 一键部署
├── init_database.sql        # 建表脚本
└── 09体育赛事数据采集与分析-项目方案.md
```

## 数据源

| 数据源 | 采集内容 | 方式 |
|--------|---------|------|
| 懂球帝 | 赛程/比分/积分榜/球员统计 | HTML 爬虫 |
| FBref | 球队/球员高级统计 (xG等) | pandas.read_html |
| Understat | 射门坐标/xG 时间线 | JSON 接口 |
| Football-Data | 历史比赛结果 | CSV 下载 |

## 联赛覆盖

- 2026 世界杯
- 英超 (Premier League)
