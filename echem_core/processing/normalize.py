"""电流归一化处理。"""

import numpy as np
from typing import Optional


def normalize_by_area(
    current: np.ndarray, area_cm2: float
) -> np.ndarray:
    """按电极几何面积归一化电流为电流密度 (mA/cm²)。

    Args:
        current: 原始电流数组 (A)。
        area_cm2: 电极几何面积 (cm²)。

    Returns:
        电流密度数组 (mA/cm²)。
    """
    if area_cm2 <= 0:
        raise ValueError(f"电极面积必须为正数，当前值: {area_cm2}")
    return current * 1000.0 / area_cm2


def normalize_by_loading(
    current: np.ndarray, loading_mg_cm2: float, area_cm2: float
) -> np.ndarray:
    """按催化剂负载量归一化电流 (mA/mg)。

    Args:
        current: 原始电流数组 (A)。
        loading_mg_cm2: 催化剂负载量 (mg/cm²)。
        area_cm2: 电极几何面积 (cm²)。

    Returns:
        质量活性数组 (mA/mg_cat)。
    """
    if loading_mg_cm2 <= 0:
        raise ValueError(f"负载量必须为正数，当前值: {loading_mg_cm2}")
    if area_cm2 <= 0:
        raise ValueError(f"电极面积必须为正数，当前值: {area_cm2}")
    return current * 1000.0 / (loading_mg_cm2 * area_cm2)


def normalize_by_ecsa(
    current: np.ndarray, ecsa_cm2: float
) -> np.ndarray:
    """按电化学活性面积（ECSA）归一化电流 (mA/cm²_ECSA)。

    Args:
        current: 原始电流数组 (A)。
        ecsa_cm2: 电化学活性面积 (cm²)。

    Returns:
        ECSA 归一化电流密度数组 (mA/cm²_ECSA)。
    """
    if ecsa_cm2 <= 0:
        raise ValueError(f"ECSA 必须为正数，当前值: {ecsa_cm2}")
    return current * 1000.0 / ecsa_cm2


def normalize_manual(
    current: np.ndarray, factor: float, label: str = ""
) -> np.ndarray:
    """使用自定义因子归一化电流。

    Args:
        current: 原始电流数组 (A)。
        factor: 归一化因子（如 BET 比表面积、金属含量等）。
        label: 归一化方式描述，仅用于 recipe 记录。

    Returns:
        归一化后的电流数组。
    """
    if factor <= 0:
        raise ValueError(f"归一化因子必须为正数，当前值: {factor}")
    return current / factor
