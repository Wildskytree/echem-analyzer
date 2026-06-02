"""光谱线型函数模块（Spectral line shape functions）。

提供高斯、洛伦兹、伪Voigt及混合线型函数，
所有函数接收 ndarray x 并返回 ndarray。
"""

import numpy as np
from numpy.typing import NDArray
from typing import Union

# ---------------------------------------------------------------------------
# 常数
# ---------------------------------------------------------------------------
_SQRT_LN2 = np.sqrt(np.log(2.0))          # sqrt(ln2)
_SQRT_PI = np.sqrt(np.pi)                  # sqrt(π)
_TWO_SQRT_LN2 = 2.0 * _SQRT_LN2           # 2*sqrt(ln2)
_FWHM_TO_SIGMA = _TWO_SQRT_LN2             # 用于高斯：HWHM = sigma * 2*sqrt(ln2)


def _sigma_from_fwhm(fwhm: float) -> float:
    """从半高全宽计算高斯标准差 sigma。"""
    return fwhm / _FWHM_TO_SIGMA


# ---------------------------------------------------------------------------
# 高斯线型  Gaussian line shape
# ---------------------------------------------------------------------------
def gaussian(x: NDArray, center: float, height: float, fwhm: float) -> NDArray:
    """高斯线型函数（Gaussian line shape）。

    公式:
        G(x) = height * exp( -4*ln(2) * ((x - center)/fwhm)^2 )

    积分面积（Area）:
        A = height * fwhm * sqrt(π / (4*ln(2)))
          ≈ height * fwhm * 1.064467

    Parameters
    ----------
    x : ndarray
        自变量数组。
    center : float
        峰中心位置。
    height : float
        峰高（峰值处数值）。
    fwhm : float
        半高全宽（Full Width at Half Maximum）。

    Returns
    -------
    ndarray
        高斯线型值。
    """
    if fwhm <= 0:
        return np.zeros_like(x)
    arg = (x - center) / fwhm
    return height * np.exp(-4.0 * np.log(2.0) * arg * arg)


# ---------------------------------------------------------------------------
# 洛伦兹线型  Lorentzian line shape
# ---------------------------------------------------------------------------
def lorentzian(x: NDArray, center: float, height: float, fwhm: float) -> NDArray:
    """洛伦兹线型函数（Lorentzian line shape）。

    公式:
        L(x) = height / (1 + ((x - center) / (fwhm/2))^2)

    积分面积（Area）:
        A = height * fwhm * π / 2

    Parameters
    ----------
    x : ndarray
        自变量数组。
    center : float
        峰中心位置。
    height : float
        峰高（峰值处数值）。
    fwhm : float
        半高全宽（Full Width at Half Maximum）。

    Returns
    -------
    ndarray
        洛伦兹线型值。
    """
    if fwhm <= 0:
        return np.zeros_like(x)
    arg = (x - center) / (fwhm / 2.0)
    return height / (1.0 + arg * arg)


# ---------------------------------------------------------------------------
# 伪Voigt线型  Pseudo-Voigt line shape
# ---------------------------------------------------------------------------
def pseudo_voigt(
    x: NDArray,
    center: float,
    height: float,
    fwhm: float,
    fraction: float = 0.5,
) -> NDArray:
    """伪Voigt线型函数（Pseudo-Voigt line shape）。

    公式:
        pV(x) = fraction * L(x) + (1 - fraction) * G(x)

    其中 L 为洛伦兹，G 为高斯，两者使用相同的 FWHM 和 height。

    积分面积（Area）:
        A = fraction * (height * fwhm * π / 2)
          + (1 - fraction) * (height * fwhm * sqrt(π / (4*ln(2))))

    Parameters
    ----------
    x : ndarray
        自变量数组。
    center : float
        峰中心位置。
    height : float
        峰高（峰值处数值）。
    fwhm : float
        半高全宽（Full Width at Half Maximum）。
    fraction : float, optional
        洛伦兹组分比例，取值范围 [0, 1]。
        默认值 0.5（各占一半）。

    Returns
    -------
    ndarray
        伪Voigt线型值。
    """
    if fwhm <= 0:
        return np.zeros_like(x)
    if fraction <= 0.0:
        return gaussian(x, center, height, fwhm)
    if fraction >= 1.0:
        return lorentzian(x, center, height, fwhm)

    g = gaussian(x, center, height, fwhm)
    l = lorentzian(x, center, height, fwhm)
    return fraction * l + (1.0 - fraction) * g


# ---------------------------------------------------------------------------
# 高斯-洛伦兹混合线型  Gaussian-Lorentzian mixed (sum) line shape
# ---------------------------------------------------------------------------
def gl_mixed(
    x: NDArray,
    center: float,
    height: float,
    fwhm: float,
    mu: float = 0.5,
) -> NDArray:
    """高斯-洛伦兹混合线型函数（Gaussian-Lorentzian mixed line shape）。

    pseudo_voigt 的别名/等价函数。mu 为洛伦兹组分比例。

    公式:
        GL(x) = mu * L(x) + (1 - mu) * G(x)

    积分面积（Area）:
        A = mu * (height * fwhm * π / 2)
          + (1 - mu) * (height * fwhm * sqrt(π / (4*ln(2))))

    Parameters
    ----------
    x : ndarray
        自变量数组。
    center : float
        峰中心位置。
    height : float
        峰高（峰值处数值）。
    fwhm : float
        半高全宽（Full Width at Half Maximum）。
    mu : float, optional
        洛伦兹组分比例（mixing parameter），取值范围 [0, 1]。
        默认值 0.5。

    Returns
    -------
    ndarray
        混合线型值。
    """
    return pseudo_voigt(x, center, height, fwhm, fraction=mu)
