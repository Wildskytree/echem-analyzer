"""Echem Analyzer 命令行工具。"""

import argparse
import os
import sys
from typing import List, Optional

from echem_core.version import __display_version__


def main(argv: Optional[List[str]] = None) -> int:
    """Echem Analyzer 命令行入口。

    用法:
        echem import <path>          导入数据文件或文件夹
        echem info <path>            显示文件信息
        echem process <path>         处理并输出结果
        echem batch <folder>         批量处理文件夹
        echem plot <path>            生成图片
    """
    parser = argparse.ArgumentParser(
        prog="echem",
        description="Echem Analyzer - 电化学数据处理工具",
    )
    parser.add_argument("--version", action="version", version=f"echem-analyzer {__display_version__}")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # import 命令
    import_parser = subparsers.add_parser("import", help="导入数据文件")
    import_parser.add_argument("path", help="文件或文件夹路径")

    # info 命令
    info_parser = subparsers.add_parser("info", help="显示文件信息")
    info_parser.add_argument("path", help="文件路径")

    # process 命令
    process_parser = subparsers.add_parser("process", help="处理数据")
    process_parser.add_argument("path", help="文件路径")
    process_parser.add_argument("--rhe", help="参比电极类型，如 Ag/AgCl")
    process_parser.add_argument("--ph", type=float, default=0.0, help="电解液 pH 值")
    process_parser.add_argument("--area", type=float, help="电极面积 (cm²)")
    process_parser.add_argument("--output", "-o", default=None, help="输出路径")

    # batch 命令
    batch_parser = subparsers.add_parser("batch", help="批量处理文件夹")
    batch_parser.add_argument("folder", help="数据文件夹路径")
    batch_parser.add_argument("--output", "-o", default="results.xlsx", help="输出 Excel 文件路径")
    batch_parser.add_argument("--rhe", help="参比电极类型")
    batch_parser.add_argument("--ph", type=float, default=0.0, help="电解液 pH 值")
    batch_parser.add_argument("--area", type=float, help="电极面积 (cm²)")
    batch_parser.add_argument("--figures", "-f", default=None, help="图片输出文件夹")

    # plot 命令
    plot_parser = subparsers.add_parser("plot", help="生成图片")
    plot_parser.add_argument("path", help="文件路径")
    plot_parser.add_argument("--style", default="acs_double", help="期刊风格")
    plot_parser.add_argument("--dpi", type=int, default=300, help="图片 DPI")
    plot_parser.add_argument("--output", "-o", default="plot.png", help="输出图片路径")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        return _dispatch(args)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


def _dispatch(args) -> int:
    """分发命令到具体的处理函数。"""
    path = args.path if hasattr(args, "path") else getattr(args, "folder", None)

    if args.command == "import":
        return cmd_import(args.path)
    elif args.command == "info":
        return cmd_info(args.path)
    elif args.command == "process":
        return cmd_process(
            args.path,
            reference=args.rhe,
            pH=args.ph,
            area=args.area,
            output=args.output,
        )
    elif args.command == "batch":
        return cmd_batch(
            args.folder,
            output=args.output,
            reference=args.rhe,
            pH=args.ph,
            area=args.area,
            figures=args.figures,
        )
    elif args.command == "plot":
        return cmd_plot(
            args.path,
            style=args.style,
            dpi=args.dpi,
            output=args.output,
        )
    return 0


def cmd_import(path: str) -> int:
    """导入数据文件。"""
    from echem_core.io.chi_parser import parse_chi_file
    from echem_core.io.csv_parser import parse_csv

    path = os.path.expanduser(path)

    if os.path.isdir(path):
        from echem_core.io.chi_parser import parse_folder
        measurements = parse_folder(path)
        print(f"导入了 {len(measurements)} 个文件:")
        for m in measurements:
            print(f"  {m}")
    elif os.path.isfile(path):
        try:
            m = parse_chi_file(path)
        except Exception:
            m = parse_csv(path)
        print(f"导入成功: {m}")
    else:
        print(f"路径不存在: {path}")
        return 1
    return 0


def cmd_info(path: str) -> int:
    """显示数据文件信息。"""
    from echem_core.io.chi_parser import parse_chi_file
    from echem_core.io.csv_parser import parse_csv
    from echem_core.model import Measurement

    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        print(f"文件不存在: {path}")
        return 1

    try:
        m = parse_chi_file(path)
    except Exception:
        try:
            m = parse_csv(path)
        except Exception as e:
            print(f"无法解析文件: {e}")
            return 1

    print(f"技术: {m.technique.value}")
    print(f"数据点: {len(m.raw_potential)}")
    print(f"电位范围: {m.raw_potential.min():.4f} ~ {m.raw_potential.max():.4f} V")
    print(f"电流范围: {m.raw_current.min():.4e} ~ {m.raw_current.max():.4e} A")
    if m.file_hash:
        print(f"文件哈希: {m.file_hash[:16]}...")
    return 0


def cmd_process(
    path: str,
    reference: Optional[str] = None,
    pH: float = 0.0,
    area: Optional[float] = None,
    output: Optional[str] = None,
) -> int:
    """处理单个数据文件。"""
    from echem_core.io.chi_parser import parse_chi_file
    from echem_core.io.csv_parser import parse_csv
    from echem_core.processing.convert import to_rhe, current_density
    from echem_core.analysis.lsv import find_e_half, tafel_slope

    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        print(f"文件不存在: {path}")
        return 1

    try:
        m = parse_chi_file(path)
    except Exception:
        m = parse_csv(path)

    potential = m.raw_potential.copy()
    current = m.raw_current.copy()

    # RHE 换算
    if reference:
        potential = to_rhe(potential, reference=reference, pH=pH)
        print(f"电位已换算至 RHE (参比: {reference}, pH={pH})")

    # 面积归一化
    if area:
        current = current_density(current, area)
        print(f"电流已归一化为电流密度 (面积: {area} cm²)")

    # LSV 分析
    if m.technique.value == "LSV":
        try:
            e_half, j_L, confidence = find_e_half(potential, current)
            print(f"\nE1/2 = {e_half:.4f} V  (置信度: {confidence})")
            print(f"j_L  = {j_L:.4e} {'mA/cm²' if area else 'A'}")

            slope, intercept, r2, s, e = tafel_slope(potential, current, j_L)
            print(f"Tafel 斜率 = {slope:.1f} mV/dec  (R² = {r2:.4f})")
        except Exception as ex:
            print(f"LSV 分析失败: {ex}")

    # 使用处理后的数据保存图片
    if output:
        import matplotlib
        matplotlib.use("Agg")
        recipe = {"steps": []}
        if reference:
            recipe["steps"].append({"step": "to_rhe", "params": {"reference": reference, "pH": pH}})
        if area:
            recipe["steps"].append({"step": "normalize_by_area", "params": {"area_cm2": area}})
        processed = m.copy_with_processed(potential, current, recipe=recipe["steps"])

        from echem_core.plotting.lsv_plot import plot_lsv
        if m.technique.value == "CV":
            from echem_core.plotting.cv_plot import plot_cv
            fig = plot_cv(processed, save_path=output)
        else:
            fig = plot_lsv(processed, save_path=output)
        print(f"图片已保存: {output}")

    return 0


def cmd_batch(
    folder: str,
    output: str = "results.xlsx",
    reference: Optional[str] = None,
    pH: float = 0.0,
    area: Optional[float] = None,
    figures: Optional[str] = None,
) -> int:
    """批量处理文件夹。"""
    from echem_core.batch.batch_processor import BatchProcessor

    folder = os.path.expanduser(folder)
    if not os.path.isdir(folder):
        print(f"文件夹不存在: {folder}")
        return 1

    processor = BatchProcessor()
    measurements = processor.load_folder(folder)
    print(f"共导入 {len(measurements)} 个文件")

    recipe = {"steps": []}
    if reference:
        recipe["steps"].append({
            "step": "to_rhe",
            "params": {"reference": reference, "pH": pH},
        })
    if area:
        recipe["steps"].append({
            "step": "normalize_by_area",
            "params": {"area_cm2": area},
        })

    if recipe["steps"]:
        processed = processor.apply_recipe(recipe)
        print("已应用处理 recipe")
    else:
        processed = measurements

    # 输出 Excel
    from echem_core.batch.report import generate_xlsx
    generate_xlsx(processed, output)
    print(f"结果已保存: {output}")

    # 输出图片
    if figures:
        fig_dir = os.path.expanduser(figures)
        os.makedirs(fig_dir, exist_ok=True)
        processor.export_figures(fig_dir)
        print(f"图片已保存: {fig_dir}")

    return 0


def cmd_plot(
    path: str,
    style: str = "acs_double",
    dpi: int = 300,
    output: str = "plot.png",
) -> int:
    """生成数据图。"""
    import matplotlib
    matplotlib.use("Agg")
    from echem_core.io.chi_parser import parse_chi_file
    from echem_core.io.csv_parser import parse_csv

    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        print(f"文件不存在: {path}")
        return 1

    try:
        m = parse_chi_file(path)
    except Exception:
        m = parse_csv(path)

    output = os.path.expanduser(output)
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    from echem_core.plotting.styles import get_style
    js = get_style(style)
    js.dpi = dpi

    if m.technique.value == "CV":
        from echem_core.plotting.cv_plot import plot_cv
        fig = plot_cv(m, style=style, save_path=output)
    else:
        from echem_core.plotting.lsv_plot import plot_lsv
        fig = plot_lsv(m, style=style, save_path=output)
    print(f"图片已保存: {output} (dpi={dpi})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
