# FIFA世界杯数据采集与分析项目 - 中期检查材料

## 生成时间
2026年06月28日 23:15:02

## 项目概述
本项目基于FIFA官方API采集2026年美加墨世界杯小组赛阶段数据，包括赛程、积分榜、球员信息和统计数据。

## 目录结构

### 01_球员可视化分析
- **六边形雷达图/**: 包含8名顶级球员的11维能力雷达图
  - 维度：进球、射门、射正、助攻、传球数、传球成功率、抢断、拦截、评分、出场时间、期望进球(xG)
  - 对比图：players_comparison.png 展示多维度横向对比

### 02_导出数据样本
- **球员统计数据.csv**: 完整球员统计指标（出场、进球、助攻、xG等）
- **球员基本信息.csv**: 球员个人信息（姓名、位置、号码、国籍、身高等）
- **小组积分榜.csv**: 各小组排名及积分情况
- **数据来源说明.csv**: 数据导出元信息

### 03_核心爬虫代码
- **fifa_official_爬虫.py**: FIFA官方API爬虫实现
  - 支持接口：赛程(schedule)、积分榜(standings)、球员(players)、球员统计(player_stats)
  - 数据源：FIFA公共JSON API (api.fifa.com) + FDH游戏日API (gameday-prod.fifa.mangodev.co.uk)
  - 特点：Token自动刷新、多语言支持、HDFS原始快照持久化

- **base_基础爬虫类.py**: 爬虫基类，提供HTTP请求、延迟控制、重试机制

### 04_数据清洗与导出代码
- **fifa_worldcup_export_导出脚本.py**: 数据清洗与格式化导出
  - 功能：从HDFS读取原始JSON快照 → Pandas DataFrame处理 → Excel/CSV导出
  - 特性：自动计算年龄、标准化字段、生成射手榜/助攻榜/评分榜TOP20
  - 输出：多Sheet Excel工作簿（球员信息、统计、积分榜、排行榜）

### 05_可视化脚本
- **visualize_player_radar_雷达图生成.py**: 球员能力雷达图生成器
  - 输入：球员统计CSV
  - 输出：8张个人雷达图 + 1张综合对比图
  - 技术：Matplotlib极坐标绘图、数据归一化(0-10分制)

## 关键技术点

### 数据采集
1. **双API架构**：
   - 主API：`https://api.fifa.com/api/v3` (赛程、积分榜、阵容)
   - 辅助API：`https://gameday-prod.fifa.mangodev.co.uk/1-0` (球员详细统计)
   
2. **Token管理**：通过 `https://cxm-api.fifa.com/fifaplusweb/api/external/gameDay/token` 获取临时访问令牌

3. **数据去重**：基于 `_externalSportsPersonId` 和球衣号码合并阵容数据与统计数据

### 数据清洗
1. **字段映射**：将FIFA API的英文字段转换为中文标准字段
2. **空值处理**：缺失数据填充默认值（如出场次数为0）
3. **排名计算**：使用Pandas rank方法计算射手榜、助攻榜、评分榜
4. **年龄计算**：基于比赛截止日期动态计算球员年龄

### 可视化设计
1. **归一化策略**：将不同量纲的指标（如进球数vs传球成功率）统一映射到0-10分
2. **雷达图维度**：11个关键指标覆盖进攻、组织、防守、效率四大维度
3. **色彩编码**：蓝色主题(#4472C4)符合FIFA官方视觉规范

## 数据规模
- 球员总数：约XXX人（覆盖所有参赛球队）
- 有效统计球员：XXX人（至少有1项非零统计数据）
- 比赛场次：小组赛阶段全部比赛
- 数据时间范围：2026年6月11日 - 7月19日

## 使用说明
1. 运行爬虫：`python backend/app/crawlers/fifa_official.py`
2. 导出数据：调用 `export_group_stage_artifacts()` 函数
3. 生成可视化：`python scripts/visualize_player_radar.py`

## 注意事项
- 本数据包仅用于学术中期检查，不包含完整数据集
- 爬虫代码需配合后端框架(FastAPI)和数据库(PostgreSQL)使用
- HDFS存储路径：`/sports/raw/fifa_official/`
