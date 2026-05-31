"""电化学数据处理：电位换算与单位转换。"""

import numpy as np
from typing import Optional


def to_rhe(
    potential: np.ndarray,
    reference: str = "RHE",
    pH: float = 0.0,
    temperature: float = 298.15,
) -> np.ndarray:
    """将测量的电位转换为相对于可逆氢电极（RHE）的电位。

    支持常见参比电极的换算公式（25°C）：
        - Ag/AgCl (饱和KCl):  E_RHE = E_meas + 0.197 + 0.059 × pH
        - SCE (饱和KCl):       E_RHE = E_meas + 0.241 + 0.059 × pH
        - Hg/HgO (1M KOH):    E_RHE = E_meas + 0.098 + 0.059 × pH
        - RHE:                 保持不变

    Args:
        potential: 测量电位数组 (V)。
        reference: 参比电极类型，支持 "Ag/AgCl", "SCE", "Hg/HgO", "RHE"。
        pH: 电解液的 pH 值（默认 0，适用于酸性条件）。
        temperature: 温度 (K)，默认 298.15 K（25°C）。温度修正系数为
                      0.05916 × (T / 298.15)。

    Returns:
        转换后的 RHE 电位数组 (V)。

    Raises:
        ValueError: 不支持的参比电极类型。
    """
    # 温度修正的能斯特系数
    nernst_factor = 0.05916 * (temperature / 298.15)

    reference_offsets = {
        "Ag/AgCl": 0.197,
        "SCE": 0.241,
        "Hg/HgO": 0.098,
        "RHE": 0.0,
    }

    ref_lower = reference.lower()
    offset = None
    for key, val in reference_offsets.items():
        if key.lower() == ref_lower:
            offset = val
            break

    if offset is None:
        raise ValueError(
            f"不支持的参比电极类型: {reference!r}。"
            f" 支持: {list(reference_offsets.keys())}"
        )

    return potential + offset + nernst_factor * pH


def current_density(current: np.ndarray, area_cm2: float) -> np.ndarray:
    """将电流转换为电流密度 (mA/cm²)。

    Args:
        current: 电流数组 (A)。
        area_cm2: 电极几何面积 (cm²)。

    Returns:
        电流密度数组 (mA/cm²)。
    """
    if area_cm2 <= 0:
        raise ValueError(f"电极面积必须为正数，当前值: {area_cm2}")
    return current * 1000.0 / area_cm2


def current_to_mass_activity(
    current: np.ndarray, loading_mg_cm2: float, area_cm2: float
) -> np.ndarray:
    """将电流转换为质量活性 (mA/mg)。

    Args:
        current: 电流数组 (A)。
        loading_mg_cm2: 催化剂负载量 (mg/cm²)。
        area_cm2: 电极几何面积 (cm²)。

    Returns:
        质量活性数组 (mA/mg)。
    """
    if loading_mg_cm2 <= 0:
        raise ValueError(f"负载量必须为正数，当前值: {loading_mg_cm2}")
    if area_cm2 <= 0:
        raise ValueError(f"电极面积必须为正数，当前值: {area_cm2}")
    return current * 1000.0 / (loading_mg_cm2 * area_cm2)


def unit_convert_current(current: np.ndarray, unit: str = "A") -> np.ndarray:
    """统一电流单位为安培 (A)。

    Args:
        current: 电流数组。
        unit: 原始单位，支持 "A", "mA", "uA", "µA", "nA"。

    Returns:
        转换为安培后的数组。
    """
    factors = {"a": 1.0, "ma": 1e-3, "ua": 1e-6, "µa": 1e-6, "na": 1e-9}
    unit_lower = unit.lower().replace("μ", "µ").replace(" ", "")
    factor = factors.get(unit_lower)
    if factor is None:
        raise ValueError(f"不支持的电流单位: {unit!r}，支持: A, mA, uA, µA, nA")
    return current * factor


def unit_convert_potential(potential: np.ndarray, unit: str = "V") -> np.ndarray:
    """统一电位单位为伏特 (V)。

    Args:
        potential: 电位数组。
        unit: 原始单位，支持 "V", "mV"。

    Returns:
        转换为伏特后的数组。
    """
    factors = {"v": 1.0, "mv": 1e-3}
    unit_lower = unit.lower().replace(" ", "")
    factor = factors.get(unit_lower)
    if factor is None:
        raise ValueError(f"不支持的电位单位: {unit!r}，支持: V, mV")
    return potential * factor


def kinetic_current(
    current: np.ndarray, limiting_current: float
) -> np.ndarray:
    """从总电流和极限电流计算动力学电流 j_k。

    公式: 1/j_k = 1/j - 1/j_L
    其中 j 是测量电流密度，j_L 是极限扩散电流密度。

    Args:
        current: 测量电流或电流密度数组。
        limiting_current: 极限扩散电流或电流密度（标量）。

    Returns:
        动力学电流数组。
    """
    return 1.0 / (1.0 / np.asarray(current, dtype=float) - 1.0 / float(limiting_current))
