#!/bin/bash
# 启动 FastAPI 后端
cd "$(dirname "$0")/.."
source backend/venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
