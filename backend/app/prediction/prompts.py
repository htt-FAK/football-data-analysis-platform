"""Prompt builders for the AI match prediction pipeline."""

from __future__ import annotations

from typing import Any


SKILL_SYSTEM_PROMPT = """
你是一位资深足球赛前分析师，负责输出可落库、可展示、可复盘的比赛预测结论。

工作原则：
1. 先分析，再下判断，最终给出结构化 JSON。
2. 有联网工具时优先利用联网结果补强结论，没有检索到强证据时也要正常完成分析。
3. 不要输出“我无法联网”“我在模拟搜索”“基于知识库猜测”之类的自我暴露语句。
4. 不要输出占位值，例如“结论待补充”“稍后再说”“TBD”“暂无”。
5. 若信息不足，就明确降低 confidence，但仍要给出完整 verdict 和 key_reasons。
6. key_reasons 至少 3 条，且必须是具体依据，不要空泛复述。

输出要求：
- 直接输出纯 JSON，不要包 markdown 代码块。
- 必须包含以下字段：
{
  "home_win_prob": 0-100 的数字,
  "draw_prob": 0-100 的数字,
  "away_win_prob": 0-100 的数字,
  "predicted_home_score": 整数,
  "predicted_away_score": 整数,
  "conservative_verdict": "一句完整结论，不能是占位语",
  "aggressive_verdict": "一句完整结论，不能是占位语",
  "confidence": 0-100 的数字,
  "key_reasons": ["至少3条具体依据"],
  "thinking": "完整推理过程，清楚说明依据与取舍"
}
"""


MERMAID_MINDMAP_TEMPLATE = """```mermaid
mindmap
  root(({home} vs {away}))
    比赛信息
      阶段: {stage}
      场地: {venue}
    主队
      {home_info}
    客队
      {away_info}
    场外因素
      {contextual_factors}
    结论
      保守: {conservative}
      激进: {aggressive}
```"""


NO_SELF_EXPOSURE_RULE = """
特别约束：
- 禁止写“无法联网”“无法访问实时信息”“模拟搜索”“只能基于已有知识”等句子。
- 即使外部信息有限，也要把 thinking 写成正常分析过程，并明确哪些点“检索到的佐证较弱”。
- conservative_verdict、aggressive_verdict、key_reasons 绝不能留空，绝不能使用占位词。
"""


def build_tactical_prompt(context_block: str, match_meta: dict, allow_search: bool = True, web_intel_block: str = "", vision_block: str = "") -> str:
    if web_intel_block:
        search_line = "1. 下方已提供实时网络情报，请据此核实双方近期战绩、预计首发、阵型、关键伤停、主帅风格、历史交锋。"
    elif allow_search:
        search_line = "1. 结合联网检索，查看双方近期战绩、预计首发、阵型、关键伤停、主帅风格、历史交锋。"
    else:
        search_line = "1. 基于你的足球知识储备和上方提供的比赛背景数据，判断双方近期战绩、预计首发、阵型、关键伤停、主帅风格、历史交锋（本次无法联网，不要声称已联网）。"
    return f"""请从【战术视角】分析 {match_meta.get('home_name', '主队')} vs {match_meta.get('away_name', '客队')}。

比赛背景：
{context_block}
{web_intel_block}
{vision_block}

本轮重点：
{search_line}
2. 重点分析阵型克制、球星破局能力、攻防转换、战术纪律性。
3. 热身赛和弱对手战绩要做含金量过滤，不能机械堆数据。
4. 视觉情报里若有首发/阵型/伤停线索，要纳入战术判断。
5. 最终必须输出完整 JSON。

{NO_SELF_EXPOSURE_RULE}
"""


def build_contextual_prompt(context_block: str, match_meta: dict, allow_search: bool = True, web_intel_block: str = "", vision_block: str = "") -> str:
    if web_intel_block:
        search_line = "1. 下方已提供实时网络情报，请据此核实赛前采访、天气、场地、球迷氛围、侨民环境、突发新闻、入境与旅途因素。"
    elif allow_search:
        search_line = "1. 结合联网检索，查看赛前采访、天气、场地、球迷氛围、侨民环境、突发新闻、入境与旅途因素。"
    else:
        search_line = "1. 基于你的足球知识储备和上方比赛背景，推断赛前氛围、天气影响、球迷情绪、旅途因素等（本次无法联网，不要声称已联网，拿不准的要写明“佐证较弱”）。"
    return f"""请从【场外微观视角】分析 {match_meta.get('home_name', '主队')} vs {match_meta.get('away_name', '客队')}。

比赛背景：
{context_block}
{web_intel_block}
{vision_block}

本轮重点：
{search_line}
2. 评估天时、地利、人和，以及大赛场景下的心理波动和民族情绪。
3. 视觉情报里若有场地天气、球迷氛围、教练态度线索，要纳入场外判断。
4. 如果未检索到强证据，要明确写成“佐证较弱”，但仍要给出完整 verdict 和 reasons。
5. 最终必须输出完整 JSON。

{NO_SELF_EXPOSURE_RULE}
"""


def build_reasoning_prompt(context_block: str, match_meta: dict, prior_rounds: list[dict]) -> str:
    prior_summary = "\n\n".join(
        f"[轮次{i+1} | {round_data.get('focus', '')} | status={round_data.get('status', '')}]\n"
        f"保守结论: {round_data.get('conservative_verdict', '无')}\n"
        f"激进结论: {round_data.get('aggressive_verdict', '无')}\n"
        f"概率: 主胜{round_data.get('home_win_prob')} / 平{round_data.get('draw_prob')} / 客胜{round_data.get('away_win_prob')}\n"
        f"比分: {round_data.get('predicted_home_score')}-{round_data.get('predicted_away_score')}\n"
        f"关键依据: {round_data.get('key_reasons', [])}\n"
        f"摘要: {(round_data.get('thinking', '') or '')[:500]}"
        for i, round_data in enumerate(prior_rounds)
    ) or "前置轮次没有可靠结论，请独立完成整轮推理。"

    return f"""你现在是【独立深度推理分析师】。请综合内部数据，并参考前置轮次摘要，但不要盲从它们。

比赛：
{match_meta.get('home_name', '主队')} vs {match_meta.get('away_name', '客队')}

内部上下文：
{context_block}

前置轮次摘要：
{prior_summary}

请按以下顺序完成：
1. 实力基线
2. 状态校准
3. 场外加权
4. 战术匹配
5. 分层预测

要求：
- thinking 要写清楚你采信了什么，舍弃了什么。
- 若前两轮出现不完整结论，也要主动修正，而不是复述。
- 最终必须输出完整 JSON。

{NO_SELF_EXPOSURE_RULE}
"""


def build_arbiter_prompt(match_meta: dict, all_rounds: list[dict]) -> str:
    rounds_text = "\n\n".join(
        f"[轮次{i+1} | {round_data.get('focus', '')} | status={round_data.get('status', '')}]\n"
        f"保守: {round_data.get('conservative_verdict', '无')}\n"
        f"激进: {round_data.get('aggressive_verdict', '无')}\n"
        f"概率: 主胜{round_data.get('home_win_prob')} / 平{round_data.get('draw_prob')} / 客胜{round_data.get('away_win_prob')}\n"
        f"比分: {round_data.get('predicted_home_score')}-{round_data.get('predicted_away_score')}\n"
        f"置信度: {round_data.get('confidence')}\n"
        f"关键依据: {round_data.get('key_reasons', [])}\n"
        f"推理摘要: {(round_data.get('thinking', '') or '')[:700]}"
        for i, round_data in enumerate(all_rounds)
    )

    return f"""你是【最终裁决官】。请综合多轮分析，对 {match_meta.get('home_name', '主队')} vs {match_meta.get('away_name', '客队')} 给出最终裁决。

多轮记录：
{rounds_text}

裁决规则：
1. 优先采信依据具体、结论完整、内部逻辑一致的轮次。
2. 若某轮只有概率没有结论，或出现占位值，要主动降权。
3. 若多轮分歧明显，要降低 confidence，并在 thinking 中解释分歧来源。
4. 最终 verdict 必须完整，不能是模板话。
5. 除 JSON 主体外，还要输出 mermaid_mindmap 字段，内容为 Mermaid mindmap 源码。

输出 schema：
{{
  "home_win_prob": number,
  "draw_prob": number,
  "away_win_prob": number,
  "predicted_home_score": integer,
  "predicted_away_score": integer,
  "conservative_verdict": "完整结论",
  "aggressive_verdict": "完整结论",
  "confidence": number,
  "key_reasons": ["至少3条依据"],
  "thinking": "裁决过程",
  "mermaid_mindmap": "```mermaid ... ```"
}}

{NO_SELF_EXPOSURE_RULE}
"""


def build_context_block(data: dict) -> str:
    lines: list[str] = []
    match = data.get("match", {}) or {}
    home = data.get("home", {}) or {}
    away = data.get("away", {}) or {}

    lines.append("# 比赛信息")
    lines.append(f"- 赛事: {match.get('league', '未知')} / 赛季: {match.get('season', '未知')}")
    lines.append(f"- 阶段: {match.get('stage') or '未知'} / 分组: {match.get('group') or '未知'}")
    lines.append(f"- 开球时间: {match.get('kickoff', '未知')}")
    lines.append(f"- 场地: {match.get('venue') or '未知'}")

    def team_block(label: str, team: dict[str, Any]) -> list[str]:
        block = [f"\n# {label}: {team.get('name', '未知')}"]
        block.append(f"- 国家: {team.get('country') or '未知'} / 教练: {team.get('coach') or '未知'}")
        stat = team.get("stat") or {}
        if stat:
            block.append("- 赛季统计:")
            block.append(
                f"  - 战绩: {stat.get('wins', 0)}-{stat.get('draws', 0)}-{stat.get('losses', 0)}"
                f" / 已赛 {stat.get('matches_played', 0)}"
            )
            block.append(f"  - 进失球: {stat.get('goals_for', 0)}/{stat.get('goals_against', 0)}")
            if stat.get("xg") is not None or stat.get("xga") is not None:
                block.append(f"  - xG/xGA: {stat.get('xg')}/{stat.get('xga')}")
            if stat.get("shots") is not None:
                block.append(f"  - 射门/射正: {stat.get('shots')}/{stat.get('shots_on_target')}")
            if stat.get("possession") is not None:
                block.append(f"  - 控球率: {stat.get('possession')}%")
            if stat.get("pass_accuracy") is not None:
                block.append(f"  - 传球成功率: {stat.get('pass_accuracy')}%")
            if stat.get("attack_score") is not None:
                block.append(f"  - 进攻评分: {stat.get('attack_score')}")
            if stat.get("defense_score") is not None:
                block.append(f"  - 防守评分: {stat.get('defense_score')}")
            if stat.get("overall_score") is not None:
                block.append(f"  - 综合评分: {stat.get('overall_score')}")

        form = team.get("recent_form") or []
        if form:
            block.append(f"- 近期战绩: {' '.join(form)}")

        standings = team.get("standings") or {}
        if standings:
            block.append(
                f"- 积分形势: 第{standings.get('position', '?')}名 / {standings.get('points', '?')}分"
                f" / 状态 {standings.get('qualification_status', '未知')}"
            )

        players = team.get("key_players") or []
        if players:
            block.append("- 核心球员:")
            for player in players[:8]:
                block.append(
                    f"  - {player.get('name')} ({player.get('position', '?')}) "
                    f"进球{player.get('goals', 0)} 助攻{player.get('assists', 0)} 评分{player.get('rating', '-')}"
                )
        return block

    lines.extend(team_block("主队", home))
    lines.extend(team_block("客队", away))

    group_standings = data.get("group_standings") or []
    if group_standings:
        lines.append("\n# 同组其他球队")
        for row in group_standings[:8]:
            lines.append(
                f"- {row.get('name', '?')}: 第{row.get('position', '?')}名 / {row.get('points', '?')}分"
                f" / {row.get('qualification_status', '')}"
            )

    data_gaps = data.get("data_gaps") or []
    if data_gaps:
        lines.append("\n# 数据缺口")
        lines.append("以下信息内部数据不足，允许通过联网补强: " + "；".join(str(item) for item in data_gaps))

    return "\n".join(lines)
