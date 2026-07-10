#!/bin/bash
# ============================================================
# 09体育赛事数据采集与分析 - 服务器环境部署脚本（适配版）
# 服务器: TencentOS Server 3
# 已有: OpenJDK 1.8.0 + Hadoop 3.3.6 伪分布式 + MySQL
# MySQL: 118.126.102.143, 用户 root1, 数据库 root1
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo_info "=========================================="
echo_info "  09体育赛事数据采集与分析 - 环境部署"
echo_info "=========================================="
echo ""

# ============================================================
# 0. 检查 Hadoop
# ============================================================
echo_info "步骤 0: 检查 Hadoop 状态..."

if command -v jps &> /dev/null; then
    JPS_OUTPUT=$(jps)
    echo_info "Hadoop 进程:"
    echo "$JPS_OUTPUT"

    if echo "$JPS_OUTPUT" | grep -q "NameNode"; then
        echo_info "NameNode 运行中 ✓"
    else
        echo_warn "NameNode 未运行，启动 Hadoop..."
        start-dfs.sh
        start-yarn.sh
        sleep 3
        jps
    fi
else
    echo_error "未找到 jps 命令，请先配置 Hadoop 环境变量"
    exit 1
fi
echo ""

# ============================================================
# 1. 检查 MySQL 连接（已有，无需安装）
# ============================================================
echo_info "步骤 1: 验证 MySQL 连接..."

# 安全: 从环境变量读取,绝不把密码硬编码到仓库 (Track H P0-2 安全修复)
# 用法: export DEPLOY_DB_HOST=xxx DEPLOY_DB_USER=xxx DEPLOY_DB_PASS=xxx DEPLOY_DB_NAME=xxx ./deploy.sh
# 或通过 .deploy.env 文件 export (已在 .gitignore 中)
if [ -f ".deploy.env" ]; then
    # shellcheck source=/dev/null
    source .deploy.env
fi
DB_HOST="${DEPLOY_DB_HOST:-118.126.102.143}"
DB_USER="${DEPLOY_DB_USER:?错误: 请设置 DEPLOY_DB_USER 环境变量 (或在 .deploy.env 中配置)}"
DB_PASS="${DEPLOY_DB_PASS:?错误: 请设置 DEPLOY_DB_PASS 环境变量}"
DB_NAME="${DEPLOY_DB_NAME:-${DB_USER}}"

if command -v mysql &> /dev/null; then
    echo_info "MySQL 客户端已安装"
else
    echo_info "安装 MySQL 客户端..."
    dnf install -y mysql
fi

echo_info "测试数据库连接: ${DB_HOST}..."
if mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -e "SELECT 1;" 2>/dev/null; then
    echo_info "MySQL 连接成功 ✓"
else
    echo_error "MySQL 连接失败，请检查网络或凭据"
    echo_error "命令: mysql -h $DB_HOST -u $DB_USER -p*** $DB_NAME"
    exit 1
fi
echo ""

# ============================================================
# 2. 安装 Redis 缓存服务（用于实时数据推送与爬虫任务队列）
# ============================================================
echo_info "步骤 2: 安装 Redis 缓存服务..."

if command -v redis-cli &> /dev/null; then
    echo_info "Redis 已安装"
else
    echo_info "安装 Redis 服务端与客户端..."
    dnf install -y redis
fi

echo_info "启动 Redis 服务..."
systemctl start redis
systemctl enable redis

echo_info "验证 Redis 连接..."
if redis-cli ping | grep -q "PONG"; then
    echo_info "Redis 连接成功 ✓"
else
    echo_error "Redis 连接失败，请检查 Redis 服务状态"
    exit 1
fi
echo ""

# ============================================================
# 3. 安装 Python 环境
# ============================================================
echo_info "步骤 3: 安装 Python 环境..."

dnf install -y python3 python3-pip python3-devel gcc make

PYTHON_VERSION=$(python3 --version 2>&1)
echo_info "Python 版本: $PYTHON_VERSION"

if [ ! -d "/opt/sports/venv" ]; then
    echo_info "创建 Python 虚拟环境..."
    python3 -m venv /opt/sports/venv
fi

source /opt/sports/venv/bin/activate
pip install --upgrade pip

echo_info "安装 Python 依赖包..."
pip install fastapi uvicorn[standard]
pip install sqlalchemy pymysql cryptography
pip install requests beautifulsoup4 lxml
pip install apscheduler pandas pyarrow
pip install hdfs scikit-learn
pip install python-multipart python-dotenv
pip install redis websockets
pip install openpyxl xlsxwriter

echo_info "Python 环境安装完成 ✓"
echo ""

# ============================================================
# 4. 安装 Node.js 18
# ============================================================
echo_info "步骤 4: 安装 Node.js 18..."

if command -v node &> /dev/null; then
    NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        echo_info "Node.js 已安装: $(node -v) ✓"
    else
        echo_warn "Node.js 版本低于 18，升级中..."
        curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
        dnf install -y nodejs
    fi
else
    curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
    dnf install -y nodejs
fi

echo_info "Node.js: $(node -v)"
echo_info "npm: $(npm -v)"
echo_info "Node.js 安装完成 ✓"
echo ""

# ============================================================
# 5. 执行建表 SQL
# ============================================================
echo_info "步骤 5: 创建数据库表..."

# 检查表是否已存在
EXISTING_TABLES=$(mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SHOW TABLES LIKE 'leagues';" 2>/dev/null | tail -1)

if [ -n "$EXISTING_TABLES" ]; then
    echo_warn "leagues 表已存在，跳过建表"
else
    echo_info "执行建表 SQL..."
    # 如果 init_database.sql 在同目录则直接执行
    if [ -f "./init_database.sql" ]; then
        mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < ./init_database.sql
        echo_info "建表 SQL 执行完成 ✓"
    else
        echo_warn "未找到 init_database.sql，请手动执行"
        echo_info "上传后执行: mysql -h $DB_HOST -u $DB_USER -p'$DB_PASS' $DB_NAME < init_database.sql"
    fi
fi

# 验证表数量（含 data_sources / crawl_logs 共 12 张表）
TABLE_COUNT=$(mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SHOW TABLES;" 2>/dev/null | grep -c -E "leagues|seasons|teams|players|matches|standings|match_events|player_stats|shots|team_stats|data_sources|crawl_logs")
echo_info "体育相关表数量: $TABLE_COUNT / 12"
if [ "$TABLE_COUNT" -lt 12 ]; then
    echo_warn "表数量不足 12 张，建议检查 init_database.sql 是否执行成功"
fi
echo ""

# ============================================================
# 6. 初始化 HDFS 目录
# ============================================================
echo_info "步骤 6: 初始化 HDFS 目录..."

HDFS_DIRS=(
    "/sports"
    "/sports/raw"
    "/sports/raw/dongqiudi/schedule"
    "/sports/raw/dongqiudi/matches"
    "/sports/raw/dongqiudi/standings"
    "/sports/raw/dongqiudi/player_stats"
    "/sports/raw/fbref/team_stats"
    "/sports/raw/fbref/player_stats"
    "/sports/raw/fbref/match_stats"
    "/sports/raw/understat/shots"
    "/sports/raw/understat/xg_timeline"
    "/sports/raw/football_data/seasons"
    "/sports/processed/leagues"
    "/sports/processed/teams"
    "/sports/processed/players"
    "/sports/processed/matches"
    "/sports/processed/shots"
    "/sports/analysis/xg_model"
    "/sports/analysis/team_rating"
    "/sports/analysis/player_rating"
    "/sports/analysis/reports"
)

for dir in "${HDFS_DIRS[@]}"; do
    hdfs dfs -test -d "$dir" 2>/dev/null || hdfs dfs -mkdir -p "$dir"
done

echo_info "HDFS 目录结构创建完成 ✓"
hdfs dfs -ls /sports/
echo ""

# ============================================================
# 7. 创建项目目录
# ============================================================
echo_info "步骤 7: 创建项目目录结构..."

PROJECT_ROOT="/opt/sports/project"

mkdir -p "$PROJECT_ROOT/backend/app/"{api,crawlers,models,services,cleaning,analysis,scheduler}
mkdir -p "$PROJECT_ROOT/scripts"
mkdir -p "$PROJECT_ROOT/docs"

for pkg_dir in app app/api app/crawlers app/models app/services app/cleaning app/analysis app/scheduler; do
    touch "$PROJECT_ROOT/backend/$pkg_dir/__init__.py"
done

echo_info "项目目录创建完成: $PROJECT_ROOT ✓"
echo ""

# ============================================================
# 8. 创建前端项目
# ============================================================
echo_info "步骤 8: 创建前端项目..."

if [ ! -d "$PROJECT_ROOT/frontend" ]; then
    cd "$PROJECT_ROOT"
    npm create vite@latest frontend -- --template react-ts
    cd frontend
    npm install
    npm install axios echarts echarts-for-react react-router-dom
    npm install antd @ant-design/icons
    echo_info "前端项目创建完成 ✓"
else
    echo_info "前端项目已存在，跳过 ✓"
fi
echo ""

# ============================================================
# 9. 创建配置文件
# ============================================================
echo_info "步骤 9: 生成配置文件..."

# .env 文件（从环境变量填充, 不硬编码密码 — Track H 安全修复）
# 注: EOF 不加单引号允许 shell 变量替换 $DB_HOST 等
cat > "$PROJECT_ROOT/backend/.env" << EOF
# MySQL 数据库配置（从环境变量填充）
DB_HOST=$DB_HOST
DB_PORT=3306
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASS
DB_NAME=$DB_NAME

# HDFS 配置
HDFS_HOST=localhost
HDFS_PORT=9870
HDFS_USER=root

# FastAPI 配置
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=True

# 爬虫配置
CRAWL_DELAY_MIN=2
CRAWL_DELAY_MAX=5

# Redis 缓存配置（用于实时数据推送与爬虫任务队列）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# WebSocket 配置（实时赛事数据推送）
WS_HEARTBEAT_INTERVAL=25
WS_LIVE_POLL_INTERVAL=30

# 实时数据抓取配置（秒）— config.py 读取 LIVE_CRAWL_INTERVAL
LIVE_CRAWL_INTERVAL=30
# 进行中比赛缓存 TTL（秒）— config.py 读取 REDIS_LIVE_TTL
REDIS_LIVE_TTL=300

# Excel 导出配置
EXPORT_DIR=/opt/sports/project/export
EXPORT_CRON=0 2 * * *
EXPORT_INCLUDE_ANOMALY=true
EXPORT_INCLUDE_COMPARISON=true
EOF

# requirements.txt
cat > "$PROJECT_ROOT/backend/requirements.txt" << 'EOF'
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
pymysql>=1.1.0
cryptography>=42.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.1.0
apscheduler>=3.10.0
pandas>=2.2.0
pyarrow>=15.0.0
hdfs>=2.7.0
scikit-learn>=1.4.0
python-multipart>=0.0.9
python-dotenv>=1.0.0
redis>=5.0.0
websockets>=12.0
openpyxl>=3.1.0
xlsxwriter>=3.2.0
EOF

echo_info "配置文件生成完成 ✓"
echo ""

# ============================================================
# 10. 创建启动脚本
# ============================================================
echo_info "步骤 10: 生成启动脚本..."

cat > "$PROJECT_ROOT/scripts/start_backend.sh" << 'EOF'
#!/bin/bash
source /opt/sports/venv/bin/activate
cd /opt/sports/project/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF
chmod +x "$PROJECT_ROOT/scripts/start_backend.sh"

cat > "$PROJECT_ROOT/scripts/start_frontend.sh" << 'EOF'
#!/bin/bash
cd /opt/sports/project/frontend
npm run dev -- --host 0.0.0.0
EOF
chmod +x "$PROJECT_ROOT/scripts/start_frontend.sh"

cat > "$PROJECT_ROOT/scripts/start_hadoop.sh" << 'EOF'
#!/bin/bash
start-dfs.sh
start-yarn.sh
echo "Hadoop 进程:"
jps
EOF
chmod +x "$PROJECT_ROOT/scripts/start_hadoop.sh"

cat > "$PROJECT_ROOT/scripts/start_redis.sh" << 'EOF'
#!/bin/bash
# 启动 Redis 服务（用于实时数据推送与爬虫任务队列）
systemctl start redis
systemctl enable redis
echo "Redis 状态:"
redis-cli ping
EOF
chmod +x "$PROJECT_ROOT/scripts/start_redis.sh"

echo_info "启动脚本生成完成 ✓"
echo ""

# ============================================================
# 11. 最终验证
# ============================================================
echo_info "步骤 11: 环境验证报告"
echo ""
echo "=========================================="

echo_info "Java: $(java -version 2>&1 | head -1)"
echo_info "Hadoop: $(hadoop version 2>&1 | head -1)"

source /opt/sports/venv/bin/activate
echo_info "Python: $(python3 --version 2>&1)"
echo_info "Node.js: $(node -v 2>&1)"
echo_info "npm: $(npm -v 2>&1)"

# MySQL 连接验证
if mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -e "USE $DB_NAME; SHOW TABLES;" 2>/dev/null | grep -q "leagues"; then
    echo_info "MySQL 数据库: 连接正常, 表已创建 ✓"
else
    echo_warn "MySQL: 表未创建，请手动执行 init_database.sql"
fi

# HDFS 验证
if hdfs dfs -test -d /sports/raw 2>/dev/null; then
    echo_info "HDFS /sports/ 目录: 正常 ✓"
else
    echo_warn "HDFS /sports/ 目录: 异常"
fi

# Redis 验证
if redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo_info "Redis 缓存服务: 连接正常 ✓"
else
    echo_warn "Redis 缓存服务: 异常，请执行 systemctl start redis"
fi

echo ""
echo_info "=========================================="
echo_info "部署完成！"
echo_info "=========================================="
echo ""
echo_info "项目目录: $PROJECT_ROOT"
echo_info ""
echo_info "启动命令:"
echo_info "  Hadoop:  bash $PROJECT_ROOT/scripts/start_hadoop.sh"
echo_info "  Redis:   bash $PROJECT_ROOT/scripts/start_redis.sh"
echo_info "  后端:    bash $PROJECT_ROOT/scripts/start_backend.sh"
echo_info "  前端:    bash $PROJECT_ROOT/scripts/start_frontend.sh"
echo_info ""
echo_info "访问地址:"
echo_info "  后端API: http://<服务器IP>:8000/docs"
echo_info "  前端:    http://<服务器IP>:5173"
echo_info ""
echo_info "数据库连接:"
echo_info "  mysql -h 118.126.102.143 -u root1 -p $DB_NAME"
echo ""
