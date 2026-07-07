# ⚽ 多源体育赛事数据采集与智能分析平台

> **从 10+ 数据源到 AI 预测，一条完整的足球数据工程管道** — 聚焦 **2026 FIFA 世界杯**

[🚀 **在线体验 → 世界杯数据大屏**](http://118.126.102.143:4173/worldcup)

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![Hadoop](https://img.shields.io/badge/Hadoop-HDFS-66CCFF?logo=apachehadoop&logoColor=white)

![World Cup Dashboard](export/ppt_charts/07_世界杯小组赛积分榜总览.png)

---

## 为什么做这个项目？

体育数据散落在 FIFA 官网、第三方 API、HTML 网页等数十个异构来源中，格式不统一、更新频率各异、反爬策略不同。大多数开源项目只解决了其中一环。

本项目试图回答一个问题：**如何从零搭建一条端到端的体育数据管道** — 从网页抓取、数据清洗治理、结构化存储，到分析建模、AI 预测、实时推送和可视化展示？

技术栈覆盖 Python（FastAPI + SQLAlchemy + pandas）、React 19（TypeScript + Zustand + React Query）、MySQL + Redis + Hadoop HDFS，以及 LLM 双模型集成。

---

## 它能做什么？

| 能力 | 说明 |
|------|------|
| 🔌 多源采集 | 10+ 数据源（FIFA、API-Football、FBref、Understat、StatsBomb 等），API/HTML 双模式，自动重试 + 指数退避 |
| 🧹 六层清洗 | 字段映射 → 实体解析 → 去重 → 缺失值填补 → 异常值检测 → 多源融合 |
| 📊 深度分析 | 球队攻防评分、球员五维雷达、xG 预期进球、联赛竞争格局、关键事件影响量化 |
| 🤖 AI 预测 | 双模型（Step-3.7-Flash + DeepSeek V4）+ Firecrawl 实时情报检索 + 阵容图片视觉分析 |
| ⚡ 实时推送 | WebSocket 直播比分，30s 定时爬取，赛后自动刷新球员数据 |

---

## 📸 核心场景

**数据采集与治理：**
| 多源异构采集架构 | 六层清洗流水线 | 异常值智能检测 |
|:---:|:---:|:---:|
| 10+ 数据源统一接入，API/HTML 双模式 | 字段映射 → 实体解析 → 去重 → 填补 → 检测 → 融合 | Z-Score + IQR + 规则三法并行 |
| ![采集架构](export/ppt_charts/01_多源异构数据采集架构.png) | ![清洗流水线](export/ppt_charts/04_数据清洗与标准化流水线.png) | ![异常值检测](export/ppt_charts/05_异常值智能检测与处理.png) |

**世界杯深度分析：**
| 小组积分榜总览 | 球队攻防四象限 | 巨星五维雷达 |
|:---:|:---:|:---:|
| 48 队 12 组实时积分与晋级态势 | 进攻效率 vs 防守稳固性定位 | 梅西、姆巴佩等核心能力对比 |
| ![积分榜](export/ppt_charts/07_世界杯小组赛积分榜总览.png) | ![攻防四象限](export/ppt_charts/09_球队攻防效率四象限.png) | ![五维雷达](export/ppt_charts/11_巨星五维能力雷达对比.png) |

> 完整 16 张分析图表见 [export/ppt_charts/](export/ppt_charts/)，含 xG 时间线、AI 预测准确率、射手榜等

---

## 🔌 API 示例

### 世界杯小组积分榜

```bash
GET /api/v1/worldcup/summary
```

```json
{
  "league": "世界杯",
  "season": "2026",
  "groups": [
    {
      "group": "A",
      "standings": [
        {"rank": 1, "team": "摩洛哥", "played": 3, "won": 2, "drawn": 1, "lost": 0, "goals_for": 5, "goals_against": 1, "points": 7},
        {"rank": 2, "team": "西班牙", "played": 3, "won": 2, "drawn": 0, "lost": 1, "goals_for": 4, "goals_against": 3, "points": 6},
        {"rank": 3, "team": "乌拉圭", "played": 3, "won": 1, "drawn": 1, "lost": 1, "goals_for": 3, "goals_against": 3, "points": 4},
        {"rank": 4, "team": "沙特阿拉伯", "played": 3, "won": 0, "drawn": 0, "lost": 3, "goals_for": 1, "goals_against": 6, "points": 0}
      ]
    }
  ]
}
```

### 手动触发数据采集

```bash
curl -X POST http://localhost:8000/api/v1/crawl/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "source": "fifa_official",
    "target": "standings",
    "league_name": "世界杯",
    "season_name": "2026"
  }'
```

```json
{
  "log_id": 347,
  "source": "fifa_official",
  "target": "standings",
  "status": "running",
  "message": "采集任务已提交，后台执行中"
}
```

---

## 🏗️ 系统架构

```
  FIFA · API-Football · FBref · Understat · 懂球帝 · StatsBomb · ... (10+)
  ┌──────────────────────────────────────┐
  │  Crawlers: 基类重试 · 反爬 · 多目标   │  ← 采集层 (30s 定时 / 手动触发)
  └────────────────┬─────────────────────┘
                   ▼
  ┌──────────────────────────────────────┐
  │  Cleaning: 字段映射→实体解析→去重→填补→│  ← 清洗层 (六层管线)
  │           异常值检测→多源融合          │
  └────────────────┬─────────────────────┘
                   ▼
  ┌────────────┬───────────┬─────────────┐
  │  MySQL 8   │  Redis    │ Hadoop HDFS │  ← 存储层 (结构化 + 缓存 + 原始落盘)
  └────────────┴───────────┴─────────────┘
                   ▼
  ┌──────────────────────────────────────┐
  │  Analysis: 球队评分 · 球员雷达 · xG · │  ← 分析层 + AI 预测
  │           事件影响 · AI双模型预测      │
  └────────────────┬─────────────────────┘
                   ▼
  ┌──────────────────────────────────────┐
  │  FastAPI · WebSocket · APScheduler   │  ← 服务层 (REST + 实时推送 + 调度)
  └────────────────┬─────────────────────┘
                   ▼
  ┌──────────────────────────────────────┐
  │  React 19 · TypeScript · ECharts    │  ← 前端 (世界杯大屏 / 详情 / 预测)
  └──────────────────────────────────────┘
```

---

## 🛠️ 技术栈

**后端**：`FastAPI` · `SQLAlchemy` · `pandas` · `scikit-learn` · `APScheduler` · `python-dotenv`
**前端**：`React 19` · `TypeScript` · `Vite` · `ECharts 5` · `Tailwind CSS` · `Zustand` · `React Query`
**存储**：`MySQL 8` · `Redis` · `Hadoop HDFS`
**AI**：`Step-3.7-Flash` · `DeepSeek V4` · `Firecrawl` (实时情报检索 + 视觉分析)

---

## 📦 数据源（按能力分组）

| 类型 | 数据源 | 覆盖 |
|------|--------|------|
| **结构化 API** | FIFA Official · API-Football · Football-Data · TheSportsDB · OpenLigaDB | 赛程/赛果/积分榜/球队阵容 |
| **HTML 爬取** | FBref · Understat · 懂球帝 · TeamRankings · Fotmob | xG/高级统计/射门事件/中文赛果 |
| **开放数据** | StatsBomb Open Data | 细粒度比赛事件（传球/射门/压迫） |

采集器统一继承 `BaseCrawler`：内置重试（最多 5 次 + 指数退避上限 30s）、User-Agent 轮换、SHA256 去重、HDFS 原始数据落盘。

---

## 📁 项目结构

```
football-data-analysis-platform/
├── backend/                  # FastAPI 后端（入口: app/main.py）
│   └── app/
│       ├── api/              # REST 路由 10 个模块（worldcup/players/predict/crawl/...）
│       ├── crawlers/         # 10+ 数据源采集器
│       ├── cleaning/         # 六层数据清洗管线
│       ├── analysis/         # 分析模型（联赛/球队/球员/xG/事件影响）
│       ├── prediction/       # AI 双模型比赛预测
│       ├── models/           # SQLAlchemy ORM
│       ├── scheduler/        # APScheduler 定时任务
│       └── services/         # 业务逻辑层
├── frontend/                 # React 前端（入口: vite dev :5173，代理 → :8000）
│   └── src/
│       ├── pages/            # 世界杯仪表板/球队/球员/比赛/预测/联赛
│       ├── components/       # 通用 UI 组件
│       ├── api/              # 请求封装
│       ├── stores/           # Zustand 状态管理
│       └── types/            # TypeScript 类型定义
├── scripts/                  # 工具脚本（FIFA 数据导入、PPT 图表生成等）
├── export/                   # 图表与示例数据
├── .env.example              # 环境变量模板
└── deploy.sh                 # 部署脚本
```

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本 |
|------|------|
| Python | 3.9+ |
| Node.js | 18+ |
| MySQL | 8.0+ |
| Redis | 6+ |
| Hadoop | 3.3.6（需 OpenJDK 1.8） |

### 启动

```bash
# 1. 克隆
git clone https://github.com/htt-FAK/football-data-analysis-platform.git
cd football-data-analysis-platform

# 2. 后端
cd backend
cp ../.env.example .env          # 编辑 .env 填入数据库、Redis 等配置
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. 前端（新终端）
cd frontend
npm install
npm run dev
```

- **前端页面**：http://localhost:5173
- **API 文档**：http://localhost:8000/docs
- **🚀 世界杯大屏**：http://localhost:5173/worldcup

---

## 📝 License

本项目为**课程设计与个人学习实践项目**，仅供学习、交流与作品展示使用。

---

<p align="center">
  <sub>From raw HTML to AI predictions — built end-to-end as a learning exercise.</sub>
</p>
