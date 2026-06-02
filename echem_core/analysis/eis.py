"""基础 EIS 分析。"""

import numpy as np
from typing import Tuple


def nyquist_data(z_real: np.ndarray, z_imag: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """返回 Nyquist 图数据（实部, 负虚部）。

    根据惯例，EIS Nyquist 图纵轴为 -Z_imag。

    Args:
        z_real: 阻抗实部数组 (Ohm)。
        z_imag: 阻抗虚部数组 (Ohm)。

    Returns:
        (z_real, neg_z_imag) 用于作图。
    """
    return np.asarray(z_real, dtype=float), -np.asarray(z_imag, dtype=float)


def impedance_axis_limits(values: np.ndarray, margin: float = 0.08) -> Tuple[float, float]:
    """Return data-adaptive axis limits for impedance plots."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0, 1.0

    vmin = float(np.min(arr))
    vmax = float(np.max(arr))
    span = vmax - vmin
    if not np.isfinite(span) or span <= 0:
        center = (vmin + vmax) / 2.0
        pad = max(abs(center) * margin, 1e-9)
        return center - pad, center + pad

    pad = span * margin
    return vmin - pad, vmax + pad


def nyquist_axis_limits(
    z_real: np.ndarray,
    z_imag: np.ndarray,
    margin: float = 0.08,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Return x/y axis limits for a Nyquist plot."""
    zr, neg_zi = nyquist_data(z_real, z_imag)
    return impedance_axis_limits(zr, margin), impedance_axis_limits(neg_zi, margin)


def bode_data(
    frequency: np.ndarray, z_real: np.ndarray, z_imag: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 Bode 图数据（频率, 阻抗模值, 相位角）。

    Args:
        frequency: 频率数组 (Hz)。
        z_real: 阻抗实部数组 (Ohm)。
        z_imag: 阻抗虚部数组 (Ohm)。

    Returns:
        (frequency, |Z|, phase_angle_deg) 用于 Bode 图。
    """
    f = np.asarray(frequency, dtype=float)
    z_mod = np.sqrt(np.asarray(z_real, dtype=float) ** 2 + np.asarray(z_imag, dtype=float) ** 2)
    phase = np.degrees(np.arctan2(np.asarray(z_imag, dtype=float), np.asarray(z_real, dtype=float)))
    return f, z_mod, phase


def estimate_rs(z_real: np.ndarray, frequency: np.ndarray = None) -> float:
    """从高频端估计溶液电阻 Rs。

    默认取实部数组的前 5% 的均值；如有频率数据则取最高 5 个频率点的实部均值。

    Args:
        z_real: 阻抗实部数组 (Ohm)。
        frequency: 频率数组 (Hz)，可选。

    Returns:
        Rs 估计值 (Ohm)。
    """
    zr = np.asarray(z_real, dtype=float)
    if frequency is not None:
        freq = np.asarray(frequency, dtype=float)
        high_freq_idx = np.argsort(freq)[-5:]  # 最高频 5 个点
        return float(np.mean(zr[high_freq_idx]))
    else:
        n = max(1, len(zr) // 20)  # 前 5%
        return float(np.mean(zr[:n]))


def estimate_rct(z_real: np.ndarray, z_imag: np.ndarray, rs: float = None) -> float:
    """从低频端估计电荷转移电阻 Rct。

    Rct ≈ Z_real(低频) - Rs。

    Args:
        z_real: 阻抗实部数组 (Ohm)。
        z_imag: 阻抗虚部数组 (Ohm)。
        rs: 溶液电阻 (Ohm)。为 None 时自动估计。

    Returns:
        Rct 估计值 (Ohm)。
    """
    zr = np.asarray(z_real, dtype=float)
    if rs is None:
        rs = estimate_rs(zr)

    # 取低频端（后 10% 点）的实部均值
    n = max(1, len(zr) // 10)
    low_freq_z = float(np.mean(zr[-n:]))
    return low_freq_z - rs
