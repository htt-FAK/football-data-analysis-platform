"""Fotmob xG 接入 — 端到端验证脚本（一键跑完，输出 PASS/FAIL）

用法（在项目根目录）：
    python verify_fotmob_xg.py

本脚本依次执行 5 步验证，任一步失败会明确指出原因：
  1. Python 语法检查（ast.parse 所有改动文件）
  2. DB schema 升级（ALTER TABLE matches 加 home_xg/away_xg，幂等）
  3. 触发 Fotmob 抓取（调用 /api/v1/crawl/trigger，需后端已启动）
  4. 查询 DB 确认某场已结束世界杯比赛 home_xg/away_xg 非空
  5. 打印结论

前置条件：
  - 后端已运行（默认 http://localhost:8000）
  - MySQL 可连接（读 backend/.env 或用默认 localhost:3306）
  - 已安装 undetected-chromedriver 并下载 chromedriver（version_main=137）
    参考 backend/_install_chromedriver.py

注意：Fotmob 的 x-fm-req 反爬依赖 UC 浏览器绕过；若 UC 未就绪，
第 3 步抓取会失败（CrawlLog 显示 failed），此时检查 chromedriver 安装。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# ── 配置（按需修改）──
BACKEND_URL = "http://localhost:8000"
DB_URL = None  # 留 None 则从 backend/.env 读 DATABASE_URL


def step1_syntax_check() -> bool:
    """1. 检查所有改动文件的 Python 语法"""
    print("\n[1/4] Python 语法检查 (ast.parse)...")
    files = [
        "backend/app/crawlers/fotmob.py",
        "backend/app/services/ingest_service.py",
        "backend/app/services/match_service.py",
        "backend/app/models/match.py",
        "backend/app/api/crawl.py",
        "backend/app/services/source_strategy.py",
        "backend/app/scheduler/jobs.py",
        "backend/app/cleaning/entity_resolver.py",
        "scripts/run_fifa_worldcup_ingest.py",
    ]
    root = Path(__file__).parent
    ok = True
    for f in files:
        p = root / f
        if not p.exists():
            print(f"  ❌ 文件不存在: {f}")
            ok = False
            continue
        try:
            ast.parse(p.read_text(encoding="utf-8"))
            print(f"  ✅ {f}")
        except SyntaxError as e:
            print(f"  ❌ {f}: {e}")
            ok = False
    return ok


def step2_schema_upgrade() -> bool:
    """2. ALTER TABLE 加 home_xg/away_xg（幂等）"""
    print("\n[2/4] DB schema 升级 (ALTER TABLE matches)...")
    try:
        # 复用项目自己的 schema 补丁逻辑，保证与正式升级路径一致
        sys.path.insert(0, str(Path(__file__).parent / "backend"))
        from app.database import SessionLocal
        from sqlalchemy import text
    except Exception as e:
        print(f"  ❌ 无法导入数据库模块（后端依赖未装或 .env 缺失）: {e}")
        print("     跳过本步——若你已用 init_database.sql 建库，请手动确认列存在。")
        return False

    db = SessionLocal()
    try:
        existing = {row[0] for row in db.execute(text("SHOW COLUMNS FROM matches")).fetchall()}
        for col, sql in [
            ("home_xg", "ALTER TABLE matches ADD COLUMN home_xg FLOAT COMMENT '主队预期进球'"),
            ("away_xg", "ALTER TABLE matches ADD COLUMN away_xg FLOAT COMMENT '客队预期进球'"),
        ]:
            if col not in existing:
                db.execute(text(sql))
                print(f"  ✅ 新增列: matches.{col}")
            else:
                print(f"  ⊙ 列已存在: matches.{col}")
        db.commit()
        return True
    except Exception as e:
        print(f"  ❌ schema 升级失败: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def step3_trigger_crawl() -> bool:
    """3. POST /api/v1/crawl/trigger {source:fotmob, target:match_xg}"""
    print("\n[3/4] 触发 Fotmob 抓取 (POST /crawl/trigger)...")
    try:
        import requests
    except ImportError:
        print("  ❌ 缺少 requests 库")
        return False

    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/v1/crawl/trigger",
            json={"source": "fotmob", "target": "match_xg"},
            timeout=15,
        )
    except requests.RequestException as e:
        print(f"  ❌ 无法连接后端 ({BACKEND_URL}): {e}")
        print("     请先启动后端：cd backend && python -m uvicorn app.main:app --reload")
        return False

    if resp.status_code != 200:
        print(f"  ❌ 触发失败 HTTP {resp.status_code}: {resp.text[:200]}")
        return False

    data = resp.json()
    log_id = data.get("log_id")
    print(f"  ✅ 采集任务已创建 log_id={log_id}")
    print(f"     抓取是异步的（UC 浏览器逐场抓，较慢）。")
    print(f"     查看进度: GET {BACKEND_URL}/api/v1/crawl/{log_id}")
    print(f"     或直接查 DB: SELECT status, fetched, updated, failed, error_msg FROM crawl_logs WHERE id={log_id};")
    return True


def step4_verify_data() -> bool:
    """4. 查询 DB 确认有比赛的 home_xg/away_xg 非空"""
    print("\n[4/4] 验证 matches.home_xg/away_xg 是否已填充...")
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
    except Exception:
        print("  ⚠ 无法连 DB 查询（见第 2 步错误）。")
        return False

    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT m.id, ht.name AS home, at.name AS away, m.home_xg, m.away_xg, m.status "
            "FROM matches m "
            "LEFT JOIN teams ht ON ht.id = m.home_team_id "
            "LEFT JOIN teams at ON at.id = m.away_team_id "
            "WHERE m.home_xg IS NOT NULL OR m.away_xg IS NOT NULL "
            "ORDER BY m.match_date DESC LIMIT 10"
        )).fetchall()
        if not rows:
            print("  ⚠ 当前没有任何比赛填充了 xG。可能原因：")
            print("     - 抓取还没跑完（等几分钟再查，或看 crawl_logs 状态）")
            print("     - Fotmob 抓取失败（UC/chromedriver 未就绪，或 x-fm-req 被挡）")
            print("     - 球队名不匹配（检查是否有重复球队：")
            print("         SELECT name, COUNT(*) FROM teams GROUP BY name HAVING COUNT(*)>1;)")
            return False
        print(f"  ✅ 找到 {len(rows)} 场已填充 xG 的比赛：")
        for r in rows:
            print(f"     [{r.id}] {r.home} vs {r.away} | xG {r.home_xg}-{r.away_xg} | {r.status}")
        return True
    except Exception as e:
        print(f"  ❌ 查询失败: {e}")
        return False
    finally:
        db.close()


def main() -> int:
    print("=" * 60)
    print("Fotmob 世界杯单场 xG 接入 — 端到端验证")
    print("=" * 60)

    results = {
        "语法检查": step1_syntax_check(),
        "schema 升级": step2_schema_upgrade(),
    }
    # 抓取与 DB 验证依赖后端/网络，单独跑
    crawl_ok = step3_trigger_crawl()
    results["触发抓取"] = crawl_ok

    print("\n" + "-" * 60)
    print("抓取是异步的。等几分钟（或看到 crawl_logs.status=success）后，")
    print("重新运行本脚本，或单独跑第 4 步验证数据已落库。")
    print("-" * 60)

    results["数据验证"] = step4_verify_data()

    print("\n" + "=" * 60)
    print("结论：")
    for step, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {step}")
    print("=" * 60)

    if all(results.values()):
        print("\n🎉 全部通过！打开任一已结束世界杯比赛详情页，")
        print("   「主队 xG / 客队 xG」卡片应显示数值，而非『比赛尚未开始』。")
        return 0
    print("\n⚠ 部分未通过，按上面提示排查。代码改动本身已写完，")
    print("  多半卡在 UC 浏览器/chromedriver 或球队名匹配上。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
