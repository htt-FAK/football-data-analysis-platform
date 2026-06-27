"""异常值检测与处理模块"""

from dataclasses import dataclass, field
from typing import Literal
import pandas as pd
import numpy as np


@dataclass
class AnomalyRecord:
    """异常值记录"""
    table_name: str
    column_name: str
    record_id: int
    original_value: float
    detection_method: str       # rule_based / zscore / iqr
    severity: str               # warning / error
    action: str                 # clamp / null / keep / delete / interpolate
    new_value: float | None = None
    note: str = ""


def detect_anomalies(
    df: pd.DataFrame,
    table_name: str,
    rules: dict[str, tuple[float, float]] | None = None,
    zscore_threshold: float = 3.0,
    iqr_multiplier: float = 1.5,
) -> list[AnomalyRecord]:
    """检测 DataFrame 中的异常值（三种方法并行）"""
    anomalies: list[AnomalyRecord] = []

    default_rules = {
        "goals": (0, 20),
        "assists": (0, 20),
        "shots": (0, 50),
        "shots_on_target": (0, 30),
        "passes": (0, 1500),
        "pass_accuracy": (0.0, 1.0),
        "possession": (0.0, 100.0),
        "height": (150, 220),
        "weight": (50, 120),
        "age": (15, 45),
        "rating": (0.0, 10.0),
        "xg": (0.0, 10.0),
        "xa": (0.0, 10.0),
        "minutes_played": (0, 6000),
    }
    if rules:
        default_rules.update(rules)

    numeric_cols = df.select_dtypes(include=[np.number]).columns

    for col in numeric_cols:
        if col in ("id", "version"):
            continue

        # 方法 1: 规则校验
        if col in default_rules:
            lo, hi = default_rules[col]
            mask = (df[col] < lo) | (df[col] > hi)
            for idx in df[mask].index:
                anomalies.append(AnomalyRecord(
                    table_name=table_name, column_name=col,
                    record_id=int(df.loc[idx, "id"]) if "id" in df.columns else idx,
                    original_value=float(df.loc[idx, col]),
                    detection_method="rule_based", severity="error",
                    action="clamp", new_value=max(lo, min(hi, float(df.loc[idx, col]))),
                    note=f"{col}={df.loc[idx, col]} 超出合理范围 [{lo}, {hi}]",
                ))

        # 方法 2: Z-Score
        if col in default_rules:
            mean, std = df[col].mean(), df[col].std()
            if std > 0:
                zscores = (df[col] - mean) / std
                mask = zscores.abs() > zscore_threshold
                for idx in df[mask].index:
                    val = float(df.loc[idx, col])
                    lo, hi = default_rules[col]
                    if lo <= val <= hi:  # 规则校验通过的才报 warning
                        anomalies.append(AnomalyRecord(
                            table_name=table_name, column_name=col,
                            record_id=int(df.loc[idx, "id"]) if "id" in df.columns else idx,
                            original_value=val,
                            detection_method="zscore", severity="warning",
                            action="keep", new_value=val,
                            note=f"{col}={val} Z-Score={zscores.loc[idx]:.2f}",
                        ))

        # 方法 3: IQR
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            lower, upper = q1 - iqr_multiplier * iqr, q3 + iqr_multiplier * iqr
            mask = (df[col] < lower) | (df[col] > upper)
            for idx in df[mask].index:
                val = float(df.loc[idx, col])
                if col in default_rules:
                    lo, hi = default_rules[col]
                    if lo <= val <= hi:
                        anomalies.append(AnomalyRecord(
                            table_name=table_name, column_name=col,
                            record_id=int(df.loc[idx, "id"]) if "id" in df.columns else idx,
                            original_value=val,
                            detection_method="iqr", severity="warning",
                            action="keep", new_value=val,
                            note=f"{col}={val} IQR范围=[{lower:.2f}, {upper:.2f}]",
                        ))

    return anomalies


def apply_cleaning(df: pd.DataFrame, anomalies: list[AnomalyRecord]) -> pd.DataFrame:
    """根据异常值记录对 DataFrame 执行清洗"""
    df = df.copy()
    for a in anomalies:
        if a.action == "clamp" and a.new_value is not None:
            if a.record_id in df.index or (df.index.name == "id" and a.record_id in df.index):
                df.loc[a.record_id, a.column_name] = a.new_value
        elif a.action == "null":
            df.loc[a.record_id, a.column_name] = np.nan
        elif a.action == "delete":
            df.drop(index=a.record_id, inplace=True, errors="ignore")
    return df
