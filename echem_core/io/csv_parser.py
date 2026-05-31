"""通用 CSV/TSV 电化学数据文件解析器。

支持逗号、制表符、分号分隔的文本数据文件，自动检测分隔符和列类型，
也可通过 col_map 参数手动指定列映射。
"""

import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from echem_core.model import Measurement, Technique

# ── 列名匹配模式 ──────────────────────────────────────────────────────────────

# 电位列匹配模式（按匹配优先级排序）
_POTENTIAL_PATTERNS: List[str] = [
    "potential/v",
    "potential",
    "e / v",
    "e (v)",
    "e/v",
    "e/v ",
    "e/v)",
    "e/v (",
    "volt",
    "e (v vs",
    "potent",
]

# 电流列匹配模式
_CURRENT_PATTERNS: List[str] = [
    "current/a",
    "current",
    "i / a",
    "i (a)",
    "i/a",
    "ampere",
    "curr",
]

# 时间列匹配模式
_TIME_PATTERNS: List[str] = [
    "time/s",
    "time",
    "t / s",
    "t (s)",
    "t/s",
    "sec",
    "second",
]

# 频率列匹配模式
_FREQUENCY_PATTERNS: List[str] = [
    "frequency/hz",
    "frequency",
    "freq",
    "f/hz",
    "f (hz)",
]

# 阻抗实部 (Z') 匹配模式
_Z_REAL_PATTERNS: List[str] = [
    "z'",
    "z'",
    "z_re",
    "z_real",
    "z' / ω",
    "z'/ω",
    "zre",
    "real z",
    "z' (ω)",
]

# 阻抗虚部 (Z") 匹配模式
_Z_IMAG_PATTERNS: List[str] = [
    'z"',
    "z\"",
    "z_im",
    "z_imag",
    'z" / ω',
    'z"/ω',
    "zim",
    "imag z",
    'z" (ω)',
]

# ── 公共辅助函数 ──────────────────────────────────────────────────────────────


def _compute_file_hash(filepath: str) -> str:
    """计算文件的 SHA-256 哈希值。

    Args:
        filepath: 文件路径。

    Returns:
        SHA-256 十六进制字符串。
    """
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        sha256.update(f.read())
    return sha256.hexdigest()


def _detect_encoding(filepath: str, encoding: Optional[str] = None) -> Tuple[str, str]:
    """检测文件编码并读取文件内容。

    Args:
        filepath: 文件路径。
        encoding: 用户指定的编码，为 None 时自动检测。

    Returns:
        (文件内容字符串, 实际使用的编码名称)。

    Raises:
        ValueError: 所有尝试的编码均无法解码时抛出。
    """
    if encoding is not None:
        encodings = [encoding]
    else:
        encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]

    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
            return content, enc
        except (UnicodeDecodeError, UnicodeError):
            continue

    raise ValueError(
        f"无法解码文件: {filepath}。请指定 encoding 参数。"
    )


def _detect_delimiter(lines: List[str]) -> Optional[str]:
    """自动检测文件使用的分隔符。

    依次尝试逗号、制表符、分号，选择首行拆分后列数最多且列数一致的分隔符。
    若以上均不理想，回退到空白符分割。

    Args:
        lines: 文件非空行列表。

    Returns:
        检测到的分隔符字符串。
    """
    if not lines:
        return ","

    delimiters: List[str] = [",", "\t", ";"]
    best_delim: str = ","
    best_score: int = 1

    for delim in delimiters:
        col_counts: List[int] = []
        for line in lines[:20]:  # 扫描前 20 行
            parts = line.split(delim)
            col_counts.append(len(parts))

        if not col_counts:
            continue

        # 选择非单列（分隔符有效）且列数稳定的分隔符
        mode_count = max(set(col_counts), key=col_counts.count)
        stability = col_counts.count(mode_count)
        if mode_count >= 2 and stability > best_score:
            best_score = stability
            best_delim = delim

    # 如果最佳分隔符得分仍偏低（数据稀疏），尝试空白符
    if best_score <= 1:
        col_counts = [len(line.split()) for line in lines[:20]]
        if col_counts and max(col_counts, default=1) >= 2:
            return None  # None 指示后续用 split() 空白分割

    return best_delim


def _find_header_row(lines: List[str]) -> int:
    """在文本行中定位表头行。

    寻找包含已知电化学列名关键词的行。若未找到关键词行，
    则返回第一行作为表头（假定无表头文件）。

    Args:
        lines: 文件文本行列表。

    Returns:
        表头行的索引。
    """
    all_keywords = (
        _POTENTIAL_PATTERNS
        + _CURRENT_PATTERNS
        + _TIME_PATTERNS
        + _FREQUENCY_PATTERNS
        + _Z_REAL_PATTERNS
        + _Z_IMAG_PATTERNS
    )

    for i, line in enumerate(lines[:100]):  # 只扫描前 100 行
        line_lower = line.strip().lower()
        # 跳过空行
        if not line_lower:
            continue

        # 检查是否包含已知电化学关键词
        for kw in all_keywords:
            if kw.lower() in line_lower:
                return i

    # 找不到关键词行，返回第一行作为表头
    return 0


def _split_row(line: str, delimiter: Optional[str]) -> List[str]:
    """根据分隔符拆分一行文本。

    Args:
        line: 文本行。
        delimiter: 分隔符（None 表示空白符分割）。

    Returns:
        拆分后的字符串列表。
    """
    if delimiter is None:
        return line.strip().split()
    return [col.strip() for col in line.strip().split(delimiter)]


def _match_column_pattern(
    col_name: str, patterns: List[str]
) -> bool:
    """检查列名是否匹配任一模式（不区分大小写、忽略空白符）。

    Args:
        col_name: 列名字符串。
        patterns: 匹配模式列表。

    Returns:
        匹配成功返回 True。
    """
    cleaned = col_name.strip().lower().replace(" ", "")
    for pat in patterns:
        pat_clean = pat.strip().lower().replace(" ", "")
        if pat_clean in cleaned or cleaned == pat_clean:
            return True
    return False


def _auto_map_columns(
    headers: List[str],
) -> Dict[str, str]:
    """根据列名自动识别标准列映射。

    依次检测电位、电流、时间、频率、Z'、Z"列。
    返回的映射字典键为 Measurement 标准字段名，值为原始列名。

    Returns:
        标准字段名到原始列名的映射字典。
    """
    mapping: Dict[str, Optional[str]] = {
        "potential": None,
        "current": None,
        "time": None,
        "frequency": None,
        "z_real": None,
        "z_imag": None,
    }

    for header in headers:
        h = header.strip()

        if mapping["potential"] is None and _match_column_pattern(h, _POTENTIAL_PATTERNS):
            mapping["potential"] = h
            continue

        if mapping["current"] is None and _match_column_pattern(h, _CURRENT_PATTERNS):
            mapping["current"] = h
            continue

        if mapping["time"] is None and _match_column_pattern(h, _TIME_PATTERNS):
            mapping["time"] = h
            continue

        if mapping["frequency"] is None and _match_column_pattern(h, _FREQUENCY_PATTERNS):
            mapping["frequency"] = h
            continue

        if mapping["z_real"] is None and _match_column_pattern(h, _Z_REAL_PATTERNS):
            mapping["z_real"] = h
            continue

        if mapping["z_imag"] is None and _match_column_pattern(h, _Z_IMAG_PATTERNS):
            mapping["z_imag"] = h
            continue

    # 清理 None 条目
    return {k: v for k, v in mapping.items() if v is not None}


def _resolve_column_index(
    header: str, headers: List[str]
) -> int:
    """根据列名查找在表头列表中的索引。

    Args:
        header: 列名。
        headers: 表头列表。

    Returns:
        列索引。

    Raises:
        ValueError: 未找到匹配列时抛出。
    """
    h_clean = header.strip().lower()
    for i, h in enumerate(headers):
        if h.strip().lower() == h_clean:
            return i

    # 模糊匹配（包含关系）
    for i, h in enumerate(headers):
        if h_clean in h.strip().lower() or h.strip().lower() in h_clean:
            return i

    raise ValueError(f"在表头中未找到列 '{header}'（可用列: {headers}）")


def _build_column_index_map(
    col_map: Optional[Dict[str, Union[str, int]]],
    headers: List[str],
) -> Dict[str, int]:
    """将列映射规范化为列索引字典。

    输入 col_map 的键可以是任何字符串（将被存入元数据），
    值可以是列索引 (int) 或列名 (str)。

    Args:
        col_map: 用户提供的列映射（可为 None）。
        headers: 表头列表。

    Returns:
        标准字段名到列索引的字典。包含 'potential' 和 'current' 至少两项。
    """
    result: Dict[str, int] = {}

    if col_map is None:
        return result

    for key, value in col_map.items():
        if isinstance(value, int):
            result[key] = value
        elif isinstance(value, str):
            result[key] = _resolve_column_index(value, headers)
        else:
            raise TypeError(f"col_map 中 '{key}' 的值类型无效: {type(value).__name__}")

    return result


def _merge_column_mapping(
    auto_map: Dict[str, str],
    manual_idx_map: Dict[str, int],
    headers: List[str],
) -> Dict[str, int]:
    """合并自动和手动列映射，手动映射优先。

    自动映射给出的是原始列名 → 标准字段。手动映射给出的是标准字段 → 列索引。
    合并后返回标准字段 → 列索引的字典。

    Args:
        auto_map: 自动检测到的标准字段 → 原始列名映射。
        manual_idx_map: 用户手动指定的标准字段 → 列索引映射。
        headers: 表头列表。

    Returns:
        合并后的标准字段 → 列索引映射。
    """
    merged: Dict[str, int] = {}

    # 先应用自动映射
    for field, col_name in auto_map.items():
        merged[field] = _resolve_column_index(col_name, headers)

    # 手动映射覆盖
    merged.update(manual_idx_map)

    return merged


def _detect_technique_from_columns(
    col_indices: Dict[str, int]
) -> Technique:
    """根据已识别的列集合推断电化学测试技术。

    Args:
        col_indices: 标准字段到列索引的映射。

    Returns:
        推断出的 Technique 枚举值。
    """
    has_frequency = "frequency" in col_indices
    has_z_real = "z_real" in col_indices
    has_z_imag = "z_imag" in col_indices
    has_potential = "potential" in col_indices
    has_current = "current" in col_indices
    has_time = "time" in col_indices

    if (has_frequency and has_z_real) or (has_frequency and has_z_imag):
        return Technique.EIS

    if has_time and not has_potential:
        return Technique.CA

    # 默认由数据特征推断
    return Technique.LSV


def _detect_technique_from_data(
    potential: np.ndarray,
) -> Technique:
    """根据电位数组的数据特征推断测试技术。

    通过检测电位方向变化次数以及首尾值是否接近来区分 LSV（单调变化）
    和 CV（有回扫）。

    Args:
        potential: 电位数组。

    Returns:
        推断出的 Technique 枚举值。
    """
    if len(potential) < 3:
        return Technique.LSV

    diff = np.diff(potential)
    # 检查是否有方向变化
    sign_changes = np.sum(diff[:-1] * diff[1:] < 0)
    if sign_changes >= 1:
        return Technique.CV

    return Technique.LSV


def _parse_data_rows(
    raw_lines: List[str],
    header_row: int,
    delimiter: Optional[str],
) -> Tuple[List[str], np.ndarray]:
    """从原始文本行中提取表头和数值数据。

    Args:
        raw_lines: 文件所有文本行。
        header_row: 表头所在行索引。
        delimiter: 分隔符（None 表示空白符）。

    Returns:
        (表头列表, 数值数据数组)。
    """
    # 解析表头
    header_line = raw_lines[header_row]
    headers = _split_row(header_line, delimiter)

    # 解析数据行（表头之后的所有行）
    data_rows: List[List[float]] = []
    for line in raw_lines[header_row + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        parts = _split_row(stripped, delimiter)
        try:
            nums = [float(p) for p in parts]
            data_rows.append(nums)
        except (ValueError, TypeError):
            # 跳过无法转换为数值的行
            continue

    if not data_rows:
        raise ValueError("文件中未找到有效的数值数据行")

    data = np.array(data_rows, dtype=float)
    return headers, data


# ── 主解析函数 ────────────────────────────────────────────────────────────────


def parse_csv(
    filepath: str,
    encoding: Optional[str] = None,
    col_map: Optional[Dict[str, Union[str, int]]] = None,
) -> Measurement:
    """解析通用 CSV/TSV 电化学数据文件。

    支持的功能：
        - 自动检测分隔符（逗号、制表符、分号、空白符）
        - 自动识别列类型（电位、电流、时间、频率、Z'、Z"）
        - 手动列映射覆盖
        - 自动推断电化学测试技术类型
        - 支持 EIS 数据（频率、Z'、Z"）

    Args:
        filepath: 数据文件路径。
        encoding: 文件编码。为 None 时依次尝试 UTF-8、UTF-8-SIG、GBK、GB2312、
            Latin-1。
        col_map: 手动列映射字典。键为标准字段名（'potential', 'current',
            'time', 'frequency', 'z_real', 'z_imag' 等），值为列索引（int）
            或列标题名称（str）。手动映射会覆盖自动检测结果。

    Returns:
        包含解析数据的 Measurement 对象。

    Raises:
        FileNotFoundError: 文件不存在时抛出。
        ValueError: 无法解析文件格式或缺少必要数据列时抛出。

    示例:
        >>> # 自动检测
        >>> m = parse_csv("data.csv")

        >>> # 手动指定列
        >>> m = parse_csv("data.csv", col_map={
        ...     "potential": "E (V)",
        ...     "current": "I (mA)",
        ...     "time": 2,
        ... })

        >>> # EIS 数据
        >>> m = parse_csv("eis.csv", col_map={
        ...     "frequency": 0,
        ...     "z_real": 1,
        ...     "z_imag": 2,
        ... })
    """
    # ── 文件存在性检查 ──
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    # ── 计算文件哈希 ──
    file_hash = _compute_file_hash(filepath)

    # ── 读取文件 ──
    content, _ = _detect_encoding(filepath, encoding)
    raw_lines = content.splitlines()

    # ── 去除空行 ──
    non_empty_lines = [line for line in raw_lines if line.strip()]
    if not non_empty_lines:
        raise ValueError(f"文件为空: {filepath}")

    # ── 检测分隔符 ──
    delimiter = _detect_delimiter(non_empty_lines)

    # ── 定位表头行 ──
    header_row = _find_header_row(non_empty_lines)

    # ── 解析表头和数据行 ──
    headers, data = _parse_data_rows(non_empty_lines, header_row, delimiter)

    # ── 自动检测列映射 ──
    auto_map = _auto_map_columns(headers)

    # ── 构建手动列映射（索引化） ──
    manual_idx_map = _build_column_index_map(col_map, headers)

    # ── 合并映射 ──
    col_indices = _merge_column_mapping(auto_map, manual_idx_map, headers)

    # ── 提取列数据 ──
    def _get_col(field: str) -> Optional[np.ndarray]:
        idx = col_indices.get(field)
        if idx is not None and idx < data.shape[1]:
            return data[:, idx]
        return None

    potential = _get_col("potential")
    current = _get_col("current")
    time = _get_col("time")
    frequency = _get_col("frequency")
    z_real = _get_col("z_real")
    z_imag = _get_col("z_imag")

    # ── 推断技术类型 ──
    technique = _detect_technique_from_columns(col_indices)
    if technique == Technique.LSV and potential is not None and len(potential) >= 3:
        technique = _detect_technique_from_data(potential)

    # ── 组装 Measurement 对象 ──
    # 对于 EIS，使用频率作为电位、Z' 作为电流、Z" 作为时间
    if technique == Technique.EIS:
        # EIS 必须有频率和 Z'
        eis_potential = frequency if frequency is not None else potential
        eis_current = z_real if z_real is not None else current
        eis_time = z_imag

        if eis_potential is None or eis_current is None:
            raise ValueError(
                f"EIS 数据缺少必要列: 需要频率或 Z'（可用列: {headers}）"
            )

        # 将原始列信息存入元数据
        extra_metadata: Dict[str, Any] = {
            "_raw_columns": headers,
            "_column_mapping": {k: headers[v] if v < len(headers) else str(v)
                                for k, v in col_indices.items()},
        }
        if frequency is not None:
            extra_metadata["frequency"] = frequency.tolist()
        if z_real is not None:
            extra_metadata["z_real"] = z_real.tolist()
        if z_imag is not None:
            extra_metadata["z_imag"] = z_imag.tolist()

        return Measurement(
            technique=technique,
            potential=eis_potential,
            current=eis_current,
            time=eis_time,
            metadata=extra_metadata,
            file_hash=file_hash,
        )

    # ── 非 EIS 数据 ──
    if potential is None and current is not None and time is not None:
        # CA/CP 类测试：用时间作为 x 轴占位
        potential = time
        time = None  # 避免重复
    elif potential is None or current is None:
        raise ValueError(
            f"无法从文件中识别电位和电流列（可用列: {headers}）。"
            "请使用 col_map 参数手动指定列映射。"
        )

    # 构建元数据，包含列映射信息
    metadata: Dict[str, Any] = {
        "_raw_columns": headers,
        "_column_mapping": {k: headers[v] if v < len(headers) else str(v)
                            for k, v in col_indices.items()},
    }
    if frequency is not None:
        metadata["frequency"] = frequency.tolist()

    return Measurement(
        technique=technique,
        potential=potential,
        current=current,
        time=time,
        metadata=metadata,
        file_hash=file_hash,
    )


__all__ = ["parse_csv"]
