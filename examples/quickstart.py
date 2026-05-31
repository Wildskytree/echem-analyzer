"""
Echem Analyzer 快速入门示例脚本。

演示完整流程：导入 CHI 数据 → 电位换算 → 归一化 → E1/2/Tafel 分析 → 出图。
"""

import os
import sys

# 确保可以从项目根目录导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")


def main():
    """运行快速入门示例。"""
    print("=" * 60)
    print("Echem Analyzer - 快速入门示例")
    print("=" * 60)

    # 1. 导入数据
    print("\n[1/5] 导入示例数据...")
    sample_path = os.path.join(os.path.dirname(__file__), "sample_chi_lsv.txt")
    if not os.path.exists(sample_path):
        print(f"示例文件不存在: {sample_path}")
        print("请先生成示例数据或使用自己的 CHI 文件。")
        return

    from echem_core.io.chi_parser import parse_chi_file
    m = parse_chi_file(sample_path)
    print(f"   ✓ 导入成功: {m}")

    # 2. 电位换算（RHE）
    print("\n[2/5] 电位换算...")
    from echem_core.processing.convert import to_rhe, current_density

    # 示例数据已是 RHE 电位，但演示 API
    potential_rhe = to_rhe(m.raw_potential, reference="RHE")
    print(f"   电位范围: {potential_rhe.min():.3f} ~ {potential_rhe.max():.3f} V vs RHE")

    # 3. 电流归一化
    print("\n[3/5] 电流归一化...")
    area = 0.196  # 5 mm 玻碳电极面积 (cm²)
    current_density_value = current_density(m.raw_current, area)
    print(f"   归一化后电流密度范围: {current_density_value.min():.4f} ~ {current_density_value.max():.4f} mA/cm²")
    print(f"   电极面积: {area} cm²")

    # 4. LSV/ORR 分析
    print("\n[4/5] LSV/ORR 分析...")
    from echem_core.analysis.lsv import find_e_half, tafel_slope, kinetic_current

    e_half, j_L, confidence = find_e_half(potential_rhe, current_density_value)
    print(f"   E1/2     = {e_half:.4f} V  (置信度: {confidence})")
    print(f"   j_L      = {j_L:.4f} mA/cm²")

    slope, intercept, r2, start, end = tafel_slope(potential_rhe, current_density_value, j_L)
    print(f"   Tafel 斜率 = {slope:.1f} mV/dec  (R² = {r2:.4f})")
    print(f"   Tafel 区间: {potential_rhe[start]:.3f} ~ {potential_rhe[end]:.3f} V")

    # 5. 生成图表
    print("\n[5/5] 生成图表...")
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(output_dir, exist_ok=True)

    from echem_core.plotting.lsv_plot import plot_lsv

    # 单条 LSV 图
    output_png = os.path.join(output_dir, "lsv_plot.png")
    plot_lsv(m, style="acs_double", title="ORR LSV Curve", save_path=output_png)
    print(f"   ✓ LSV 图已保存: {output_png}")

    output_svg = os.path.join(output_dir, "lsv_plot.svg")
    plot_lsv(m, style="acs_single", save_path=output_svg)
    print(f"   ✓ SVG 已保存: {output_svg}")

    print("\n" + "=" * 60)
    print("完成！输出文件：")
    print(f"  - {output_png}")
    print(f"  - {output_svg}")
    print("=" * 60)


if __name__ == "__main__":
    main()
