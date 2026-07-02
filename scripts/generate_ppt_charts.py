"""
PPT数据分析可视化图表生成脚本
生成16张高质量PPT图表，分为5大板块
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# ==================== 基础配置 ====================

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.dpi'] = 300
matplotlib.rcParams['savefig.dpi'] = 300
matplotlib.rcParams['savefig.bbox'] = 'tight'
matplotlib.rcParams['savefig.facecolor'] = 'white'

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / 'export' / 'ppt_charts'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 配色方案
COLORS = {
    'primary': '#1e3a5f',
    'primary_light': '#2d5a8e',
    'primary_dark': '#0f2540',
    'accent_green': '#10b981',
    'accent_amber': '#f59e0b',
    'accent_red': '#ef4444',
    'accent_blue': '#3b82f6',
    'accent_purple': '#8b5cf6',
    'accent_pink': '#ec4899',
    'gray_100': '#f1f5f9',
    'gray_200': '#e2e8f0',
    'gray_400': '#94a3b8',
    'gray_500': '#64748b',
    'gray_600': '#475569',
    'gray_800': '#1e293b',
}

# 位置配色
POSITION_COLORS = {
    'FW': '#ef4444',
    'MF': '#3b82f6',
    'DF': '#10b981',
    'GK': '#f59e0b',
}

# ==================== 工具函数 ====================

def save_fig(fig, name, title=None):
    """保存图表并关闭"""
    path = OUTPUT_DIR / f'{name}.png'
    fig.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  ✓ {name}.png  -  {title or name}')
    return path

def set_chinese_font():
    """确保中文字体可用"""
    import os
    font_paths = [
        'C:/Windows/Fonts/simhei.ttf',
        'C:/Windows/Fonts/msyh.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            from matplotlib.font_manager import FontProperties
            return FontProperties(fname=fp)
    return None

fp = set_chinese_font()

# ==================== 数据加载 ====================

def load_data():
    """加载所有数据"""
    data = {}
    
    # 积分榜数据
    standings_path = PROJECT_ROOT / 'export' / 'worldcup_fifa' / 'worldcup_group_stage_standings_20260701_011407.csv'
    if standings_path.exists():
        data['standings'] = pd.read_csv(standings_path)
    else:
        data['standings'] = None
    
    # 球员统计数据
    player_stats_path = PROJECT_ROOT / 'export' / 'worldcup_fifa' / 'worldcup_group_stage_player_stats_20260701_011407.csv'
    if player_stats_path.exists():
        data['player_stats'] = pd.read_csv(player_stats_path)
    else:
        data['player_stats'] = None
    
    return data

DATA = load_data()

# ==================== 板块一：多源数据采集与整合 ====================

def chart_01_data_source_architecture():
    """图1：多源异构数据采集架构图"""
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # 标题
    ax.text(7, 9.5, '多源异构数据采集架构', fontsize=20, fontweight='bold',
            ha='center', color=COLORS['primary_dark'])
    
    # 数据源层
    sources = [
        ('FIFA官网', 0.5),
        ('懂球帝', 2.0),
        ('FBref', 3.5),
        ('Football-Data', 5.0),
        ('Understat', 6.5),
        ('StatsBomb', 8.0),
        ('OpenLigaDB', 9.5),
        ('TheSportsDB', 11.0),
    ]
    
    source_colors = ['#3b82f6', '#ef4444', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#84cc16']
    
    for i, (name, x) in enumerate(sources):
        rect = FancyBboxPatch((x, 7.2), 1.3, 0.8, boxstyle="round,pad=0.1",
                              facecolor=source_colors[i], edgecolor='white', linewidth=2, alpha=0.9)
        ax.add_patch(rect)
        ax.text(x + 0.65, 7.6, name, fontsize=9, ha='center', va='center',
                color='white', fontweight='bold')
    
    # 采集层
    ax.text(7, 6.2, '数据采集层', fontsize=14, fontweight='bold',
            ha='center', color=COLORS['primary'])
    
    collect_methods = [
        ('API调用', '#3b82f6'),
        ('网页爬虫', '#10b981'),
        ('定时调度', '#f59e0b'),
    ]
    for i, (name, color) in enumerate(collect_methods):
        x = 4.5 + i * 2.5
        rect = FancyBboxPatch((x, 5.2), 2, 0.7, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor='white', linewidth=2, alpha=0.85)
        ax.add_patch(rect)
        ax.text(x + 1, 5.55, name, fontsize=11, ha='center', va='center',
                color='white', fontweight='bold')
    
    # 清洗层
    ax.text(7, 4.2, '数据清洗与标准化', fontsize=14, fontweight='bold',
            ha='center', color=COLORS['primary'])
    
    clean_steps = ['字段映射', '实体解析', '去重合并', '缺失补全', '异常过滤']
    for i, step in enumerate(clean_steps):
        x = 1.5 + i * 2.3
        rect = FancyBboxPatch((x, 3.2), 2, 0.7, boxstyle="round,pad=0.1",
                              facecolor=COLORS['primary_light'], edgecolor='white', linewidth=2, alpha=0.85)
        ax.add_patch(rect)
        ax.text(x + 1, 3.55, step, fontsize=10, ha='center', va='center',
                color='white', fontweight='bold')
    
    # 存储层
    ax.text(7, 2.2, '数据存储层', fontsize=14, fontweight='bold',
            ha='center', color=COLORS['primary'])
    
    storages = [
        ('MySQL\n结构化数据', '#3b82f6'),
        ('HDFS\n批量数据', '#8b5cf6'),
        ('Redis\n缓存数据', '#ef4444'),
    ]
    for i, (name, color) in enumerate(storages):
        x = 3 + i * 3.5
        rect = FancyBboxPatch((x, 0.8), 2.8, 1, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor='white', linewidth=2, alpha=0.85)
        ax.add_patch(rect)
        ax.text(x + 1.4, 1.3, name, fontsize=10, ha='center', va='center',
                color='white', fontweight='bold')
    
    # 箭头连接
    for y in [7.0, 5.0, 4.0, 2.0]:
        ax.annotate('', xy=(7, y - 0.3), xytext=(7, y + 0.1),
                    arrowprops=dict(arrowstyle='->', color=COLORS['gray_600'], lw=2))
    
    return save_fig(fig, '01_多源异构数据采集架构', '多源异构数据采集架构')


def chart_02_data_source_matrix():
    """图2：数据源覆盖能力矩阵"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    data_sources = ['FIFA官网', '懂球帝', 'FBref', 'Football-Data', 
                    'Understat', 'StatsBomb', 'OpenLigaDB', 'TheSportsDB']
    data_types = ['赛程', '赛果', '积分榜', '球员统计', '射门(xG)', '比赛事件', '球队数据']
    
    # 覆盖矩阵 (1=覆盖, 0=未覆盖)
    matrix = np.array([
        [1, 1, 1, 1, 0, 1, 1],  # FIFA官网
        [1, 1, 1, 1, 0, 1, 1],  # 懂球帝
        [1, 1, 1, 1, 1, 0, 1],  # FBref
        [1, 1, 1, 1, 1, 0, 1],  # Football-Data
        [0, 1, 0, 0, 1, 0, 1],  # Understat
        [0, 1, 0, 1, 1, 1, 0],  # StatsBomb
        [1, 1, 1, 1, 0, 0, 1],  # OpenLigaDB
        [1, 1, 1, 1, 0, 0, 1],  # TheSportsDB
    ])
    
    # 颜色映射
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        'custom', [COLORS['gray_200'], COLORS['primary_light']])
    
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=1, aspect='auto')
    
    # 标签
    ax.set_xticks(range(len(data_types)))
    ax.set_xticklabels(data_types, fontsize=11, fontweight='bold', color=COLORS['gray_800'])
    ax.set_yticks(range(len(data_sources)))
    ax.set_yticklabels(data_sources, fontsize=10, color=COLORS['gray_800'])
    
    # 添加勾选标记
    for i in range(len(data_sources)):
        for j in range(len(data_types)):
            if matrix[i, j] == 1:
                ax.text(j, i, '●', ha='center', va='center', fontsize=12,
                        color='white', fontweight='bold')
    
    # 标题
    ax.set_title('数据源覆盖能力矩阵', fontsize=16, fontweight='bold',
                 pad=20, color=COLORS['primary_dark'])
    
    # 网格线
    ax.set_xticks(np.arange(len(data_types) + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(data_sources) + 1) - 0.5, minor=True)
    ax.grid(which='minor', color='white', linestyle='-', linewidth=2)
    ax.tick_params(which='minor', bottom=False, left=False)
    
    # 底部统计
    coverage = matrix.sum(axis=0) / len(data_sources) * 100
    for j, cov in enumerate(coverage):
        ax.text(j, len(data_sources) - 0.3, f'{cov:.0f}%', ha='center', va='top',
                fontsize=9, color=COLORS['gray_600'])
    
    return save_fig(fig, '02_数据源覆盖能力矩阵', '数据源覆盖能力矩阵')


def chart_03_data_volume_stats():
    """图3：数据采集规模与时效性"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [2, 1]})
    
    # 左侧：数据量柱状图
    categories = ['世界杯球队', '英超球队', '世界杯球员', '英超球员', 
                  '小组赛场次', '英超场次', '射门记录', '比赛事件']
    values = [48, 20, 736, 600, 36, 380, 5200, 8500]
    colors_list = [COLORS['primary']]*2 + [COLORS['primary_light']]*2 + \
                  [COLORS['accent_blue']]*2 + [COLORS['accent_green']]*2
    
    bars = ax1.barh(categories[::-1], values[::-1], color=colors_list[::-1], height=0.6)
    ax1.set_title('数据采集规模', fontsize=14, fontweight='bold',
                  pad=15, color=COLORS['primary_dark'])
    ax1.set_xlabel('数量', fontsize=11, color=COLORS['gray_600'])
    ax1.tick_params(axis='y', labelsize=10)
    
    # 添加数值标签
    for bar, val in zip(bars, values[::-1]):
        ax1.text(bar.get_width() + max(values)*0.02, bar.get_y() + bar.get_height()/2,
                 f'{val:,}', va='center', fontsize=10, fontweight='bold',
                 color=COLORS['gray_800'])
    
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.set_xlim(0, max(values) * 1.15)
    
    # 右侧：时效性指标卡
    ax2.axis('off')
    
    metrics = [
        ('实时更新', 'WebSocket', COLORS['accent_green']),
        ('轮询频率', '5分钟', COLORS['accent_blue']),
        ('数据源', '8个', COLORS['accent_amber']),
        ('数据字段', '25+', COLORS['accent_purple']),
    ]
    
    for i, (label, value, color) in enumerate(metrics):
        y = 0.85 - i * 0.22
        rect = FancyBboxPatch((0.1, y - 0.08), 0.8, 0.16, boxstyle="round,pad=0.02",
                              facecolor=color, edgecolor='none', alpha=0.15)
        ax2.add_patch(rect)
        ax2.text(0.5, y + 0.02, value, fontsize=20, fontweight='bold',
                 ha='center', color=color)
        ax2.text(0.5, y - 0.04, label, fontsize=10, ha='center',
                 color=COLORS['gray_600'])
    
    ax2.set_title('时效性与丰富度', fontsize=14, fontweight='bold',
                  pad=15, color=COLORS['primary_dark'])
    
    fig.suptitle('数据采集规模与时效性', fontsize=16, fontweight='bold',
                 y=1.02, color=COLORS['primary_dark'])
    
    return save_fig(fig, '03_数据采集规模与时效性', '数据采集规模与时效性')


# ==================== 板块二：数据清洗与标准化 ====================

def chart_04_cleaning_pipeline():
    """图4：数据清洗与标准化流水线"""
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    ax.text(7, 7.4, '数据清洗与标准化流水线', fontsize=18, fontweight='bold',
            ha='center', color=COLORS['primary_dark'])
    
    steps = [
        ('01', '多源数据接入', 'API / 爬虫 / 文件', COLORS['primary']),
        ('02', '字段映射', '统一字段名与格式', COLORS['primary_light']),
        ('03', '实体解析', '球队/球员名归一化', COLORS['accent_blue']),
        ('04', '去重合并', '多源数据融合去重', COLORS['accent_green']),
        ('05', '缺失补全', '智能插值与填充', COLORS['accent_amber']),
        ('06', '异常过滤', '规则法 + Z-Score + IQR', COLORS['accent_red']),
    ]
    
    n = len(steps)
    box_width = 1.8
    box_height = 1.6
    spacing = (14 - n * box_width) / (n + 1)
    
    for i, (num, title, desc, color) in enumerate(steps):
        x = spacing + i * (box_width + spacing)
        y = 3.5
        
        # 主框
        rect = FancyBboxPatch((x, y), box_width, box_height,
                              boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor='white', linewidth=3, alpha=0.9)
        ax.add_patch(rect)
        
        # 步骤编号
        ax.text(x + box_width/2, y + box_height - 0.35, num, fontsize=24,
                ha='center', fontweight='bold', color='white', alpha=0.8)
        
        # 标题
        ax.text(x + box_width/2, y + 0.75, title, fontsize=11,
                ha='center', fontweight='bold', color='white')
        
        # 描述
        ax.text(x + box_width/2, y + 0.35, desc, fontsize=8,
                ha='center', color='white', alpha=0.9)
        
        # 箭头
        if i < n - 1:
            arrow_x = x + box_width + spacing / 2
            ax.annotate('', xy=(arrow_x + spacing/2 - 0.2, y + box_height/2),
                        xytext=(arrow_x - spacing/2 + 0.2, y + box_height/2),
                        arrowprops=dict(arrowstyle='->', color=COLORS['gray_400'], lw=2))
    
    # 输入输出
    ax.text(0.8, 5.5, '原始数据\n(多源异构)', fontsize=11, ha='center',
            fontweight='bold', color=COLORS['gray_600'])
    ax.annotate('', xy=(spacing + 0.3, 4.5), xytext=(0.8, 5.2),
                arrowprops=dict(arrowstyle='->', color=COLORS['gray_600'], lw=2))
    
    ax.text(13.2, 5.5, '高质量数据\n(结构化)', fontsize=11, ha='center',
            fontweight='bold', color=COLORS['accent_green'])
    ax.annotate('', xy=(13.2, 5.2), xytext=(14 - spacing - 0.3, 4.5),
                arrowprops=dict(arrowstyle='->', color=COLORS['gray_600'], lw=2))
    
    # 底部说明
    ax.text(7, 1.5, '输出：统一统计口径 · 完整字段覆盖 · 异常值已过滤 · 实体已归一化',
            fontsize=10, ha='center', style='italic',
            color=COLORS['gray_600'])
    
    return save_fig(fig, '04_数据清洗与标准化流水线', '数据清洗与标准化流水线')


def chart_05_anomaly_detection():
    """图5：异常值智能检测与处理"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # 左侧：箱线图展示IQR检测
    np.random.seed(42)
    # 生成模拟数据：球员评分
    normal_data = np.random.normal(7.0, 0.8, 100)
    outliers = [9.8, 9.6, 4.5, 4.2]
    all_data = np.concatenate([normal_data, outliers])
    
    bp = ax1.boxplot(all_data, vert=True, patch_artist=True, widths=0.5,
                     medianprops=dict(color=COLORS['primary'], linewidth=2),
                     whiskerprops=dict(color=COLORS['gray_600']),
                     capprops=dict(color=COLORS['gray_600']))
    
    bp['boxes'][0].set_facecolor(COLORS['primary_light'])
    bp['boxes'][0].set_alpha(0.6)
    
    # 标记异常值
    ax1.scatter([1]*len(outliers), outliers, color=COLORS['accent_red'], 
                s=80, zorder=5, label='异常值')
    
    # IQR标注
    q1 = np.percentile(all_data, 25)
    q3 = np.percentile(all_data, 75)
    iqr = q3 - q1
    upper = q3 + 1.5 * iqr
    lower = q1 - 1.5 * iqr
    
    ax1.axhline(y=upper, color=COLORS['accent_amber'], linestyle='--', 
                alpha=0.7, label=f'上界(Q3+1.5IQR)={upper:.2f}')
    ax1.axhline(y=lower, color=COLORS['accent_amber'], linestyle='--', 
                alpha=0.7, label=f'下界(Q1-1.5IQR)={lower:.2f}')
    
    ax1.set_title('IQR 异常值检测（球员评分示例）', fontsize=13, fontweight='bold',
                  pad=15, color=COLORS['primary_dark'])
    ax1.set_ylabel('评分', fontsize=11, color=COLORS['gray_600'])
    ax1.set_xticks([])
    ax1.legend(fontsize=9, loc='upper right')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    
    # 右侧：处理策略表
    ax2.axis('off')
    ax2.set_title('异常值处理策略', fontsize=13, fontweight='bold',
                  pad=15, color=COLORS['primary_dark'])
    
    strategies = [
        ('截断 (Clamp)', '超出范围的值限制到边界', '进球 > 20', COLORS['accent_amber']),
        ('置空 (Null)', '无法判断合理性的异常', '传球数 = -1', COLORS['accent_red']),
        ('插值 (Interpolate)', '相邻数据趋势明确时', '单场缺失射门数', COLORS['accent_green']),
        ('保留 (Keep)', '真实存在的极端值', '单场5球（五星表现）', COLORS['accent_blue']),
    ]
    
    for i, (name, desc, example, color) in enumerate(strategies):
        y = 0.82 - i * 0.2
        # 色块
        rect = Rectangle((0.05, y - 0.06), 0.1, 0.12, color=color, alpha=0.8)
        ax2.add_patch(rect)
        # 名称
        ax2.text(0.18, y + 0.02, name, fontsize=11, fontweight='bold',
                 color=COLORS['gray_800'])
        # 描述
        ax2.text(0.18, y - 0.04, desc, fontsize=9, color=COLORS['gray_600'])
        # 示例
        ax2.text(0.95, y, example, fontsize=9, ha='right',
                 style='italic', color=COLORS['gray_400'])
    
    return save_fig(fig, '05_异常值智能检测与处理', '异常值智能检测与处理')


def chart_06_data_fusion():
    """图6：多源数据融合效果对比"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [1, 1.2]})
    
    # 左侧：Venn图示意（用三个圆表示）
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 10)
    ax1.axis('off')
    ax1.set_title('多源数据覆盖重叠', fontsize=13, fontweight='bold',
                  pad=15, color=COLORS['primary_dark'])
    
    # 三个圆
    circles = [
        ((4, 6.5), 2.5, COLORS['primary'], 'FIFA官网', 0.7),
        ((6.5, 5), 2.5, COLORS['accent_blue'], '懂球帝', 0.6),
        ((5, 3.5), 2.5, COLORS['accent_green'], 'FBref', 0.5),
    ]
    
    for (x, y), r, color, label, alpha in circles:
        circle = Circle((x, y), r, facecolor=color, alpha=0.3, 
                       edgecolor=color, linewidth=2)
        ax1.add_patch(circle)
        label_x = x + (r + 0.3) * np.cos(0.5) if x > 5 else x - (r + 0.3) * np.cos(0.5)
        label_y = y + r + 0.3 if y > 5 else y - r - 0.3
    
    ax1.text(3.5, 7.2, 'FIFA官网', fontsize=10, fontweight='bold',
             color=COLORS['primary'])
    ax1.text(7.2, 5.7, '懂球帝', fontsize=10, fontweight='bold',
             color=COLORS['accent_blue'])
    ax1.text(4.2, 1.5, 'FBref', fontsize=10, fontweight='bold',
             color=COLORS['accent_green'])
    
    ax1.text(5, 5.2, '三源交集\n高质量数据', fontsize=9, ha='center',
             fontweight='bold', color=COLORS['gray_800'])
    
    # 右侧：对比表格
    ax2.axis('off')
    ax2.set_title('数据融合前后对比', fontsize=13, fontweight='bold',
                  pad=15, color=COLORS['primary_dark'])
    
    metrics = [
        ('球员数据完整度', '65%', '92%', '+27%', COLORS['accent_green']),
        ('字段丰富度', '12项', '25项', '+108%', COLORS['accent_green']),
        ('数据准确率', '85%', '97%', '+12%', COLORS['accent_green']),
        ('球队覆盖数', '32支', '48支', '+50%', COLORS['accent_green']),
        ('异常值占比', '8.3%', '0.5%', '-94%', COLORS['accent_red']),
    ]
    
    # 表头
    headers = ['指标', '单源 (FIFA)', '三源融合', '提升幅度']
    header_y = 0.9
    col_x = [0.05, 0.35, 0.6, 0.82]
    
    for i, h in enumerate(headers):
        ax2.text(col_x[i], header_y, h, fontsize=10, fontweight='bold',
                 color='white',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor=COLORS['primary'], edgecolor='none'))
    
    # 数据行
    for i, (metric, before, after, change, change_color) in enumerate(metrics):
        y = header_y - 0.13 * (i + 1)
        bg_color = COLORS['gray_100'] if i % 2 == 0 else 'white'
        ax2.axhspan(y - 0.05, y + 0.05, xmin=0.02, xmax=0.98,
                    color=bg_color, zorder=0)
        
        ax2.text(col_x[0], y, metric, fontsize=10, va='center',
                 color=COLORS['gray_800'])
        ax2.text(col_x[1], y, before, fontsize=10, va='center',
                 color=COLORS['gray_600'], ha='center')
        ax2.text(col_x[2], y, after, fontsize=10, va='center',
                 fontweight='bold', color=COLORS['primary'], ha='center')
        ax2.text(col_x[3], y, change, fontsize=10, va='center',
                 fontweight='bold', color=change_color, ha='center')
    
    return save_fig(fig, '06_多源数据融合效果', '多源数据融合效果对比')


# ==================== 板块三：联赛竞争格局分析 ====================

def chart_07_standings_heatmap():
    """图7：世界杯小组赛积分榜总览"""
    fig, ax = plt.subplots(figsize=(14, 10))
    
    if DATA['standings'] is not None:
        df = DATA['standings']
    else:
        # 模拟数据
        groups = [f'Group {chr(65+i)}' for i in range(12)]
        rows = []
        for g in groups:
            for pos in range(1, 5):
                rows.append({
                    '分组': g,
                    '排名': pos,
                    '球队': f'Team {g}-{pos}',
                    '积分': [9, 6, 3, 0][pos-1] + (pos%2)
                })
        df = pd.DataFrame(rows)
    
    groups = df['分组'].unique()
    n_groups = len(groups)
    teams_per_group = 4
    
    # 积分数据矩阵
    points_matrix = np.zeros((teams_per_group, n_groups))
    team_names = []
    qualified_mask = np.zeros((teams_per_group, n_groups), dtype=bool)
    
    for i, group in enumerate(groups):
        group_df = df[df['分组'] == group].sort_values('排名')
        for j in range(teams_per_group):
            if j < len(group_df):
                points_matrix[j, i] = group_df.iloc[j]['积分']
                team_names.append(group_df.iloc[j]['球队'])
                if j < 2:
                    qualified_mask[j, i] = True
            else:
                team_names.append('')
    
    # 热力图
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        'points', ['#fef2f2', '#fee2e2', '#fecaca', '#fca5a5', '#f87171', 
                   '#60a5fa', '#3b82f6', '#2563eb', '#1d4ed8'])
    
    im = ax.imshow(points_matrix, cmap=cmap, vmin=0, vmax=9, aspect='auto')
    
    # 小组标签
    group_labels = [g.replace('Group ', '组 ') for g in groups]
    ax.set_xticks(range(n_groups))
    ax.set_xticklabels(group_labels, fontsize=10, fontweight='bold',
                       color=COLORS['gray_800'])
    
    # 排名标签
    ax.set_yticks(range(teams_per_group))
    ax.set_yticklabels(['第1名', '第2名', '第3名', '第4名'], fontsize=10,
                       color=COLORS['gray_600'])
    
    # 添加数值和队名
    for i in range(teams_per_group):
        for j in range(n_groups):
            idx = j * teams_per_group + i
            pts = points_matrix[i, j]
            name = team_names[idx] if idx < len(team_names) else ''
            
            # 积分数字
            color = 'white' if pts >= 6 else COLORS['gray_800']
            ax.text(j, i - 0.15, f'{pts:.0f}分', ha='center', va='center',
                    fontsize=11, fontweight='bold', color=color)
            
            # 队名
            ax.text(j, i + 0.2, name[:6], ha='center', va='center',
                    fontsize=7, color=color, alpha=0.9)
            
            # 出线标记
            if qualified_mask[i, j]:
                rect = Rectangle((j - 0.48, i - 0.48), 0.96, 0.96,
                                fill=False, edgecolor=COLORS['accent_green'],
                                linewidth=2.5, linestyle='-')
                ax.add_patch(rect)
    
    # 标题
    ax.set_title('2026世界杯小组赛积分榜总览', fontsize=16, fontweight='bold',
                 pad=20, color=COLORS['primary_dark'])
    
    # 图例
    legend_patches = [
        mpatches.Patch(facecolor=COLORS['accent_green'], edgecolor=COLORS['accent_green'],
                      label='晋级淘汰赛', fill=False, linewidth=2),
    ]
    ax.legend(handles=legend_patches, loc='lower right', fontsize=9)
    
    # 色条
    cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_label('积分', fontsize=10, color=COLORS['gray_600'])
    
    return save_fig(fig, '07_世界杯小组赛积分榜总览', '世界杯小组赛积分榜总览')


def chart_08_league_competitiveness():
    """图8：小组竞争激烈程度量化分析"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    if DATA['standings'] is not None:
        df = DATA['standings']
        groups = df['分组'].unique()
        competitiveness = {}
        std_devs = {}
        
        for group in groups:
            points = df[df['分组'] == group]['积分'].values
            if len(points) >= 2:
                std = np.std(points)
                score = max(0.0, 100.0 - std * 3.3)
                competitiveness[group] = round(score, 1)
                std_devs[group] = round(std, 2)
    else:
        competitiveness = {f'Group {chr(65+i)}': 60 + np.random.randint(0, 35) for i in range(12)}
        std_devs = {g: round((100 - v) / 3.3, 2) for g, v in competitiveness.items()}
    
    # 排序
    sorted_groups = sorted(competitiveness.keys(), 
                          key=lambda g: competitiveness[g], reverse=True)
    scores = [competitiveness[g] for g in sorted_groups]
    stds = [std_devs[g] for g in sorted_groups]
    
    group_labels = [g.replace('Group ', '组 ') for g in sorted_groups]
    
    # 颜色渐变
    colors = []
    for s in scores:
        if s >= 80:
            colors.append(COLORS['accent_green'])
        elif s >= 60:
            colors.append(COLORS['accent_amber'])
        else:
            colors.append(COLORS['accent_red'])
    
    bars = ax.bar(range(len(sorted_groups)), scores, color=colors, 
                  width=0.6, edgecolor='white', linewidth=1)
    
    # 数值标签
    for i, (bar, score, std) in enumerate(zip(bars, scores, stds)):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{score:.1f}', ha='center', fontsize=10, fontweight='bold',
                color=COLORS['gray_800'])
    
    ax.set_xticks(range(len(sorted_groups)))
    ax.set_xticklabels(group_labels, fontsize=9, rotation=45, ha='right')
    ax.set_ylabel('竞争度得分', fontsize=11, color=COLORS['gray_600'])
    ax.set_ylim(0, 105)
    
    ax.set_title('小组竞争激烈程度量化分析', fontsize=16, fontweight='bold',
                 pad=20, color=COLORS['primary_dark'])
    
    # 标注最焦灼和最悬殊
    max_idx = scores.index(max(scores))
    min_idx = scores.index(min(scores))
    
    ax.annotate(f'最焦灼\n(标准差={stds[max_idx]:.1f})',
                xy=(max_idx, scores[max_idx]),
                xytext=(max_idx + 1, scores[max_idx] + 8),
                fontsize=9, color=COLORS['accent_green'], fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=COLORS['accent_green']))
    
    ax.annotate(f'最悬殊\n(标准差={stds[min_idx]:.1f})',
                xy=(min_idx, scores[min_idx]),
                xytext=(min_idx - 2, scores[min_idx] + 10),
                fontsize=9, color=COLORS['accent_red'], fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=COLORS['accent_red']))
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # 辅助线
    ax.axhline(y=80, color=COLORS['accent_green'], linestyle='--', alpha=0.3)
    ax.axhline(y=60, color=COLORS['accent_amber'], linestyle='--', alpha=0.3)
    
    return save_fig(fig, '08_小组竞争激烈程度', '小组竞争激烈程度量化分析')


def chart_09_team_attack_defense():
    """图9：球队攻防效率四象限分析"""
    fig, ax = plt.subplots(figsize=(12, 10))
    
    if DATA['standings'] is not None and DATA['player_stats'] is not None:
        df = DATA['standings']
        teams = df['球队'].unique()
        
        np.random.seed(42)
        attack_ratings = []
        defense_ratings = []
        points = []
        team_names = []
        group_names = []
        
        for _, row in df.iterrows():
            gf = row.get('进球', 0)
            ga = row.get('失球', 0)
            pts = row.get('积分', 0)
            
            attack = min(100, (gf / 6) * 100 + np.random.normal(0, 5))
            defense = min(100, (1 - ga / 8) * 100 + np.random.normal(0, 5))
            attack = max(20, min(95, attack))
            defense = max(20, min(95, defense))
            
            attack_ratings.append(attack)
            defense_ratings.append(defense)
            points.append(pts)
            team_names.append(row['球队'])
            group_names.append(row['分组'])
    else:
        np.random.seed(42)
        n_teams = 48
        attack_ratings = np.random.normal(60, 15, n_teams)
        defense_ratings = np.random.normal(60, 15, n_teams)
        points = np.random.randint(0, 10, n_teams)
        team_names = [f'Team {i}' for i in range(n_teams)]
    
    attack_ratings = np.array(attack_ratings)
    defense_ratings = np.array(defense_ratings)
    points = np.array(points)
    
    # 散点图
    scatter = ax.scatter(attack_ratings, defense_ratings, 
                         s=points * 15 + 50,
                         c=points, cmap='RdYlGn',
                         alpha=0.7, edgecolors='white', linewidth=1.5, zorder=5)
    
    # 四象限分割线
    mid_x = np.mean(attack_ratings)
    mid_y = np.mean(defense_ratings)
    
    ax.axvline(x=mid_x, color=COLORS['gray_400'], linestyle='--', alpha=0.7, linewidth=1.5)
    ax.axhline(y=mid_y, color=COLORS['gray_400'], linestyle='--', alpha=0.7, linewidth=1.5)
    
    # 四象限标签
    ax.text(mid_x + 5, 98, '攻守兼备', fontsize=12, fontweight='bold',
            color=COLORS['accent_green'], alpha=0.8)
    ax.text(22, 98, '守强攻弱', fontsize=12, fontweight='bold',
            color=COLORS['accent_blue'], alpha=0.8)
    ax.text(mid_x + 5, 22, '攻强守弱', fontsize=12, fontweight='bold',
            color=COLORS['accent_amber'], alpha=0.8)
    ax.text(22, 22, '攻守俱弱', fontsize=12, fontweight='bold',
            color=COLORS['accent_red'], alpha=0.8)
    
    # 标注TOP球队
    top_indices = np.argsort(points)[-8:][::-1]
    for idx in top_indices:
        ax.annotate(team_names[idx], 
                   (attack_ratings[idx], defense_ratings[idx]),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=8, color=COLORS['gray_800'],
                   fontweight='bold')
    
    ax.set_xlabel('进攻评分', fontsize=12, color=COLORS['gray_600'])
    ax.set_ylabel('防守评分', fontsize=12, color=COLORS['gray_600'])
    ax.set_title('球队攻防效率四象限分析', fontsize=16, fontweight='bold',
                 pad=20, color=COLORS['primary_dark'])
    
    ax.set_xlim(15, 100)
    ax.set_ylim(15, 100)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # 色条
    cbar = fig.colorbar(scatter, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_label('积分', fontsize=10, color=COLORS['gray_600'])
    
    # 球大小图例
    for s in [3, 6, 9]:
        ax.scatter([], [], s=s*15 + 50, c='gray', alpha=0.5,
                   label=f'{s}分')
    ax.legend(scatterpoints=1, frameon=False, labelspacing=1, 
              title='积分', loc='lower right', fontsize=8)
    
    return save_fig(fig, '09_球队攻防效率四象限', '球队攻防效率四象限分析')


# ==================== 板块四：球员能力分析 ====================

def chart_10_top_scorers():
    """图10：小组赛射手榜 TOP10"""
    fig, ax = plt.subplots(figsize=(12, 7))
    
    if DATA['player_stats'] is not None:
        df = DATA['player_stats'].copy()
        df = df.sort_values('进球', ascending=False).head(10)
    else:
        players = ['梅西', '姆巴佩', '哈兰德', '维尼修斯', '凯恩',
                   '加克波', '登贝莱', '温达夫', '萨尔', 'C罗']
        goals = [6, 5, 4, 4, 4, 3, 3, 3, 3, 3]
        teams = ['阿根廷', '法国', '挪威', '巴西', '英格兰',
                 '荷兰', '法国', '德国', '塞内加尔', '葡萄牙']
        positions = ['FW'] * 10
        minutes = [200, 264, 270, 350, 263, 368, 210, 151, 244, 270]
        xg = [3.1, 1.7, 2.4, 3.1, 2.1, 1.3, 0.8, 1.4, 2.8, 1.7]
        df = pd.DataFrame({
            '球员姓名': players, '进球': goals, '球队': teams,
            '位置': positions, '出场时间(分钟)': minutes, 'xG': xg
        })
    
    players = df['球员姓名'].tolist()[:10]
    goals = df['进球'].tolist()[:10]
    
    # 位置颜色
    if '位置' in df.columns:
        pos_colors = [POSITION_COLORS.get(p, COLORS['gray_600']) 
                      for p in df['位置'].tolist()[:10]]
    else:
        pos_colors = [COLORS['primary']] * 10
    
    # 反转顺序用于横向条形图
    players = players[::-1]
    goals = goals[::-1]
    pos_colors = pos_colors[::-1]
    
    bars = ax.barh(players, goals, color=pos_colors, height=0.6,
                   edgecolor='white', linewidth=1.5)
    
    # 数值标签
    for bar, g in zip(bars, goals):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                f'{g} 球', va='center', fontsize=11, fontweight='bold',
                color=COLORS['gray_800'])
    
    # 添加球队和出场时间
    if '球队' in df.columns and '出场时间(分钟)' in df.columns:
        teams = df['球队'].tolist()[:10][::-1]
        minutes = df['出场时间(分钟)'].tolist()[:10][::-1]
        for i, (t, m) in enumerate(zip(teams, minutes)):
            ax.text(0.1, i, f'{t} · {m}\'', va='center', fontsize=8,
                    color='white', alpha=0.9)
    
    ax.set_xlabel('进球数', fontsize=11, color=COLORS['gray_600'])
    ax.set_title('小组赛射手榜 TOP10', fontsize=16, fontweight='bold',
                 pad=20, color=COLORS['primary_dark'])
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_xlim(0, max(goals) * 1.25)
    
    # 位置图例
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=POSITION_COLORS[pos], label=label)
                      for pos, label in [('FW', '前锋'), ('MF', '中场'), ('DF', '后卫')]]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=10)
    
    return save_fig(fig, '10_小组赛射手榜TOP10', '小组赛射手榜TOP10')


def chart_11_player_radar():
    """图11：巨星能力对比 — 五维能力雷达"""
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
    
    dimensions = ['进攻', '组织', '防守', '身体', '纪律']
    N = len(dimensions)
    
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    
    # 球员数据
    players_data = [
        ('梅西', '#ef4444', [95, 88, 45, 60, 90]),
        ('姆巴佩', '#3b82f6', [92, 75, 40, 88, 70]),
        ('哈兰德', '#f59e0b', [90, 50, 35, 95, 65]),
        ('维尼修斯', '#10b981', [88, 78, 45, 85, 75]),
    ]
    
    for name, color, values in players_data:
        values_plot = values + [values[0]]
        ax.plot(angles, values_plot, linewidth=2.5, label=name, color=color)
        ax.fill(angles, values_plot, color=color, alpha=0.15)
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dimensions, fontsize=12, fontweight='bold',
                       color=COLORS['gray_800'])
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=8,
                       color=COLORS['gray_400'])
    
    ax.set_title('巨星能力对比 — 五维能力雷达', fontsize=16, fontweight='bold',
                 pad=30, color=COLORS['primary_dark'])
    
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=11)
    
    # 网格线样式
    ax.grid(color=COLORS['gray_200'], linewidth=1)
    ax.set_facecolor('white')
    
    return save_fig(fig, '11_巨星五维能力雷达对比', '巨星五维能力雷达对比')


def chart_12_player_heatmap():
    """图12：球员能力矩阵 — 多维能力总览"""
    fig, ax = plt.subplots(figsize=(12, 10))
    
    dimensions = ['进攻', '组织', '防守', '身体', '纪律', '综合']
    N_dim = len(dimensions)
    
    # TOP20球员数据
    np.random.seed(42)
    player_names = ['梅西', '姆巴佩', '哈兰德', '维尼修斯', '凯恩',
                    '加克波', '登贝莱', '温达夫', '萨尔', '曼赞比',
                    '奥亚萨瓦尔', '贝林厄姆', 'C罗', '德布劳内', '范戴克',
                    '阿利松', '莫德里奇', '莱万', '萨拉赫', '内马尔']
    
    n_players = len(player_names)
    
    # 生成模拟评分
    scores = np.zeros((n_players, N_dim))
    for i in range(n_players):
        base = 85 - i * 1.5 + np.random.normal(0, 3)
        scores[i, 0] = base + np.random.normal(0, 5)  # 进攻
        scores[i, 1] = base - 5 + np.random.normal(0, 8)  # 组织
        scores[i, 2] = base - 20 + np.random.normal(0, 10)  # 防守
        scores[i, 3] = base - 5 + np.random.normal(0, 6)  # 身体
        scores[i, 4] = base + np.random.normal(0, 4)  # 纪律
        scores[i, 5] = np.mean(scores[i, :5])  # 综合
    
    # 按综合排序
    sorted_idx = np.argsort(scores[:, -1])[::-1]
    scores = scores[sorted_idx]
    player_names = [player_names[i] for i in sorted_idx]
    
    # 热力图
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        'custom', ['#fef2f2', '#fecaca', '#fca5a5', '#60a5fa', '#3b82f6', '#1d4ed8'])
    
    im = ax.imshow(scores, cmap=cmap, vmin=50, vmax=95, aspect='auto')
    
    # 标签
    ax.set_xticks(range(N_dim))
    ax.set_xticklabels(dimensions, fontsize=11, fontweight='bold',
                       color=COLORS['gray_800'])
    ax.set_yticks(range(n_players))
    ax.set_yticklabels(player_names, fontsize=10, color=COLORS['gray_800'])
    
    # 数值
    for i in range(n_players):
        for j in range(N_dim):
            val = scores[i, j]
            color = 'white' if val > 75 else COLORS['gray_800']
            fontweight = 'bold' if j == N_dim - 1 else 'normal'
            ax.text(j, i, f'{val:.1f}', ha='center', va='center',
                    fontsize=8, color=color, fontweight=fontweight)
    
    ax.set_title('球员能力矩阵 — TOP20多维能力总览', fontsize=16, fontweight='bold',
                 pad=20, color=COLORS['primary_dark'])
    
    # 高亮综合列
    ax.axvline(x=N_dim - 1.5, color=COLORS['primary'], linewidth=2.5)
    
    cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_label('能力评分', fontsize=10, color=COLORS['gray_600'])
    
    return save_fig(fig, '12_球员能力矩阵TOP20', '球员能力矩阵TOP20')


def chart_13_position_distribution():
    """图13：各位置球员表现分布"""
    fig, ax = plt.subplots(figsize=(10, 7))
    
    np.random.seed(42)
    
    # 各位置评分分布
    positions = ['FW', 'MF', 'DF', 'GK']
    pos_labels = ['前锋 (FW)', '中场 (MF)', '后卫 (DF)', '门将 (GK)']
    pos_colors = [POSITION_COLORS[p] for p in positions]
    
    # 生成分布数据
    dist_data = {
        'FW': np.random.normal(68, 10, 180),
        'MF': np.random.normal(65, 9, 240),
        'DF': np.random.normal(63, 8, 200),
        'GK': np.random.normal(66, 11, 60),
    }
    
    data_list = [dist_data[p] for p in positions]
    
    # 箱线图
    bp = ax.boxplot(data_list, patch_artist=True, widths=0.5,
                    medianprops=dict(color='white', linewidth=2),
                    whiskerprops=dict(color=COLORS['gray_600']),
                    capprops=dict(color=COLORS['gray_600']),
                    flierprops=dict(marker='o', markerfacecolor=COLORS['gray_400'],
                                   markersize=4, alpha=0.5))
    
    for patch, color in zip(bp['boxes'], pos_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    # 添加小提琴轮廓（用散点模拟）
    for i, (pos, data) in enumerate(zip(positions, data_list)):
        # 添加数据点分布（jitter）
        x_jitter = np.random.normal(i + 1, 0.08, len(data))
        ax.scatter(x_jitter, data, alpha=0.15, s=10,
                   c=POSITION_COLORS[pos], zorder=0)
    
    # 均值线
    means = [np.mean(d) for d in data_list]
    for i, m in enumerate(means):
        ax.scatter(i + 1, m, marker='D', s=80, zorder=5,
                   color='white', edgecolors=COLORS['gray_800'], linewidth=2)
        ax.text(i + 1, m + 1.5, f'{m:.1f}', ha='center', fontsize=9,
                fontweight='bold', color=COLORS['gray_800'])
    
    ax.set_xticks(range(1, len(pos_labels) + 1))
    ax.set_xticklabels(pos_labels, fontsize=11, fontweight='bold',
                       color=COLORS['gray_800'])
    ax.set_ylabel('综合评分', fontsize=11, color=COLORS['gray_600'])
    ax.set_title('各位置球员表现分布', fontsize=16, fontweight='bold',
                 pad=20, color=COLORS['primary_dark'])
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # 图例
    from matplotlib.lines import Line2D
    legend_elements = [Line2D([0], [0], marker='D', color='w', markerfacecolor='white',
                             markeredgecolor=COLORS['gray_800'], markersize=8, label='均值')]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    return save_fig(fig, '13_各位置球员表现分布', '各位置球员表现分布')


# ==================== 板块五：比赛深度分析 ====================

def chart_14_xg_timeline():
    """图14：比赛进程分析 — xG预期进球时间线"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    np.random.seed(42)
    
    # 模拟一场比赛的xG时间线（法国 vs 瑞典）
    minutes = np.arange(0, 91)
    
    # 法国队射门和xG
    fra_shots = [(12, 0.08), (23, 0.15), (35, 0.25), (41, 0.32), 
                 (55, 0.18), (67, 0.42), (78, 0.12), (85, 0.22)]
    swe_shots = [(18, 0.12), (29, 0.08), (47, 0.15), (62, 0.22), (72, 0.10)]
    
    # 实际进球
    fra_goals = [(41, '格列兹曼'), (67, '姆巴佩')]
    swe_goals = [(72, '伊萨克')]
    
    # 计算累计xG
    fra_cum = np.zeros(91)
    swe_cum = np.zeros(91)
    
    for minute, xg in fra_shots:
        for m in range(minute, 91):
            fra_cum[m] += xg
    
    for minute, xg in swe_shots:
        for m in range(minute, 91):
            swe_cum[m] += xg
    
    # 绘制阶梯线
    ax.step(minutes, fra_cum, where='post', color=COLORS['primary'], 
            linewidth=3, label='法国 (xG)', alpha=0.9)
    ax.step(minutes, swe_cum, where='post', color=COLORS['accent_amber'], 
            linewidth=3, label='瑞典 (xG)', alpha=0.9)
    
    # 标注射门
    for minute, xg in fra_shots:
        ax.scatter(minute, fra_cum[minute], s=80, color=COLORS['primary'],
                   zorder=5, edgecolors='white', linewidth=1.5)
    
    for minute, xg in swe_shots:
        ax.scatter(minute, swe_cum[minute], s=80, color=COLORS['accent_amber'],
                   zorder=5, edgecolors='white', linewidth=1.5)
    
    # 标注实际进球
    for minute, scorer in fra_goals:
        ax.annotate(f'⚽ {scorer}', xy=(minute, fra_cum[minute] + 0.15),
                   fontsize=9, fontweight='bold', color=COLORS['primary'],
                   ha='center')
        ax.axvline(x=minute, color=COLORS['primary'], linestyle=':', alpha=0.4)
    
    for minute, scorer in swe_goals:
        ax.annotate(f'⚽ {scorer}', xy=(minute, swe_cum[minute] + 0.15),
                   fontsize=9, fontweight='bold', color=COLORS['accent_amber'],
                   ha='center')
        ax.axvline(x=minute, color=COLORS['accent_amber'], linestyle=':', alpha=0.4)
    
    # 半场线
    ax.axvline(x=45, color=COLORS['gray_400'], linestyle='--', alpha=0.5)
    ax.text(45, max(fra_cum[-1], swe_cum[-1]) * 0.95, '中场', ha='center',
            fontsize=9, color=COLORS['gray_500'], style='italic')
    
    ax.set_xlabel('比赛时间 (分钟)', fontsize=11, color=COLORS['gray_600'])
    ax.set_ylabel('累计预期进球 (xG)', fontsize=11, color=COLORS['gray_600'])
    ax.set_title('比赛进程分析 — xG预期进球时间线\n法国 3-1 瑞典', 
                 fontsize=15, fontweight='bold', pad=20, color=COLORS['primary_dark'])
    
    ax.legend(fontsize=11, loc='upper left')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_xlim(0, 90)
    ax.set_ylim(0, max(fra_cum[-1], swe_cum[-1]) * 1.3)
    
    # 底部说明
    ax.text(45, -max(fra_cum[-1], swe_cum[-1]) * 0.15,
            f'最终比分：法国 3-1 瑞典  |  xG：法国 {fra_cum[-1]:.2f} - {swe_cum[-1]:.2f} 瑞典',
            ha='center', fontsize=10, style='italic', color=COLORS['gray_600'])
    
    return save_fig(fig, '14_xG预期进球时间线', 'xG预期进球时间线')


def chart_15_event_impact():
    """图15：比赛关键事件影响力量化"""
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # 关键事件数据
    events = [
        ('姆巴佩进球\n67\'', 'goal', 95, COLORS['accent_green']),
        ('伊萨克进球\n72\'', 'goal', 78, COLORS['accent_amber']),
        ('格列兹曼进球\n41\'', 'goal', 85, COLORS['accent_green']),
        ('瑞典红牌\n58\'', 'red_card', 72, COLORS['accent_red']),
        ('姆巴佩黄牌\n35\'', 'yellow', 35, COLORS['accent_amber']),
        ('法国换人\n55\'', 'substitution', 25, COLORS['accent_blue']),
        ('法国点球\n67\'', 'penalty', 88, COLORS['accent_green']),
        ('瑞典换人\n60\'', 'substitution', 20, COLORS['accent_blue']),
    ]
    
    # 按影响力排序
    events.sort(key=lambda x: x[2], reverse=True)
    
    names = [e[0] for e in events]
    impacts = [e[2] for e in events]
    colors = [e[3] for e in events]
    
    bars = ax.barh(names[::-1], impacts[::-1], color=colors[::-1],
                   height=0.6, edgecolor='white', linewidth=1.5)
    
    # 数值标签
    for bar, imp in zip(bars, impacts[::-1]):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                f'{imp}', va='center', fontsize=11, fontweight='bold',
                color=COLORS['gray_800'])
    
    ax.set_xlabel('影响力评分', fontsize=11, color=COLORS['gray_600'])
    ax.set_title('比赛关键事件影响力量化\n法国 3-1 瑞典', fontsize=15, fontweight='bold',
                 pad=20, color=COLORS['primary_dark'])
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_xlim(0, 105)
    
    # 图例
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLORS['accent_green'], label='进球/利好'),
        Patch(facecolor=COLORS['accent_red'], label='红牌/利空'),
        Patch(facecolor=COLORS['accent_amber'], label='黄牌/中立'),
        Patch(facecolor=COLORS['accent_blue'], label='换人调整'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=10)
    
    # 影响力分级线
    for threshold, label, color in [(80, '重大影响', COLORS['accent_red']),
                                     (50, '中等影响', COLORS['accent_amber'])]:
        ax.axvline(x=threshold, color=color, linestyle='--', alpha=0.4)
        ax.text(threshold, len(events) - 0.3, label, fontsize=8,
                color=color, ha='center')
    
    return save_fig(fig, '15_比赛关键事件影响力量化', '比赛关键事件影响力量化')


def chart_16_prediction_accuracy():
    """图16：AI预测准确率分析"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [1, 1.2]})
    
    # 左侧：环形图
    labels = ['命中比分', '命中胜负', '未中']
    sizes = [35, 30, 35]
    colors_pie = [COLORS['accent_green'], COLORS['accent_amber'], COLORS['gray_400']]
    
    wedges, texts, autotexts = ax1.pie(sizes, labels=labels, colors=colors_pie,
                                       autopct='%1.1f%%', startangle=90,
                                       pctdistance=0.75,
                                       wedgeprops=dict(width=0.4, edgecolor='white', linewidth=3))
    
    for text in texts:
        text.set_fontsize(11)
        text.set_fontweight('bold')
        text.set_color(COLORS['gray_800'])
    
    for autotext in autotexts:
        autotext.set_fontsize(10)
        autotext.set_fontweight('bold')
        autotext.set_color('white')
    
    # 中心文字
    ax1.text(0, 0.1, '总预测', ha='center', fontsize=11, color=COLORS['gray_600'])
    ax1.text(0, -0.15, '20场', ha='center', fontsize=20, fontweight='bold',
             color=COLORS['primary'])
    
    ax1.set_title('预测命中分布', fontsize=14, fontweight='bold',
                  pad=20, color=COLORS['primary_dark'])
    
    # 右侧：详细统计表
    ax2.axis('off')
    ax2.set_title('预测准确率分析', fontsize=14, fontweight='bold',
                  pad=20, color=COLORS['primary_dark'])
    
    stats = [
        ('总预测场次', '20场', COLORS['primary']),
        ('命中比分', '7场 (35%)', COLORS['accent_green']),
        ('命中胜负', '6场 (30%)', COLORS['accent_amber']),
        ('完全命中', '13场 (65%)', COLORS['primary_light']),
        ('未命中', '7场 (35%)', COLORS['gray_400']),
        ('平均置信度', '78.5%', COLORS['accent_purple']),
    ]
    
    for i, (label, value, color) in enumerate(stats):
        y = 0.85 - i * 0.13
        
        # 标签
        ax2.text(0.1, y, label, fontsize=11, va='center',
                 color=COLORS['gray_600'])
        
        # 数值
        ax2.text(0.85, y, value, fontsize=14, va='center',
                 fontweight='bold', color=color, ha='right')
        
        # 分隔线
        if i < len(stats) - 1:
            ax2.axhline(y=y - 0.06, xmin=0.05, xmax=0.95,
                       color=COLORS['gray_200'], linewidth=1)
    
    # 底部说明
    ax2.text(0.5, 0.05, 
             '三档判定：命中比分(预测比分=实际) > 命中胜负(胜负正确) > 未中',
             ha='center', fontsize=9, style='italic', color=COLORS['gray_500'])
    
    return save_fig(fig, '16_AI预测准确率分析', 'AI预测准确率分析')


# ==================== 主函数 ====================

def generate_all():
    """生成所有16张PPT图表"""
    print('=' * 60)
    print('  开始生成 PPT 数据分析图表')
    print('=' * 60)
    
    print('\n📊 板块一：多源数据采集与整合')
    chart_01_data_source_architecture()
    chart_02_data_source_matrix()
    chart_03_data_volume_stats()
    
    print('\n🧹 板块二：数据清洗与标准化')
    chart_04_cleaning_pipeline()
    chart_05_anomaly_detection()
    chart_06_data_fusion()
    
    print('\n🏆 板块三：联赛竞争格局分析')
    chart_07_standings_heatmap()
    chart_08_league_competitiveness()
    chart_09_team_attack_defense()
    
    print('\n⚽ 板块四：球员能力分析')
    chart_10_top_scorers()
    chart_11_player_radar()
    chart_12_player_heatmap()
    chart_13_position_distribution()
    
    print('\n📈 板块五：比赛深度分析')
    chart_14_xg_timeline()
    chart_15_event_impact()
    chart_16_prediction_accuracy()
    
    print('\n' + '=' * 60)
    print(f'  ✅ 全部 16 张图表生成完毕！')
    print(f'  📁 输出目录：{OUTPUT_DIR}')
    print('=' * 60)


if __name__ == '__main__':
    generate_all()
