"""Package midterm check materials for FIFA World Cup project."""

import shutil
import zipfile
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def create_package():
    """Create a zip package with all midterm check materials."""
    
    # Source paths
    base_dir = PROJECT_ROOT
    export_dir = base_dir / "export" / "worldcup_fifa"
    scripts_dir = base_dir / "scripts"
    backend_dir = base_dir / "backend"
    
    # Output package path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_name = f"FIFA世界杯数据采集与分析_中期检查材料_{timestamp}"
    package_dir = base_dir / "packages" / package_name
    
    # Create package directory structure
    print(f"Creating package: {package_name}")
    package_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Copy radar charts
    print("Copying radar charts...")
    radar_src = export_dir / "radar_charts"
    radar_dst = package_dir / "01_球员可视化分析" / "六边形雷达图"
    if radar_src.exists():
        shutil.copytree(radar_src, radar_dst)
    
    # 2. Copy key data files
    print("Copying data files...")
    data_dst = package_dir / "02_导出数据样本"
    data_dst.mkdir(parents=True, exist_ok=True)
    
    # Latest player stats CSV
    stats_files = list(export_dir.glob("worldcup_group_stage_player_stats_*.csv"))
    if stats_files:
        latest_stats = max(stats_files, key=lambda p: p.stat().st_mtime)
        shutil.copy2(latest_stats, data_dst / "球员统计数据.csv")
    
    # Latest players info CSV
    players_files = list(export_dir.glob("worldcup_group_stage_players_*.csv"))
    if players_files:
        latest_players = max(players_files, key=lambda p: p.stat().st_mtime)
        shutil.copy2(latest_players, data_dst / "球员基本信息.csv")
    
    # Standings CSV
    standings_files = list(export_dir.glob("worldcup_group_stage_standings_*.csv"))
    if standings_files:
        latest_standings = max(standings_files, key=lambda p: p.stat().st_mtime)
        shutil.copy2(latest_standings, data_dst / "小组积分榜.csv")
    
    # Sources metadata CSV
    sources_files = list(export_dir.glob("worldcup_group_stage_sources_*.csv"))
    if sources_files:
        latest_sources = max(sources_files, key=lambda p: p.stat().st_mtime)
        shutil.copy2(latest_sources, data_dst / "数据来源说明.csv")
    
    # 3. Copy crawler code
    print("Copying crawler code...")
    crawler_dst = package_dir / "03_核心爬虫代码"
    crawler_dst.mkdir(parents=True, exist_ok=True)
    
    # FIFA official crawler (完整版，需要后端框架)
    fifa_crawler = backend_dir / "app" / "crawlers" / "fifa_official.py"
    if fifa_crawler.exists():
        shutil.copy2(fifa_crawler, crawler_dst / "fifa_official_爬虫_完整版.py")
    
    # Base crawler
    base_crawler = backend_dir / "app" / "crawlers" / "base.py"
    if base_crawler.exists():
        shutil.copy2(base_crawler, crawler_dst / "base_基础爬虫类.py")
    
    # Standalone crawler (独立版，可直接运行)
    standalone_crawler = scripts_dir / "standalone_fifa_crawler.py"
    if standalone_crawler.exists():
        shutil.copy2(standalone_crawler, crawler_dst / "standalone_fifa_crawler_独立可运行版.py")
    
    # README for crawler usage
    readme_crawler = scripts_dir / "README_爬虫使用说明.md"
    if readme_crawler.exists():
        shutil.copy2(readme_crawler, crawler_dst / "README_爬虫使用说明.md")
    
    # 4. Copy export code
    print("Copying export code...")
    export_dst = package_dir / "04_数据清洗与导出代码"
    export_dst.mkdir(parents=True, exist_ok=True)
    
    # FIFA export script
    fifa_export = backend_dir / "app" / "export" / "fifa_worldcup_export.py"
    if fifa_export.exists():
        shutil.copy2(fifa_export, export_dst / "fifa_worldcup_export_导出脚本.py")
    
    # Visualization script
    viz_script = scripts_dir / "visualize_player_radar.py"
    if viz_script.exists():
        viz_dst = package_dir / "05_可视化脚本"
        viz_dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(viz_script, viz_dst / "visualize_player_radar_雷达图生成.py")
    
    # 5. Skip README as requested
    
    # 6. Create zip file
    print("Creating zip archive...")
    packages_dir = base_dir / "packages"
    zip_path = packages_dir / f"{package_name}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in package_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(packages_dir)
                zipf.write(file_path, arcname)
    
    print(f"\n[OK] Package created successfully!")
    print(f"Zip file: {zip_path}")
    print(f"Package size: {zip_path.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"\nContents:")
    for item in sorted(package_dir.iterdir()):
        if item.is_dir():
            print(f"  [DIR] {item.name}/")
            for subitem in sorted(item.rglob('*')):
                if subitem.is_file():
                    rel_path = subitem.relative_to(package_dir)
                    print(f"     [FILE] {rel_path}")
        else:
            print(f"  [FILE] {item.name}")
    
    return zip_path


if __name__ == '__main__':
    create_package()
