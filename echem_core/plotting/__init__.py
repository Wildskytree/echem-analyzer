"""电化学绘图模块。

提供期刊风格的 CV 曲线绘制、峰标注和多曲线比较功能。
"""

from echem_core.plotting.cv_plot import plot_cv, plot_cv_comparison
from echem_core.plotting.styles import (
    ACS_DOUBLE,
    ACS_SINGLE,
    RSC,
    WILEY,
    JournalStyle,
    get_style,
    list_styles,
)

__all__ = [
    "plot_cv",
    "plot_cv_comparison",
    "JournalStyle",
    "ACS_SINGLE",
    "ACS_DOUBLE",
    "RSC",
    "WILEY",
    "get_style",
    "list_styles",
]
