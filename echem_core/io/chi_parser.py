"""CHI Instruments 电化学工作站数据文件解析器。

支持 CHI 600/700/1100 系列导出的 .txt 文件格式。
"""

import numpy as np
import os
import hashlib
import re
from typing import Optional, Tuple

from echem_core.model import Measurement, Technique


def parse_chi_file(filepath: str, encoding: str = None) -> Measurement:
    """解析 CHI Instruments 导出的 .txt 文件。

    CHI .txt 文件格式特征：
        - 文件头包含 "CHI Instruments" 标识
        - 包含 "Potential/V", "Current/A", "Time/sec" 等列名
        - 数据以表格形式在文件头之后

    Args:
        filepath: CHI .txt 文件路径。
        encoding: 文件编码，为 None 时自动检测（优先 UTF-8，回退 GBK）。

    Returns:
        包含原始数据的 Measurement 对象。

    Raises:
        ValueError: 文件格式无法识别或缺少必要数据列。
        FileNotFoundError: 文件不存在。
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    # 计算文件哈希
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        sha256.update(f.read())
    file_hash = sha256.hexdigest()

    # 检测编码
    if encoding is None:
        encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
    else:
        encodings = [encoding]

    content = None
    used_encoding = None
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
            used_encoding = enc
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if content is None:
        raise ValueError(f"无法解码文件: {filepath}。请指定 encoding 参数。")

    lines = content.splitlines()
    if _is_csstudio_file(lines):
        from echem_core.io.corrtest_parser import parse_corrtest_file

        return parse_corrtest_file(filepath)

    # 定位表头行和数据起始行
    header_row = None
    data_start = None
    column_names = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # 检查是否包含 CHI Instruments 标识
        if "CHI" in stripped and ("Instruments" in stripped or "Electrochemical" in stripped):
            continue
        # 检测真正的数据表头行，避免把 "Quiet Time (sec) = ..." 等元数据误作表头。
        if _is_data_header_line(stripped):
            header_row = i
            column_names = _split_header_columns(stripped)
            data_start = i + 1
            # 跳过空行
            while data_start < len(lines) and not lines[data_start].strip():
                data_start += 1
            break

    if header_row is None:
        # 尝试自动检测：找到第一行连续数字数据
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.replace("\t", " ").split()
            try:
                nums = [float(p) for p in parts]
                if len(nums) >= 2:
                    if _content_indicates_eis(lines) and len(nums) >= 3:
                        column_names = _generic_eis_columns(len(nums))
                    else:
                        # 生成通用列名
                        column_names = [f"Column_{j}" for j in range(len(nums))]
                    data_start = i
                    break
            except ValueError:
                continue

    if data_start is None:
        raise ValueError(f"无法识别 CHI 文件格式: {filepath}")

    # 解析数据
    data_lines = []
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        # 尝试逗号分隔、制表符分隔、空格分隔
        parts = None
        if "," in stripped:
            parts = [p.strip() for p in stripped.split(",") if p.strip()]
        if parts is None or len(parts) < 2:
            parts = stripped.replace(",", " ").split()
        try:
            nums = [float(p) for p in parts]
            data_lines.append(nums)
        except ValueError:
            continue

    if not data_lines:
        raise ValueError(f"文件中未找到数值数据: {filepath}")

    data = np.array(data_lines)

    # 识别技术类型
    technique = _detect_technique(column_names, data, lines)

    # 提取电位和电流列
    potential, current, time = _extract_columns(column_names, data, technique)

    # 解析元数据
    metadata = _parse_chi_metadata(lines, filepath)
    if technique == Technique.EIS:
        metadata["frequency"] = potential.tolist()
        metadata["z_real"] = current.tolist()
        if time is not None:
            metadata["z_imag"] = time.tolist()

    return Measurement(
        technique=technique,
        potential=potential,
        current=current,
        time=time,
        metadata=metadata,
        file_hash=file_hash,
    )


def _is_csstudio_file(lines: list) -> bool:
    """Return True for CorrTest CSStudio exports with gzip metadata headers."""
    for line in lines:
        stripped = line.lstrip("\ufeff").strip()
        if not stripped:
            continue
        return stripped.startswith("CSStudioFile") and "H4sI" in stripped
    return False


def _split_header_columns(line: str) -> list:
    stripped = line.strip()
    if "\t" in stripped:
        parts = stripped.split("\t")
    elif "," in stripped:
        parts = stripped.split(",")
    else:
        parts = stripped.split()
    return [part.strip() for part in parts if part.strip()]


def _is_data_header_line(line: str) -> bool:
    if "=" in line:
        return False
    columns = _split_header_columns(line)
    if len(columns) < 2:
        return False

    recognized = 0
    for column in columns:
        normalized = _normalize_column_name(column)
        if (
            _is_potential_column(normalized)
            or _is_current_column(normalized)
            or _is_time_column(normalized)
            or _is_frequency_column(normalized)
            or _is_impedance_column(normalized)
            or "phase" in normalized
        ):
            recognized += 1
    return recognized >= 2


def _normalize_column_name(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace(" ", "")
        .replace("\u00b2", "2")
        .replace("\u03a9", "ohm")
        .replace("\u2126", "ohm")
        .replace("\u2032", "'")
        .replace("\u2019", "'")
        .replace("\u2033", '"')
    )


def _is_potential_column(name: str) -> bool:
    return any(
        token in name
        for token in ("potential", "potent", "volt", "e(v)", "e/v", "e/")
    )


def _is_current_column(name: str) -> bool:
    return any(
        token in name
        for token in ("current", "curr", "ampere", "i(a", "i/a", "i/")
    )


def _is_time_column(name: str) -> bool:
    return any(token in name for token in ("time", "t(s)", "t/s", "sec"))


def _is_frequency_column(name: str) -> bool:
    return "freq" in name or name in {"f(hz)", "f/hz", "frequency"}


def _is_z_real_column(name: str) -> bool:
    if _is_z_imag_column(name):
        return False
    return any(
        token in name
        for token in ("z'", "zreal", "z_real", "zre", "z_re", "rez", "re(z)")
    )


def _is_z_imag_column(name: str) -> bool:
    return any(
        token in name
        for token in ('z"', "z''", "zimag", "z_imag", "zim", "z_im", "imz", "im(z)")
    )


def _is_impedance_column(name: str) -> bool:
    return any(
        token in name
        for token in ("z'", 'z"', "z''", "zreal", "z_real", "zimag", "z_imag", "impedance")
    )


def _content_indicates_eis(lines: list) -> bool:
    for line in lines[:80]:
        lower = line.strip().lower()
        if any(
            token in lower
            for token in (
                "a.c. impedance",
                "ac impedance",
                "impedance",
                "eis",
            )
        ):
            return True
    return False


def _content_indicates_cp(lines: Optional[list]) -> bool:
    if not lines:
        return False
    for line in lines[:120]:
        lower = line.strip().lower()
        if any(
            token in lower
            for token in (
                "chronopotentiometry",
                "galvanostatic",
                "galstatic",
                "constant current",
                "恒电流",
                "计时电位",
            )
        ):
            return True
    return False


def _content_indicates_ca(lines: Optional[list]) -> bool:
    if not lines:
        return False
    for line in lines[:120]:
        lower = line.strip().lower()
        if any(
            token in lower
            for token in (
                "chronoamperometry",
                "potentiostatic",
                "constant potential",
                "potential step",
                "potstep",
                "i-t",
                "i/t",
                "恒电位",
                "计时电流",
            )
        ):
            return True
    return False


def _column_index(col_lower: list, predicate, default: Optional[int], ncols: int) -> Optional[int]:
    for idx, column in enumerate(col_lower):
        if idx >= ncols:
            break
        if predicate(column):
            return idx
    if default is not None and default < ncols:
        return default
    return None


def _is_monotonic_time_axis(values: Optional[np.ndarray]) -> bool:
    if values is None or len(values) < 3:
        return False
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 3:
        return False
    diff = np.diff(arr)
    return bool(np.all(diff > 0) or np.all(diff < 0))


def _is_nearly_constant_signal(
    values: np.ndarray,
    rel_tol: float = 5e-3,
    abs_tol: float = 1e-10,
) -> bool:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 3:
        return False
    span = float(np.max(arr) - np.min(arr))
    scale = max(float(np.max(np.abs(arr))), abs(float(np.nanmean(arr))), 1e-12)
    return span <= abs_tol or span / scale <= rel_tol


def _looks_like_potential_sweep(potential: np.ndarray) -> bool:
    arr = np.asarray(potential, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 4:
        return False
    span = float(np.max(arr) - np.min(arr))
    if span <= 0 or not np.isfinite(span):
        return False
    diff = np.diff(arr)
    tol = max(span * 1e-4, 1e-12)
    signs = np.sign(diff[np.abs(diff) > tol])
    if signs.size < max(3, int(0.2 * diff.size)):
        return False
    sign_changes = int(np.sum(signs[:-1] * signs[1:] < 0))
    dominant_fraction = max(
        np.count_nonzero(signs > 0),
        np.count_nonzero(signs < 0),
    ) / signs.size
    return sign_changes <= 1 and dominant_fraction >= 0.85


def _infer_stability_technique(
    column_names: list,
    data: np.ndarray,
    lines: Optional[list],
) -> Optional[Technique]:
    """Detect CA/CP time-series that also contain E/I/T columns."""
    if data.shape[1] < 3:
        return None

    col_lower = [_normalize_column_name(c) for c in column_names]
    ncols = data.shape[1]
    potential_idx = _column_index(col_lower, _is_potential_column, 0, ncols)
    current_idx = _column_index(col_lower, _is_current_column, 1, ncols)
    time_idx = _column_index(col_lower, _is_time_column, 2, ncols)

    if time_idx is None or not _is_monotonic_time_axis(data[:, time_idx]):
        return None

    if _content_indicates_cp(lines):
        return Technique.CP
    if _content_indicates_ca(lines):
        return Technique.CA

    if potential_idx is None or current_idx is None:
        return None

    potential = data[:, potential_idx]
    current = data[:, current_idx]
    if _is_nearly_constant_signal(current) and not _looks_like_potential_sweep(potential):
        return Technique.CP
    if _is_nearly_constant_signal(potential, rel_tol=1e-3, abs_tol=1e-6):
        return Technique.CA
    return None


def _generic_eis_columns(count: int) -> list:
    names = ["Freq/Hz", "Z'/ohm", 'Z"/ohm', "Z/ohm", "Phase/deg"]
    if count <= len(names):
        return names[:count]
    return names + [f"Column_{idx}" for idx in range(len(names), count)]


def _is_date_metadata_line(line: str) -> bool:
    stripped = line.strip()
    lower = stripped.lower()
    if lower.startswith("date") or lower.startswith("time/date"):
        return True
    if re.search(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", stripped):
        return True
    return bool(
        re.search(
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+\d{1,2},\s+\d{4}\b",
            lower,
        )
    )


def _detect_technique(
    column_names: list, data: np.ndarray, lines: Optional[list] = None
) -> Technique:
    """根据列名和数据特征检测电化学技术类型。"""
    col_lower = [_normalize_column_name(c) for c in column_names]

    has_frequency = any(_is_frequency_column(c) for c in col_lower)
    has_impedance = any(_is_impedance_column(c) for c in col_lower)

    if (has_frequency and has_impedance) or (lines is not None and _content_indicates_eis(lines)):
        return Technique.EIS

    has_time = any(_is_time_column(c) for c in col_lower)
    has_potential = any(_is_potential_column(c) for c in col_lower)
    has_current = any(_is_current_column(c) for c in col_lower)
    if has_time and has_current and not has_potential:
        return Technique.CA
    if has_time and has_potential and not has_current:
        return Technique.CP
    if has_time and has_potential and has_current:
        stability_technique = _infer_stability_technique(column_names, data, lines)
        if stability_technique is not None:
            return stability_technique

    # 默认基于数据特征判断：如果电位单调变化 -> LSV，否则可能是 CV
    if data.shape[1] >= 1:
        potential = data[:, 0]
        diff = np.diff(potential)
        sign_changes = np.sum(diff[:-1] * diff[1:] < 0)
        if sign_changes > 1:
            return Technique.CV
        else:
            return Technique.LSV

    return Technique.LSV


def _extract_columns(
    column_names: list, data: np.ndarray, technique: Technique
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
    """从数据矩阵中提取电位、电流和时间列。"""
    col_lower = [_normalize_column_name(c) for c in column_names]
    ncols = data.shape[1]

    potential = None
    current = None
    time = None

    if technique == Technique.EIS:
        frequency_idx = None
        z_real_idx = None
        z_imag_idx = None
        for i, c in enumerate(col_lower):
            if i >= ncols:
                break
            if frequency_idx is None and _is_frequency_column(c):
                frequency_idx = i
            if z_real_idx is None and _is_z_real_column(c):
                z_real_idx = i
            if z_imag_idx is None and _is_z_imag_column(c):
                z_imag_idx = i

        if frequency_idx is None and ncols >= 1:
            frequency_idx = 0
        if z_real_idx is None and ncols >= 2:
            z_real_idx = 1
        if z_imag_idx is None and ncols >= 3:
            z_imag_idx = 2
        if frequency_idx is None or z_real_idx is None or z_imag_idx is None:
            raise ValueError(f"无法从列名 {column_names} 中识别 EIS 频率/Z'/Z'' 列")
        return data[:, frequency_idx], data[:, z_real_idx], data[:, z_imag_idx]

    # 找电位列
    for i, c in enumerate(col_lower):
        if i >= ncols:
            break
        if _is_potential_column(c):
            potential = data[:, i]
            break
    if potential is None and ncols >= 1:
        potential = data[:, 0]  # 默认第一列为电位

    # 找电流列
    for i, c in enumerate(col_lower):
        if i >= ncols:
            break
        if _is_current_column(c):
            current = data[:, i]
            break
    if current is None and ncols >= 2:
        current = data[:, 1]  # 默认第二列为电流
    elif current is None and ncols >= 1:
        current = data[:, 0]

    # 找时间列
    for i, c in enumerate(col_lower):
        if i >= ncols:
            break
        if _is_time_column(c):
            time = data[:, i]
            break
    if time is None and ncols >= 3:
        time = data[:, 2]

    if potential is None or current is None:
        raise ValueError(f"无法从列名 {column_names} 中识别电位或电流列")

    return potential, current, time


def _parse_chi_metadata(lines: list, filepath: str) -> dict:
    """从文件头解析元数据。"""
    metadata = {
        "sample_name": os.path.basename(filepath),
        "date": None,
        "instrument": "CHI Instruments",
    }

    for line in lines[:50]:
        lower = line.lower()
        if "a.c. impedance" in lower or "ac impedance" in lower:
            metadata["experiment"] = "A.C. Impedance"
        if metadata["date"] is None and _is_date_metadata_line(line):
            metadata["date"] = line.strip()
        if "electrode" in lower:
            parts = line.split(":")
            if len(parts) > 1:
                metadata["reference_electrode"] = parts[1].strip()
        if "rpm" in lower or "rotation" in lower:
            match = re.search(r"(\d+)", line)
            if match:
                metadata["rotation_rpm"] = float(match.group(1))
        if "scan" in lower and ("rate" in lower or "speed" in lower):
            match = re.search(r"([-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?)", line)
            if match:
                scan_rate = float(match.group(1))
                metadata["scan_rate_raw"] = scan_rate
                if "mv/s" in lower or "mv s" in lower:
                    scan_rate /= 1000.0
                    metadata["scan_rate_mV_s"] = float(match.group(1))
                metadata["scan_rate"] = scan_rate
        if lower.startswith("segment") and "=" in line:
            match = re.search(r"(\d+)", line)
            if match:
                metadata["segment_count"] = int(match.group(1))
        if lower.startswith("init p/n") and "=" in line:
            value = line.split("=", 1)[1].strip().upper()
            if value.startswith("P"):
                metadata["initial_direction"] = "positive"
            elif value.startswith("N"):
                metadata["initial_direction"] = "negative"

    return metadata


def parse_folder(folder_path: str) -> list:
    """批量解析文件夹中所有 CHI .txt 文件。

    Args:
        folder_path: 包含 CHI 数据文件的文件夹路径。

    Returns:
        Measurement 对象列表。
    """
    measurements = []
    for fname in sorted(os.listdir(folder_path)):
        if fname.lower().endswith((".txt", ".csv")):
            try:
                m = parse_chi_file(os.path.join(folder_path, fname))
                measurements.append(m)
            except Exception as e:
                print(f"跳过 {fname}: {e}")
    return measurements
