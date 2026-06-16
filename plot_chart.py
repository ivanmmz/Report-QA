import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# 过去12个月的数据 (2025年5月 - 2026年5月)
months = [
    '2025/05', '2025/06', '2025/07', '2025/08', '2025/09',
    '2025/10', '2025/11', '2025/12',
    '2026/01', '2026/02', '2026/03', '2026/04', '2026/05'
]
efficiency = [0.624, 0.615, 0.604, 0.607, 0.598, 0.604, 0.602, 0.598, 0.581, 0.589, 0.607, 0.625, 0.628]

# 尝试找到中文字体
try:
    font_paths = [
        'C:/Windows/Fonts/msyh.ttc',  # 微软雅黑
        'C:/Windows/Fonts/simsun.ttc', # 宋体
        'C:/Windows/Fonts/simhei.ttf', # 黑体
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    ]
    font_found = None
    for fp in font_paths:
        try:
            if fm.findfont(fm.FontProperties(fname=fp), fallback_to_default=False):
                font_found = fp
                break
        except:
            pass
    if font_found:
        font_prop = fm.FontProperties(fname=font_found)
    else:
        font_prop = fm.FontProperties()
        print("No Chinese font found, labels may show as squares")
except:
    font_prop = fm.FontProperties()

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [1.8, 1]})

# 柱状图
x = np.arange(len(months))
width = 0.6
colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(months)))
bars = ax1.bar(x, efficiency, width, color=colors, edgecolor='white', linewidth=0.5)

# 数据标签
for bar, val in zip(bars, efficiency):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
             f'{val:.3f}', ha='center', va='bottom', fontsize=9, fontproperties=font_prop)

ax1.set_xticks(x)
ax1.set_xticklabels(months, fontsize=9, fontproperties=font_prop, rotation=45)
ax1.set_ylabel('Efficiency (kW/RT)', fontsize=11, fontproperties=font_prop)
ax1.set_title('Chiller Plant Efficiency - Monthly (kW/RT)', fontsize=13, fontproperties=font_prop, fontweight='bold')
ax1.set_ylim(0.55, 0.66)
ax1.axhline(y=0.6, color='red', linestyle='--', alpha=0.5, label='Target: 0.600 kW/RT')
ax1.legend(prop=font_prop, fontsize=10)
ax1.grid(axis='y', alpha=0.3)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)

# 折线图
ax2.plot(x, efficiency, 'o-', color='#2196F3', linewidth=2.5, markersize=8, markerfacecolor='white', markeredgewidth=2)

# 数据标签
for i, (m, v) in enumerate(zip(months, efficiency)):
    ax2.annotate(f'{v:.3f}', (i, v), textcoords="offset points", xytext=(0, 12),
                ha='center', fontsize=9, fontproperties=font_prop)

ax2.set_xticks(x)
ax2.set_xticklabels(months, fontsize=9, fontproperties=font_prop, rotation=45)
ax2.set_ylabel('Efficiency (kW/RT)', fontsize=11, fontproperties=font_prop)
ax2.set_xlabel('Month', fontsize=11, fontproperties=font_prop)
ax2.set_ylim(0.55, 0.66)
ax2.axhline(y=0.6, color='red', linestyle='--', alpha=0.5, label='Target: 0.600 kW/RT')
ax2.legend(prop=font_prop, fontsize=10)
ax2.grid(axis='y', alpha=0.3)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('chiller_plant_efficiency.png', dpi=150, bbox_inches='tight')
print("Chart saved successfully!")
