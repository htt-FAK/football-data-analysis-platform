#!/usr/bin/env bash
# 国旗本地化下载脚本
# 用法：在 frontend 目录下执行 bash download_flags.sh
# 从 jsDelivr CDN 批量下载本项目用到的所有国家/地区国旗 SVG 到 public/flags/
# 下载完后提交 public/flags/ 到 git，前端即可从本地加载（不再依赖外部 CDN）

set -e

TARGET_DIR="public/flags"
mkdir -p "$TARGET_DIR"

# 本项目 COUNTRY_META_MAP 中用到的所有国家码（去重）
# 来源：frontend/src/lib/utils.ts 的 COUNTRY_META_MAP
CODES=(
  # 英国构成国（特殊码）
  gb-eng gb-sct gb-wls
  # 常规国家（两位字母码）
  ar au at dz be ba br cv cm ca cw co cd cr hr cz cl dk ec eg fr de gh
  ht hu ir iq it jp jo kr mx ma nz nl ng no pl pa pt py qa sa sn rs za
  es se ch ci tn tr us uz uy
)

# 源：lipis/flag-icons（原项目用的就是这个库），通过 jsDelivr 拉 4x3 SVG
SRC_BASE="https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3"

echo "开始下载 ${#CODES[@]} 个国旗 SVG 到 $TARGET_DIR/ ..."
echo "源：jsDelivr (lipis/flag-icons 4x3)"
echo "----------------------------------------"

success=0
failed=0
failed_list=()

for code in "${CODES[@]}"; do
  out="$TARGET_DIR/$code.svg"
  # 已存在则跳过
  if [ -f "$out" ]; then
    echo "  [跳过] $code.svg 已存在"
    success=$((success + 1))
    continue
  fi
  # 下载（-s 静默，-f 失败返回非零，--retry 重试）
  if curl -sf --retry 2 --max-time 15 "$SRC_BASE/$code.svg" -o "$out"; then
    echo "  [成功] $code.svg"
    success=$((success + 1))
  else
    echo "  [失败] $code.svg"
    failed=$((failed + 1))
    failed_list+=("$code")
    rm -f "$out"
  fi
done

echo "----------------------------------------"
echo "完成：成功 $success / 失败 $failed / 总计 ${#CODES[@]}"

if [ "$failed" -gt 0 ]; then
  echo ""
  echo "❌ 以下国旗下载失败，可重新运行本脚本重试："
  printf '   %s.svg\n' "${failed_list[@]}"
  echo ""
  echo "如果反复失败，可能是服务器访问 jsDelivr 受限，可手动换源："
  echo "   将 SRC_BASE 改为 https://flagcdn.com（需相应调整文件名/格式）"
  exit 1
fi

echo ""
echo "✅ 全部国旗下载完成！"
echo "下一步："
echo "  1. git add public/flags && git commit -m '国旗本地化' && git push"
echo "  2. 服务器 git pull && cd frontend && npm run build"
echo "  3. 前端将从此服务器本地加载国旗，不再依赖外部 CDN"
