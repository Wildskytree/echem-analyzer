"""批量电化学数据处理引擎。

提供 BatchProcessor 类，支持文件夹批量导入、Recipe 链式处理
和批量图表导出。
"""

from __future__ import annotations

import os
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np

from echem_core.io.chi_parser import parse_chi_file
from echem_core.io.csv_parser import parse_csv
from echem_core.model import Measurement, Technique
from echem_core.processing.convert import to_rhe
from echem_core.processing.normalize import normalize_by_area
from echem_core.processing.background import subtract, auto_match
from echem_core.plotting.lsv_plot import plot_lsv, plot_lsv_comparison
from echem_core.plotting.styles import JournalStyle, get_style


class BatchProcessor:
    """批量电化学数据处理引擎。

    支持：
    - 从文件夹自动导入 CHI（.txt）和 CSV 文件
    - 通过 Recipe 字典定义处理链（RHE 转换、面积归一化、背景扣除）
    - 批量导出 LSV / CV 图形

    Attributes:
        measurements: 当前加载的 Measurement 对象列表。
        recipe: 最后一次应用的处理配方副本。
    """

    SUPPORTED_EXTENSIONS: tuple = (".txt", ".csv")

    def __init__(
        self,
        measurements: Optional[Sequence[Measurement]] = None,
    ) -> None:
        """初始化 BatchProcessor。

        Args:
            measurements: 可选的初始测量列表。
        """
        self._measurements: List[Measurement] = (
            list(measurements) if measurements is not None else []
        )
        self._recipe: List[Dict[str, Any]] = []

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def measurements(self) -> List[Measurement]:
        """当前加载的所有 Measurement 对象列表（副本）。"""
        return list(self._measurements)

    @property
    def recipe(self) -> List[Dict[str, Any]]:
        """最近一次应用的处理配方（副本）。"""
        import copy
        return copy.deepcopy(self._recipe)

    # ── 文件导入 ────────────────────────────────────────────────────────────

    def load_folder(
        self,
        path: Union[str, Path],
        recursive: bool = False,
        verbose: bool = True,
    ) -> List[Measurement]:
        """从文件夹自动导入 CHI 和 CSV 文件。

        识别 .txt 文件（CHI 格式）和 .csv 文件，使用对应的解析器
        自动导入，每个文件生成一个 Measurement 对象。

        Args:
            path: 文件夹路径。
            recursive: 是否递归扫描子文件夹（默认 False）。
            verbose: 是否打印导入进度信息（默认 True）。

        Returns:
            导入的 Measurement 对象列表（也赋值给 self.measurements）。

        Raises:
            FileNotFoundError: 路径不存在或不是文件夹。
        """
        folder = Path(path)
        if not folder.exists():
            raise FileNotFoundError(f"路径不存在: {folder}")
        if not folder.is_dir():
            raise NotADirectoryError(f"路径不是文件夹: {folder}")

        filepaths: List[Path] = []
        if recursive:
            for ext in self.SUPPORTED_EXTENSIONS:
                filepaths.extend(folder.rglob(f"*{ext}"))
        else:
            for ext in self.SUPPORTED_EXTENSIONS:
                filepaths.extend(folder.glob(f"*{ext}"))

        filepaths = sorted(set(filepaths))
        if not filepaths:
            if verbose:
                print(f"[BatchProcessor] 在 {folder} 中未找到支持的文件")
            self._measurements = []
            return []

        loaded: List[Measurement] = []
        skipped: int = 0

        for fp in filepaths:
            try:
                suffix = fp.suffix.lower()
                if suffix == ".txt":
                    m = parse_chi_file(str(fp))
                else:
                    m = parse_csv(str(fp))
                loaded.append(m)
                if verbose:
                    print(f"  ✓ {fp.name}  →  {m.technique.value}  ({m.file_hash[:8]}...)")
            except Exception as e:
                skipped += 1
                if verbose:
                    print(f"  ✗ {fp.name}  跳过: {e}")

        self._measurements = loaded
        if verbose:
            print(
                f"[BatchProcessor] 完成: 导入 {len(loaded)} 个文件"
                f"{f'，跳过 {skipped} 个' if skipped else ''}"
            )
        return loaded

    # ── Recipe 处理 ─────────────────────────────────────────────────────────

    def apply_recipe(self, recipe: dict) -> List[Measurement]:
        """按 Recipe 字典对当前所有测量执行处理链。

        Recipe 格式::

            {
                "steps": [
                    {"step": "to_rhe", "params": {"reference": "Ag/AgCl", "pH": 13}},
                    {"step": "normalize_by_area", "params": {"area_cm2": 0.196}},
                    {"step": "subtract_background", "params": {"blank": <Measurement>}},
                ]
            }

        Args:
            recipe: 处理配方字典。必须包含 ``"steps"`` 键，值为步骤列表。
                    每步包含 ``"step"``（处理名称）和可选的 ``"params"``
                    （参数字典）。

        Returns:
            处理后的 Measurement 对象列表（每个原始对象对应一个处理后副本）。

        Raises:
            ValueError: Recipe 格式错误或包含未知处理步骤。
            TypeError: 参数类型不正确。
        """
        if not isinstance(recipe, dict):
            raise TypeError("recipe 必须是字典类型")
        steps = recipe.get("steps", [])
        if not isinstance(steps, list):
            raise TypeError("recipe['steps'] 必须是列表")

        result: List[Measurement] = list(self._measurements)  # 副本

        for step_def in steps:
            if not isinstance(step_def, dict):
                raise TypeError("每个处理步骤必须是字典类型")
            step_name = step_def.get("step")
            params = step_def.get("params", {})
            if params is None:
                params = {}
            if not isinstance(params, dict):
                raise TypeError(f"步骤 '{step_name}' 的 params 必须是字典")

            if step_name == "to_rhe":
                result = self._apply_to_rhe(result, params)
            elif step_name == "normalize_by_area":
                result = self._apply_normalize_by_area(result, params)
            elif step_name == "subtract_background":
                result = self._apply_subtract_background(result, params)
            else:
                raise ValueError(
                    f"未知处理步骤: '{step_name}'。"
                    f" 支持的步骤: to_rhe, normalize_by_area, subtract_background"
                )

        # 保存配方
        import copy
        self._recipe = copy.deepcopy(steps)
        self._measurements = result
        return result

    # ── 图表导出 ───────────────────────────────────────────────────────────

    def export_figures(
        self,
        output_dir: Union[str, Path],
        style: Union[str, JournalStyle] = "acs_double",
        format: str = "png",
        dpi: int = 300,
        show_e_half: bool = True,
        per_sample: bool = False,
    ) -> List[Path]:
        """将所有测量结果保存为图表。

        默认将所有 LSV 测量绘制在同一张图上；如果 *per_sample* 为
        True，则为每个测量单独保存一张图。

        Args:
            output_dir: 输出文件夹路径（不存在则自动创建）。
            style: 期刊风格名称或 JournalStyle 对象（默认 "acs_double"）。
            format: 图片格式（如 "png", "svg", "pdf", "tiff"）。
            dpi: 图片分辨率。
            show_e_half: 是否在图上标注半波电位。
            per_sample: 若为 True，每个测量单独成图。

        Returns:
            已保存的图片文件路径列表。

        Raises:
            ValueError: 没有可导出的数据。
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        measurements = self._measurements
        if not measurements:
            raise ValueError("没有可导出的测量数据，请先调用 load_folder() 或 apply_recipe()")

        saved: List[Path] = []

        if per_sample:
            # 每张图只画一条曲线
            for i, m in enumerate(measurements):
                fname = (
                    f"{m.metadata.get('sample_name', f'measurement_{i:04d}')}"
                    f".{format}"
                )
                fpath = output_dir / fname
                try:
                    fig = plot_lsv(
                        m,
                        style=style,
                        title=m.metadata.get("sample_name"),
                        show_e_half=show_e_half,
                    )
                    fig.savefig(str(fpath), dpi=dpi, bbox_inches="tight")
                    import matplotlib.pyplot as plt
                    plt.close(fig)
                    saved.append(fpath)
                except Exception as e:
                    print(f"  导出 {fpath.name} 失败: {e}")
                    continue
        else:
            # 全部画在同一张图上
            lsves = [m for m in measurements if m.technique in (Technique.LSV, Technique.CV)]
            if lsves:
                fname = f"lsv_comparison.{format}"
                fpath = output_dir / fname
                try:
                    fig = plot_lsv_comparison(
                        lsves,
                        labels=[m.metadata.get("sample_name", f"M{i}") for i, m in enumerate(lsves)],
                        style=style,
                    )
                    fig.savefig(str(fpath), dpi=dpi, bbox_inches="tight")
                    import matplotlib.pyplot as plt
                    plt.close(fig)
                    saved.append(fpath)
                except Exception as e:
                    print(f"  导出 {fpath.name} 失败: {e}")
            else:
                # 没有 LSV/CV 数据，逐个导出原始图
                for i, m in enumerate(measurements):
                    fname = (
                        f"{m.metadata.get('sample_name', f'measurement_{i:04d}')}"
                        f".{format}"
                    )
                    fpath = output_dir / fname
                    try:
                        fig = plot_lsv(
                            m,
                            style=style,
                            title=m.metadata.get("sample_name"),
                            show_e_half=show_e_half,
                        )
                        fig.savefig(str(fpath), dpi=dpi, bbox_inches="tight")
                        import matplotlib.pyplot as plt
                        plt.close(fig)
                        saved.append(fpath)
                    except Exception as e:
                        print(f"  导出 {fpath.name} 失败: {e}")
                        continue

        print(f"[BatchProcessor] 导出 {len(saved)} 张图到 {output_dir}")
        return saved


    # ── 内部处理方法 ───────────────────────────────────────────────────────

    @staticmethod
    def _apply_to_rhe(
        measurements: List[Measurement],
        params: Dict[str, Any],
    ) -> List[Measurement]:
        """将测量电位转换为 RHE 标度。"""
        reference = params.get("reference", "RHE")
        pH = params.get("pH", 0.0)
        temperature = params.get("temperature", 298.15)

        result: List[Measurement] = []
        for m in measurements:
            pot = m.raw_potential if m.processed_potential is None else m.processed_potential
            cur = m.raw_current if m.processed_current is None else m.processed_current
            pot_rhe = to_rhe(pot, reference=reference, pH=pH, temperature=temperature)
            result.append(
                m.copy_with_processed(
                    pot_rhe,
                    cur,
                    {"step": "to_rhe", "params": {"reference": reference, "pH": pH}},
                )
            )
        return result

    @staticmethod
    def _apply_normalize_by_area(
        measurements: List[Measurement],
        params: Dict[str, Any],
    ) -> List[Measurement]:
        """按电极几何面积归一化电流为电流密度。"""
        area_cm2 = params.get("area_cm2")
        if area_cm2 is None:
            raise ValueError("normalize_by_area 步骤缺少必选参数 'area_cm2'")
        area_cm2 = float(area_cm2)

        result: List[Measurement] = []
        for m in measurements:
            cur = m.raw_current if m.processed_current is None else m.processed_current
            pot = m.raw_potential if m.processed_potential is None else m.processed_potential
            cur_density = normalize_by_area(cur, area_cm2)
            result.append(
                m.copy_with_processed(
                    pot,
                    cur_density,
                    {"step": "normalize_by_area", "params": {"area_cm2": area_cm2}},
                )
            )
        return result

    @staticmethod
    def _apply_subtract_background(
        measurements: List[Measurement],
        params: Dict[str, Any],
    ) -> List[Measurement]:
        """扣除背景电流。

        params 中可包含 ``"blank"``（一个 Measurement 对象）作为统一空白，
        或 ``"blanks"``（Measurement 列表）用于自动匹配扣除。
        """
        blank = params.get("blank")
        blanks = params.get("blanks", [])

        result: List[Measurement] = []
        for m in measurements:
            pot = m.raw_potential if m.processed_potential is None else m.processed_potential
            cur = m.raw_current if m.processed_current is None else m.processed_current

            if blank is not None:
                # 使用统一空白
                blank_cur = (
                    blank.processed_current
                    if blank.processed_current is not None
                    else blank.raw_current
                )
                cur_sub = subtract(cur, blank_cur)
            elif blanks:
                # 自动匹配
                sample_name = m.metadata.get("sample_name", "")
                matched = auto_match(
                    [(sample_name, cur)],
                    [(b.metadata.get("sample_name", ""),
                      b.processed_current if b.processed_current is not None else b.raw_current)
                     for b in blanks],
                )
                cur_sub = matched[0][1]
            else:
                raise ValueError(
                    "subtract_background 步骤需要 'blank'（单个空白）"
                    "或 'blanks'（空白列表）参数"
                )

            result.append(
                m.copy_with_processed(
                    pot, cur_sub,
                    {"step": "subtract_background"},
                )
            )
        return result

    # ── 便利方法 ───────────────────────────────────────────────────────────

    def __len__(self) -> int:
        """返回当前加载的测量数量。"""
        return len(self._measurements)

    def __getitem__(self, index: int) -> Measurement:
        """按索引访问测量对象。"""
        return self._measurements[index]

    def __repr__(self) -> str:
        return (
            f"BatchProcessor("
            f"measurements={len(self._measurements)}, "
            f"recipe_steps={len(self._recipe)})"
        )


def export_data_for_origin(
    measurements: Sequence[Measurement],
    output_dir: Union[str, Path],
) -> List[Path]:
    """导出 Origin 可直接导入的制表符分隔数据文件。

    每个 Measurement 输出一个 ``*_data.txt`` 文件，数字使用科学计数法。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    saved: List[Path] = []
    for index, measurement in enumerate(measurements):
        headers, columns = _origin_columns_for_measurement(measurement)
        if len(columns) < 2:
            continue

        arrays = [np.asarray(column, dtype=float) for column in columns]
        n_points = min(len(array) for array in arrays)
        if n_points == 0:
            continue

        data = np.column_stack([array[:n_points] for array in arrays])
        sample_name = measurement.metadata.get("sample_name") or f"measurement_{index:04d}"
        filename = f"{_safe_origin_stem(sample_name, index)}_data.txt"
        path = _unique_path(output_dir / filename, saved)
        np.savetxt(
            path,
            data,
            delimiter="\t",
            fmt="%.10e",
            header="\t".join(headers),
            comments="",
        )
        saved.append(path)

    print(f"[BatchProcessor] 导出 {len(saved)} 个 Origin 数据文件到 {output_dir}")
    return saved


def _origin_columns_for_measurement(
    measurement: Measurement,
) -> tuple[List[str], List[np.ndarray]]:
    metadata = measurement.metadata

    if measurement.technique == Technique.EIS:
        frequency = _optional_array(metadata.get("frequency", measurement.raw_potential))
        z_real = _optional_array(metadata.get("z_real", measurement.raw_current))
        z_imag = _optional_array(metadata.get("z_imag", measurement.raw_time))

        headers: List[str] = []
        columns: List[np.ndarray] = []
        for header, column in (
            ("frequency", frequency),
            ("z_real", z_real),
            ("z_imag", z_imag),
        ):
            if column is not None:
                headers.append(header)
                columns.append(column)
        return headers, columns

    headers = ["potential", "current"]
    columns = [measurement.raw_potential, measurement.raw_current]
    if measurement.raw_time is not None:
        headers.append("time")
        columns.append(measurement.raw_time)
    return headers, columns


def _optional_array(values: Any) -> Optional[np.ndarray]:
    if values is None:
        return None
    return np.asarray(values, dtype=float)


def _safe_origin_stem(sample_name: Any, index: int) -> str:
    name = str(sample_name).strip() or f"measurement_{index:04d}"
    stem = Path(name).stem or name
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip(" ._")
    return stem or f"measurement_{index:04d}"


def _unique_path(path: Path, existing: Sequence[Path]) -> Path:
    used = {p.resolve() for p in existing}
    if not path.exists() and path.resolve() not in used:
        return path

    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists() and candidate.resolve() not in used:
            return candidate
        counter += 1


__all__ = ["BatchProcessor", "export_data_for_origin"]
