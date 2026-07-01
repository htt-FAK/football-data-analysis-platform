"""命令行导出 Football-Data 清洗前 / 清洗后 Excel。"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.football_data_pipeline import export_raw_and_clean_excel

EXPORT_DIR = PROJECT_ROOT / "export" / "football_data"


if __name__ == "__main__":
    raw, clean, count = export_raw_and_clean_excel(EXPORT_DIR)
    print(f"COUNT={count}")
    print(f"RAW={raw}")
    print(f"CLEAN={clean}")
