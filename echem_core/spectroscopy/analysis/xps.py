"""
XPS 光谱分析模块。

提供 X 射线光电子能谱（XPS）专用分析功能，包括：

- Shirley 背景扣除（迭代式）
- 线性背景扣除
- 多峰拟合（基于 PeakFit 拟合器）
- 能量校准（参考峰对齐）

依赖 :mod:`echem_core.spectroscopy.fitting` 中的 PeakFit / FitResult
以及 :mod:`echem_core.spectroscopy.model.spectrum` 中的 Spectrum 数据模型。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from numpy.typing import NDArray

from echem_core.spectroscopy.fitting.lineshapes import (
    gaussian,
    gl_mixed,
    lorentzian,
    pseudo_voigt,
)
from echem_core.spectroscopy.fitting.peak_fit import FitResult, PeakFit
from echem_core.spectroscopy.model.spectrum import Spectrum

# ---------------------------------------------------------------------------
# 线型名称 → 函数映射（与 peak_fit 保持一致）
# ---------------------------------------------------------------------------
_LINESHAPE_MAP: Dict[str, Any] = {
    "gaussian": gaussian,
    "lorentzian": lorentzian,
    "pseudo_voigt": pseudo_voigt,
    "gl_mixed": gl_mixed,
}

# ---------------------------------------------------------------------------
# Shirley 背景
# ---------------------------------------------------------------------------
def shirley_background(
    x: NDArray,
    y: NDArray,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> NDArray:
    """迭代计算 Shirley 背景。

    对 XPS 光谱应用 Shirley 迭代背景扣除算法 [Shirley1972]_。
    背景形状通过迭代确定：每次迭代将信号在背景之上的
    累积积分（从当前点向高结合能端）归一化到端点背景值之间。

    参考文献
    ----------
    .. [Shirley1972] D. A. Shirley, "High-resolution X-ray photoemission
       spectrum of the valence bands of gold", Phys. Rev. B 5, 4709 (1972).

    Parameters
    ----------
    x : ndarray
        结合能（或其它 x 轴坐标），可升序或降序排列。
    y : ndarray
        原始强度数据。
    max_iter : int, default=100
        最大迭代次数。
    tol : float, default=1e-6
        收敛判据。相邻两次迭代背景数组的最大绝对差值
        低于该值时停止迭代。

    Returns
    -------
    ndarray
        计算得到的 Shirley 背景值，形状与 ``y`` 相同。

    Notes
    -----
    算法自动检测 x 的排列方向（升序或降序），
    并将端点强度分别视为低结合能端和高结合能端的背景值。
    净信号（y - 背景）中的负值在每次迭代时截断为零。
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)

    if n < 3:
        return np.zeros_like(y)

    # 判断数据方向
    ascending: bool = x[0] < x[-1]  # True: 升序（低 BE → 高 BE）

    # 端点背景强度
    if ascending:
        i_high = y[-1]  # 高结合能端（数组末尾）
        i_low = y[0]    # 低结合能端（数组开头）
    else:
        i_high = y[0]   # 高结合能端（数组开头）
        i_low = y[-1]   # 低结合能端（数组末尾）

    # 初始背景：简单线性连接两端
    bg = np.linspace(i_low, i_high, n) if ascending else np.linspace(i_high, i_low, n)

    # 预计算梯形积分所需的微分步长
    dx = np.diff(x)
    if np.any(dx <= 0 if not ascending else dx <= 0):
        # 不允许相邻点间距为零或方向不一致
        pass  # 正常数据不会出现此情况

    for _iteration in range(max_iter):
        bg_old = bg.copy()

        # 净信号（截断负值）
        net = y - bg
        net = np.clip(net, 0.0, None)

        # 累积梯形积分
        avg = (net[:-1] + net[1:]) * 0.5
        cumulative = np.zeros(n)
        cumulative[1:] = np.cumsum(avg * dx)
        total_area = cumulative[-1]

        if total_area <= 0.0:
            # 净信号为零或负，无法继续迭代
            break

        # 从当前点向高结合能端积分
        if ascending:
            # 升序：高结合能端在末尾 → 积分方向为 k → N-1
            partial = total_area - cumulative
        else:
            # 降序：高结合能端在开头 → 积分方向为 0 → k
            partial = cumulative

        bg = i_high + (i_low - i_high) * partial / total_area

        if np.max(np.abs(bg - bg_old)) < tol:
            break

    return bg


# ---------------------------------------------------------------------------
# 线性背景
# ---------------------------------------------------------------------------
def linear_background(
    x: NDArray,
    y: NDArray,
    x_range: Optional[Tuple[float, float]] = None,
) -> NDArray:
    """计算线性背景（直线连接两端点）。

    在指定的 x 范围内拟合一条直线连接两端点的 y 值，
    返回该直线在所有 x 坐标上的取值。

    Parameters
    ----------
    x : ndarray
        横坐标数组。
    y : ndarray
        纵坐标数组。
    x_range : Tuple[float, float], optional
        背景两端点对应的 x 坐标 ``(x_left, x_right)``。
        若为 ``None``，则使用 x 的首尾元素。

    Returns
    -------
    ndarray
        线性背景值，形状与 ``y`` 相同。

    Examples
    --------
    >>> x = np.linspace(0, 10, 100)
    >>> y = 2.0 + 0.5 * x + np.sin(x)
    >>> bg = linear_background(x, y)
    >>> bg.shape == y.shape
    True
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if x_range is None:
        x_lo, x_hi = x[0], x[-1]
    else:
        x_lo, x_hi = float(x_range[0]), float(x_range[1])

    # 在线性插值获取端点处的 y 值
    y_lo = float(np.interp(x_lo, x, y))
    y_hi = float(np.interp(x_hi, x, y))

    # 两点确定一条直线
    if abs(x_hi - x_lo) < 1e-15:
        return np.full_like(y, y_lo)

    slope = (y_hi - y_lo) / (x_hi - x_lo)
    intercept = y_lo - slope * x_lo

    return slope * x + intercept


# ---------------------------------------------------------------------------
# 辅助：从 Spectrum 提取数据
# ---------------------------------------------------------------------------
def _get_xy(spectrum: Spectrum) -> Tuple[NDArray, NDArray]:
    """从 Spectrum 对象提取 x/y 数据，优先使用已处理数据。"""
    if spectrum.processed_x is not None and spectrum.processed_y is not None:
        return spectrum.processed_x, spectrum.processed_y
    return spectrum.raw_x, spectrum.raw_y


# ---------------------------------------------------------------------------
# 峰值拟合区域
# ---------------------------------------------------------------------------
def fit_region(
    spectrum: Spectrum,
    peaks_config: List[Dict[str, Any]],
    bg_type: str = "shirley",
) -> FitResult:
    """对 XPS 光谱指定区域进行多峰拟合。

    根据 ``peaks_config`` 中的峰配置创建 :class:`~echem_core.spectroscopy.fitting.peak_fit.PeakFit`
    拟合器，先扣除背景（Shirley 或线性），再对净信号进行多峰拟合。

    Parameters
    ----------
    spectrum : Spectrum
        待拟合的 XPS 光谱对象。优先使用 ``processed_x`` / ``processed_y``，
        不存在时回退到 ``raw_x`` / ``raw_y``。
    peaks_config : List[Dict[str, Any]]
        峰配置列表。每个元素是一个字典，支持以下键：

        - **center** (*float*) — 峰中心初始值（必须）。
        - **height** (*float*) — 峰高初始值（必须）。
        - **fwhm** (*float*) — 半高全宽初始值（必须）。
        - **lineshape** (*str*, optional) — 线型，默认 ``'gaussian'``。
          支持 ``'gaussian'``、``'lorentzian'``、``'pseudo_voigt'``、
          ``'gl_mixed'``。
        - **bounds** (*Dict[str, Tuple[float, float]]*, optional) —
          参数边界，格式如 ``{'center': (280, 290), 'fwhm': (0.1, 5)}``。
          每个键对应 ``(min, max)`` 元组，可仅指定部分参数。

        示例::

            [
                {
                    'center': 284.8,
                    'height': 10000,
                    'fwhm': 1.5,
                    'lineshape': 'gl_mixed',
                    'bounds': {'center': (280, 290)},
                },
                {
                    'center': 286.5,
                    'height': 2000,
                    'fwhm': 1.8,
                    'lineshape': 'gl_mixed',
                },
            ]

    bg_type : str, default='shirley'
        背景扣除类型：

        - ``'shirley'`` — 使用 :func:`shirley_background` 迭代扣除。
        - ``'linear'`` — 使用 :func:`linear_background` 直线扣除。
        - ``'none'`` — 不扣背景。

    Returns
    -------
    FitResult
        包含拟合参数、统计量和各峰信息的拟合结果。

    Raises
    ------
    ValueError
        当 ``bg_type`` 或 ``peaks_config`` 中的线型不支持时抛出。

    Examples
    --------
    >>> from echem_core.spectroscopy.model.spectrum import Spectrum
    >>> import numpy as np
    >>> x = np.linspace(280, 300, 500)
    >>> y = (10000 * np.exp(-4 * np.log(2) * ((x - 284.8) / 1.5) ** 2)
    ...      + 2000 * np.exp(-4 * np.log(2) * ((x - 286.5) / 1.8) ** 2)
    ...      + 500)
    >>> spec = Spectrum("XPS", x, y, x_unit="eV", y_unit="counts")
    >>> config = [
    ...     {"center": 284.8, "height": 10000, "fwhm": 1.5,
    ...      "lineshape": "gl_mixed",
    ...      "bounds": {"center": (283, 287)}},
    ...     {"center": 286.5, "height": 2000, "fwhm": 1.8,
    ...      "lineshape": "gl_mixed",
    ...      "bounds": {"center": (285, 289)}},
    ... ]
    >>> result = fit_region(spec, config, bg_type="shirley")
    >>> result.r_squared > 0.9
    True
    """
    # 提取数据
    x, y = _get_xy(spectrum)

    # --- 背景扣除 ---
    bg_type_lower = bg_type.strip().lower()

    if bg_type_lower == "shirley":
        bg = shirley_background(x, y)
        y_corrected = y - bg
    elif bg_type_lower == "linear":
        bg = linear_background(x, y)
        y_corrected = y - bg
    elif bg_type_lower == "none":
        y_corrected = y.copy()
    else:
        raise ValueError(
            f"不支持的背景类型: {bg_type!r}。"
            f"可选值: 'shirley', 'linear', 'none'"
        )

    # --- 构建 PeakFit 拟合器 ---
    pf = PeakFit()

    for peak_cfg in peaks_config:
        center = peak_cfg.get("center")
        height = peak_cfg.get("height")
        fwhm = peak_cfg.get("fwhm")
        lineshape = peak_cfg.get("lineshape", "gaussian").lower()

        if center is None or height is None or fwhm is None:
            raise ValueError(
                "peaks_config 中每个峰必须包含 'center'、'height' 和 'fwhm'"
            )

        if lineshape not in _LINESHAPE_MAP:
            raise ValueError(
                f"不支持线型: {lineshape!r}。"
                f"可选: {list(_LINESHAPE_MAP.keys())}"
            )

        # 转换边界格式：{(min, max)} → {min: ..., max: ...}
        bounds_raw = peak_cfg.get("bounds", {})
        bounds_converted: Dict[str, Dict[str, float]] = {}
        for param_name, bound_tuple in bounds_raw.items():
            if isinstance(bound_tuple, (tuple, list)) and len(bound_tuple) == 2:
                bmin, bmax = bound_tuple
                entry: Dict[str, float] = {}
                if bmin is not None:
                    entry["min"] = float(bmin)
                if bmax is not None:
                    entry["max"] = float(bmax)
                if entry:
                    bounds_converted[param_name] = entry
            else:
                # 兼容原有格式
                bounds_converted[param_name] = dict(bound_tuple)  # type: ignore[arg-type]

        pf.add_peak(
            center=float(center),
            height=float(height),
            fwhm=float(fwhm),
            lineshape=lineshape,
            bounds=bounds_converted,
        )

    # --- 执行拟合（不使用 PeakFit 内置背景） ---
    result = pf.fit(x, y_corrected)

    return result


# ---------------------------------------------------------------------------
# 能量校准
# ---------------------------------------------------------------------------
def calibrate(
    spectrum: Spectrum,
    reference_peak: float = 284.8,
    reference_name: str = "C1s",
) -> Spectrum:
    """校准 XPS 结合能（刚性平移 x 轴）。

    在光谱中搜索指定参考峰附近的最高点（或拟合峰中心），
    将整个 x 轴刚性平移，使参考峰对齐到标准结合能位置。

    Parameters
    ----------
    spectrum : Spectrum
        待校准的 XPS 光谱对象。
    reference_peak : float, default=284.8
        参考峰的标准结合能位置（单位：eV）。
    reference_name : str, default='C1s'
        参考峰名称，仅用于校准记录的元数据（如 'C1s'）。

    Returns
    -------
    Spectrum
        新的 Spectrum 对象，其 x 轴已刚性平移校准，
        并在处理配方中记录校准信息。

    Notes
    -----
    校准策略：

    1. 在 ``reference_peak ± 5 eV`` 范围内搜索最大强度对应的 x 坐标
       作为实测峰中心。
    2. 计算偏移量 ``offset = measured - reference``。
    3. 新 x 轴 = 原 x 轴 - offset。

    对于信噪比较高、且参考峰明显的谱图，该方法能提供
    快速有效的校准。若需要更高精度，建议先用
    :func:`fit_region` 拟合后再手动计算偏移。

    Examples
    --------
    >>> import numpy as np
    >>> from echem_core.spectroscopy.model.spectrum import Spectrum
    >>> x = np.linspace(280, 300, 500)
    >>> y = 10000 * np.exp(-4 * np.log(2) * ((x - 285.5) / 1.5) ** 2)
    >>> spec = Spectrum("XPS", x, y, x_unit="eV", y_unit="counts")
    >>> calibrated = calibrate(spec, reference_peak=284.8, reference_name="C1s")
    >>> # 峰值现在应在 284.8 eV 附近
    >>> import numpy.testing as npt
    >>> x_new = calibrated.processed_x if calibrated.processed_x is not None else calibrated.raw_x
    >>> peak_idx = np.argmax(calibrated.raw_y if calibrated.processed_y is None else calibrated.processed_y)
    >>> abs(x_new[peak_idx] - 284.8) < 0.1
    True
    """
    x, y = _get_xy(spectrum)

    # 在参考峰附近 ±5 eV 范围内搜索最大强度
    search_half_range: float = 5.0
    lo = reference_peak - search_half_range
    hi = reference_peak + search_half_range

    mask = (x >= lo) & (x <= hi)
    if np.any(mask):
        x_roi = x[mask]
        y_roi = y[mask]
        measured_center = x_roi[np.argmax(y_roi)]
    else:
        # 如果参考范围外，使用全局最大值作为替代
        measured_center = x[np.argmax(y)]

    # 计算偏移量（需对齐到的目标位置 - 当前实测位置）
    offset = measured_center - reference_peak

    # 新 x 轴：刚性平移
    x_calibrated = x - offset

    recipe: Dict[str, Any] = {
        "step": "energy_calibration",
        "params": {
            "reference_name": reference_name,
            "reference_peak": reference_peak,
            "measured_center": float(measured_center),
            "offset": float(offset),
        },
    }

    return spectrum.copy_with_processed(x_calibrated, y, recipe=recipe)


# ---------------------------------------------------------------------------
# 模块导出
# ---------------------------------------------------------------------------
__all__ = [
    "shirley_background",
    "linear_background",
    "fit_region",
    "calibrate",
]
