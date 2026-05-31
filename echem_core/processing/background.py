"""背景扣除处理。"""

import numpy as np
import re
from typing import Dict, List, Optional, Tuple


def subtract(sample_current: np.ndarray, blank_current: np.ndarray) -> np.ndarray:
    """从样品电流中扣除空白背景电流。

    要求样品和空白数组长度相同，否则会插值对齐。

    Args:
        sample_current: 样品电流/电流密度数组。
        blank_current: 空白背景电流/电流密度数组。

    Returns:
        背景扣除后的电流数组。
    """
    if len(sample_current) != len(blank_current):
        # 插值对齐到样品长度
        blank_interp = np.interp(
            np.linspace(0, 1, len(sample_current)),
            np.linspace(0, 1, len(blank_current)),
            blank_current,
        )
        return np.asarray(sample_current, dtype=float) - blank_interp
    return np.asarray(sample_current, dtype=float) - np.asarray(blank_current, dtype=float)


def auto_match(
    samples: List[Tuple[str, np.ndarray]],
    blanks: List[Tuple[str, np.ndarray]],
) -> List[Tuple[str, np.ndarray, Optional[str]]]:
    """自动按命名规则将样品与空白匹配并扣除。

    匹配规则：提取文件名中的转速（如 1600rpm, 2500rpm）和扫描速率，
    自动匹配相同条件下blank。如找不到匹配则返回原始数据。

    Args:
        samples: 样品列表 [(名称, 电流数组), ...]。
        blanks: 空白列表 [(名称, 电流数组), ...]。

    Returns:
        [(名称, 扣除后电流, 匹配的空白名称), ...]
    """

    def extract_key(name: str) -> Tuple[str, ...]:
        """提取命名中的转速和扫速等关键信息。"""
        keys = []
        rpm_match = re.search(r"(\d+)\s*rpm", name, re.IGNORECASE)
        if rpm_match:
            keys.append(f"rpm{rpm_match.group(1)}")
        sr_match = re.search(r"(\d+)\s*mv", name, re.IGNORECASE)
        if sr_match:
            keys.append(f"sr{sr_match.group(1)}")
        return tuple(keys)

    blank_keys = [(name, extract_key(name), arr) for name, arr in blanks]
    results = []

    for samp_name, samp_arr in samples:
        samp_key = extract_key(samp_name)
        matched_blank_name = None
        matched_blank_arr = None

        # 找完全匹配的 blank
        for blank_name, blank_key, blank_arr in blank_keys:
            if samp_key == blank_key or samp_name == blank_name:
                matched_blank_name = blank_name
                matched_blank_arr = blank_arr
                break

        # 没找到精确匹配就用第一个 blank
        if matched_blank_arr is None and blanks:
            matched_blank_name = blanks[0][0]
            matched_blank_arr = blanks[0][1]

        if matched_blank_arr is not None:
            subtracted = subtract(samp_arr, matched_blank_arr)
        else:
            subtracted = np.asarray(samp_arr, dtype=float)

        results.append((samp_name, subtracted, matched_blank_name))

    return results
