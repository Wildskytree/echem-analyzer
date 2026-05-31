"""
LSV（线性扫描伏安法）和 ORR（氧还原反应）分析函数。

提供半波电位、起始电位、Tafel 斜率、动力学电流及 Koutecký-Levich 分析。
依赖 numpy 和 scipy.stats 进行数值拟合与统计。
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from scipy import stats


# ────────────────────────────────────────────────────────────────
# 辅助函数
# ────────────────────────────────────────────────────────────────


def kinetic_current(
    current: np.ndarray,
    limiting_current: float,
) -> np.ndarray:
    """
    计算动力学电流（传质校正电流）。

    .. math:: j_k = \\frac{j_L \\cdot j}{j_L - j}

    Args:
        current:         实测电流密度 [mA/cm²]（通常为负值，表示还原电流）
        limiting_current: 极限扩散电流密度 [mA/cm²]

    Returns:
        动力学电流密度数组 [mA/cm²]

    Raises:
        ValueError: 当存在任何 |current| ≥ |limiting_current| 的数据点时抛出，
                    此时动力学电流发散，物理上无意义。
    """
    if np.any(np.abs(current) >= np.abs(limiting_current) - 1e-15):
        raise ValueError(
            "动力学电流发散：实测电流绝对值必须严格小于极限电流绝对值。"
        )
    return (limiting_current * current) / (limiting_current - current)


# ────────────────────────────────────────────────────────────────
# 半波电位
# ────────────────────────────────────────────────────────────────


def find_e_half(
    potential: np.ndarray,
    current: np.ndarray,
) -> Tuple[float, float, str]:
    """
    寻找半波电位 E₁/₂。

    步骤:
        1. 取原始数据的最后 30% 作为扩散平台区（对应扫至最负电位时的数据），
           计算平均极限电流 *j_L*
        2. 对平台区作线性回归，以 R² 评估平台质量
        3. 在当前 - 电位空间中插值，找到 **j = j_L / 2** 对应的电位

    Args:
        potential:  电位数组 [V]
        current:    电流密度数组 [mA/cm²]

    Returns:
        ``(e_half, j_L, confidence)`` 元组:
            - **e_half** — 半波电位 [V]（通过线性插值得到）
            - **j_L** — 极限扩散电流密度 [mA/cm²]（平台区均值）
            - **confidence** — 置信度标签：
                ``'high'``（R² > 0.95）、``'medium'``（R² > 0.80）、``'low'``

    Raises:
        ValueError: 数据点少于 10 个。
    """
    n = len(potential)
    if n < 10:
        raise ValueError("数据点太少（%d），至少需要 10 个点进行半波电位分析。" % n)

    # 1. 自动检测扩散平台区的位置
    #    比较前 30% 和后 30% 的平均 |current|，较大的为平台
    n_third = int(0.3 * n)
    mean_front = float(np.mean(np.abs(current[:n_third])))
    mean_back = float(np.mean(np.abs(current[-n_third:])))

    if mean_front >= mean_back:
        # 平台在数据开头（如反向扫描：0.0 → 1.2 V）
        pot_plt = potential[:n_third]
        cur_plt = current[:n_third]
    else:
        # 平台在数据末尾（如正向扫描：1.2 → 0.0 V）
        pot_plt = potential[-n_third:]
        cur_plt = current[-n_third:]

    # 2. 极限电流
    j_L = float(np.mean(cur_plt))

    # 3. 平台区线性回归 R²
    res = stats.linregress(pot_plt, cur_plt)
    r_squared = float(res.rvalue ** 2)

    # 4. 置信度
    if r_squared > 0.95:
        confidence = "high"
    elif r_squared > 0.80:
        confidence = "medium"
    else:
        confidence = "low"

    # 5. 半波电位 —— 按电流升序插值
    #    电流从 ~0 到 j_L（负值），j_L/2 介于二者之间
    sort_by_cur = np.argsort(current)          # 升序（最负 → 最正）
    pot_by_cur = potential[sort_by_cur]
    cur_asc = current[sort_by_cur]
    e_half = float(np.interp(j_L / 2.0, cur_asc, pot_by_cur))

    return e_half, j_L, confidence


# ────────────────────────────────────────────────────────────────
# 起始电位
# ────────────────────────────────────────────────────────────────


def find_e_onset(
    potential: np.ndarray,
    current: np.ndarray,
    method: str = "tangent",
) -> float:
    """
    寻找起始电位 E_onset。

    切线法步骤:
        1. 按电位升序排列数据
        2. 计算 dI/dE 数值导数，定位最陡上升点（导数最负处）
        3. 以最陡点为中心取窗口作线性拟合，得到切线方程
        4. 取前 10% 数据点的平均电流作为基线
        5. 外推切线与基线相交，交点电位即为 E_onset

    Args:
        potential:  电位数组 [V]
        current:    电流密度数组 [mA/cm²]
        method:     计算方法，目前仅支持 ``'tangent'``

    Returns:
        起始电位 [V]

    Raises:
        ValueError: 不支持的 method；数据点少于 10 个。
    """
    if method != "tangent":
        raise ValueError(
            f"不支持的方法: '{method}'，目前仅支持 'tangent'。"
        )

    n = len(potential)
    if n < 10:
        raise ValueError("数据点太少（%d），至少需要 10 个点进行起始电位分析。" % n)

    # 按电位升序排列
    sort_idx = np.argsort(potential)
    pot_sorted = potential[sort_idx]
    cur_sorted = current[sort_idx]

    # 1. 数值导数
    dI_dE = np.gradient(cur_sorted, pot_sorted)

    # 2. 最陡上升点（导数最大值处对应于电流急剧增大的拐点）
    steepest_idx = int(np.argmax(dI_dE))

    # 3. 窗口线性拟合
    half_win = max(5, n // 20)
    left = max(0, steepest_idx - half_win)
    right = min(n, steepest_idx + half_win + 1)

    res = stats.linregress(
        pot_sorted[left:right], cur_sorted[left:right]
    )

    # 4. 基线电流（前 10% 的均值）
    baseline_current = float(np.mean(cur_sorted[: max(1, n // 10)]))

    # 5. 外推切线至基线：y = m·x + b  →  x = (y - b) / m
    if abs(res.slope) < 1e-15:
        raise ValueError("切线斜率为零，无法外推求起始电位。")
    e_onset = float((baseline_current - res.intercept) / res.slope)

    return e_onset


def tafel_slope(
    potential: np.ndarray, current: np.ndarray, j_L: float
) -> tuple:
    """计算 Tafel 斜率 (mV/dec)。

    Tafel 方程: E = a + b · log₁₀|jₖ|，其中 b 为 Tafel 斜率。
    本函数的核心拟合逻辑为 log₁₀|jₖ| = α·E + β，再换算为
    b = 1/α，并转换为 mV/dec 输出。

    步骤：
        1. 剔除 >0.99·|j_L| 的点（动力学电流会发散）
        2. 计算动力学电流 jₖ = j·j_L/(j_L−j)
        3. 取 |jₖ| > 1e-15 的有效点，log₁₀|jₖ| vs E
        4. 在电位排序后的中间 40% 区域滑动扫描，找 R²>0.98 的最优线性区
        5. 未找到时回退使用整个中间 40% 区域

    Args:
        potential: 电位数组 (V vs RHE)。
        current: 电流或电流密度数组（与 j_L 单位一致）。
        j_L: 极限扩散电流（与 current 单位一致）。

    Returns:
        (slope_mV_dec, intercept, r_squared, region_start, region_end):
            slope_mV_dec: Tafel 斜率 (mV/dec)，带符号。
                          还原反应为负值，绝对值即为 Tafel 斜率。
            intercept: 拟合截距。
            r_squared: 拟合 R²。
            region_start: 线性区在原始数组中的起始索引。
            region_end: 线性区在原始数组中的结束索引。

    Raises:
        ValueError: 数据点太少、有效点不足或全部发散时抛出。
    """
    import numpy as np
    from scipy import stats as scipy_stats

    potential = np.asarray(potential, dtype=float)
    current = np.asarray(current, dtype=float)
    n = len(potential)
    if n < 20:
        raise ValueError("数据点太少（%d），至少需要 20 个点进行 Tafel 分析。" % n)

    # 1. 剔除过于接近极限电流的数据点（动力学电流会发散）
    safe = np.abs(current) < 0.99 * np.abs(j_L)
    if not np.any(safe):
        raise ValueError("所有数据点的电流值均过于接近极限电流，无法进行 Tafel 分析。")

    pot_safe = potential[safe]
    cur_safe = current[safe]

    # 2. 计算动力学电流
    j_k = kinetic_current(cur_safe, j_L)
    abs_j_k = np.abs(j_k)

    # 排除动力学电流为零的无效点
    valid = abs_j_k > 1e-15
    if not np.any(valid):
        raise ValueError("所有数据点的动力学电流均无效，无法进行 Tafel 分析。")

    pot_valid = pot_safe[valid]
    j_k_valid = j_k[valid]
    abs_j_k_valid = abs_j_k[valid]
    log_j_k = np.log10(abs_j_k_valid)

    n_valid = len(pot_valid)
    if n_valid < 20:
        raise ValueError(
            "有效数据点太少（%d），至少需要 20 个有效的动力学电流值。" % n_valid
        )

    # 3. 按电位排序
    sort_idx = np.argsort(pot_valid)
    pot_sorted = pot_valid[sort_idx]
    log_sorted = log_j_k[sort_idx]

    # 有效点的原始索引映射
    valid_mask = np.zeros(len(potential), dtype=bool)
    valid_mask[np.where(safe)[0][valid]] = True
    valid_orig_indices = np.where(valid_mask)[0]

    # 4. 在中间 40% 区域内扫描
    mid_start = int(0.3 * n_valid)
    mid_end = int(0.7 * n_valid)
    min_win = max(5, n_valid // 20)

    best_r2 = -1.0
    best_slope_dec_v = 0.0  # log10|j_k| 对 E 的斜率 (dec/V)
    best_intercept = 0.0
    best_start = 0
    best_end = 0

    for i in range(mid_start, mid_end - min_win + 1):
        for j in range(i + min_win, mid_end + 1):
            x_seg = pot_sorted[i:j]
            y_seg = log_sorted[i:j]
            if len(x_seg) < min_win:
                continue
            res = scipy_stats.linregress(x_seg, y_seg)
            r2 = float(res.rvalue ** 2)
            if r2 > 0.98 and r2 > best_r2:
                best_r2 = r2
                best_slope_dec_v = float(res.slope)
                best_intercept = float(res.intercept)
                best_start = int(valid_orig_indices[sort_idx[i]])
                best_end = int(valid_orig_indices[sort_idx[j - 1]])
                if best_start > best_end:
                    best_start, best_end = best_end, best_start

    # 5. 回退：未找到满足条件的线性区时，使用整个中间 40% 区域
    if best_r2 < 0:
        x_fb = pot_sorted[mid_start:mid_end]
        y_fb = log_sorted[mid_start:mid_end]
        res = scipy_stats.linregress(x_fb, y_fb)
        best_slope_dec_v = float(res.slope)
        best_intercept = float(res.intercept)
        best_r2 = float(res.rvalue ** 2)
        best_start = int(valid_orig_indices[sort_idx[mid_start]])
        best_end = int(valid_orig_indices[sort_idx[mid_end - 1]])

    # 换算为 Tafel 斜率 b = dE/d(log|j|) = 1 / (d(log|j|)/dE)
    # 单位: V/dec → mV/dec
    if abs(best_slope_dec_v) < 1e-12:
        slope_mv_dec = 0.0
    else:
        slope_mv_dec = 1000.0 / best_slope_dec_v

    return slope_mv_dec, best_intercept, best_r2, best_start, best_end


# ────────────────────────────────────────────────────────────────
# Koutecký–Levich 分析
# ────────────────────────────────────────────────────────────────


def kl_plot(
    measurements_by_rpm: Dict[float, Tuple[np.ndarray, np.ndarray]],
    n_electrons_param: float | None = None,
    F: float = 96485.0,
    C_O2: float = 1.2e-6,
    D_O2: float = 1.9e-5,
    nu: float = 0.01,
) -> Tuple[float, float]:
    """
    Koutecký–Levich（K-L）分析。

    将不同转速下的 LSV 曲线插值到公共电位网格，在半波电位附近
    作 1/j vs 1/√ω 线性回归，从斜率计算电子转移数 *n*，从截距
    得到 1/j_k。

    K-L 方程:

    .. math::
        \\frac{1}{j} = \\frac{1}{j_k} +
        \\frac{1}{0.62 \\, n \\, F \\, C \\, D^{2/3} \\, \\nu^{-1/6} \\, \\sqrt{\\omega}}

    Args:
        measurements_by_rpm:  字典 {转速 (RPM): (potential, current)}。
                              至少需要 3 组不同转速的数据。
        n_electrons_param:    已知电子转移数（可选）。若提供，则直接使用该值
                              而不再从斜率计算。
        F:                    法拉第常数 [C/mol]，默认 96485.0。
        C_O2:                 O₂ 溶解度 [mol/cm³]，默认 1.2×10⁻⁶（0.1 M KOH）。
        D_O2:                 O₂ 扩散系数 [cm²/s]，默认 1.9×10⁻⁵。
        nu:                   溶液运动粘度 [cm²/s]，默认 0.01。

    Returns:
        ``(n, intercept)`` 元组:
            - **n** — 电子转移数（计算值或用户指定的已知值）
            - **intercept** — K-L 直线截距，对应 1/j_k [cm²/mA]
    """
    if len(measurements_by_rpm) < 3:
        raise ValueError(
            "至少需要 3 个不同转速的数据点进行 K-L 分析（当前: %d）。"
            % len(measurements_by_rpm)
        )

    # 1. 确定公共电位范围
    pot_low = None
    pot_high = None
    for pot, _ in measurements_by_rpm.values():
        lo, hi = float(np.min(pot)), float(np.max(pot))
        if pot_low is None or lo > pot_low:
            pot_low = lo
        if pot_high is None or hi < pot_high:
            pot_high = hi

    if pot_low is None or pot_high is None or pot_high - pot_low < 1e-6:
        raise ValueError("不同转速数据的电位范围无有效交集。")

    n_grid = 500
    common_pot = np.linspace(pot_low, pot_high, n_grid)

    # 2. 插值所有曲线到公共网格
    interp_curves: Dict[float, np.ndarray] = {}
    for rpm, (pot, cur) in measurements_by_rpm.items():
        sort_idx = np.argsort(pot)
        interp_curves[rpm] = np.interp(
            common_pot, pot[sort_idx], cur[sort_idx]
        )

    # 3. 以最慢转速的半波电位作为 K-L 分析电位
    slowest_rpm = min(measurements_by_rpm.keys())
    slow_pot, slow_cur = measurements_by_rpm[slowest_rpm]
    e_half, _, _ = find_e_half(slow_pot, slow_cur)
    e_half_idx = int(np.argmin(np.abs(common_pot - e_half)))
    e_kl = common_pot[e_half_idx]

    # 4. 构建 K-L 数据点: 1/j vs 1/√ω
    inv_sqrt_omega = []
    inv_j = []

    for rpm, cur_interp in interp_curves.items():
        omega = 2.0 * np.pi * rpm / 60.0  # RPM → rad/s
        j_at_e = cur_interp[e_half_idx]

        inv_sqrt_omega.append(1.0 / np.sqrt(omega))
        inv_j.append(1.0 / abs(j_at_e))

    x = np.array(inv_sqrt_omega)
    y = np.array(inv_j)

    # 5. 线性回归
    res = stats.linregress(x, y)
    slope = float(res.slope)
    intercept = float(res.intercept)

    # 6. 电子转移数
    if n_electrons_param is not None:
        n = float(n_electrons_param)
    else:
        # B = 0.62 · n · F · C · D^{2/3} · ν^{-1/6}
        B_factor = 0.62 * F * C_O2 * (D_O2 ** (2.0 / 3.0)) * (nu ** (-1.0 / 6.0))
        if abs(slope) < 1e-30:
            raise ValueError("K-L 斜率为零，无法计算电子转移数。")
        n = abs(1.0 / (slope * B_factor))

    return n, intercept
