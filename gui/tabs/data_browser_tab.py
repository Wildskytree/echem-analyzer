"""数据浏览与导入标签页。"""

import os
import numpy as np

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QFileDialog, QLabel, QTableWidget, QTableWidgetItem,
                               QSplitter, QLineEdit, QGroupBox, QHeaderView,
                               QMessageBox, QMenu, QGridLayout, QProgressDialog)
from PySide6.QtCore import Qt, QObject, QThread, Signal, Slot

from gui.widgets.measurement_list import MeasurementTreeWidget
from gui.widgets.analysis_common import measurement_label, measurement_name, technique_value
from echem_core.io.chi_parser import parse_chi_file
from echem_core.io.corrtest_parser import parse_corrtest_file
from echem_core.io.csv_parser import parse_csv
from echem_core.model import Technique


def _parse_measurement_file(filepath):
    """Parse a supported measurement file without touching GUI objects."""
    last_error = None
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".txt":
        parsers = [parse_chi_file, parse_corrtest_file]
    elif ext == ".csv":
        parsers = [parse_csv]
    else:
        raise ValueError(f"不支持的文件类型: {ext or '无扩展名'}")

    for parser in parsers:
        try:
            return parser(filepath)
        except Exception as exc:
            last_error = exc

    raise ValueError(str(last_error) if last_error is not None else "无法识别文件格式")


class FileImportWorker(QObject):
    """Background parser for batch imports."""

    progress = Signal(int, int, str)
    imported = Signal(object, str)
    failed = Signal(str, str)
    finished = Signal(int, int, bool)

    def __init__(self, paths):
        super().__init__()
        self._paths = list(paths)
        self._cancelled = False

    @Slot()
    def run(self):
        success_count = 0
        failure_count = 0
        total = len(self._paths)

        for index, filepath in enumerate(self._paths, start=1):
            if self._cancelled:
                break

            basename = os.path.basename(filepath)
            self.progress.emit(index - 1, total, basename)
            try:
                measurement = _parse_measurement_file(filepath)
            except Exception as exc:
                failure_count += 1
                self.failed.emit(filepath, str(exc))
            else:
                success_count += 1
                self.imported.emit(measurement, filepath)
            self.progress.emit(index, total, basename)

        self.finished.emit(success_count, failure_count, self._cancelled)

    def cancel(self):
        self._cancelled = True


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
        self._import_thread = None
        self._import_worker = None
        self._progress_dialog = None
        self._import_failures = []
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
        self.import_paths(paths)
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
        self.import_paths(files)

    def _import_folder(self):
        """导入文件夹中所有支持的文件。"""
        folder = QFileDialog.getExistingDirectory(self, "选择数据文件夹")
        if not folder:
            return
        paths = [
            os.path.join(folder, fname)
            for fname in sorted(os.listdir(folder))
            if fname.lower().endswith((".txt", ".csv"))
        ]
        self.import_paths(paths)

    def import_paths(self, paths):
        """后台导入一个或多个文件。"""
        paths = [
            path for path in paths
            if path and os.path.isfile(path) and path.lower().endswith((".txt", ".csv"))
        ]
        if not paths:
            QMessageBox.information(self, "导入文件", "没有找到支持的 .txt 或 .csv 文件。")
            return
        if self._import_thread is not None and self._import_thread.isRunning():
            QMessageBox.information(self, "正在导入", "已有导入任务正在运行，请等待完成或取消。")
            return

        self._import_failures = []
        self._set_import_controls_enabled(False)
        self.tree.setSortingEnabled(False)

        self._progress_dialog = QProgressDialog("准备导入...", "取消", 0, len(paths), self)
        self._progress_dialog.setWindowTitle("导入数据")
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setAutoClose(False)
        self._progress_dialog.setAutoReset(False)
        self._progress_dialog.show()

        thread = QThread(self)
        worker = FileImportWorker(paths)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_import_progress)
        worker.imported.connect(self._on_worker_imported)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(self._on_import_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_import_thread_finished)
        self._progress_dialog.canceled.connect(lambda: worker.cancel())

        self._import_thread = thread
        self._import_worker = worker
        thread.start()

    def _parse_and_add(self, filepath):
        """解析文件并添加到列表。"""
        try:
            measurement = _parse_measurement_file(filepath)
            self._add_measurement(measurement, select=True, emit_changed=True)
            return measurement
        except Exception as last_error:
            QMessageBox.warning(self, "导入失败",
                                f"无法导入文件:\n{os.path.basename(filepath)}\n\n错误: {last_error}")
            return None

    def _add_measurement(self, measurement, select=False, emit_changed=False):
        self._measurements.append(measurement)
        self._last_imported = measurement
        self.tree.add_measurement(measurement)
        self.measurement_imported.emit(measurement)
        if emit_changed:
            self.measurements_changed.emit(self.get_all_measurements())
        self._refresh_quick_start()
        if select:
            self.tree.select_measurement(measurement)

    def _set_import_controls_enabled(self, enabled):
        self.btn_import_files.setEnabled(enabled)
        self.btn_import_folder.setEnabled(enabled)
        self.btn_clear.setEnabled(enabled)
        self.btn_delete.setEnabled(enabled)

    def _on_import_progress(self, current, total, filename):
        dialog = self._progress_dialog
        if dialog is None:
            return
        dialog.setMaximum(total)
        dialog.setLabelText(
            f"正在导入 {current + 1 if current < total else current}/{total}: {filename}"
        )
        dialog.setValue(current)

    def _on_worker_imported(self, measurement, _filepath):
        self._add_measurement(measurement, select=False, emit_changed=False)

    def _on_worker_failed(self, filepath, error):
        self._import_failures.append((filepath, error))

    def _on_import_finished(self, success_count, failure_count, cancelled):
        self.tree.setSortingEnabled(True)
        self._set_import_controls_enabled(True)

        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog.deleteLater()
            self._progress_dialog = None

        self._refresh_quick_start()
        self.measurements_changed.emit(self.get_all_measurements())
        if self._last_imported is not None:
            self.tree.select_measurement(self._last_imported)

        if failure_count:
            shown = self._import_failures[:5]
            detail = "\n".join(
                f"{os.path.basename(path)}: {error}" for path, error in shown
            )
            more = "" if len(self._import_failures) <= 5 else f"\n...另有 {len(self._import_failures) - 5} 个失败"
            QMessageBox.warning(
                self,
                "导入完成",
                f"成功导入 {success_count} 个文件，失败 {failure_count} 个。"
                f"{' 已取消。' if cancelled else ''}\n\n{detail}{more}",
            )
        elif cancelled:
            QMessageBox.information(self, "导入已取消", f"已导入 {success_count} 个文件。")

    def _on_import_thread_finished(self):
        self._import_thread = None
        self._import_worker = None

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
        measurement = self.tree.measurement_for_item(item)
        if measurement is None:
            return
        if not item.isSelected():
            self.tree.clearSelection()
            item.setSelected(True)
            self.tree.setCurrentItem(item)

        menu = QMenu(self)
        act_process = menu.addAction("⚙️ 处理...")
        act_plot = menu.addAction("📈 绘图...")
        menu.addSeparator()
        type_menu = menu.addMenu("修改数据类型")
        type_actions = {}
        current_tech = technique_value(measurement)
        for technique in Technique:
            action = type_menu.addAction(technique.value)
            action.setCheckable(True)
            action.setChecked(technique.value == current_tech)
            type_actions[action] = technique
        menu.addSeparator()
        act_export = menu.addAction("💾 导出数据")
        menu.addSeparator()
        act_delete = menu.addAction("❌ 删除")
        action = menu.exec(self.tree.mapToGlobal(pos))
        if action in type_actions:
            self._change_measurement_technique(measurement, type_actions[action])
        elif action == act_process or action == act_plot:
            tech = technique_value(measurement)
            self.analysis_requested.emit("STABILITY" if tech in ("CA", "CP") else tech)
        elif action == act_delete:
            self._delete_selected()

    def _change_measurement_technique(self, measurement, technique):
        old_tech = technique_value(measurement)
        if old_tech == technique.value:
            return
        measurement.set_technique(technique, manual=True)
        self.tree.refresh_measurement(measurement)
        self._show_preview(measurement)
        self._refresh_quick_start()
        self.measurements_changed.emit(self.get_all_measurements())
        self.tree.select_measurement(measurement)
        self.tree.measurement_selected.emit(measurement)

    def get_all_measurements(self):
        return list(self._measurements)
