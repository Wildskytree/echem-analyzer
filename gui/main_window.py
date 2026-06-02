"""Echem Analyzer 主窗口。"""

import os
import sys
from PySide6.QtWidgets import (QMainWindow, QTabWidget, QStatusBar,
                               QMenuBar, QMenu, QToolBar, QMessageBox,
                               QFileDialog, QVBoxLayout, QWidget, QLabel,
                               QSplitter, QApplication, QStyleFactory)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QKeySequence, QIcon, QPalette, QColor

from gui.tabs.data_browser_tab import DataBrowserTab
from gui.tabs.lsv_tab import LSVTab
from gui.tabs.cv_tab import CVTab
from gui.tabs.eis_tab import EISTab
from gui.tabs.stability_tab import StabilityTab
from gui.tabs.batch_tab import BatchTab
from gui.tabs.project_tab import ProjectTab


class MainWindow(QMainWindow):
    """Echem Analyzer 主窗口。"""

    APP_NAME = "Echem Analyzer — 电化学数据分析工具"
    APP_VERSION = "0.1.0"

    def __init__(self):
        super().__init__()
        self._dark_theme = False
        self._setup_window()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_statusbar()
        self._apply_theme()

    def _setup_window(self):
        """设置窗口基本属性。"""
        self.setWindowTitle(self.APP_NAME)
        self.setMinimumSize(1280, 820)
        self.resize(1500, 950)
        # 启用 HiDPI 支持
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    def _setup_menubar(self):
        """构建菜单栏。"""
        menubar = self.menuBar()

        # ── 文件菜单 ──
        file_menu = menubar.addMenu("文件(&F)")

        self.act_import = QAction("📂 导入文件...", self)
        self.act_import.setShortcut(QKeySequence("Ctrl+O"))
        self.act_import.triggered.connect(self._import_files)
        file_menu.addAction(self.act_import)

        self.act_import_folder = QAction("📁 导入文件夹...", self)
        self.act_import_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.act_import_folder.triggered.connect(self._import_folder)
        file_menu.addAction(self.act_import_folder)

        file_menu.addSeparator()

        self.act_save_project = QAction("💾 保存项目...", self)
        self.act_save_project.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save_project.triggered.connect(self._save_project)
        file_menu.addAction(self.act_save_project)

        self.act_load_project = QAction("📂 加载项目...", self)
        self.act_load_project.setShortcut(QKeySequence("Ctrl+O"))
        self.act_load_project.triggered.connect(self._load_project)
        file_menu.addAction(self.act_load_project)

        file_menu.addSeparator()

        self.act_export_report = QAction("📊 导出报告...", self)
        self.act_export_report.triggered.connect(self._export_report)
        file_menu.addAction(self.act_export_report)

        file_menu.addSeparator()

        self.act_exit = QAction("退出(&X)", self)
        self.act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_exit.triggered.connect(self.close)
        file_menu.addAction(self.act_exit)

        # ── 编辑菜单 ──
        edit_menu = menubar.addMenu("编辑(&E)")
        self.act_clear = QAction("🗑️ 清空所有数据", self)
        self.act_clear.triggered.connect(self._clear_all)
        edit_menu.addAction(self.act_clear)

        # ── 视图菜单 ──
        view_menu = menubar.addMenu("视图(&V)")
        self.act_toggle_theme = QAction("🌙 切换暗色主题", self)
        self.act_toggle_theme.setShortcut(QKeySequence("Ctrl+T"))
        self.act_toggle_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(self.act_toggle_theme)

        # ── 工具菜单 ──
        tools_menu = menubar.addMenu("工具(&T)")
        self.act_batch = QAction("⚙️ 批量处理", self)
        self.act_batch.triggered.connect(lambda: self.tab_widget.setCurrentWidget(self.batch_tab))
        tools_menu.addAction(self.act_batch)

        # ── 帮助菜单 ──
        help_menu = menubar.addMenu("帮助(&H)")
        self.act_about = QAction("关于 Echem Analyzer", self)
        self.act_about.triggered.connect(self._show_about)
        help_menu.addAction(self.act_about)

    def _setup_toolbar(self):
        """构建快捷工具栏。"""
        toolbar = QToolBar("快捷工具栏")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction(self.act_import)
        toolbar.addAction(self.act_save_project)
        toolbar.addSeparator()
        act_lsv = QAction("📈 LSV", self)
        act_lsv.triggered.connect(lambda: self.tab_widget.setCurrentWidget(self.lsv_tab))
        toolbar.addAction(act_lsv)

        act_cv = QAction("📊 CV", self)
        act_cv.triggered.connect(lambda: self.tab_widget.setCurrentWidget(self.cv_tab))
        toolbar.addAction(act_cv)

        act_eis = QAction("🔄 EIS", self)
        act_eis.triggered.connect(lambda: self.tab_widget.setCurrentWidget(self.eis_tab))
        toolbar.addAction(act_eis)

        act_stability = QAction("⏱ 稳定性", self)
        act_stability.triggered.connect(lambda: self.tab_widget.setCurrentWidget(self.stability_tab))
        toolbar.addAction(act_stability)

        toolbar.addSeparator()
        toolbar.addAction(self.act_toggle_theme)

    def _setup_central_widget(self):
        """构建主内容区域。"""
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建所有标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        self.data_browser_tab = DataBrowserTab()
        self.lsv_tab = LSVTab()
        self.cv_tab = CVTab()
        self.eis_tab = EISTab()
        self.stability_tab = StabilityTab()
        self.batch_tab = BatchTab()
        self.project_tab = ProjectTab()

        self.tab_widget.addTab(self.data_browser_tab, "📂 数据浏览")
        self.tab_widget.addTab(self.lsv_tab, "📈 LSV")
        self.tab_widget.addTab(self.cv_tab, "📊 CV 分析")
        self.tab_widget.addTab(self.eis_tab, "🔄 EIS")
        self.tab_widget.addTab(self.stability_tab, "⏱ 稳定性")
        self.tab_widget.addTab(self.batch_tab, "⚙️ 批量处理")
        self.tab_widget.addTab(self.project_tab, "💼 项目")

        # 连接信号：数据浏览器选择变化时更新各分析标签页
        self.data_browser_tab.tree.measurement_selected.connect(
            self._on_measurement_selected)
        self.data_browser_tab.measurements_changed.connect(
            self._on_measurements_changed)
        self.data_browser_tab.analysis_requested.connect(
            self._open_analysis_tab)
        self.data_browser_tab.measurement_imported.connect(
            lambda m: self.project_tab.log_event(f"导入: {m.metadata.get('sample_name', '?')}"))

        layout.addWidget(self.tab_widget)
        self.setCentralWidget(central)

    def _setup_statusbar(self):
        """构建状态栏。"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_status = QLabel("就绪")
        self.lbl_count = QLabel("测量数: 0")
        self.status_bar.addWidget(self.lbl_status, 1)
        self.status_bar.addPermanentWidget(self.lbl_count)

    # ── 事件处理 ──

    def _on_measurement_selected(self, measurement):
        """当在数据浏览器中选择测量时更新各标签页。"""
        if measurement is None:
            return
        tech = measurement.technique.value if hasattr(measurement.technique, 'value') else str(measurement.technique)
        name = measurement.metadata.get("sample_name", "未知")
        self.lbl_status.setText(f"已选择: {name} ({tech})")
        self.lbl_count.setText(f"测量数: {len(self.data_browser_tab.get_all_measurements())}")

        # 根据技术类型更新对应的分析标签页
        if tech == "LSV":
            self.lsv_tab.set_measurement(measurement)
        elif tech == "CV":
            self.cv_tab.set_measurement(measurement)
        elif tech == "EIS":
            self.eis_tab.set_measurement(measurement)
        elif tech in ("CA", "CP"):
            self.stability_tab.set_measurement(measurement)

    def _on_measurements_changed(self, measurements):
        """导入、删除或清空数据后同步所有分析标签页的文件下拉框。"""
        measurements = list(measurements)
        self.lbl_count.setText(f"测量数: {len(measurements)}")
        self.lsv_tab.set_measurements(measurements)
        self.cv_tab.set_measurements(measurements)
        self.eis_tab.set_measurements(measurements)
        self.stability_tab.set_measurements(measurements)

    def _open_analysis_tab(self, tech):
        """从数据浏览器快速入口切换到对应分析标签页。"""
        tab_map = {
            "LSV": self.lsv_tab,
            "CV": self.cv_tab,
            "EIS": self.eis_tab,
            "STABILITY": self.stability_tab,
            "CA": self.stability_tab,
            "CP": self.stability_tab,
        }
        tab = tab_map.get(tech)
        if tab is not None:
            self.tab_widget.setCurrentWidget(tab)

    def _import_files(self):
        """菜单触发的导入文件。"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "导入电化学数据文件", "",
            "数据文件 (*.txt *.csv);;所有文件 (*)")
        if files:
            self.data_browser_tab.import_paths(files)

    def _import_folder(self):
        self.data_browser_tab._import_folder()

    def _save_project(self):
        self.project_tab._save_project()

    def _load_project(self):
        self.project_tab._load_project()

    def _export_report(self):
        self.project_tab._export_report()

    def _clear_all(self):
        reply = QMessageBox.question(self, "确认清空",
                                     "确定要清空所有导入的数据吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.data_browser_tab._clear_all()
            self.lbl_count.setText("测量数: 0")
            self.lbl_status.setText("已清空所有数据")

    def _toggle_theme(self):
        """切换暗色/亮色主题。"""
        self._dark_theme = not self._dark_theme
        self._apply_theme()
        act = self.act_toggle_theme
        act.setText("☀️ 切换亮色主题" if self._dark_theme else "🌙 切换暗色主题")

    def _apply_theme(self):
        """应用当前主题。"""
        app = QApplication.instance()
        if self._dark_theme:
            app.setStyle(QStyleFactory.create("Fusion"))
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            app.setPalette(palette)
        else:
            app.setStyle(QStyleFactory.create("Fusion"))
            app.setPalette(app.style().standardPalette())

    def _show_about(self):
        """显示关于对话框。"""
        QMessageBox.about(self, "关于 Echem Analyzer",
                         f"<h2>Echem Analyzer</h2>"
                         f"<p><b>版本:</b> {self.APP_VERSION}</p>"
                         f"<p>电化学数据分析桌面工具</p>"
                         f"<p>技术栈: PySide6 + Matplotlib + NumPy/SciPy</p>"
                         f"<p>支持 LSV、CV、EIS、CA/CP 稳定性分析</p>"
                         f"<hr><p>© 2026 Echem Analyzer Team</p>")

    def closeEvent(self, event):
        """窗口关闭事件。"""
        reply = QMessageBox.question(self, "确认退出",
                                     "确定要退出 Echem Analyzer 吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


def run_app():
    """启动应用的主函数。"""
    # HiDPI 支持
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("Echem Analyzer")
    app.setOrganizationName("Echem Analyzer Team")
    app.setStyle(QStyleFactory.create("Fusion"))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
