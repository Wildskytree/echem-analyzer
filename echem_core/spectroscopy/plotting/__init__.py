"""光谱绘图模块。

提供期刊风格的光谱曲线绘制、峰标注和多曲线比较功能。
"""

from echem_core.spectroscopy.plotting.spectrum_plot import (
    plot_spectra_comparison,
    plot_spectrum,
)

__all__ = [
    "plot_spectrum",
    "plot_spectra_comparison",
]
