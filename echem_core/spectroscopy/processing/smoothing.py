"""
信号平滑处理模块。

提供多种平滑滤波方法，用于电化学光谱数据的降噪处理。
"""

from typing import Union

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d
from scipy.signal import savgol_filter


def savgol_smooth(
    y: Union[NDArray[np.floating], list[float]],
    window_length: int = 9,
    polyorder: int = 2,
) -> NDArray[np.floating]:
    """
    Savitzky-Golay 平滑滤波。

    通过局部多项式拟合实现对信号的平滑处理，在降噪的同时
    较好地保留信号的形状和特征（如峰宽、高度）。

    参数
    ----------
    y : ndarray | list[float]
        待平滑的一维信号数据。
    window_length : int, default=9
        滤波窗口长度，必须为正奇数。
    polyorder : int, default=2
        多项式拟合阶数，必须小于 window_length。

    返回
    -------
    ndarray
        平滑处理后的一维数组，与输入形状相同。

    参考
    --------
    scipy.signal.savgol_filter
    """
    return savgol_filter(y, window_length, polyorder)


def moving_average(
    y: Union[NDArray[np.floating], list[float]],
    window: int = 5,
) -> NDArray[np.floating]:
    """
    移动平均平滑滤波。

    使用指定宽度的滑动窗口对信号进行均值滤波，简单有效地
    抑制随机噪声。

    参数
    ----------
    y : ndarray | list[float]
        待平滑的一维信号数据。
    window : int, default=5
        滑动窗口大小。窗口两端会在数据边界处自动收缩。

    返回
    -------
    ndarray
        平滑处理后的一维数组，与输入形状相同。

    注意
    ------
    边界处使用的有效窗口宽度小于 `window`，可能导致边界
    附近平滑程度略低。
    """
    y_arr = np.asarray(y, dtype=np.float64)
    n = len(y_arr)
    # 累积和用于快速计算滑动窗口和
    cum = np.cumsum(y_arr, dtype=np.float64)
    # 将 cum[window:] 原地转换为以 y[i-window+1]..y[i] 为窗口的和
    cum[window:] = cum[window:] - cum[:-window]
    out = np.empty_like(y_arr)
    # 左边界：前 window-1 个点，有效窗口大小依次为 1..window-1
    out[: window - 1] = cum[: window - 1] / np.arange(1, min(window, n + 1))
    # 中间主体：每个点都有完整的 window 个邻居
    out[window - 1 :] = cum[window - 1 :] / window
    # 右边界：最后 window-1 个点，有效窗口宽度从 window-1 递减到 1
    for i in range(max(0, n - window + 1), n):
        start = max(0, i - window + 1)
        out[i] = np.mean(y_arr[start : i + 1])
    return out


def gaussian_filter(
    y: Union[NDArray[np.floating], list[float]],
    sigma: float = 2.0,
) -> NDArray[np.floating]:
    """
    高斯平滑滤波。

    使用一维高斯核对信号进行卷积平滑，sigma 控制平滑程度。
    适用于去除高斯噪声，同时保持信号的整体趋势。

    参数
    ----------
    y : ndarray | list[float]
        待平滑的一维信号数据。
    sigma : float, default=2.0
        高斯核的标准差。值越大平滑程度越强。

    返回
    -------
    ndarray
        平滑处理后的一维数组，与输入形状相同。

    参考
    --------
    scipy.ndimage.gaussian_filter1d
    """
    return gaussian_filter1d(y, sigma)
