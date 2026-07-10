# 后端测试套件

## 快速开始

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v --cov=app --cov-report=term-missing
```

## 运行特定测试

```bash
# 只运行 LLM 客户端测试
pytest tests/unit/test_llm_client.py -v

# 只运行 orchestrator 测试
pytest tests/unit/test_orchestrator.py -v

# 只运行 web_search 测试
pytest tests/unit/test_web_search.py -v

# 只运行 versioning 测试
pytest tests/unit/test_versioning.py -v

# 运行某个具体测试
pytest tests/unit/test_llm_client.py::TestCallWithRetry::test_retry_on_500_then_success -v
```

## 目录结构

```
tests/
├── conftest.py          # 共享 fixtures（mock Session、mock HTTP）
├── pytest.ini           # pytest 配置（markers、async_mode、warning 过滤）
├── README.md            # 本文件
└── unit/
    ├── test_orchestrator.py   # B1 并行 / B3 缓存 / C1 日志（12+ tests）
    ├── test_llm_client.py     # C2 重试 / JSON 解析（15+ tests）
    ├── test_web_search.py     # Firecrawl 集成（5+ tests）
    └── test_versioning.py     # G race condition（4+ tests）
```

## 测试命名约定

- 函数名：`test_` 前缀（pytest 标准）
- 类名：`Test*` 前缀
- 文件名：`test_*.py`
- docstring/注释：中文
- 函数名：英文 snake_case

## Mock 策略

| 外部依赖 | Mock 方式 |
|---------|----------|
| MySQL (SQLAlchemy Session) | `unittest.mock.MagicMock` |
| HTTP (requests.post) | `unittest.mock.patch` + 预设 response |
| LLM API | `patch('requests.post')` 返回 mock response |
| Firecrawl | `patch('app.prediction.web_search.requests.post')` |
| 时间 (time.time / time.sleep) | `patch` 或 `monkeypatch` |

## 添加新测试

1. 在 `tests/unit/` 下创建 `test_<module_name>.py`
2. 导入待测模块（`from app.xxx import yyy`）
3. 使用 `conftest.py` 中的共享 fixtures（`mock_db_session`、`fake_llm_response` 等）
4. 确保所有外部依赖都被 mock，测试可完全离线运行
