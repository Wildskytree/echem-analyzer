"""CSV 格式光谱文件解析器。

提供从 CSV 文件（以逗号、制表符或空格分隔）中读取光谱数据
并构造 :class:`~echem_core.spectroscopy.model.spectrum.Spectrum`
对象的工具函数。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from ..model.spectrum import Spectrum


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

_DELIMITER_CANDIDATES = [",", "\t", " "]


def _find_data_start(lines: List[str]) -> int:
    """找到数据起始行的索引。

    扫描每一行，找到第一个包含至少两个独立数字的行（跳过空行）。
    数字可以带符号、小数点和科学记数法（如 -1.23e-4）。

    Returns:
        数据起始行索引（0-based）。如果没有找到则返回 0。
    """
    num_pattern = re.compile(
        r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
    )
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        numbers = num_pattern.findall(stripped)
        if len(numbers) >= 2:
            return i
    return 0


def _detect_delimiter(lines: List[str], data_start: int) -> str:
    """从数据行中自动判断列分隔符。

    依次尝试逗号、制表符、空格。选择能使所有数据行产生
    相同列数的分隔符。若都不一致，回退到逗号。

    Returns:
        选定的分隔符字符串。
    """
    data_lines = [l for l in lines[data_start:] if l.strip()]

    best_delim = ","
    best_consistency = -1

    for delim in _DELIMITER_CANDIDATES:
        col_counts: List[int] = []
        for line in data_lines:
            parts = line.strip().split(delim)
            # 剔除空字段（连续空格/制表符产生空字符串）
            parts = [p for p in parts if p]
            if len(parts) >= 2:
                # 确认至少有 2 个可解析为数字的字段
                numeric_count = 0
                for p in parts:
                    try:
                        float(p)
                        numeric_count += 1
                    except ValueError:
                        pass
                if numeric_count >= 2:
                    col_counts.append(numeric_count)

        if not col_counts:
            continue

        all_same = len(set(col_counts)) == 1
        count = len(col_counts)  # 匹配的数据行数
        # 优先选择所有行列数一致的分隔符；相同时选匹配行数多的
        score = (1000 if all_same else 0) + count
        if score > best_consistency:
            best_consistency = score
            best_delim = delim

    return best_delim


def _parse_columns(
    lines: List[str],
    data_start: int,
    delimiter: str,
) -> Tuple[np.ndarray, np.ndarray, Optional[str]]:
    """从数据行中提取 x, y 两列。

    支持：
    - 两列数据 → x, y
    - 三列数据 → x, y, 第三列作为元数据（暂不处理）
    - 更多列 → 取前两列

    Returns:
        (x_array, y_array, extra_info)
    """
    x_vals: List[float] = []
    y_vals: List[float] = []
    extra: Optional[str] = None

    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        parts = [p.strip() for p in stripped.split(delimiter) if p.strip()]
        if len(parts) < 2:
            continue
        try:
            x = float(parts[0])
            y = float(parts[1])
            x_vals.append(x)
            y_vals.append(y)
            if len(parts) >= 3 and extra is None:
                extra = parts[2]
        except ValueError:
            continue

    if not x_vals:
        raise ValueError("未能在文件中找到有效的光谱数据（至少需要两列数字）")

    return np.array(x_vals, dtype=float), np.array(y_vals, dtype=float), extra


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def parse_csv_spectrum(
    filepath: str,
    technique: str = "Raman",
    x_unit: str = "cm-1",
    y_unit: str = "intensity",
) -> Spectrum:
    """从 CSV 文件中解析光谱数据并返回 :class:`Spectrum` 对象。

    自动检测分隔符（逗号 / 制表符 / 空格）并跳过表头行。
    支持两列（x, y）或三列（x, y, 额外列）格式。

    Args:
        filepath:
            光谱 CSV 文件路径（支持 ``~`` 用户目录展开）。
        technique:
            光谱测试技术名称，默认为 ``'Raman'``。
            会被传入 :class:`~echem_core.spectroscopy.model.spectrum.SpectrumTechnique`。
        x_unit:
            x 轴物理单位，默认为 ``'cm-1'``。
        y_unit:
            y 轴物理单位，默认为 ``'intensity'``。

    Returns:
        解析好的 :class:`Spectrum` 实例。

    Raises:
        FileNotFoundError: 文件不存在时抛出。
        ValueError: 文件为空或无法解析到有效数据时抛出。

    Example:
        >>> spec = parse_csv_spectrum("data/raman_001.csv")
        >>> spec.technique
        <SpectrumTechnique.RAMAN: 'Raman'>
        >>> spec.raw_x.shape[0]
        1024
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    raw_text = path.read_text(encoding="utf-8", errors="replace")
    if not raw_text.strip():
        raise ValueError(f"文件为空: {path}")

    lines = raw_text.splitlines()
    data_start = _find_data_start(lines)
    delimiter = _detect_delimiter(lines, data_start)
    x, y, _ = _parse_columns(lines, data_start, delimiter)

    return Spectrum(
        technique=technique,
        x=x,
        y=y,
        x_unit=x_unit,
        y_unit=y_unit,
        metadata={"filepath": str(path.resolve())},
        file_hash=None,
    )


def parse_folder(
    folder: str,
    technique: str = "Raman",
) -> List[Spectrum]:
    """批量解析指定文件夹下所有 CSV 光谱文件。

    递归扫描文件夹（扩展名：``.csv``、``.CSV``、``.tsv``、``.TSV``、
    ``.dat``、``.txt``），对每个文件调用 :func:`parse_csv_spectrum`。

    Args:
        folder:
            包含 CSV 光谱文件的文件夹路径（支持 ``~`` 展开）。
        technique:
            光谱测试技术名称，会传递给每个解析调用。

    Returns:
        所有成功解析的 :class:`Spectrum` 实例列表。
        解析失败的文件会被静默跳过（打印警告但不中断）。

    Example:
        >>> specs = parse_folder("~/data/raman_batch")
        >>> len(specs)
        12
    """
    folder_path = Path(folder).expanduser()
    if not folder_path.is_dir():
        raise NotADirectoryError(f"路径不是有效目录: {folder_path}")

    extensions = {".csv", ".tsv", ".dat", ".txt"}
    spectra: List[Spectrum] = []

    for fpath in sorted(folder_path.rglob("*")):
        if not fpath.is_file():
            continue
        if fpath.suffix.lower() not in extensions:
            continue
        try:
            spec = parse_csv_spectrum(
                filepath=str(fpath),
                technique=technique,
                x_unit="cm-1",
                y_unit="intensity",
            )
            spectra.append(spec)
        except Exception as exc:
            import warnings

            warnings.warn(f"跳过文件 {fpath.name}: {exc}")

    return spectra


__all__ = ["parse_csv_spectrum", "parse_folder"]
