"""光谱峰值拟合模块（Spectral peak fitting module）。

提供 PeakFit 拟合器与 FitResult 结果类，
基于 lmfit 实现多峰线型拟合，支持高斯、洛伦兹、伪 Voigt 等线型
以及线性/常数背景扣除。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
from lmfit import Model, Parameter, Parameters
from lmfit.models import ConstantModel, LinearModel
from numpy.typing import NDArray

from echem_core.spectroscopy.fitting.lineshapes import (
    gaussian,
    gl_mixed,
    lorentzian,
    pseudo_voigt,
)

# ---------------------------------------------------------------------------
# 线型名称 → 函数映射
# ---------------------------------------------------------------------------
_LINESHAPE_MAP: Dict[str, Any] = {
    "gaussian": gaussian,
    "lorentzian": lorentzian,
    "pseudo_voigt": pseudo_voigt,
    "gl_mixed": gl_mixed,
}

# ---------------------------------------------------------------------------
# 面积计算常量
# ---------------------------------------------------------------------------
_AREA_FACTOR_GAUSSIAN: float = np.sqrt(np.pi / (4.0 * np.log(2.0)))  # ≈ 1.064467
_AREA_FACTOR_LORENTZIAN: float = np.pi / 2.0  # ≈ 1.570796


def _compute_area(lineshape: str, height: float, fwhm: float,
                   fraction: Optional[float] = None) -> float:
    """根据线型计算峰面积。

    Parameters
    ----------
    lineshape : str
        线型名称。
    height : float
        峰高。
    fwhm : float
        半高全宽。
    fraction : float, optional
        洛伦兹组分比例（仅 pseudo_voigt / gl_mixed 使用）。

    Returns
    -------
    float
        计算得到的峰面积。
    """
    ls = lineshape.lower()
    if ls == "gaussian":
        return height * fwhm * _AREA_FACTOR_GAUSSIAN
    if ls == "lorentzian":
        return height * fwhm * _AREA_FACTOR_LORENTZIAN
    if ls in ("pseudo_voigt", "gl_mixed"):
        frac = fraction if fraction is not None else 0.5
        area_g = height * fwhm * _AREA_FACTOR_GAUSSIAN
        area_l = height * fwhm * _AREA_FACTOR_LORENTZIAN
        return (1.0 - frac) * area_g + frac * area_l
    return 0.0


# ---------------------------------------------------------------------------
# 背景模型工厂
# ---------------------------------------------------------------------------
def _make_background_model(bg_type: str) -> Model:
    """创建背景 lmfit 模型。

    Parameters
    ----------
    bg_type : str
        背景类型，'constant' 或 'linear'。

    Returns
    -------
    Model
        lmfit 模型实例。
    """
    if bg_type == "constant":
        return ConstantModel(prefix="bg_")
    if bg_type == "linear":
        return LinearModel(prefix="bg_")
    raise ValueError(f"不支持的背景类型: {bg_type}，仅支持 'constant' 和 'linear'")


# ===================================================================
# FitResult — 拟合结果类
# ===================================================================
class FitResult:
    """拟合结果类，存储拟合参数、统计量及残差。

    Attributes
    ----------
    params : Dict[str, float]
        最佳拟合参数字典（参数名 → 最佳值）。
    peaks : List[Dict[str, float]]
        每个峰的拟合结果列表，每个元素包含
        ``center``, ``height``, ``fwhm``, ``area`` 字段。
    residual : NDArray
        拟合残差（y - y_fit）。
    r_squared : float
        决定系数 R²。
    chi_squared : float
        卡方统计量（约化后残差平方和）。
    aic : float
        Akaike 信息准则。
    bic : float
        Bayesian 信息准则。
    """

    def __init__(self, lmfit_result: Any, peak_infos: List[Dict[str, Any]],
                 x: NDArray, y: NDArray) -> None:
        """初始化 FitResult。

        Parameters
        ----------
        lmfit_result : lmfit.model.ModelResult
            lmfit 拟合结果对象。
        peak_infos : List[Dict]
            每个峰的元信息列表。
        x : NDArray
            自变量数据。
        y : NDArray
            因变量数据。
        """
        self._result = lmfit_result
        self._peak_infos = peak_infos
        self._x = x
        self._y = y

        self.params = {}
        for name, param in lmfit_result.params.items():
            self.params[name] = param.value

        self.peaks = []
        for info in peak_infos:
            prefix = info["prefix"]
            center = lmfit_result.params[f"{prefix}center"].value
            height = lmfit_result.params[f"{prefix}height"].value
            fwhm = lmfit_result.params[f"{prefix}fwhm"].value
            fraction = None
            if info["lineshape"] == "pseudo_voigt":
                fraction = lmfit_result.params[f"{prefix}fraction"].value
            elif info["lineshape"] == "gl_mixed":
                fraction = lmfit_result.params[f"{prefix}mu"].value
            area = _compute_area(info["lineshape"], height, fwhm, fraction)
            self.peaks.append({
                "center": center,
                "height": height,
                "fwhm": fwhm,
                "area": area,
            })

        self.residual = lmfit_result.residual
        # 计算 R²
        ss_res = np.sum(self.residual ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        self.r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        self.chi_squared = lmfit_result.chisqr
        self.aic = lmfit_result.aic
        self.bic = lmfit_result.bic

    def report(self) -> str:
        """返回格式化的拟合报告字符串。

        Returns
        -------
        str
            包含拟合统计量和各峰参数的多行报告。
        """
        lines = []
        lines.append("=" * 60)
        lines.append("光谱峰值拟合报告")
        lines.append("=" * 60)
        lines.append("")

        lines.append("【拟合优度统计】")
        lines.append(f"  决定系数 R²      : {self.r_squared:.6f}")
        lines.append(f"  卡方统计量 χ²    : {self.chi_squared:.6e}")
        lines.append(f"  AIC              : {self.aic:.4f}")
        lines.append(f"  BIC              : {self.bic:.4f}")
        lines.append("")

        lines.append("【各峰拟合参数】")
        for i, peak in enumerate(self.peaks):
            lines.append(f"  峰 {i + 1}:")
            lines.append(f"    中心 (center) : {peak['center']:.6f}")
            lines.append(f"    峰高 (height) : {peak['height']:.6f}")
            lines.append(f"    半高全宽 (FWHM): {peak['fwhm']:.6f}")
            lines.append(f"    面积 (area)   : {peak['area']:.6f}")

        lines.append("")
        lines.append("【拟合参数完整列表】")
        for name, val in self.params.items():
            lines.append(f"  {name:20s} = {val:.6f}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (f"FitResult(peaks={len(self.peaks)}, "
                f"R²={self.r_squared:.4f}, "
                f"χ²={self.chi_squared:.4e})")


# ===================================================================
# PeakFit — 峰值拟合器
# ===================================================================
class PeakFit:
    """光谱峰值拟合器，支持多峰拟合与背景扣除。

    示例
    -----
    >>> pf = PeakFit()
    >>> pf.add_peak(center=500, height=1.0, fwhm=20,
    ...             lineshape="gaussian",
    ...             bounds={"center": {"min": 490, "max": 510}})
    >>> pf.add_peak(center=600, height=0.5, fwhm=30,
    ...             lineshape="lorentzian")
    >>> pf.set_background(bg_type="linear")
    >>> result = pf.fit(x, y)
    >>> print(result.report())
    >>> pf.plot(x, y)
    """

    def __init__(self) -> None:
        """初始化空的 PeakFit 拟合器。"""
        self._peaks: List[Dict[str, Any]] = []      # 峰参数列表
        self._bg_type: str = "none"                  # 背景类型
        self._bg_params: Optional[Dict[str, float]] = None  # 背景初始参数

    # ------------------------------------------------------------------
    # 添加峰
    # ------------------------------------------------------------------
    def add_peak(self, center: float, height: float, fwhm: float,
                 lineshape: str = "gaussian",
                 bounds: Optional[Dict[str, Dict[str, float]]] = None) -> None:
        """添加一个拟合峰。

        Parameters
        ----------
        center : float
            峰中心位置初始值。
        height : float
            峰高初始值。
        fwhm : float
            半高全宽初始值。
        lineshape : str, optional
            线型名称，可选 ``'gaussian'``, ``'lorentzian'``,
            ``'pseudo_voigt'``, ``'gl_mixed'``，默认 ``'gaussian'``。
        bounds : Dict[str, Dict[str, float]], optional
            参数边界约束字典，格式如::

                {
                    "center": {"min": 490, "max": 510},
                    "height": {"min": 0.0},
                    "fwhm":   {"min": 5.0, "max": 50.0},
                }

            可仅指定部分参数的 ``min`` / ``max``。
        """
        ls = lineshape.lower()
        if ls not in _LINESHAPE_MAP:
            raise ValueError(
                f"不支持的线型: '{lineshape}'。支持: {list(_LINESHAPE_MAP.keys())}"
            )

        info = {
            "center": center,
            "height": height,
            "fwhm": fwhm,
            "lineshape": ls,
            "bounds": bounds if bounds else {},
            "prefix": f"p{len(self._peaks)}_",
        }
        self._peaks.append(info)

    # ------------------------------------------------------------------
    # 设置背景
    # ------------------------------------------------------------------
    def set_background(self, bg_type: str = "linear",
                       params: Optional[Dict[str, float]] = None) -> None:
        """设置背景模型。

        Parameters
        ----------
        bg_type : str, optional
            背景类型，可选 ``'linear'``（线性，y = intercept + slope * x）
            或 ``'constant'``（常数，y = c），默认 ``'linear'``。
        params : Dict[str, float], optional
            背景参数的初始值，如 ``{"c": 0.1}`` 或
            ``{"intercept": 0.0, "slope": 0.0}``。
        """
        if bg_type not in ("constant", "linear"):
            raise ValueError(
                f"不支持的背景类型: '{bg_type}'。支持: 'constant', 'linear'"
            )
        self._bg_type = bg_type
        self._bg_params = params

    # ------------------------------------------------------------------
    # 构建复合模型
    # ------------------------------------------------------------------
    def _build_model(self) -> Tuple[Model, Parameters]:
        """构建 lmfit 复合模型并设置参数初值与边界。

        Returns
        -------
        Tuple[Model, Parameters]
            (复合模型对象, 参数对象)。
        """
        composite: Optional[Model] = None
        params = Parameters()

        # --- 添加各峰模型 ---
        for info in self._peaks:
            func = _LINESHAPE_MAP[info["lineshape"]]
            model = Model(func, prefix=info["prefix"],
                          independent_vars=["x"])
            if composite is None:
                composite = model
            else:
                composite += model

            # 设置初始值
            prefix = info["prefix"]
            params[f"{prefix}center"] = Parameter(
                name=f"{prefix}center", value=info["center"])
            params[f"{prefix}height"] = Parameter(
                name=f"{prefix}height", value=info["height"])
            params[f"{prefix}fwhm"] = Parameter(
                name=f"{prefix}fwhm", value=info["fwhm"],
                min=1e-12)  # FWHM 必须 > 0

            # 对 pseudo_voigt / gl_mixed 额外设置混合比例参数
            if info["lineshape"] == "pseudo_voigt":
                params[f"{prefix}fraction"] = Parameter(
                    name=f"{prefix}fraction", value=0.5,
                    min=0.0, max=1.0)
            elif info["lineshape"] == "gl_mixed":
                params[f"{prefix}mu"] = Parameter(
                    name=f"{prefix}mu", value=0.5,
                    min=0.0, max=1.0)

            # 应用用户自定义边界约束
            bounds = info["bounds"]
            for pname in ("center", "height", "fwhm"):
                if pname in bounds:
                    p = bounds[pname]
                    if "min" in p:
                        params[f"{prefix}{pname}"].min = p["min"]
                    if "max" in p:
                        params[f"{prefix}{pname}"].max = p["max"]

        # --- 添加背景模型 ---
        if self._bg_type != "none":
            bg_model = _make_background_model(self._bg_type)
            if composite is None:
                composite = bg_model
            else:
                composite += bg_model

            # 合并背景参数
            bg_params = bg_model.make_params()
            if self._bg_params:
                for name, val in self._bg_params.items():
                    if f"bg_{name}" in bg_params:
                        bg_params[f"bg_{name}"].value = val
                    elif name in bg_params:
                        bg_params[name].value = val
            params.update(bg_params)

        if composite is None:
            raise RuntimeError("未添加任何峰或背景模型，请先调用 add_peak() 或 set_background()")

        return composite, params

    # ------------------------------------------------------------------
    # 拟合
    # ------------------------------------------------------------------
    def fit(self, x: NDArray, y: NDArray) -> FitResult:
        """执行峰值拟合。

        Parameters
        ----------
        x : NDArray
            自变量数据（如波数、波长等）。
        y : NDArray
            因变量数据（如强度、吸光度等）。

        Returns
        -------
        FitResult
            包含拟合参数、统计量和各峰信息的拟合结果。
        """
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        model, params = self._build_model()
        lmfit_result = model.fit(y, params, x=x)

        return FitResult(lmfit_result, self._peaks, x, y)

    # ------------------------------------------------------------------
    # 绘图
    # ------------------------------------------------------------------
    def plot(self, x: NDArray, y: NDArray,
             ax: Optional[plt.Axes] = None) -> plt.Axes:
        """绘制拟合结果图，包含原始数据、总拟合曲线、
        各分峰曲线和残差子图。

        Parameters
        ----------
        x : NDArray
            自变量数据。
        y : NDArray
            因变量数据。
        ax : matplotlib.axes.Axes, optional
            绘图轴对象。若为 ``None`` 则新建图形和轴。

        Returns
        -------
        matplotlib.axes.Axes
            主图（数据+拟合）的 Axes 对象。
        """
        result = self.fit(x, y)

        if ax is None:
            fig, (ax_top, ax_bot) = plt.subplots(
                2, 1, figsize=(8, 6), gridspec_kw={"height_ratios": [3, 1]},
                sharex=True
            )
            ax = ax_top
        else:
            # 如果用户只提供了一个 ax，创建残差子图
            fig = ax.figure
            # 尝试获取已有的底部子图
            all_axes = fig.axes
            if len(all_axes) >= 2:
                ax_bot = all_axes[1]
            else:
                # 分割 ax 所在的子图
                from matplotlib.gridspec import GridSpecFromSubplotSpec
                gs = GridSpecFromSubplotSpec(
                    2, 1, subplot_spec=ax.get_subplotspec(),
                    height_ratios=[3, 1], hspace=0.05)
                ax.set_subplotspec(gs[0])
                ax_bot = fig.add_subplot(gs[1])

        # 主图：原始数据、总拟合、各分峰
        y_fit = result._result.best_fit
        ax.plot(x, y, "o", markersize=4, label="实验数据", color="C0", zorder=1)
        ax.plot(x, y_fit, "-", linewidth=2, label="总拟合", color="C1", zorder=3)

        # 绘制各分峰
        if self._bg_type != "none":
            # 计算背景单独分量
            bg_comp = result._result.eval_components().get("bg_", None)
            if bg_comp is None:
                # 对于 ConstantModel/LinearModel，前缀是 bg_
                for key, val in result._result.eval_components().items():
                    if key.startswith("bg_"):
                        bg_comp = val
                        break

        colors = ["C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
        for i, info in enumerate(self._peaks):
            prefix = info["prefix"]
            comp = result._result.eval_components().get(prefix, None)
            if comp is not None:
                ax.plot(x, comp, "--", linewidth=1.5,
                        label=f"峰 {i + 1} ({info['lineshape']})",
                        color=colors[i % len(colors)], zorder=2)

        ax.set_ylabel("强度 (Intensity)")
        ax.legend(fontsize=8, framealpha=0.8)
        ax.grid(True, alpha=0.3)

        # 残差子图
        residual = result.residual
        ax_bot.plot(x, residual, "o-", markersize=3, linewidth=0.8,
                    color="gray", label="残差")
        ax_bot.axhline(0, color="k", linewidth=0.5, linestyle="--")
        ax_bot.set_xlabel("自变量 X")
        ax_bot.set_ylabel("残差")
        ax_bot.grid(True, alpha=0.3)
        ax_bot.legend(fontsize=8)

        fig.tight_layout()
        return ax
