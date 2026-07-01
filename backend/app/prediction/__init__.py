"""AI 预测模块 — 多模型多轮赛前前瞻分析。

编排流程：
  ① context_builder 采集内部数据
  ② step-3.7-flash 战术视角 + 联网搜索
  ③ step-3.7-flash 场外微观视角 + 联网搜索
  ④ deepseek-v4-flash 全量推理
  ⑤ deepseek-v4-flash 综合裁决
"""

from app.prediction.orchestrator import PredictionOrchestrator

__all__ = ["PredictionOrchestrator"]
