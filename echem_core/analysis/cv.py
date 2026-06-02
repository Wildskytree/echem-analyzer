"""CV（循环伏安法）分析函数。

提供 CV 数据的峰检测、双电层电容（Cdl）计算和电化学活性面积（ECSA）计算。
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import signal, stats

from echem_core.model.measurement import Measurement


CDL_IRREGULAR_SCAN_MESSAGE = (
    "CV data appears to have irregular scan pattern. Please ensure the data has "
    "at least one complete forward+backward sweep."
)


def find_peaks(
    potential: np.ndarray,
    current: np.ndarray,
    direction: str = "both",
) -> List[Dict[str, float | str]]:
    """在 CV 数据中检测氧化峰和还原峰。

    使用 :func:`scipy.signal.find_peaks` 配合 ``prominence`` 参数实现峰检测。
    先将 CV 拆分为正向扫描和反向扫描两段：正向扫描（电位升高）中检测正电流峰为氧化峰，
    反向扫描（电位降低）中对电流取反后检测峰为还原峰。

    Args:
        potential: 电位数组（V）。
        current: 电流数组（A）。
        direction: 峰检测方向。可选值：
            - ``"both"``: 同时检测氧化峰和还原峰（默认）；
            - ``"oxidative"``: 仅检测氧化峰；
            - ``"reductive"``: 仅检测还原峰。

    Returns:
        峰列表，每个元素为包含以下字段的字典：

        - ``peak_potential``: 峰电位（V）
        - ``peak_current``: 峰电流（A）
        - ``peak_type``: 峰类型，``"oxidative"`` 或 ``"reductive"``

    Raises:
        ValueError: 当 ``direction`` 不是有效选项时抛出。

    Note:
        如果没有检测到任何峰，返回空列表。峰检测的灵敏度受数据噪声影响，
        建议先对数据进行平滑处理后再调用此函数。
    """
    if direction not in ("both", "oxidative", "reductive"):
        raise ValueError(
            f"direction 必须是 'both', 'oxidative' 或 'reductive'，收到 '{direction}'"
        )

    potential = np.asarray(potential, dtype=float)
    current = np.asarray(current, dtype=float)

    if potential.ndim != 1 or current.ndim != 1:
        raise ValueError("potential 和 current 必须是一维数组")
    if potential.size != current.size:
        raise ValueError("potential 和 current 长度必须一致")
    if potential.size < 5:
        return []

    # ------------------------------------------------------------------
    # 1. 识别电位方向转折点，拆分正向段和反向段
    # ------------------------------------------------------------------
    diff = np.diff(potential)
    # 忽略非常小的噪声变化
    diff[~np.isnan(diff)] = np.where(
        np.abs(diff[~np.isnan(diff)]) < 1e-12, 0, diff[~np.isnan(diff)]
    )

    # 电位单调变化段的符号
    signs = np.sign(diff)
    # 符号发生变化的位置
    sign_changes = np.where(np.diff(signs, prepend=signs[0]) != 0)[0]

    # 如果没有转折点（LSV），整体作为正向扫描处理
    if len(sign_changes) == 0:
        segments: List[Tuple[str, np.ndarray, np.ndarray]] = [
            ("oxidative", potential, current),
        ]
    else:
        # 相邻转折点之间的区间即为一个扫描段
        breakpoints = np.concatenate([[0], sign_changes, [len(potential) - 1]])
        segments = []
        for i in range(len(breakpoints) - 1):
            start = int(breakpoints[i])
            end = int(breakpoints[i + 1]) + 1
            if end - start < 3:
                continue
            seg_pot = potential[start:end]
            seg_cur = current[start:end]
            # 根据电位变化方向标记段类型
            if seg_pot[-1] > seg_pot[0]:
                seg_type = "oxidative"
            elif seg_pot[-1] < seg_pot[0]:
                seg_type = "reductive"
            else:
                continue  # 电位无变化，跳过
            segments.append((seg_type, seg_pot, seg_cur))

    # ------------------------------------------------------------------
    # 2. 在每个扫描段中检测对应类型的峰
    # ------------------------------------------------------------------
    peaks: List[Dict[str, float | str]] = []
    prominence = 0.05 * (np.max(current) - np.min(current))

    for seg_type, seg_pot, seg_cur in segments:
        if direction == "oxidative" and seg_type == "reductive":
            continue
        if direction == "reductive" and seg_type == "oxidative":
            continue

        if seg_type == "oxidative":
            # 氧化峰：正向扫描检测正电流峰
            search_signal = seg_cur
            # 限制检测正电流
            peak_indices, properties = signal.find_peaks(
                search_signal,
                prominence=prominence,
                height=0,
            )
        else:
            # 还原峰：反向扫描检测负电流峰（取反后检测）
            search_signal = -seg_cur
            peak_indices, properties = signal.find_peaks(
                search_signal,
                prominence=prominence,
                height=0,
            )

        for idx in peak_indices:
            peaks.append({
                "peak_potential": float(seg_pot[idx]),
                "peak_current": float(seg_cur[idx]),
                "peak_type": seg_type,
            })

    # 按电位排序
    peaks.sort(key=lambda p: p["peak_potential"])
    return peaks


def _split_cv(
    potential: np.ndarray,
    current: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """将 CV 数据拆分为正向扫描和反向扫描。

    通过检测电位数组的一阶差分符号确定转折点。对于完整循环的 CV，
    返回 (forward_potential, forward_current, backward_potential, backward_current)；
    如果无法识别转折，向前后段各返回空数组。

    Args:
        potential: 电位数组（V）。
        current: 电流数组（A）。

    Returns:
        (forward_potential, forward_current, backward_potential, backward_current)
        四元组，各元素为一维 ndarray。
    """
    empty = np.array([], dtype=float)
    potential = np.asarray(potential, dtype=float)
    current = np.asarray(current, dtype=float)
    if potential.ndim != 1 or current.ndim != 1 or potential.size != current.size:
        return empty, empty, empty, empty

    finite = np.isfinite(potential) & np.isfinite(current)
    potential = potential[finite]
    current = current[finite]
    if potential.size < 2:
        return empty, empty, empty, empty

    diff = np.diff(potential)
    signs = np.zeros_like(diff, dtype=int)
    signs[diff > 1e-12] = 1
    signs[diff < -1e-12] = -1

    nonzero_diff_idx = np.flatnonzero(signs)
    if nonzero_diff_idx.size < 2:
        return empty, empty, empty, empty

    runs = []
    run_start = int(nonzero_diff_idx[0])
    prev_idx = int(nonzero_diff_idx[0])
    prev_sign = int(signs[prev_idx])
    for diff_idx_raw in nonzero_diff_idx[1:]:
        diff_idx = int(diff_idx_raw)
        sign = int(signs[diff_idx])
        if sign != prev_sign:
            runs.append((prev_sign, run_start, prev_idx))
            run_start = diff_idx
            prev_sign = sign
        prev_idx = diff_idx
    runs.append((prev_sign, run_start, prev_idx))

    if len(runs) < 2:
        return empty, empty, empty, empty

    def segment_from_run(run):
        _direction, start_diff, end_diff = run
        return (
            potential[start_diff : end_diff + 2].copy(),
            current[start_diff : end_diff + 2].copy(),
        )

    def clean_segment(seg_pot, seg_cur):
        if seg_pot.size == 0:
            return empty, empty
        if seg_pot[-1] < seg_pot[0]:
            seg_pot = seg_pot[::-1]
            seg_cur = seg_cur[::-1]
        unique_pot, inverse, counts = np.unique(
            seg_pot,
            return_inverse=True,
            return_counts=True,
        )
        if unique_pot.size != seg_pot.size:
            cur_sum = np.zeros(unique_pot.size, dtype=float)
            np.add.at(cur_sum, inverse, seg_cur)
            seg_pot = unique_pot
            seg_cur = cur_sum / counts
        return seg_pot, seg_cur

    fwd_pot, fwd_cur = clean_segment(*segment_from_run(runs[0]))
    rev_pot, rev_cur = clean_segment(*segment_from_run(runs[1]))
    return fwd_pot, fwd_cur, rev_pot, rev_cur


def _coerce_scan_rate(value) -> Optional[float]:
    if value is None:
        return None
    try:
        scan_rate = float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?", text)
        if not match:
            return None
        scan_rate = float(match.group(0))
        lower = text.lower()
        if "mv/s" in lower or "mv s" in lower:
            scan_rate /= 1000.0
    if not np.isfinite(scan_rate) or scan_rate <= 0:
        return None
    return float(scan_rate)


def detect_scan_rate(measurement: Measurement) -> Optional[float]:
    """Return scan rate in V/s from metadata or the potential-time trace."""
    scan_rate = _coerce_scan_rate(measurement.metadata.get("scan_rate"))
    if scan_rate is not None:
        return scan_rate

    time = measurement.raw_time
    if time is None:
        return None

    potential = (
        measurement.processed_potential
        if measurement.processed_potential is not None
        else measurement.raw_potential
    )
    potential = np.asarray(potential, dtype=float)
    time = np.asarray(time, dtype=float)
    n = min(potential.size, time.size)
    if n < 3:
        return None

    d_potential = np.diff(potential[:n])
    d_time = np.diff(time[:n])
    mask = (
        np.isfinite(d_potential)
        & np.isfinite(d_time)
        & (np.abs(d_time) > 1e-12)
        & (np.abs(d_potential) > 1e-12)
    )
    if np.count_nonzero(mask) == 0:
        return None

    rates = np.abs(d_potential[mask] / d_time[mask])
    rates = rates[np.isfinite(rates) & (rates > 0)]
    if rates.size == 0:
        return None
    return float(np.median(rates))


def calc_cdl(
    measurements: List[Measurement],
) -> Tuple[float, float, List[float], List[float]]:
    """通过不同扫描速率的 CV 数据计算双电层电容（Cdl）。

    对每个测量对象：
    1. 将 CV 拆分为正向和反向扫描。
    2. 在电位中点附近的双电层区（非法拉第区），计算正向与反向电流之差的一半
       （Δj/2）。
    3. 以 Δj/2 为纵坐标、扫描速率为横坐标进行线性拟合，斜率为 Cdl。

    Args:
        measurements: 带有不同扫描速率的 :class:`Measurement` 对象列表。
            每个对象的 ``metadata["scan_rate"]`` 必须为有效数值（V/s）。

    Returns:
        (cdl, r_squared, df_dv_values, scan_rates) 四元组：

        - ``cdl``: 双电层电容（F）。
        - ``r_squared``: 线性拟合的决定系数。
        - ``df_dv_values``: 各测量对应的 Δj/2 值列表。
        - ``scan_rates``: 各测量对应的扫描速率列表（V/s）。

    Raises:
        ValueError: 测量对象少于 2 个、扫描速率无效或无法计算 Δj/2 时抛出。

    Note:
        为了避免法拉第电流干扰，该方法仅在电位范围的中点附近（±10 % 范围内）
        采样电流差值。如果已知特定的非法拉第电位区间，建议先截取后再调用。
    """
    if len(measurements) < 2:
        raise ValueError("至少需要 2 个不同扫描速率的测量数据")

    scan_data = []

    for m in measurements:
        sr = detect_scan_rate(m)
        if sr is None:
            raise ValueError(
                f"测量数据 {m!r} 的 scan_rate 无效（{m.metadata.get('scan_rate')}）"
            )
        scan_data.append((sr, m))

    scan_data.sort(key=lambda item: item[0])

    df_dv_values: List[float] = []
    scan_rates: List[float] = []

    for sr, m in scan_data:
        # 使用处理后的数据，若无则使用原始数据
        potential = (
            m.processed_potential
            if m.processed_potential is not None
            else m.raw_potential
        )
        current = (
            m.processed_current
            if m.processed_current is not None
            else m.raw_current
        )

        # 拆分正向/反向扫描
        fwd_pot, fwd_cur, rev_pot, rev_cur = _split_cv(potential, current)
        if fwd_pot.size < 5 or rev_pot.size < 5:
            raise ValueError(CDL_IRREGULAR_SCAN_MESSAGE)

        # 确定电位范围的中点，在其 ±10 % 范围内采样
        pot_min = max(float(np.min(fwd_pot)), float(np.min(rev_pot)))
        pot_max = min(float(np.max(fwd_pot)), float(np.max(rev_pot)))
        pot_mid = (pot_min + pot_max) / 2.0
        pot_half_range = (pot_max - pot_min) * 0.1

        # 在非法拉第区窗口内插值获得正向和反向电流
        window_mask_fwd = np.abs(fwd_pot - pot_mid) <= pot_half_range
        window_mask_rev = np.abs(rev_pot - pot_mid) <= pot_half_range

        if np.sum(window_mask_fwd) < 2 or np.sum(window_mask_rev) < 2:
            # 尝试扩大窗口
            pot_half_range = (pot_max - pot_min) * 0.2
            window_mask_fwd = np.abs(fwd_pot - pot_mid) <= pot_half_range
            window_mask_rev = np.abs(rev_pot - pot_mid) <= pot_half_range
            if np.sum(window_mask_fwd) < 2 or np.sum(window_mask_rev) < 2:
                raise ValueError(
                    f"测量数据 {m!r} 在非法拉第区没有足够的采样点"
                )

        # 插值到共同电位网格
        common_pot = np.linspace(
            np.max([np.min(fwd_pot[window_mask_fwd]), np.min(rev_pot[window_mask_rev])]),
            np.min([np.max(fwd_pot[window_mask_fwd]), np.max(rev_pot[window_mask_rev])]),
            num=50,
        )
        interp_fwd = np.interp(common_pot, fwd_pot, fwd_cur)
        interp_rev = np.interp(common_pot, rev_pot, rev_cur)

        # Δj/2：正向与反向电流差的一半（取绝对值后平均）
        delta_j_half = np.mean(np.abs(interp_fwd - interp_rev)) / 2.0

        df_dv_values.append(delta_j_half)
        scan_rates.append(float(sr))

    # 线性拟合：Δj/2 [A] vs 扫描速率 [V/s]，斜率为 Cdl [F]
    x = np.array(scan_rates, dtype=float)
    y = np.array(df_dv_values, dtype=float)
    if np.unique(np.round(x, decimals=12)).size < 2:
        raise ValueError("至少需要 2 个不同扫描速率的测量数据")

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    r_squared = float(r_value**2)

    return float(slope), r_squared, df_dv_values, scan_rates


def calc_ecsa(
    cdl: float,
    specific_capacitance: float = 0.04,
) -> float:
    """根据双电层电容计算电化学活性面积（ECSA）。

    ECSA（电化学活性面积，cm²）与 Cdl（双电层电容，F）的关系：

    .. math::

        \\text{ECSA} = \\frac{C_{\\text{dl}}}{C_{\\text{s}}}

    其中 :math:`C_{\\text{s}}` 为单位面积的比电容（mF/cm²）。

    Args:
        cdl: 双电层电容值（F），通常由 :func:`calc_cdl` 计算获得。
        specific_capacitance: 单位面积的比电容（mF/cm²）。
            默认值 0.04 mF/cm² 适用于碱性环境中常见金属表面。
            常见参考值：

            - 多晶铂在 H₂SO₄ 中: 0.02 mF/cm²
            - 多晶金在 H₂SO₄ 中: 0.03 mF/cm²
            - 金属氧化物表面在碱性中: 0.04–0.06 mF/cm²

    Returns:
        电化学活性面积（cm²）。

    Raises:
        ValueError: 当 ``cdl`` 或 ``specific_capacitance`` 为非正数时抛出。
    """
    if cdl <= 0:
        raise ValueError(f"cdl 必须为正数，收到 {cdl}")
    if specific_capacitance <= 0:
        raise ValueError(
            f"specific_capacitance 必须为正数，收到 {specific_capacitance}"
        )

    # 将比电容从 mF/cm² 转换为 F/cm²
    cs_f_per_cm2 = specific_capacitance * 1e-3
    ecsa = cdl / cs_f_per_cm2
    return float(ecsa)


__all__ = ["find_peaks", "calc_cdl", "calc_ecsa"]
