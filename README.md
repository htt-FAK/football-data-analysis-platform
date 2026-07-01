# Football Data Analysis Platform

> 体育赛事数据采集与分析平台 · 课程设计作品集项目

一个面向足球/体育赛事场景的数据平台原型：从多源数据采集、清洗标准化、结构化存储，到分析建模、实时推送与可视化展示，形成相对完整的数据产品闭环。

## 项目亮点

- **多源数据采集**：整合懂球帝、FBref、Understat、Football-Data 等多个数据源
- **数据治理闭环**：包含字段映射、去重、缺失值处理、异常值检测、多源合并
- **分析能力**：支持球队评分、球员能力分析、xG 模型、联赛格局分析、关键事件影响评估
- **工程化结构**：后端、前端、建表脚本、部署脚本、调度模块拆分清晰
- **可扩展性**：已预留 HDFS、Redis、WebSocket、定时任务等能力接口

## 适用场景

该项目适合作为以下方向的课程设计 / 作品集展示：

- 体育数据采集与分析
- Web 全栈课程项目
- 数据工程与数据治理实践
- 数据产品原型设计
- FastAPI + React 的前后端分离项目

## 系统架构

```text
多源体育数据
    ↓
爬虫采集层（Crawlers）
    ↓
数据清洗层（映射 / 去重 / 缺失值 / 异常值 / 合并）
    ↓
存储层（MySQL / HDFS / Redis）
    ↓
分析层（球队 / 球员 / xG / 联赛 / 事件影响）
    ↓
服务层（FastAPI / WebSocket / Scheduler / Export）
    ↓
前端展示层（React + TypeScript + ECharts）
```

## 核心功能

### 1. 多源数据采集
当前后端已按模块拆分多个数据源采集器，包括：

- 懂球帝
- FBref
- Understat
- Football-Data
- API-Football
- TheSportsDB
- OpenLigaDB
- TeamRankings

### 2. 数据清洗与标准化
项目提供较完整的数据治理流程：

- `field_mapping.py`：统一多源字段口径
- `dedup.py`：去重处理
- `missing_value.py`：缺失值填补
- `outlier.py`：异常值检测
- `merge.py`：多源数据合并

### 3. 数据分析模块
项目内置多个分析方向：

- **team_rating.py**：球队攻防评分
- **player_rating.py**：球员能力评估
- **xg_model.py**：预期进球（xG）分析
- **league_analysis.py**：联赛竞争格局分析
- **event_impact.py**：关键事件影响分析

### 4. 服务能力
- REST API（FastAPI）
- WebSocket 实时推送
- Redis 缓存与消息能力
- APScheduler 定时任务
- Excel 报表导出

## 技术栈

### 后端
- Python 3.9+
- FastAPI
- SQLAlchemy
- pandas
- scikit-learn
- Redis
- APScheduler

### 前端
- React
- TypeScript
- Vite
- ECharts

### 数据与部署
- MySQL
- Hadoop HDFS
- Linux / Shell 脚本部署

## 项目结构

```text
课设/
├── backend/                 # FastAPI 后端核心代码
│   ├── app/
│   │   ├── analysis/        # 分析模型
│   │   ├── api/             # API 路由
│   │   ├── cleaning/        # 数据清洗
│   │   ├── crawlers/        # 多源采集器
│   │   ├── export/          # 导出功能
│   │   ├── models/          # 数据模型
│   │   ├── scheduler/       # 定时任务
│   │   └── services/        # 业务服务层
│   └── requirements.txt
├── frontend/                # 前端目录
├── scripts/                 # 启动脚本
├── deploy.sh                # 部署脚本
├── init_database.sql        # 数据库初始化脚本
├── .env.example             # 环境变量模板
└── README.md
```

## 快速开始

### 1. 克隆项目
```bash
git clone git@github.com:htt-FAK/football-data-analysis-platform.git
cd football-data-analysis-platform
```

### 2. 安装后端依赖
```bash
cd backend
pip install -r requirements.txt
```

### 3. 配置环境变量
参考根目录下的 `.env.example` 补充数据库、Redis、HDFS 等配置。

### 4. 初始化数据库
```bash
mysql -u root -p < ../init_database.sql
```

### 5. 启动后端
```bash
uvicorn app.main:app --reload
```

如需完整启动链路，可进一步结合：
- `scripts/start_backend.sh`
- `scripts/start_frontend.sh`
- `scripts/start_hadoop.sh`
- `deploy.sh`

## API 与展示能力

项目后端已按业务拆分多个接口模块，例如：

- `leagues.py`
- `teams.py`
- `players.py`
- `matches.py`
- `live.py`
- `crawl.py`
- `data_sources.py`
- `websocket.py`

这意味着项目不仅是“采集脚本集合”，而是朝着**可交互平台**方向设计的完整原型。

## 项目价值

这个项目比较适合在 GitHub 上作为作品集展示，因为它覆盖了从“数据获取”到“数据服务”的完整链路：

- 有明确业务场景：体育赛事数据分析
- 有后端架构：FastAPI + 服务分层 + 数据模型
- 有数据工程思路：采集、清洗、标准化、存储、分析
- 有平台能力：接口、实时推送、调度、导出
- 有进一步扩展空间：前端大屏、更多联赛、更多分析模型

## 仓库说明

当前仓库中仍保留了一些课程过程文档、参考 PDF、任务安排表等资料。这些文件主要用于课程交付与过程留档，不代表项目主体。

如果后续要把仓库进一步打磨成更纯粹的作品集，可以继续做两步：

1. 把课程模板/参考文档移动到 `docs/academic/` 或单独归档
2. 继续补充项目截图、接口示例、页面预览与部署说明

## 后续可优化方向

- 增加首页截图 / 系统架构图 / 页面预览图
- 增加接口示例与测试说明
- 增加 Docker / Docker Compose 部署方式
- 清理课程交付型附件，保留更纯粹的项目结构
- 完善前端页面说明，提高作品集展示感

## License

本项目为课程设计与个人学习实践项目，仅供学习、交流与作品展示使用。
## World Cup strategy

This repository now follows a task-oriented World Cup delivery strategy:

- Match-level World Cup data is the P0 path.
- Player contribution summaries are guaranteed before advanced radar views.
- Advanced player analytics are rendered only when data completeness is high enough.
- API-Football is the primary structured source for live and basic player tasks.
- FBref and Understat remain advanced enrichment sources.

