# Echem Analyzer

面向电化学/催化科研人员的**开源数据后处理工具**。

一键完成 LSV/CV/EIS 数据的导入、处理、分析和论文级图表导出。

## ✨ 功能

- **数据导入** — 支持 CHI Instruments (.txt)、通用 CSV/TSV 格式
- **电位换算** — Ag/AgCl、SCE、Hg/HgO → RHE，支持 pH 和温度修正
- **电流归一化** — 几何面积归一化 (mA/cm²)、负载量归一化 (mA/mg)、ECSA 归一化
- **背景扣除** — 自动按命名规则匹配空白
- **LSV 分析** — E1/2、j_L、Tafel 斜率、K-L 分析（电子转移数 n）
- **CV 分析** — 峰值识别、Cdl、ECSA
- **EIS 分析** — Nyquist/Bode 图、Rs/Rct 估计
- **期刊级图表** — ACS/RSC/Wiley 尺寸预设、色盲友好配色，导出 TIFF/PNG/SVG/PDF
- **批量处理** — 文件夹导入 → 统一 recipe → Excel 汇总 → 批量出图

[📖 使用说明书](USER_GUIDE.md)

## 🚀 快速安装

```bash
# 克隆仓库
git clone https://github.com/YOUR_GITHUB_USERNAME/echem-analyzer.git
cd echem-analyzer

# 创建虚拟环境并安装
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 📖 快速使用

### 命令行

```bash
# 导入并查看数据信息
echem import examples/sample_chi_lsv.txt
echem info examples/sample_chi_lsv.txt

# 处理单个文件（RHE 换算 + 面积归一化 + E1/2/Tafel 自动计算）
echem process examples/sample_chi_lsv.txt --rhe RHE --area 0.196

# 批量处理文件夹
echem batch examples/ --rhe Ag/AgCl --ph 13 --area 0.196 -o results.xlsx --figures ./figures

# 生成图片
echem plot examples/sample_chi_lsv.txt --style acs_double -o lsv_plot.png
```

### Python API

```python
from echem_core.io.chi_parser import parse_chi_file
from echem_core.processing.convert import to_rhe, current_density
from echem_core.analysis.lsv import find_e_half, tafel_slope

# 导入数据
m = parse_chi_file("data/sample.txt")

# 电位换算和归一化
potential = to_rhe(m.raw_potential, reference="Ag/AgCl", pH=13)
current = current_density(m.raw_current, area_cm2=0.196)

# ORR 分析
e_half, j_L, confidence = find_e_half(potential, current)
slope, intercept, r2, _, _ = tafel_slope(potential, current, j_L)

print(f"E1/2 = {e_half:.3f} V ({confidence})")
print(f"Tafel = {slope:.1f} mV/dec (R² = {r2:.3f})")
```

## 📂 项目结构

```
echem_core/
├── io/          数据导入 (CHI、CSV 解析器)
├── model/       数据模型 (Measurement, Technique)
├── processing/  数据处理 (电位换算、归一化、背景扣除)
├── analysis/    分析算法 (LSV、CV、EIS)
├── plotting/    图表绘制 (期刊风格模板)
├── batch/       批处理引擎和报告导出
└── cli.py       命令行入口
```

## 🤝 贡献

欢迎提交 Issue 和 PR：https://github.com/Wildskytree/echem-analyzer

需要新仪器格式支持？请附上示例文件。

## ☕ 支持项目

如果这个工具帮你节省了整理数据的时间，欢迎赞助维护：

- 微信赞赏码：

  <img src="assets/wechat_reward.jpg" alt="微信赞赏码" width="200"/>

## 📄 License

MIT
