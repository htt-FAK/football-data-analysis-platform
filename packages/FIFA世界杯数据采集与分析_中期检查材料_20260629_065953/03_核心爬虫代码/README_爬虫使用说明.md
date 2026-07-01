# FIFA世界杯数据爬虫使用说明

## 问题说明

**为什么直接运行 `backend/app/crawlers/fifa_official.py` 没有结果？**

因为原始爬虫代码依赖完整的后端框架环境，包括：

1. **BaseCrawler 基类** - 提供HTTP请求、重试、延迟等基础功能
2. **HDFS客户端** - 用于保存原始数据快照
3. **配置管理系统** - 读取 `.env` 文件中的配置
4. **日志系统** - 统一的日志记录
5. **FastAPI框架** - 整个后端服务架构

单独运行 `fifa_official.py` 会因为缺少这些依赖而报错。

---

## 解决方案

我们提供了两个版本的爬虫：

### 方案一：独立版爬虫（推荐用于演示/教学）

**文件位置：** `scripts/standalone_fifa_crawler.py`

**特点：**
- ✅ 无需后端框架，直接运行
- ✅ 只需安装 `requests` 库
- ✅ 数据保存为JSON格式，方便查看
- ✅ 适合中期检查、课程演示

**使用方法：**
```bash
# 1. 确保已安装 requests
pip install requests

# 2. 运行爬虫
cd "D:\Users\黄涛韬\OneDrive\桌面\课设"
python scripts\standalone_fifa_crawler.py

# 3. 查看输出
# 数据保存在 output/ 文件夹中
```

**输出内容：**
- `standings_*.json` - 小组积分榜（48条记录）
- `schedule_*.json` - 比赛赛程（103场比赛）
- `teams_*.json` - 参赛球队列表（48支球队）

---

### 方案二：完整版爬虫（生产环境使用）

**文件位置：** `backend/app/crawlers/fifa_official.py`

**特点：**
- ✅ 集成完整后端框架
- ✅ 支持HDFS数据存储
- ✅ 自动Token刷新
- ✅ 多语言支持
- ✅ 球员详细统计数据

**使用方法：**
```bash
# 1. 启动完整后端服务
cd "D:\Users\黄涛韬\OneDrive\桌面\课设"

# 2. 通过API调用爬虫
# 需要启动 FastAPI 服务后，通过接口调用
# 具体见 backend/README.md
```

---

## 数据导出说明

如果需要将爬取的数据转换为Excel格式供老师查看，可以使用以下脚本：

```bash
# 使用已有的导出脚本
cd "D:\Users\黄涛韬\OneDrive\桌面\课设"
python -c "
from backend.app.export.fifa_worldcup_export import export_group_stage_csv_bundle
export_group_stage_csv_bundle('export/worldcup_fifa')
"
```

---

## 常见问题

### Q1: 运行时提示缺少模块？
**A:** 安装所需依赖：
```bash
pip install requests pandas openpyxl
```

### Q2: 爬取速度慢或失败？
**A:** 
- 检查网络连接（需要访问FIFA官方API）
- API可能有频率限制，建议间隔一段时间再试
- 查看控制台错误信息进行排查

### Q3: 数据是英文的，能转成中文吗？
**A:** 
- 独立版爬虫获取的是英文数据
- 完整版爬虫支持多语言（修改 `language` 参数为 `zh`）
- 或使用Excel手动翻译关键字段

### Q4: 如何查看爬取的数据？
**A:** 
- JSON文件：用文本编辑器或浏览器打开
- 转换为CSV/Excel：使用 `backend/app/export/fifa_worldcup_export.py` 脚本

---

## 技术架构对比

| 特性 | 独立版 | 完整版 |
|------|--------|--------|
| 依赖框架 | ❌ 无 | ✅ FastAPI + HDFS |
| 安装难度 | ⭐ 简单 | ⭐⭐⭐ 复杂 |
| 数据持久化 | JSON文件 | HDFS + 数据库 |
| 适用场景 | 演示/教学 | 生产环境 |
| 代码行数 | ~200行 | ~1200行 |
| 可移植性 | ⭐⭐⭐ 高 | ⭐ 低 |

---

## 联系信息

如有问题，请联系项目维护者：
- 姓名：黄涛韬
- 学校：广东理工学院
- 专业：软件工程

---

**最后更新：** 2026-06-29
