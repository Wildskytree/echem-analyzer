"""数据浏览与导入标签页。"""

import os
import numpy as np

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QFileDialog, QLabel, QTableWidget, QTableWidgetItem,
                               QSplitter, QLineEdit, QGroupBox, QHeaderView,
                               QMessageBox, QMenu, QGridLayout)
from PySide6.QtCore import Qt, Signal

from gui.widgets.measurement_list import MeasurementTreeWidget
from gui.widgets.analysis_common import measurement_label, measurement_name, technique_value
from echem_core.io.chi_parser import parse_chi_file
from echem_core.io.corrtest_parser import parse_corrtest_file
from echem_core.io.csv_parser import parse_csv


class DataBrowserTab(QWidget):
    """数据浏览与导入标签页。

    支持拖放导入、文件选择、数据预览、搜索过滤和右键菜单。
    """

    measurement_imported = Signal(object)  # Measurement
    measurements_changed = Signal(list)    # List[Measurement]
    analysis_requested = Signal(str)       # 技术类型

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._measurements = []
        self._last_imported = None
        self._drop_highlight = False
        self._default_style_sheet = self.styleSheet()
        self._setup_ui()

    def dragEnterEvent(self, event):
        """接受从文件管理器拖入的 txt/csv 文件。"""
        if self._drop_file_paths(event):
            self._set_drop_highlight(True)
            event.acceptProposedAction()
        else:
            self._set_drop_highlight(False)
            event.ignore()

    def dragMoveEvent(self, event):
        if self._drop_file_paths(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drop_highlight(False)
        event.accept()

    def dropEvent(self, event):
        """解析并导入拖放的 txt/csv 文件。"""
        paths = self._drop_file_paths(event)
        self._set_drop_highlight(False)
        if not paths:
            event.ignore()
            return
        for filepath in paths:
            self._parse_and_add(filepath)
        event.acceptProposedAction()

    def _drop_file_paths(self, event):
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            return []
        paths = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            filepath = url.toLocalFile()
            if filepath.lower().endswith((".txt", ".csv")):
                paths.append(filepath)
        return paths

    def _set_drop_highlight(self, enabled):
        if self._drop_highlight == enabled:
            return
        self._drop_highlight = enabled
        if enabled:
            self.setStyleSheet(
                "DataBrowserTab { background-color: #e8f4ff; "
                "border: 2px dashed #2f80ed; }"
            )
        else:
            self.setStyleSheet(self._default_style_sheet)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 工具栏 ---
        toolbar = QHBoxLayout()
        self.btn_import_files = QPushButton("📂 导入文件")
        self.btn_import_folder = QPushButton("📁 导入文件夹")
        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_delete = QPushButton("❌ 删除选中")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 搜索文件名...")
        self.search_box.textChanged.connect(self._filter_measurements)

        toolbar.addWidget(self.btn_import_files)
        toolbar.addWidget(self.btn_import_folder)
        toolbar.addWidget(self.btn_delete)
        toolbar.addWidget(self.btn_clear)
        toolbar.addStretch()
        toolbar.addWidget(self.search_box)

        self.btn_import_files.clicked.connect(self._import_files)
        self.btn_import_folder.clicked.connect(self._import_folder)
        self.btn_clear.clicked.connect(self._clear_all)
        self.btn_delete.clicked.connect(self._delete_selected)

        # --- 分割布局：文件列表 + 数据预览 ---
        splitter = QSplitter(Qt.Vertical)

        # 文件列表
        list_group = QGroupBox("测量数据列表")
        list_layout = QVBoxLayout(list_group)
        self.tree = MeasurementTreeWidget()
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        list_layout.addWidget(self.tree)

        # 数据预览
        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_label = QLabel("请选择一个测量文件以预览数据")
        self.preview_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.preview_table)
        self.preview_table.hide()

        splitter.addWidget(list_group)
        splitter.addWidget(preview_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # --- 快速开始 ---
        quick_group = QGroupBox("快速开始")
        quick_layout = QGridLayout(quick_group)
        self.lbl_quick_summary = QLabel("尚未导入数据。请先导入 CHI txt 或 CSV 文件。")
        self.lbl_quick_recent = QLabel("最近导入: -")
        self.btn_open_lsv = QPushButton("打开 LSV 分析")
        self.btn_open_cv = QPushButton("打开 CV 分析")
        self.btn_open_eis = QPushButton("打开 EIS 分析")
        self.btn_open_stability = QPushButton("打开稳定性分析")
        for btn, tech in (
            (self.btn_open_lsv, "LSV"),
            (self.btn_open_cv, "CV"),
            (self.btn_open_eis, "EIS"),
            (self.btn_open_stability, "STABILITY"),
        ):
            btn.clicked.connect(lambda _checked=False, t=tech: self.analysis_requested.emit(t))
        quick_layout.addWidget(self.lbl_quick_summary, 0, 0, 1, 4)
        quick_layout.addWidget(self.lbl_quick_recent, 1, 0, 1, 4)
        quick_layout.addWidget(self.btn_open_lsv, 2, 0)
        quick_layout.addWidget(self.btn_open_cv, 2, 1)
        quick_layout.addWidget(self.btn_open_eis, 2, 2)
        quick_layout.addWidget(self.btn_open_stability, 2, 3)
        self._refresh_quick_start()

        main_layout.addLayout(toolbar)
        main_layout.addWidget(splitter)
        main_layout.addWidget(quick_group)

        # 连接信号
        self.tree.measurement_selected.connect(self._show_preview)

    def _import_files(self):
        """导入单个或多个文件。"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择电化学数据文件", "",
            "数据文件 (*.txt *.csv);;所有文件 (*)"
        )
        if not files:
            return
        for fp in files:
            self._parse_and_add(fp)

    def _import_folder(self):
        """导入文件夹中所有支持的文件。"""
        folder = QFileDialog.getExistingDirectory(self, "选择数据文件夹")
        if not folder:
            return
        for fname in sorted(os.listdir(folder)):
            if fname.lower().endswith(('.txt', '.csv')):
                self._parse_and_add(os.path.join(folder, fname))

    def _parse_and_add(self, filepath):
        """解析文件并添加到列表。"""
        last_error = None
        ext = os.path.splitext(filepath)[1].lower()

        # Try each parser in order.
        if ext == '.txt':
            parsers = [parse_chi_file, parse_corrtest_file]
        else:
            parsers = [parse_csv]

        for parser in parsers:
            try:
                m = parser(filepath)
                self._measurements.append(m)
                self._last_imported = m
                self.tree.add_measurement(m)
                self.tree.select_measurement(m)
                self.measurement_imported.emit(m)
                self.measurements_changed.emit(self.get_all_measurements())
                self._refresh_quick_start()
                return m
            except Exception as e:
                last_error = e
                continue

        if last_error is not None:
            QMessageBox.warning(self, "导入失败",
                                f"无法导入文件:\n{os.path.basename(filepath)}\n\n错误: {last_error}")
        return None

    def _clear_all(self):
        """清空所有数据。"""
        self._measurements.clear()
        self._last_imported = None
        self.tree.clear_measurements()
        self._clear_preview()
        self.measurements_changed.emit([])
        self._refresh_quick_start()

    def _delete_selected(self):
        """删除选中的数据。"""
        removed = self.tree.remove_selected()
        if not removed:
            return
        removed_ids = {id(m) for m in removed}
        self._measurements = [m for m in self._measurements if id(m) not in removed_ids]
        if self._last_imported is not None and id(self._last_imported) in removed_ids:
            self._last_imported = self._measurements[-1] if self._measurements else None
        self._clear_preview()
        self.measurements_changed.emit(self.get_all_measurements())
        self._refresh_quick_start()

    def _filter_measurements(self, text):
        """搜索过滤文件名。"""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            haystack = " ".join(item.text(c) for c in range(item.columnCount()))
            item.setHidden(text.lower() not in haystack.lower())

    def _show_preview(self, measurement):
        """在预览表中显示数据。"""
        if measurement is None:
            self._clear_preview()
            return
        tech = technique_value(measurement)
        pot = measurement.processed_potential if measurement.processed_potential is not None else measurement.raw_potential
        cur = measurement.processed_current if measurement.processed_current is not None else measurement.raw_current
        t = measurement.raw_time

        n_points = len(pot)
        display_points = min(n_points, 1000)

        if tech == "EIS":
            self.preview_table.setColumnCount(3)
            self.preview_table.setHorizontalHeaderLabels(["频率 (Hz)", "Z' (Ω)", "Z'' (Ω)"])
        elif tech == "CA":
            self.preview_table.setColumnCount(2)
            self.preview_table.setHorizontalHeaderLabels(["时间 (s)", "电流 (A)"])
        elif tech == "CP":
            self.preview_table.setColumnCount(2)
            self.preview_table.setHorizontalHeaderLabels(["时间 (s)", "电位 (V)"])
        elif t is not None:
            self.preview_table.setColumnCount(3)
            self.preview_table.setHorizontalHeaderLabels(["电位 (V)", "电流 (A)", "时间 (s)"])
        else:
            self.preview_table.setColumnCount(2)
            self.preview_table.setHorizontalHeaderLabels(["电位 (V)", "电流 (A)"])

        self.preview_table.setRowCount(display_points)
        step = max(1, n_points // display_points)
        for i in range(display_points):
            idx = min(i * step, n_points - 1)
            if tech == "EIS":
                self.preview_table.setItem(i, 0, QTableWidgetItem(f"{pot[idx]:.6g}"))
                self.preview_table.setItem(i, 1, QTableWidgetItem(f"{cur[idx]:.6g}"))
                z_imag = t[idx] if t is not None else float("nan")
                self.preview_table.setItem(i, 2, QTableWidgetItem(f"{z_imag:.6g}"))
            elif tech == "CP":
                x_val = t[idx] if t is not None else idx
                self.preview_table.setItem(i, 0, QTableWidgetItem(f"{x_val:.6f}"))
                self.preview_table.setItem(i, 1, QTableWidgetItem(f"{pot[idx]:.6f}"))
            else:
                self.preview_table.setItem(i, 0, QTableWidgetItem(f"{pot[idx]:.6f}"))
                self.preview_table.setItem(i, 1, QTableWidgetItem(f"{cur[idx]:.6e}"))
            if tech not in ("EIS", "CA", "CP") and t is not None and i < display_points:
                idx_t = min(i * step, len(t) - 1)
                self.preview_table.setItem(i, 2, QTableWidgetItem(f"{t[idx_t]:.6f}"))

        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.preview_label.hide()
        self.preview_table.show()

    def _clear_preview(self):
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.hide()
        self.preview_label.setText("请选择一个测量文件以预览数据")
        self.preview_label.show()

    def _refresh_quick_start(self):
        counts = {}
        for measurement in self._measurements:
            tech = technique_value(measurement)
            if tech in ("CA", "CP"):
                counts["STABILITY"] = counts.get("STABILITY", 0) + 1
            counts[tech] = counts.get(tech, 0) + 1

        total = len(self._measurements)
        if total == 0:
            self.lbl_quick_summary.setText("尚未导入数据。请先导入 CHI txt 或 CSV 文件。")
            self.lbl_quick_recent.setText("最近导入: -")
        else:
            detail = "，".join(
                f"{tech}: {count}" for tech, count in sorted(counts.items()) if tech != "STABILITY"
            )
            self.lbl_quick_summary.setText(f"已导入 {total} 个测量数据。{detail}")
            recent = measurement_label(self._last_imported) if self._last_imported else "-"
            self.lbl_quick_recent.setText(f"最近导入: {recent}")

        self.btn_open_lsv.setEnabled(counts.get("LSV", 0) > 0)
        self.btn_open_cv.setEnabled(counts.get("CV", 0) > 0)
        self.btn_open_eis.setEnabled(counts.get("EIS", 0) > 0)
        self.btn_open_stability.setEnabled(counts.get("STABILITY", 0) > 0)

    def select_measurement(self, measurement):
        self.tree.select_measurement(measurement)

    def _show_context_menu(self, pos):
        """右键菜单。"""
        item = self.tree.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_process = menu.addAction("⚙️ 处理...")
        act_plot = menu.addAction("📈 绘图...")
        menu.addSeparator()
        act_export = menu.addAction("💾 导出数据")
        menu.addSeparator()
        act_delete = menu.addAction("❌ 删除")
        action = menu.exec(self.tree.mapToGlobal(pos))
        if action == act_delete:
            self._delete_selected()

    def get_all_measurements(self):
        return list(self._measurements)
