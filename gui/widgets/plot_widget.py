"""Matplotlib 嵌入 PySide6 的绘图控件。

根据运行环境自动选择后端：有显示器时用 Qt5Agg，否则用 Agg。
"""

import os
import matplotlib

# 自动选择后端
if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or not os.environ.get("DISPLAY"):
    matplotlib.use("Agg")
else:
    matplotlib.use("Qt5Agg")

from echem_core.plotting.fonts import configure_matplotlib_fonts
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget, QSizePolicy
from PySide6.QtCore import Qt

configure_matplotlib_fonts()


class PlotWidget(QWidget):
    """嵌入 Matplotlib 图表的 PySide6 控件。

    提供 FigureCanvas 和导航工具栏，支持交互式缩放/平移。
    """

    def __init__(self, parent=None, figsize=(5, 4), dpi=100):
        super().__init__(parent)
        self.figure = Figure(figsize=figsize, dpi=dpi)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        try:
            self.toolbar = NavigationToolbar(self.canvas, self)
            toolbar_visible = True
        except Exception:
            self.toolbar = QWidget()  # 占位
            toolbar_visible = False

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        if toolbar_visible:
            layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    @property
    def ax(self):
        """获取当前活动的坐标轴（自动创建）。"""
        if not self.figure.axes:
            self.figure.add_subplot(111)
        return self.figure.axes[0]

    def clear(self):
        """清除所有坐标轴。"""
        self.figure.clear()

    def refresh(self):
        """刷新画布。"""
        self.canvas.draw_idle()

    def save_figure(self, filepath):
        """保存当前图形到文件。"""
        self.figure.savefig(filepath, dpi=300, bbox_inches='tight')
