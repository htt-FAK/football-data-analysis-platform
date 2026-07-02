# ⚽ Football Data Analysis Platform

> **多源体育赛事数据采集与智能分析平台**

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)
![ECharts](https://img.shields.io/badge/ECharts-5-AA344D?logo=apacheecharts&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

🚀 **在线演示**：[http://118.126.102.143:4173/worldcup](http://118.126.102.143:4173/worldcup)

面向足球/体育赛事场景的全栈数据平台：从**多源数据采集**、**智能清洗标准化**、**结构化存储**，到**深度分析建模**、**实时推送**与**可视化展示**，形成完整的数据产品闭环。

---

## ✨ 项目亮点

- **多源异构采集**：整合 10+ 主流体育数据源，支持 API 与 HTML 双模式采集，内置反爬策略与重试机制
- **数据治理闭环**：字段映射 → 实体解析 → 去重 → 缺失值填补 → 异常值检测 → 多源融合，六层清洗管线
- **深度分析引擎**：球队攻防评分、球员五维能力模型、xG 预期进球、联赛竞争格局、关键事件影响量化
- **工程化架构**：前后端分离 · 微服务分层 · 定时调度 · 缓存加速 · WebSocket 实时推送

---

## 📸 项目预览

| 世界杯积分榜 | 球员能力雷达 | xG 预期进球 |
| :----------: | :----------: | :---------: |
| ![世界杯积分榜](export/ppt_charts/07_世界杯小组赛积分榜总览.png) | ![球员能力雷达](export/ppt_charts/11_巨星五维能力雷达对比.png) | ![xG预期进球](export/ppt_charts/14_xG预期进球时间线.png) |

| 球队攻防四象限 | 数据清洗流程 | AI 预测分析 |
| :-----------: | :----------: | :---------: |
| ![球队攻防](export/ppt_charts/09_球队攻防效率四象限.png) | ![数据清洗](export/ppt_charts/04_数据清洗与标准化流水线.png) | ![AI预测](export/ppt_charts/16_AI预测准确率分析.png) |

> 更多可视化图表请查看 [export/ppt_charts/](export/ppt_charts/)

---

## 🎯 核心功能

### 1. 多源数据采集

内置 10+ 数据源采集器，覆盖赛程、赛果、积分榜、球员统计、射门事件等维度：

| 数据源 | 类型 | 覆盖内容 |
|--------|------|---------|
| FIFA Official | API | 世界杯官方数据 |
| API-Football | API | 联赛/杯赛结构化数据 |
| FBref | HTML | 高级球员统计 |
| Understat | HTML | xG 预期进球数据 |
| 懂球帝 | HTML | 中文赛程赛果 |
| Football-Data | API | 欧洲五大联赛 |
| TheSportsDB | API | 球队/球员元数据 |
| OpenLigaDB | API | 德甲等联赛 |
| TeamRankings | HTML | 排名数据 |
| StatsBomb | Open Data | 高级事件数据 |

**采集能力**：
- 自动重试 + 指数退避（最多 5 次）
- 随机延迟 + User-Agent 轮换
- 多目标分发（live/schedule/standings/players）
- HDFS 原始数据落盘

### 2. 智能数据清洗

六层数据治理管线，保障数据质量：

```
原始数据 → 字段映射 → 实体解析 → 去重 → 缺失值填补 → 异常值检测 → 多源融合 → 高质量数据
```

| 模块 | 说明 | 核心文件 |
|------|------|---------|
| 字段映射 | 统一多源字段口径与单位 | `field_mapping.py` |
| 实体解析 | 球队/球员/联赛别名归一化 | `entity_resolver.py` |
| 去重处理 | 多源重复数据智能合并 | `dedup.py` |
| 缺失值填补 | 按字段类型智能填充 | `missing_value.py` |
| 异常值检测 | 规则校验 + Z-Score + IQR 三法并行 | `outlier.py` |
| 多源融合 | 按可信度优先级合并 | `merge.py` |

### 3. 深度分析引擎

五大分析维度，从宏观联赛到微观事件全覆盖：

| 分析方向 | 说明 | 核心文件 |
|---------|------|---------|
| 联赛竞争格局 | 竞争激烈度、强弱分布、趋势分析 | `league_analysis.py` |
| 球队攻防评分 | 进攻/防守/组织三维评分 | `team_rating.py` |
| 球员能力模型 | 五维能力雷达 + 位置加权 | `player_rating.py` |
| xG 预期进球 | 基于射门特征的进球概率 | `xg_model.py` |
| 事件影响量化 | 进球/红牌/点球等事件影响力 | `event_impact.py` |

### 4. 可视化平台

React + TypeScript + ECharts 构建的交互式数据平台：

- 🏆 **世界杯仪表板**：积分榜、射手榜、近期比赛、对阵图
- ⚽ **比赛详情**：xG 时间线、阵容、事件流、统计对比
- 👤 **球员详情**：五维雷达图、生涯数据、位置分布
- 🏟️ **球队详情**：攻防数据、球员名单、比赛记录
- 🤖 **AI 预测**：比赛结果预测 + 多轮分析 + 准确率统计
- 📊 **联赛页面**：积分榜、赛程、球队列表

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     多源体育数据（10+）                       │
│  FIFA · API-Football · FBref · Understat · 懂球帝 · ...     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                   爬虫采集层 (Crawlers)                      │
│        基类封装 · 重试机制 · 反爬策略 · 多目标分发            │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                  数据清洗层 (Cleaning)                       │
│   字段映射 · 实体解析 · 去重 · 缺失值 · 异常值 · 多源合并     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    存储层 (Storage)                          │
│              MySQL · Redis · Hadoop HDFS                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                   分析层 (Analysis)                          │
│   联赛格局 · 球队评分 · 球员能力 · xG模型 · 事件影响          │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                   服务层 (Services)                          │
│    FastAPI · WebSocket · APScheduler · Excel导出            │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                 前端展示层 (Frontend)                        │
│           React · TypeScript · Vite · ECharts               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 技术栈

### 后端
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logo=sqlalchemy&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikitlearn&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![APScheduler](https://img.shields.io/badge/APScheduler-336791?logo=clock&logoColor=white)

### 前端
![React](https://img.shields.io/badge/React-61DAFB?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)
![ECharts](https://img.shields.io/badge/ECharts-AA344D?logo=apacheecharts&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-06B6D4?logo=tailwindcss&logoColor=white)

### 数据与部署
![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white)
![Hadoop](https://img.shields.io/badge/Hadoop-66CCFF?logo=apachehadoop&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=white)

---

## 📁 项目结构

```
football-data-analysis-platform/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── analysis/           # 分析模型（联赛/球队/球员/xG/事件）
│   │   ├── api/                # API 路由（10+ 业务模块）
│   │   ├── cleaning/           # 数据清洗（6层管线）
│   │   ├── crawlers/           # 多源采集器（10+ 数据源）
│   │   ├── models/             # SQLAlchemy 数据模型
│   │   ├── prediction/         # AI 预测模块
│   │   ├── scheduler/          # 定时任务调度
│   │   ├── services/           # 业务服务层
│   │   ├── export/             # Excel 导出
│   │   ├── static/             # 静态页面
│   │   ├── config.py           # 配置管理
│   │   ├── database.py         # 数据库连接
│   │   ├── redis_client.py     # Redis 客户端
│   │   ├── hdfs_client.py      # HDFS 客户端
│   │   └── main.py             # 应用入口
│   ├── export_football_data.py
│   └── requirements.txt
│
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── api/                # API 封装
│   │   ├── components/         # 通用组件
│   │   ├── pages/              # 页面组件
│   │   ├── hooks/              # 自定义 Hooks
│   │   ├── stores/             # 状态管理
│   │   ├── types/              # TypeScript 类型
│   │   └── ...
│   └── 配置文件
│
├── scripts/                    # 工具脚本
│   ├── generate_ppt_charts.py  # PPT 图表生成
│   ├── run_fifa_worldcup_ingest.py  # FIFA 数据导入
│   ├── visualize_player_radar.py    # 雷达图生成
│   └── start_*.sh              # 启动脚本
│
├── export/
│   ├── ppt_charts/             # 16 张可视化展示图表
│   ├── sample_players/         # 示例球员数据
│   └── worldcup_fifa/          # FIFA 世界杯示例数据
│
├── .env.example                # 环境变量模板
├── .gitignore
├── deploy.sh                   # 部署脚本
└── README.md
```

---

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/htt-FAK/football-data-analysis-platform.git
cd football-data-analysis-platform
```

### 2. 后端启动
```bash
cd backend
pip install -r requirements.txt

# 配置环境变量
cp ../.env.example .env
# 编辑 .env 填入数据库、Redis 等配置

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 前端启动
```bash
cd frontend
npm install
npm run dev
```

### 4. 访问
- 前端页面：http://localhost:5173
- API 文档：http://localhost:8000/docs

---

## 📄 API 模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 联赛 | `/api/v1/leagues` | 联赛列表、详情、积分榜 |
| 球队 | `/api/v1/teams` | 球队信息、阵容、统计 |
| 球员 | `/api/v1/players` | 球员列表、详情、能力评分 |
| 比赛 | `/api/v1/matches` | 赛程、赛果、比赛详情 |
| 直播 | `/api/v1/live` | 实时比分、事件推送 |
| 预测 | `/api/v1/predict` | AI 比赛预测 |
| 爬虫 | `/api/v1/crawl` | 数据采集任务管理 |
| 数据源 | `/api/v1/data-sources` | 数据源状态监控 |
| 世界杯 | `/api/v1/worldcup` | 世界杯专属接口 |
| WebSocket | `/ws` | 实时数据推送 |

---

## 📝 License

本项目为课程设计与个人学习实践项目，仅供学习、交流与作品展示使用。

---

<p align="center">
  <sub>Built with ❤️ using Python & React</sub>
</p>
