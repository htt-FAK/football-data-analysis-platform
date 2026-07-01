"""Generate hexagonal radar charts for FIFA World Cup players."""

import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd
from pathlib import Path
import os

# Set Chinese font support
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False


def normalize_stats(value, min_val, max_val):
    """Normalize a stat value to 0-10 scale."""
    if max_val == min_val:
        return 5
    normalized = (value - min_val) / (max_val - min_val) * 10
    return max(0, min(10, normalized))


def draw_hexagon_radar(ax, stats, labels, title, color='#4472C4'):
    """Draw a hexagonal radar chart."""
    # Number of variables
    N = len(stats)
    
    # What will be the angle of each axis in the plot
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]  # Complete the loop
    
    # The plot is circular, so we need to "complete the loop"
    stats_plot = list(stats) + [stats[0]]
    
    # Draw one axe per variable and add labels
    plt.xticks(angles[:-1], labels, color='grey', size=10)
    
    # Draw radar chart
    ax.plot(angles, stats_plot, linewidth=2, linestyle='solid', color=color)
    ax.fill(angles, stats_plot, color=color, alpha=0.25)
    
    # Add title
    ax.set_title(title, size=12, weight='bold', pad=20)
    
    # Set y-axis limits
    ax.set_ylim(0, 10)
    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_yticklabels(['2', '4', '6', '8', '10'], color='grey', size=8)
    
    # Rotate labels to prevent overlap
    plt.setp(ax.get_xticklabels(), rotation=30, ha='right')


def generate_player_radar_charts(csv_path, output_dir, top_n=8):
    """Generate radar charts for top players."""
    # Read data - try multiple encodings
    for encoding in ['utf-8-sig', 'gbk', 'gb2312', 'utf-8']:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            print(f"Successfully read CSV with encoding: {encoding}")
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Could not read CSV file with any supported encoding")
    
    # Sort by rating and get top players
    df_sorted = df.sort_values(by=['评分', '进球', '助攻'], ascending=[False, False, False]).head(top_n)
    
    # Define radar chart metrics
    metrics = {
        '进攻': ['进球', '射门', '射正'],
        '组织': ['助攻', '传球数', '传球成功率(%)'],
        '防守': ['抢断', '拦截'],
        '效率': ['评分', '出场时间(分钟)', 'xG']
    }
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Calculate global min/max for normalization
    all_stats = []
    for _, row in df_sorted.iterrows():
        player_stats = [
            row['进球'],
            row['射门'],
            row['射正'],
            row['助攻'],
            row['传球数'],
            row['传球成功率(%)'],
            row['抢断'],
            row['拦截'],
            row['评分'],
            row['出场时间(分钟)'],
            row['xG']
        ]
        all_stats.append(player_stats)
    
    all_stats_array = np.array(all_stats)
    mins = all_stats_array.min(axis=0)
    maxs = all_stats_array.max(axis=0)
    
    # Generate radar chart for each player
    for idx, (_, row) in enumerate(df_sorted.iterrows()):
        # Normalize stats
        raw_stats = [
            row['进球'],
            row['射门'],
            row['射正'],
            row['助攻'],
            row['传球数'],
            row['传球成功率(%)'],
            row['抢断'],
            row['拦截'],
            row['评分'],
            row['出场时间(分钟)'],
            row['xG']
        ]
        
        normalized_stats = [
            normalize_stats(raw_stats[i], mins[i], maxs[i])
            for i in range(len(raw_stats))
        ]
        
        labels = [
            '进球', '射门', '射正',
            '助攻', '传球数', '传球成功率',
            '抢断', '拦截',
            '评分', '出场时间', '期望进球'
        ]
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
        
        # Player info
        player_name = row['球员姓名']
        team = row['球队']
        position = row['位置']
        group = row['分组']
        
        title = f"{player_name}\n{team} | {position} | {group}"
        
        # Draw radar
        draw_hexagon_radar(ax, normalized_stats, labels, title)
        
        # Save figure
        filename = f"player_{idx+1}_{player_name.replace(' ', '_')}.png"
        filepath = output_path / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"Generated: {filename}")
    
    # Also generate a combined comparison chart
    generate_comparison_chart(df_sorted, output_path)
    
    return output_path


def generate_comparison_chart(df_sorted, output_path):
    """Generate a combined comparison chart for all top players."""
    # Select key metrics for comparison
    metrics_to_compare = ['进球', '助攻', '评分', '射门', '传球成功率(%)']
    metric_labels = ['进球', '助攻', '评分', '射门', '传球成功率']
    
    # Normalize each metric across all players
    normalized_data = {}
    for metric in metrics_to_compare:
        values = df_sorted[metric].values
        min_val = values.min()
        max_val = values.max()
        normalized_data[metric] = [(v - min_val) / (max_val - min_val) * 10 if max_val != min_val else 5 
                                    for v in values]
    
    # Create grouped bar chart
    fig, ax = plt.subplots(figsize=(14, 8))
    
    x = np.arange(len(df_sorted))
    width = 0.15
    
    bars = []
    colors = ['#FF6B6B', '#4ECDC4', '#95E1D3', '#F38181', '#AA96DA']
    
    for i, (metric, label) in enumerate(zip(metrics_to_compare, metric_labels)):
        offset = (i - len(metrics_to_compare) / 2 + 0.5) * width
        bar = ax.bar(x + offset, normalized_data[metric], width, label=label, color=colors[i], alpha=0.8)
        bars.append(bar)
    
    # Add labels
    ax.set_xlabel('球员', fontsize=12, weight='bold')
    ax.set_ylabel('标准化得分 (0-10)', fontsize=12, weight='bold')
    ax.set_title('世界杯小组赛阶段 - 顶级球员多维度对比', fontsize=14, weight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{row['球员姓名'][:10]}" for _, row in df_sorted.iterrows()], 
                       rotation=45, ha='right', fontsize=9)
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path / 'players_comparison.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print("Generated: players_comparison.png")


if __name__ == '__main__':
    # Input CSV path
    csv_file = r"D:\Users\黄涛韬\OneDrive\桌面\课设\export\worldcup_fifa\worldcup_group_stage_player_stats_20260628_222857.csv"
    
    # Output directory
    output_dir = r"D:\Users\黄涛韬\OneDrive\桌面\课设\export\worldcup_fifa\radar_charts"
    
    # Generate charts
    result_path = generate_player_radar_charts(csv_file, output_dir, top_n=8)
    
    print(f"\nAll charts saved to: {result_path}")
