#!/bin/bash
# ============================================================
# 09体育赛事数据采集与分析 - 代码同步脚本
# 用途：把本地 backend 代码一键同步到服务器，覆盖 deploy.sh 生成的空架子
#
# 用法：
#   bash sync_code.sh                     # 使用默认服务器配置
#   SERVER_USER=root SERVER_HOST=1.2.3.4 bash sync_code.sh   # 指定服务器
#
# 前置条件：已完成 deploy.sh（环境已装好、目录已创建）
# 同步范围：backend/app 全部代码 + requirements.txt + .env.example
# ============================================================

set -e

# ── 服务器配置（可用环境变量覆盖）──
SERVER_USER="${SERVER_USER:-root}"
SERVER_HOST="${SERVER_HOST:-118.126.102.143}"
REMOTE_PROJECT="/opt/sports/project"
REMOTE_BACKEND="$REMOTE_PROJECT/backend"

# ── 本地路径（脚本所在目录即项目根）──
LOCAL_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOCAL_BACKEND="$LOCAL_ROOT/backend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
echo_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo_info "=========================================="
echo_info "  代码同步 → ${SERVER_USER}@${SERVER_HOST}"
echo_info "=========================================="
echo ""

# ── 1. 前置检查 ──
echo_info "步骤 1: 前置检查..."

if [ ! -d "$LOCAL_BACKEND/app" ]; then
    echo_error "本地 backend/app 目录不存在: $LOCAL_BACKEND/app"
    echo_error "请在项目根目录（含 backend/ 的那一层）执行本脚本"
    exit 1
fi

echo_info "检查服务器连通性: ${SERVER_HOST}..."
if ssh -o ConnectTimeout=5 "${SERVER_USER}@${SERVER_HOST}" "echo ok" &>/dev/null; then
    echo_info "服务器连通 ✓"
else
    echo_error "无法连接 ${SERVER_USER}@${SERVER_HOST}，请检查 SSH 配置"
    exit 1
fi

# 检查服务器上项目目录是否已创建（deploy.sh 是否跑过）
if ! ssh "${SERVER_USER}@${SERVER_HOST}" "test -d $REMOTE_BACKEND" 2>/dev/null; then
    echo_warn "服务器上 $REMOTE_BACKEND 不存在"
    echo_warn "请先执行 deploy.sh 完成环境部署，再跑本脚本"
    echo_info "自动创建目录..."
    ssh "${SERVER_USER}@${SERVER_HOST}" "mkdir -p $REMOTE_BACKEND/app"
fi
echo ""

# ── 2. 同步代码 ──
echo_info "步骤 2: 同步 backend/app 代码到服务器..."

rsync -avz --delete \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    "$LOCAL_BACKEND/app/" "${SERVER_USER}@${SERVER_HOST}:$REMOTE_BACKEND/app/"

echo_info "代码同步完成 ✓"
echo ""

# ── 3. 同步依赖与配置文件 ──
echo_info "步骤 3: 同步 requirements.txt 和配置..."

scp "$LOCAL_BACKEND/requirements.txt" "${SERVER_USER}@${SERVER_HOST}:$REMOTE_BACKEND/" 2>/dev/null \
    && echo_info "requirements.txt 已同步 ✓" \
    || echo_warn "requirements.txt 不存在，跳过（deploy.sh 已生成）"

if [ -f "$LOCAL_ROOT/.env.example" ]; then
    scp "$LOCAL_ROOT/.env.example" "${SERVER_USER}@${SERVER_HOST}:$REMOTE_BACKEND/" 2>/dev/null \
        && echo_info ".env.example 已同步 ✓" \
        || echo_warn ".env.example 同步失败"
fi

# 确保 .env 存在（deploy.sh 已生成，没有则从 .env.example 复制）
ssh "${SERVER_USER}@${SERVER_HOST}" "
    if [ ! -f '$REMOTE_BACKEND/.env' ] && [ -f '$REMOTE_BACKEND/.env.example' ]; then
        cp '$REMOTE_BACKEND/.env.example' '$REMOTE_BACKEND/.env'
        echo '.env 从 .env.example 创建完成'
    fi
    ls -la '$REMOTE_BACKEND/.env' 2>/dev/null && echo '.env 存在 ✓'
" 2>/dev/null
echo ""

# ── 4. 同步 SQL（如需更新表结构）──
echo_info "步骤 4: 同步 init_database.sql（如需更新表结构可手动执行）..."

if [ -f "$LOCAL_ROOT/init_database.sql" ]; then
    scp "$LOCAL_ROOT/init_database.sql" "${SERVER_USER}@${SERVER_HOST}:/root/" 2>/dev/null \
        && echo_info "init_database.sql 已同步到 /root/ ✓" \
        || echo_warn "init_database.sql 同步失败"
    echo_info "如需重建表，请在服务器执行："
    echo_info "  mysql -h 118.126.102.143 -u root1 -p root1 < /root/init_database.sql"
fi
echo ""

# ── 5. 验证 ──
echo_info "步骤 5: 验证同步结果..."

FILE_COUNT=$(ssh "${SERVER_USER}@${SERVER_HOST}" \
    "find $REMOTE_BACKEND/app -name '*.py' | wc -l" 2>/dev/null)
echo_info "服务器 backend/app 下 Python 文件数: $FILE_COUNT"

if [ "${FILE_COUNT:-0}" -lt 30 ]; then
    echo_warn "文件数偏少（<30），可能同步不完整，请检查"
else
    echo_info "同步正常，文件数充足 ✓"
fi

# 列出关键文件确认
echo_info "关键文件检查:"
ssh "${SERVER_USER}@${SERVER_HOST}" "
    for f in app/main.py app/config.py app/api/websocket.py app/services/ingest_service.py; do
        if [ -f '$REMOTE_BACKEND/\$f' ]; then
            echo '  ✓ \$f'
        else
            echo '  ✗ \$f (缺失!)'
        fi
    done
" 2>/dev/null
echo ""

# ── 6. 完成 ──
echo_info "=========================================="
echo_info "  代码同步完成！"
echo_info "=========================================="
echo ""
echo_info "下一步：登录服务器启动服务"
echo_info "  ssh ${SERVER_USER}@${SERVER_HOST}"
echo_info "  bash $REMOTE_PROJECT/scripts/start_backend.sh"
echo_info ""
echo_info "验证后端："
echo_info "  curl http://${SERVER_HOST}:8000/docs  (或浏览器打开)"
echo_info ""
echo_info "如需重启后端（代码更新后）："
echo_info "  ssh ${SERVER_USER}@${SERVER_HOST} 'bash $REMOTE_PROJECT/scripts/start_backend.sh'"
echo ""
