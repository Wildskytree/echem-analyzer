"""
期刊绘图风格配置模块。

提供 JournalStyle 类，用于将预配置的期刊出版风格应用于 Matplotlib 坐标轴。
内置风格包括 ACS（单栏/双栏）、RSC 和 Wiley 的常见投稿尺寸。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import matplotlib as mpl

from echem_core.plotting.fonts import configure_matplotlib_fonts

# 黄金分割比 (φ)
_GOLDEN_RATIO = 1.618

configure_matplotlib_fonts()


# ── 色盲友好型 8 色调色板（Wong, 2011, Nature Methods） ──────────────────
_COLORBLIND_SAFE_PALETTE = [
    "#000000",  # 黑色
    "#E69F00",  # 橙色
    "#56B4E9",  # 天蓝
    "#009E73",  # 蓝绿
    "#F0E442",  # 黄色
    "#0072B2",  # 蓝色
    "#D55E00",  # 朱红
    "#CC79A7",  # 紫红
]


def _mm_to_inches(mm: float) -> float:
    """将毫米转换为英寸（Matplotlib 中图形尺寸使用英寸）。"""
    return mm / 25.4


def _golden_height(width_mm: float) -> float:
    """根据宽度（毫米）按黄金分割比自动计算高度（毫米）。"""
    return width_mm / _GOLDEN_RATIO


@dataclass
class JournalStyle:
    """期刊绘图风格配置。

    封装了投稿期刊所需的图形尺寸、字体、分辨率及配色方案。
    通过 :meth:`apply` 方法将风格应用到指定的 Matplotlib 坐标轴。

    Attributes
    ----------
    name : str
        风格名称。
    width_mm : float
        图形宽度（毫米）。
    height_mm : float
        图形高度（毫米）；若未指定，按黄金分割比自动计算。
    font_family : str
        字体家族名称，例如 ``"sans-serif"``、``"Arial"``。
    font_size : int
        坐标轴刻度标签的基础字号（磅）。
    dpi : int
        输出图片的分辨率（每英寸点数）。
    colors : list[str]
        色盲友好的配色列表（8 种颜色）。
    line_width : float
        数据线宽（磅）。
    """

    name: str
    width_mm: float
    height_mm: Optional[float] = None
    font_family: str = "sans-serif"
    font_size: int = 10
    dpi: int = 300
    colors: List[str] = field(default_factory=lambda: _COLORBLIND_SAFE_PALETTE.copy())
    line_width: float = 1.5

    def __post_init__(self) -> None:
        """若未指定高度，按黄金分割比自动计算。"""
        if self.height_mm is None:
            self.height_mm = _golden_height(self.width_mm)

    def apply(self, ax) -> None:
        """将当前风格应用到指定的 Matplotlib 坐标轴。

        设置内容：
            - 图形尺寸（英寸）
            - 字体家族与字号
            - 刻度标签字号
            - 标题字号
            - 坐标轴标签字号
            - 线宽（``rcParams["lines.linewidth"]``）
            - 风格颜色为默认颜色循环（仅该坐标轴）
            - 图片分辨率（DPI）

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            需要应用风格的 Matplotlib 坐标轴对象。
        """
        fig = ax.figure

        # 安全取值：若图尚未挂接到 figure，则 __post_init__ 保证 height_mm 为 float
        h_mm = self.height_mm if self.height_mm is not None else _golden_height(self.width_mm)

        fig.set_size_inches(_mm_to_inches(self.width_mm), _mm_to_inches(h_mm))

        # ── rcParams 全局设置 ──────────────────────────────────────────
        configure_matplotlib_fonts()
        mpl.rcParams["font.family"] = self.font_family
        mpl.rcParams["font.size"] = self.font_size
        mpl.rcParams["axes.labelsize"] = self.font_size + 1
        mpl.rcParams["axes.titlesize"] = self.font_size + 3
        mpl.rcParams["xtick.labelsize"] = self.font_size - 1
        mpl.rcParams["ytick.labelsize"] = self.font_size - 1
        mpl.rcParams["lines.linewidth"] = self.line_width
        mpl.rcParams["figure.dpi"] = self.dpi
        mpl.rcParams["savefig.dpi"] = self.dpi

        # ── 该坐标轴的颜色循环 ──────────────────────────────────────────
        ax.set_prop_cycle(color=self.colors)

        # ── 刻度线方向 ──────────────────────────────────────────────────
        ax.tick_params(direction="in", which="both")


# ── 内置期刊风格常量 ─────────────────────────────────────────────────────

ACS_SINGLE = JournalStyle(
    name="ACS_SINGLE",
    width_mm=85,
    font_family="sans-serif",
    font_size=8,
    line_width=1.0,
)

ACS_DOUBLE = JournalStyle(
    name="ACS_DOUBLE",
    width_mm=178,
    font_family="sans-serif",
    font_size=9,
    line_width=1.2,
)

RSC = JournalStyle(
    name="RSC",
    width_mm=84,
    font_family="sans-serif",
    font_size=8,
    line_width=1.0,
)

WILEY = JournalStyle(
    name="WILEY",
    width_mm=169,
    font_family="sans-serif",
    font_size=9,
    line_width=1.2,
)

# ── 风格注册表 ──────────────────────────────────────────────────────────

_STYLE_REGISTRY: Dict[str, JournalStyle] = {
    s.name: s
    for s in [ACS_SINGLE, ACS_DOUBLE, RSC, WILEY]
}


def list_styles() -> List[JournalStyle]:
    """返回所有已注册的期刊风格列表。

    Returns
    -------
    list[JournalStyle]
        所有内置风格对象。
    """
    return list(_STYLE_REGISTRY.values())


def get_style(name: str) -> JournalStyle:
    """按名称获取已注册的期刊风格。

    Parameters
    ----------
    name : str
        风格名称，例如 ``"ACS_SINGLE"``、``"RSC"``。

    Returns
    -------
    JournalStyle
        匹配的风格对象。

    Raises
    ------
    KeyError
        未找到对应名称的风格。
    """
    if name not in _STYLE_REGISTRY:
        raise KeyError(
            f"未知风格: '{name}'。可用风格: {list(_STYLE_REGISTRY.keys())}"
        )
    return _STYLE_REGISTRY[name]


__all__ = [
    "JournalStyle",
    "ACS_SINGLE",
    "ACS_DOUBLE",
    "RSC",
    "WILEY",
    "list_styles",
    "get_style",
]
