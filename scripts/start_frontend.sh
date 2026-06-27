#!/bin/bash
# 启动 React 前端
cd "$(dirname "$0")/../frontend"
npm run dev -- --host 0.0.0.0
