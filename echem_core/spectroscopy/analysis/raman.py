"""
拉曼光谱分析模块。

提供拉曼光谱中 D 峰（~1350 cm⁻¹）和 G 峰（~1580 cm⁻¹）的
峰属性提取及 ID/IG 比值计算功能。
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
from scipy.integrate import trapezoid

from echem_core.spectroscopy.model.spectrum import Spectrum
from echem_core.spectroscopy.processing.baseline import (
    als_baseline,
    arpls_baseline,
    polynomial_baseline,
    rubberband_baseline,
)
from echem_core.spectroscopy.fitting.lineshapes import gaussian


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
_DEFAULT_D_RANGE: Tuple[float, float] = (1300.0, 1400.0)
"""D 峰默认波数范围 (cm⁻¹)。"""

_DEFAULT_G_RANGE: Tuple[float, float] = (1500.0, 1640.0)
"""G 峰默认波数范围 (cm⁻¹)。"""


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------
def _get_xy(spectrum: Spectrum) -> Tuple[np.ndarray, np.ndarray]:
    """
    从 Spectrum 对象中提取 x 和 y 数据。

    优先使用 processed_x / processed_y，若不存在则回退到 raw_x / raw_y。

    Parameters
    ----------
    spectrum : Spectrum
        光谱对象。

    Returns
    -------
    x : np.ndarray
        横坐标数组。
    y : np.ndarray
        纵坐标数组。
    """
    if spectrum.processed_x is not None and spectrum.processed_y is not None:
        return spectrum.processed_x, spectrum.processed_y
    return spectrum.raw_x, spectrum.raw_y


def _slice_range(
    x: np.ndarray, y: np.ndarray, lo: float, hi: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    按波数范围截取光谱数据。

    Parameters
    ----------
    x : np.ndarray
        全波段横坐标。
    y : np.ndarray
        全波段纵坐标（可已做基线校正）。
    lo : float
        范围下限 (cm⁻¹)。
    hi : float
        范围上限 (cm⁻¹)。

    Returns
    -------
    x_roi : np.ndarray
        范围内的横坐标。
    y_roi : np.ndarray
        范围内的纵坐标。
    mask : np.ndarray
        布尔掩码，与 x 等长，范围内为 True。
    """
    mask = (x >= lo) & (x <= hi)
    return x[mask], y[mask], mask


def _apply_baseline(
    x: np.ndarray,
    y: np.ndarray,
    method: Optional[str],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    对光谱应用基线校正。

    Parameters
    ----------
    x : np.ndarray
        横坐标。
    y : np.ndarray
        纵坐标。
    method : str or None
        基线校正方法：'als', 'arpls', 'poly', 'rubberband' 或 None（不做校正）。

    Returns
    -------
    baseline : np.ndarray
        基线值，与 y 等长。
    corrected_y : np.ndarray
        基线校正后的数据 (y - baseline)。
    """
    if method is None:
        return np.zeros_like(y), y.copy()

    method_lower = method.strip().lower()

    if method_lower == "als":
        return als_baseline(y)
    elif method_lower == "arpls":
        return arpls_baseline(y)
    elif method_lower == "poly":
        return polynomial_baseline(x, y)
    elif method_lower == "rubberband":
        return rubberband_baseline(x, y)
    else:
        raise ValueError(
            f"不支持的基线校正方法: {method!r}。"
            f"可选值: 'als', 'arpls', 'poly', 'rubberband', None"
        )


def _find_peak_in_range(
    x: np.ndarray, y: np.ndarray, lo: float, hi: float
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    在指定波数范围内寻找峰，返回峰位置、高度、半高全宽和面积。

    使用 scipy.signal.find_peaks 检测峰，选取最高峰。
    半高全宽通过半高处的线性插值估算。

    Parameters
    ----------
    x : np.ndarray
        全波段横坐标（已基线校正）。
    y : np.ndarray
        全波段纵坐标（已基线校正）。
    lo : float
        峰范围下限 (cm⁻¹)。
    hi : float
        峰范围上限 (cm⁻¹)。

    Returns
    -------
    position : float or None
        峰中心位置。
    height : float or None
        峰高。
    fwhm : float or None
        半高全宽。
    area : float or None
        峰面积（通过梯形积分计算）。
    """
    x_roi, y_roi, mask = _slice_range(x, y, lo, hi)

    if len(x_roi) < 3:
        return None, None, None, None

    # 使用 find_peaks 检测峰
    peaks, properties = find_peaks(y_roi)
    if len(peaks) == 0:
        return None, None, None, None

    # 选取最高峰
    top_idx = peaks[np.argmax(y_roi[peaks])]
    position = float(x_roi[top_idx])
    height = float(y_roi[top_idx])

    # 面积：对全范围进行梯形积分
    area = float(trapezoid(y_roi, x_roi))

    # 半高全宽估算：在半高处进行线性插值
    half_max = height / 2.0
    # 左侧：从峰位置向左搜索，找到第一个低于 half_max 的点
    left_idx = top_idx
    while left_idx > 0 and y_roi[left_idx] > half_max:
        left_idx -= 1
    # 如果已经超出峰范围，扩大搜索范围到整个 x 数组
    if left_idx == 0 and y_roi[0] > half_max:
        # 在全波段中向左搜索
        global_mask = mask
        global_x = x[mask]
        global_y = y[mask]
        left_idx = top_idx
        while left_idx > 0 and global_y[left_idx] > half_max:
            left_idx -= 1

    left_x = x_roi[left_idx] if left_idx < len(x_roi) - 1 else x_roi[0]
    # 如果 left_idx 处的 y 仍高于 half_max，使用第一个点
    if y_roi[left_idx] > half_max:
        left_x = x_roi[0]
    elif left_idx < len(x_roi) - 1:
        # 线性插值
        x1, x2 = x_roi[left_idx], x_roi[left_idx + 1]
        y1, y2 = y_roi[left_idx], y_roi[left_idx + 1]
        if y2 != y1:
            left_x = x1 + (half_max - y1) * (x2 - x1) / (y2 - y1)

    # 右侧：从峰位置向右搜索
    right_idx = top_idx
    while right_idx < len(x_roi) - 1 and y_roi[right_idx] > half_max:
        right_idx += 1

    right_x = x_roi[right_idx] if right_idx > 0 else x_roi[-1]
    if y_roi[right_idx] > half_max:
        right_x = x_roi[-1]
    elif right_idx > 0:
        # 线性插值
        x1, x2 = x_roi[right_idx - 1], x_roi[right_idx]
        y1, y2 = y_roi[right_idx - 1], y_roi[right_idx]
        if y2 != y1:
            right_x = x1 + (half_max - y1) * (x2 - x1) / (y2 - y1)

    fwhm = float(abs(right_x - left_x))

    return position, height, fwhm, area


def _fit_gaussian_in_range(
    x: np.ndarray, y: np.ndarray, lo: float, hi: float
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    在指定波数范围内对峰进行高斯拟合。

    Parameters
    ----------
    x : np.ndarray
        全波段横坐标（已基线校正）。
    y : np.ndarray
        全波段纵坐标（已基线校正）。
    lo : float
        峰范围下限 (cm⁻¹)。
    hi : float
        峰范围上限 (cm⁻¹)。

    Returns
    -------
    position : float or None
        拟合得到的峰中心位置。
    height : float or None
        拟合得到的峰高。
    fwhm : float or None
        拟合得到的半高全宽。
    area : float or None
        由拟合参数计算得到的峰面积。
    """
    x_roi, y_roi, _ = _slice_range(x, y, lo, hi)

    if len(x_roi) < 5:
        return None, None, None, None

    # 初始值估算
    max_idx = np.argmax(y_roi)
    center0 = float(x_roi[max_idx])
    height0 = float(y_roi[max_idx])
    fwhm0 = (hi - lo) / 4.0  # 粗略估计：范围的 1/4

    try:
        popt, _ = curve_fit(
            gaussian,
            x_roi,
            y_roi,
            p0=[center0, height0, fwhm0],
            bounds=([lo, 0.0, (hi - lo) * 0.01], [hi, height0 * 3.0, hi - lo]),
            maxfev=5000,
        )
    except (RuntimeError, ValueError):
        return None, None, None, None

    position = float(popt[0])
    height = float(popt[1])
    fwhm = float(popt[2])

    # 高斯峰面积: A = height * fwhm * sqrt(pi / (4 * ln(2)))
    #          ≈ height * fwhm * 1.064467
    area = float(height * fwhm * np.sqrt(np.pi / (4.0 * np.log(2.0))))

    return position, height, fwhm, area


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------
def calc_dg_ratio(
    spectrum: Spectrum,
    d_range: Tuple[float, float] = _DEFAULT_D_RANGE,
    g_range: Tuple[float, float] = _DEFAULT_G_RANGE,
    method: str = "height",
    baseline_method: str = "als",
) -> Dict[str, object]:
    """
    计算拉曼光谱的 D 峰与 G 峰比值 (ID/IG)。

    对拉曼光谱进行基线校正后，分别在 D 峰和 G 峰所在的波数范围内
    检测峰，提取峰位置、高度、半高全宽和面积，并计算 ID/IG 比值。

    Parameters
    ----------
    spectrum : Spectrum
        拉曼光谱对象。优先使用 processed_x / processed_y，
        若不存在则使用 raw_x / raw_y。
    d_range : Tuple[float, float], default=(1300, 1400)
        D 峰波数范围 (cm⁻¹)，格式为 (下限, 上限)。
    g_range : Tuple[float, float], default=(1500, 1640)
        G 峰波数范围 (cm⁻¹)，格式为 (下限, 上限)。
    method : str, default='height'
        峰强度的计算方式：

        - ``'height'`` — 取基线校正后范围内的最高点作为峰高。
        - ``'area'``   — 对基线校正后范围内进行梯形积分，用面积作为强度。
        - ``'fit'``    — 使用高斯拟合提取峰参数，峰高作为强度。
    baseline_method : str, default='als'
        基线校正方法，传递给基线处理模块。可选值：

        - ``'als'``        — 非对称最小二乘（默认）
        - ``'arpls'``      — 自适应重加权惩罚最小二乘
        - ``'poly'``       — 多项式拟合
        - ``'rubberband'`` — 橡皮筋（凸包）校正
        - ``None``         — 不做基线校正

    Returns
    -------
    result : dict
        包含以下键的字典：

        - **id_ig** (*float*) — ID/IG 比值。
          根据 method 不同，使用峰高比或面积比。
        - **d_position** (*float or None*) — D 峰位置 (cm⁻¹)。
        - **d_height** (*float or None*) — D 峰高度。
        - **d_fwhm** (*float or None*) — D 峰半高全宽 (cm⁻¹)。
        - **d_area** (*float or None*) — D 峰面积。
        - **g_position** (*float or None*) — G 峰位置 (cm⁻¹)。
        - **g_height** (*float or None*) — G 峰高度。
        - **g_fwhm** (*float or None*) — G 峰半高全宽 (cm⁻¹)。
        - **g_area** (*float or None*) — G 峰面积。
        - **method** (*str*) — 使用的计算方法。

    Raises
    ------
    ValueError
        当 method 或 baseline_method 为不支持的值时抛出。

    Examples
    --------
    >>> from echem_core.spectroscopy.model.spectrum import Spectrum
    >>> import numpy as np
    >>> x = np.linspace(1200, 1700, 500)
    >>> y = np.exp(-((x - 1350) ** 2) / 200) + 0.5 * np.exp(-((x - 1580) ** 2) / 150)
    >>> spec = Spectrum("Raman", x, y, x_unit="cm⁻¹", y_unit="a.u.")
    >>> result = calc_dg_ratio(spec, method="height")
    >>> result["id_ig"]
    2.0
    """
    method = method.strip().lower()
    if method not in ("height", "area", "fit"):
        raise ValueError(
            f"method 必须为 'height'、'area' 或 'fit'，收到: {method!r}"
        )

    # 提取数据
    x, y = _get_xy(spectrum)

    # 基线校正
    _, corrected_y = _apply_baseline(x, y, baseline_method)

    # --- D 峰分析 ---
    if method == "fit":
        d_pos, d_height, d_fwhm, d_area = _fit_gaussian_in_range(
            x, corrected_y, d_range[0], d_range[1]
        )
    else:
        d_pos, d_height, d_fwhm, d_area = _find_peak_in_range(
            x, corrected_y, d_range[0], d_range[1]
        )

    # 如果 height 方法没找到峰，尝试在范围内取最大值作为 fallback
    if method == "height" and d_height is None:
        _, y_roi, _ = _slice_range(corrected_y, corrected_y, d_range[0], d_range[1])
        if len(y_roi) > 0:
            # 使用 _slice_range 需要 x, y 参数；重新调用
            x_roi, y_roi, _ = _slice_range(x, corrected_y, d_range[0], d_range[1])
            if len(x_roi) > 0:
                max_idx = np.argmax(y_roi)
                d_pos = float(x_roi[max_idx])
                d_height = float(y_roi[max_idx])
                d_fwhm = None
                d_area = float(trapezoid(y_roi, x_roi))

    # --- G 峰分析 ---
    if method == "fit":
        g_pos, g_height, g_fwhm, g_area = _fit_gaussian_in_range(
            x, corrected_y, g_range[0], g_range[1]
        )
    else:
        g_pos, g_height, g_fwhm, g_area = _find_peak_in_range(
            x, corrected_y, g_range[0], g_range[1]
        )

    if method == "height" and g_height is None:
        x_roi, y_roi, _ = _slice_range(x, corrected_y, g_range[0], g_range[1])
        if len(x_roi) > 0:
            max_idx = np.argmax(y_roi)
            g_pos = float(x_roi[max_idx])
            g_height = float(y_roi[max_idx])
            g_fwhm = None
            g_area = float(trapezoid(y_roi, x_roi))

    # --- ID/IG 比值计算 ---
    if method == "area":
        # 使用面积比
        if d_area is not None and g_area is not None and g_area > 0:
            id_ig = d_area / g_area
        else:
            id_ig = float("nan")
    else:
        # 'height' 和 'fit' 都使用峰高比
        if d_height is not None and g_height is not None and g_height > 0:
            id_ig = d_height / g_height
        else:
            id_ig = float("nan")

    return {
        "id_ig": id_ig,
        "d_position": d_pos,
        "d_height": d_height,
        "d_fwhm": d_fwhm,
        "d_area": d_area,
        "g_position": g_pos,
        "g_height": g_height,
        "g_fwhm": g_fwhm,
        "g_area": g_area,
        "method": method,
    }


def batch_process(
    spectra: List[Spectrum],
    **kwargs,
) -> List[Dict[str, object]]:
    """
    批量处理拉曼光谱，计算每条光谱的 D/G 峰比值。

    对光谱列表中的每一条依次调用 :func:`calc_dg_ratio`，
    返回结果字典组成的列表。

    Parameters
    ----------
    spectra : List[Spectrum]
        拉曼光谱对象列表。
    **kwargs
        传递给 :func:`calc_dg_ratio` 的额外参数，
        如 ``d_range``、``g_range``、``method``、``baseline_method`` 等。

    Returns
    -------
    List[dict]
        每个元素是 :func:`calc_dg_ratio` 返回的结果字典，
        顺序与输入光谱列表一致。

    Examples
    --------
    >>> from echem_core.spectroscopy.model.spectrum import Spectrum
    >>> import numpy as np
    >>> specs = []
    >>> for _ in range(3):
    ...     x = np.linspace(1200, 1700, 500)
    ...     y = np.exp(-((x - 1350) ** 2) / 200) + 0.5 * np.exp(-((x - 1580) ** 2) / 150)
    ...     specs.append(Spectrum("Raman", x, y))
    >>> results = batch_process(specs, method="height")
    >>> len(results)
    3
    """
    return [calc_dg_ratio(spec, **kwargs) for spec in spectra]


__all__ = [
    "calc_dg_ratio",
    "batch_process",
]
