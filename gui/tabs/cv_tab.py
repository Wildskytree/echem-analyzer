"""CV 分析标签页。"""

import os

import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QComboBox, QDoubleSpinBox, QGroupBox,
                               QFormLayout, QSplitter, QTextEdit, QMessageBox,
                               QFileDialog, QTabWidget, QTableWidget,
                               QTableWidgetItem, QCheckBox, QDialog,
                               QDialogButtonBox, QSpinBox,
                               QListWidget, QListWidgetItem, QLineEdit,
                               QSizePolicy, QMenu)
from PySide6.QtCore import Qt

from gui.widgets.plot_widget import PlotWidget
from gui.widgets.analysis_common import (
    apply_publication_style,
    configure_result_table,
    copy_table,
    export_table,
    measurement_label,
    measurement_name,
    scrollable_panel,
    set_auto_limits,
    technique_value,
)
from echem_core.analysis.cv import (
    CDL_IRREGULAR_SCAN_MESSAGE,
    detect_scan_rate,
    find_peaks,
    calc_cdl,
    calc_ecsa,
)


class CVTab(QWidget):
    """CV 分析标签页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_measurements = []
        self._cv_measurements = []
        self._measurement = None
        self._cdl_measurements = []
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("当前文件:"))
        self.cb_measurement = QComboBox()
        self.cb_measurement.setMinimumWidth(320)
        self.cb_measurement.currentIndexChanged.connect(self._on_measurement_changed)
        selector_layout.addWidget(self.cb_measurement, 1)
        self.lbl_selected = QLabel("未选择 CV 数据")
        self.lbl_selected.setMinimumWidth(0)
        self.lbl_selected.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        selector_layout.addWidget(self.lbl_selected)
        main_layout.addLayout(selector_layout)

        # 左侧控制面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # CV 参数
        param_group = QGroupBox("CV 分析参数")
        param_layout = QFormLayout()
        param_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.cb_peak_direction = QComboBox()
        self.cb_peak_direction.addItems(["both", "oxidative", "reductive"])
        param_layout.addRow("峰检测方向:", self.cb_peak_direction)
        param_group.setLayout(param_layout)
        left_layout.addWidget(param_group)

        # 操作按钮
        self.btn_analyze = QPushButton("▶ 峰检测与分析")
        self.btn_analyze.clicked.connect(self._run_peak_analysis)
        self.btn_export_plot = QPushButton("💾 导出图表")
        self.btn_export_plot.clicked.connect(self._export_plot)
        self.btn_export_plot.setEnabled(False)
        self.btn_copy_results = QPushButton("复制峰结果")
        self.btn_copy_results.clicked.connect(lambda: copy_table(self.peak_table))
        self.btn_export_results = QPushButton("导出峰结果")
        self.btn_export_results.clicked.connect(
            lambda: export_table(self.peak_table, self, "cv_peak_results.csv")
        )

        left_layout.addWidget(self.btn_analyze)
        left_layout.addWidget(self.btn_export_plot)
        left_layout.addWidget(self.btn_copy_results)
        left_layout.addWidget(self.btn_export_results)

        # CV 分圈导出
        cycle_group = QGroupBox("CV 分圈导出")
        cycle_layout = QVBoxLayout()
        cycle_select_layout = QHBoxLayout()
        cycle_select_layout.addWidget(QLabel("圈数:"))
        self.spin_cycle = QSpinBox()
        self.spin_cycle.setRange(1, 99)
        self.spin_cycle.setValue(1)
        cycle_select_layout.addWidget(self.spin_cycle, 1)
        cycle_layout.addLayout(cycle_select_layout)

        self.btn_export_cycle = QPushButton("导出单圈")
        self.btn_export_cycle.clicked.connect(self._export_single_cycle)
        self.btn_export_cycle.setEnabled(False)
        self.btn_split_by_voltage = QPushButton("按电压分圈")
        self.btn_split_by_voltage.clicked.connect(self._split_cycles_by_voltage)
        self.btn_split_by_voltage.setEnabled(False)
        cycle_layout.addWidget(self.btn_export_cycle)
        cycle_layout.addWidget(self.btn_split_by_voltage)
        cycle_group.setLayout(cycle_layout)
        left_layout.addWidget(cycle_group)

        # Cdl / ECSA 部分
        cdl_group = QGroupBox("Cdl / ECSA 计算")
        cdl_layout = QVBoxLayout()

        cdl_layout.addWidget(QLabel("选择不同扫速的 CV 数据用于 Cdl 计算:"))
        self.cdl_list = QListWidget()
        self.cdl_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.cdl_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cdl_list.customContextMenuRequested.connect(self._show_cdl_context_menu)
        cdl_layout.addWidget(QLabel("(从数据浏览器拖入或点击添加)"))
        self.btn_add_cdl = QPushButton("➕ 添加当前 CV 到 Cdl 列表")
        self.btn_add_cdl.clicked.connect(self._add_to_cdl_list)
        self.btn_add_all_cdl = QPushButton("自动添加全部 CV")
        self.btn_add_all_cdl.clicked.connect(
            lambda _checked=False: self._add_all_to_cdl_list(show_message=True)
        )
        self.btn_remove_cdl = QPushButton("❌ 删除选中 CV")
        self.btn_remove_cdl.clicked.connect(self._remove_selected_cdl)
        self.btn_clear_cdl = QPushButton("🗑️ 清空 Cdl 列表")
        self.btn_clear_cdl.clicked.connect(self._clear_cdl_list)
        self.btn_calc_cdl = QPushButton("📊 计算 Cdl / ECSA")
        self.btn_calc_cdl.clicked.connect(self._calc_cdl)

        cdl_layout.addWidget(self.cdl_list)
        cdl_layout.addWidget(self.btn_add_cdl)
        cdl_layout.addWidget(self.btn_add_all_cdl)
        cdl_layout.addWidget(self.btn_remove_cdl)
        cdl_layout.addWidget(self.btn_clear_cdl)
        cdl_layout.addWidget(self.btn_calc_cdl)

        self.spin_specific_c = QDoubleSpinBox()
        self.spin_specific_c.setRange(0.001, 1.0)
        self.spin_specific_c.setValue(0.04)
        self.spin_specific_c.setSuffix(" mF/cm²")
        self.spin_specific_c.setSingleStep(0.01)
        cdl_layout.addWidget(QLabel("比电容:"))
        cdl_layout.addWidget(self.spin_specific_c)

        cdl_group.setLayout(cdl_layout)
        left_layout.addWidget(cdl_group)
        left_layout.addStretch()

        # 右侧：绘图 + 结果
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("图表标题:"))
        self.txt_plot_title = QLineEdit("CV 曲线")
        self.txt_plot_title.setPlaceholderText("留空则不显示标题")
        self.txt_plot_title.editingFinished.connect(self._apply_current_title)
        title_layout.addWidget(self.txt_plot_title, 1)
        right_layout.addLayout(title_layout)

        self.plot_widget = PlotWidget(figsize=(6, 4))
        self._fig_created = False
        right_layout.addWidget(self.plot_widget)

        self.result_tabs = QTabWidget()

        # 峰结果
        peak_widget = QWidget()
        peak_layout = QVBoxLayout(peak_widget)
        self.peak_table = QTableWidget()
        configure_result_table(self.peak_table, ["峰类型", "电位 (V)", "电流 (A)"])
        peak_layout.addWidget(self.peak_table)
        self.result_tabs.addTab(peak_widget, "峰检测结果")

        # Cdl 结果
        cdl_result_widget = QWidget()
        cdl_result_layout = QVBoxLayout(cdl_result_widget)
        self.txt_cdl = QTextEdit()
        self.txt_cdl.setReadOnly(True)
        cdl_result_layout.addWidget(self.txt_cdl)
        self.result_tabs.addTab(cdl_result_widget, "Cdl/ECSA 结果")

        right_layout.addWidget(self.result_tabs)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(scrollable_panel(left_panel, min_width=360))
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([360, 1000])
        main_layout.addWidget(splitter, 1)

    def set_measurements(self, measurements, preferred=None):
        self._all_measurements = list(measurements)
        self._cv_measurements = [
            m for m in self._all_measurements if technique_value(m) == "CV"
        ]
        self._cdl_measurements = [m for m in self._cdl_measurements if m in self._cv_measurements]
        self._sort_cdl_measurements()
        self._rebuild_cdl_list()
        target = preferred if preferred in self._cv_measurements else self._measurement
        if target not in self._cv_measurements:
            target = self._cv_measurements[0] if self._cv_measurements else None

        self.cb_measurement.blockSignals(True)
        self.cb_measurement.clear()
        for measurement in self._cv_measurements:
            self.cb_measurement.addItem(measurement_label(measurement), measurement)
        if target is not None:
            self.cb_measurement.setCurrentIndex(self._cv_measurements.index(target))
        self.cb_measurement.blockSignals(False)
        self._measurement = target
        self._update_selected_label()
        self._plot_current_curve()

    def set_measurement(self, measurement):
        """设置当前测量数据。"""
        self.set_measurements(self._all_measurements or [measurement], preferred=measurement)

    def _on_measurement_changed(self, _index=None):
        self._measurement = self.cb_measurement.currentData()
        self._update_selected_label()
        self._plot_current_curve()

    def _update_selected_label(self):
        if self._measurement is None:
            self.lbl_selected.setText("未选择 CV 数据")
        else:
            label = measurement_label(self._measurement)
            self.lbl_selected.setText(label)
            self.lbl_selected.setToolTip(label)

    def _plot_title(self):
        return self.txt_plot_title.text().strip()

    def _apply_current_title(self):
        title = self._plot_title()
        for ax in self.plot_widget.figure.axes:
            ax.set_title(title)
        self.plot_widget.refresh()

    def _scan_rate_for_display(self, measurement):
        scan_rate = detect_scan_rate(measurement)
        return f"{scan_rate:.4g} V/s" if scan_rate is not None else "未识别"

    def _sort_cdl_measurements(self):
        self._cdl_measurements.sort(
            key=lambda measurement: (
                detect_scan_rate(measurement) is None,
                detect_scan_rate(measurement) or float("inf"),
                measurement_name(measurement),
            )
        )

    def _set_cycle_export_enabled(self, enabled):
        self.btn_export_cycle.setEnabled(enabled)
        self.btn_split_by_voltage.setEnabled(enabled)

    def _current_cv_arrays(self):
        if self._measurement is None:
            raise ValueError("请先选择 CV 数据。")

        measurement = self._measurement
        potential = (
            measurement.processed_potential
            if measurement.processed_potential is not None
            else measurement.raw_potential
        )
        current = (
            measurement.processed_current
            if measurement.processed_current is not None
            else measurement.raw_current
        )

        potential = np.asarray(potential, dtype=float)
        current = np.asarray(current, dtype=float)
        n = min(potential.size, current.size)
        potential = potential[:n]
        current = current[:n]
        finite = np.isfinite(potential) & np.isfinite(current)
        potential = potential[finite]
        current = current[finite]
        if potential.size < 5:
            raise ValueError("有效 CV 数据点不足，无法分圈。")
        return potential, current

    def _detect_cv_segments(self, potential, current):
        potential = np.asarray(potential, dtype=float)
        current = np.asarray(current, dtype=float)
        if potential.ndim != 1 or current.ndim != 1 or potential.size != current.size:
            return []
        if potential.size < 5:
            return []

        span = float(np.max(potential) - np.min(potential))
        if not np.isfinite(span) or span <= 0:
            return []

        diff = np.diff(potential)
        tol = max(span * 1e-8, 1e-12)
        signs = np.zeros(diff.shape, dtype=int)
        signs[diff > tol] = 1
        signs[diff < -tol] = -1
        nonzero = np.flatnonzero(signs)
        if nonzero.size == 0:
            return []

        runs = []
        run_start = int(nonzero[0])
        run_sign = int(signs[run_start])
        prev_idx = run_start
        for idx_raw in nonzero[1:]:
            idx = int(idx_raw)
            sign = int(signs[idx])
            if sign != run_sign:
                runs.append((run_sign, run_start, prev_idx))
                run_start = idx
                run_sign = sign
            prev_idx = idx
        runs.append((run_sign, run_start, prev_idx))

        min_span = max(span * 1e-4, tol)
        segments = []
        for sign, start_diff, end_diff in runs:
            start = int(start_diff)
            end = int(end_diff) + 1
            if end - start + 1 < 3:
                continue
            if abs(float(potential[end] - potential[start])) < min_span:
                continue
            segments.append(
                {
                    "start": start,
                    "end": end,
                    "direction": "positive" if sign > 0 else "negative",
                    "points": end - start + 1,
                }
            )
        return segments

    def _detect_cv_cycles(self, potential, current):
        segments = self._detect_cv_segments(potential, current)
        cycles = []
        for idx in range(0, len(segments) - 1, 2):
            start = int(segments[idx]["start"])
            end = int(segments[idx + 1]["end"])
            if end <= start:
                continue
            cycle_potential = potential[start : end + 1]
            cycle_current = current[start : end + 1]
            cycles.append(
                {
                    "number": len(cycles) + 1,
                    "segments": (idx + 1, idx + 2),
                    "potential": cycle_potential,
                    "current": cycle_current,
                    "point_count": int(cycle_potential.size),
                }
            )
        return cycles, segments

    def _txt_path(self, path):
        if path and not os.path.splitext(path)[1]:
            return f"{path}.txt"
        return path

    def _write_cycle_file(self, path, potential, current):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write("Potential/V\tCurrent/A\n")
            for value_e, value_i in zip(potential, current):
                handle.write(f"{value_e:.12g}\t{value_i:.12g}\n")

    def _export_single_cycle(self):
        if self._measurement is None:
            QMessageBox.warning(self, "提示", "请先选择 CV 数据。")
            return

        try:
            potential, current = self._current_cv_arrays()
            cycles, segments = self._detect_cv_cycles(potential, current)
            if not cycles:
                QMessageBox.warning(
                    self,
                    "分圈失败",
                    "未检测到完整 CV 圈。请确认数据至少包含两个连续扫描段。",
                )
                return

            cycle_number = self.spin_cycle.value()
            if cycle_number > len(cycles):
                QMessageBox.warning(
                    self,
                    "分圈失败",
                    f"当前数据仅检测到 {len(cycles)} 圈（{len(segments)} 段）。",
                )
                return

            cycle = cycles[cycle_number - 1]
            default_name = f"cv_cycle_{cycle_number}.txt"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "导出单圈",
                default_name,
                "文本文件 (*.txt);;所有文件 (*)",
            )
            if not path:
                return
            path = self._txt_path(path)
            self._write_cycle_file(path, cycle["potential"], cycle["current"])
            QMessageBox.information(self, "导出成功", f"单圈数据已保存到:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def _ask_voltage_range(self, potential):
        pot_min = float(np.min(potential))
        pot_max = float(np.max(potential))

        dialog = QDialog(self)
        dialog.setWindowTitle("按电压分圈")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        spin_low = QDoubleSpinBox()
        spin_low.setRange(-1e6, 1e6)
        spin_low.setDecimals(6)
        spin_low.setSingleStep(max((pot_max - pot_min) / 100.0, 0.001))
        spin_low.setSuffix(" V")
        spin_low.setValue(pot_min)

        spin_high = QDoubleSpinBox()
        spin_high.setRange(-1e6, 1e6)
        spin_high.setDecimals(6)
        spin_high.setSingleStep(max((pot_max - pot_min) / 100.0, 0.001))
        spin_high.setSuffix(" V")
        spin_high.setValue(pot_max)

        form.addRow("最低电位:", spin_low)
        form.addRow("最高电位:", spin_high)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return None

        low = spin_low.value()
        high = spin_high.value()
        if low >= high:
            QMessageBox.warning(self, "电压范围无效", "最低电位必须小于最高电位。")
            return None
        return low, high

    def _choose_cycles_for_export(self, cycles):
        exportable = [cycle for cycle in cycles if cycle["point_count"] > 0]
        if not exportable:
            QMessageBox.warning(self, "分圈失败", "所选电压范围内没有可导出的数据点。")
            return None

        dialog = QDialog(self)
        dialog.setWindowTitle("选择导出圈数")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("选择要导出的圈数:"))

        list_widget = QListWidget()
        all_item = QListWidgetItem(
            f"全部 ({len(exportable)} 圈，共 {sum(c['point_count'] for c in exportable)} 点)"
        )
        all_item.setData(Qt.UserRole, "all")
        list_widget.addItem(all_item)

        for cycle in cycles:
            item = QListWidgetItem(f"第 {cycle['number']} 圈 - {cycle['point_count']} 点")
            item.setData(Qt.UserRole, cycle["number"])
            if cycle["point_count"] <= 0:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            list_widget.addItem(item)

        list_widget.setCurrentRow(0)
        layout.addWidget(list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return None

        item = list_widget.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _split_cycles_by_voltage(self):
        if self._measurement is None:
            QMessageBox.warning(self, "提示", "请先选择 CV 数据。")
            return

        try:
            potential, current = self._current_cv_arrays()
            cycles, segments = self._detect_cv_cycles(potential, current)
            if not cycles:
                QMessageBox.warning(
                    self,
                    "分圈失败",
                    "未检测到完整 CV 圈。请确认数据至少包含两个连续扫描段。",
                )
                return

            voltage_range = self._ask_voltage_range(potential)
            if voltage_range is None:
                return
            low, high = voltage_range

            ranged_cycles = []
            for cycle in cycles:
                mask = (cycle["potential"] >= low) & (cycle["potential"] <= high)
                cycle_potential = cycle["potential"][mask]
                cycle_current = cycle["current"][mask]
                ranged_cycles.append(
                    {
                        "number": cycle["number"],
                        "potential": cycle_potential,
                        "current": cycle_current,
                        "point_count": int(cycle_potential.size),
                    }
                )

            choice = self._choose_cycles_for_export(ranged_cycles)
            if choice is None:
                return

            exportable = [cycle for cycle in ranged_cycles if cycle["point_count"] > 0]
            if choice == "all":
                directory = QFileDialog.getExistingDirectory(self, "选择保存目录")
                if not directory:
                    return
                saved_paths = []
                for cycle in exportable:
                    path = os.path.join(directory, f"cv_cycle_{cycle['number']}.txt")
                    self._write_cycle_file(path, cycle["potential"], cycle["current"])
                    saved_paths.append(path)
                QMessageBox.information(
                    self,
                    "导出成功",
                    f"已保存 {len(saved_paths)} 个单圈文件到:\n{directory}",
                )
                return

            selected = next(
                (cycle for cycle in exportable if cycle["number"] == choice),
                None,
            )
            if selected is None:
                QMessageBox.warning(self, "导出失败", "未找到所选圈数的数据。")
                return

            default_name = f"cv_cycle_{selected['number']}.txt"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "导出分圈数据",
                default_name,
                "文本文件 (*.txt);;所有文件 (*)",
            )
            if not path:
                return
            path = self._txt_path(path)
            self._write_cycle_file(path, selected["potential"], selected["current"])
            QMessageBox.information(self, "导出成功", f"单圈数据已保存到:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "分圈失败", str(exc))

    def _plot_current_curve(self):
        """Plot the selected CV curve without running peak detection."""
        if self._measurement is None:
            self.plot_widget.clear()
            self.plot_widget.refresh()
            self.peak_table.setRowCount(0)
            self._fig_created = False
            self.btn_export_plot.setEnabled(False)
            self._set_cycle_export_enabled(False)
            return

        try:
            m = self._measurement
            pot = m.processed_potential if m.processed_potential is not None else m.raw_potential
            cur = m.processed_current if m.processed_current is not None else m.raw_current

            self.plot_widget.clear()
            ax = self.plot_widget.ax
            ax.plot(pot, cur, color="#1f77b4", linewidth=1.5, label=measurement_name(m))
            ax.set_xlabel("E / V")
            ax.set_ylabel("I / A")
            title = self._plot_title()
            if title:
                ax.set_title(title)
            apply_publication_style(ax)
            set_auto_limits(ax, pot, cur)
            ax.legend(fontsize=8)
            self.peak_table.setRowCount(0)
            self.plot_widget.refresh()
            self._fig_created = True
            self.btn_export_plot.setEnabled(True)
            self._set_cycle_export_enabled(True)
        except Exception:
            self.plot_widget.clear()
            self.plot_widget.refresh()
            self.peak_table.setRowCount(0)
            self._fig_created = False
            self.btn_export_plot.setEnabled(False)
            self._set_cycle_export_enabled(False)

    def _run_peak_analysis(self, checked=False, silent=False):
        """执行峰检测与分析。"""
        if self._measurement is None:
            self.plot_widget.clear()
            self.plot_widget.refresh()
            self.peak_table.setRowCount(0)
            if not silent:
                QMessageBox.warning(self, "提示", "请先选择 CV 数据。")
            return

        try:
            m = self._measurement
            pot = m.processed_potential if m.processed_potential is not None else m.raw_potential
            cur = m.processed_current if m.processed_current is not None else m.raw_current

            # 绘图
            self.plot_widget.clear()
            ax = self.plot_widget.ax
            ax.plot(pot, cur, color="#1f77b4", linewidth=1.5, label=measurement_name(m))
            ax.set_xlabel("E / V")
            ax.set_ylabel("I / A")
            title = self._plot_title()
            if title:
                ax.set_title(title)
            apply_publication_style(ax)
            set_auto_limits(ax, pot, cur)
            ax.legend(fontsize=8)

            # 峰检测
            direction = self.cb_peak_direction.currentText()
            peaks = find_peaks(pot, cur, direction=direction)

            # 填充峰表
            self.peak_table.setRowCount(len(peaks))
            for i, peak in enumerate(peaks):
                pt = "氧化峰" if peak["peak_type"] == "oxidative" else "还原峰"
                self.peak_table.setItem(i, 0, QTableWidgetItem(pt))
                self.peak_table.setItem(i, 1, QTableWidgetItem(f"{peak['peak_potential']:.4f}"))
                self.peak_table.setItem(i, 2, QTableWidgetItem(f"{peak['peak_current']:.6e}"))

                # 在图上标注峰
                color = 'r' if peak["peak_type"] == "oxidative" else 'g'
                ax.scatter(peak['peak_potential'], peak['peak_current'],
                          color=color, s=50, zorder=5)
                ax.annotate(f"{peak['peak_potential']:.3f}V",
                           xy=(peak['peak_potential'], peak['peak_current']),
                           fontsize=8, color=color)

            self.plot_widget.refresh()
            self._fig_created = True
            self.btn_export_plot.setEnabled(True)

        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "分析错误", f"峰检测失败:\n{e}")

    def _add_to_cdl_list(self):
        """添加当前测量到 Cdl 计算列表。"""
        if self._measurement is None:
            QMessageBox.warning(self, "提示", "请先选择 CV 数据。")
            return
        if self._measurement not in self._cdl_measurements:
            self._cdl_measurements.append(self._measurement)
            self._sort_cdl_measurements()
            self._rebuild_cdl_list()

    def _add_all_to_cdl_list(self, show_message=True):
        """将当前项目中可识别扫速的全部 CV 添加到 Cdl 列表。"""
        self._cdl_measurements = [
            measurement
            for measurement in self._cv_measurements
            if detect_scan_rate(measurement) is not None
        ]
        self._sort_cdl_measurements()
        self._rebuild_cdl_list()
        if show_message and len(self._cdl_measurements) < 2:
            QMessageBox.information(
                self,
                "Cdl / ECSA",
                "当前导入的 CV 数据中少于 2 个文件可识别扫速。",
            )

    def _clear_cdl_list(self):
        """清空 Cdl 计算列表。"""
        self._cdl_measurements.clear()
        self.cdl_list.clear()

    def _remove_selected_cdl(self):
        """从 Cdl 计算列表中删除选中的 CV。"""
        selected_items = self.cdl_list.selectedItems()
        if not selected_items and self.cdl_list.currentItem() is not None:
            selected_items = [self.cdl_list.currentItem()]
        if not selected_items:
            return

        removed_ids = {item.data(Qt.UserRole) for item in selected_items}
        self._cdl_measurements = [
            measurement
            for measurement in self._cdl_measurements
            if id(measurement) not in removed_ids
        ]
        self._rebuild_cdl_list()

    def _show_cdl_context_menu(self, pos):
        item = self.cdl_list.itemAt(pos)
        if item is None:
            return
        if not item.isSelected():
            self.cdl_list.clearSelection()
            item.setSelected(True)
            self.cdl_list.setCurrentItem(item)

        menu = QMenu(self)
        act_remove = menu.addAction("❌ 删除此 CV")
        action = menu.exec(self.cdl_list.mapToGlobal(pos))
        if action == act_remove:
            self._remove_selected_cdl()

    def _rebuild_cdl_list(self):
        self.cdl_list.clear()
        self._sort_cdl_measurements()
        for measurement in self._cdl_measurements:
            name = measurement.metadata.get("sample_name", "未知")
            sr = self._scan_rate_for_display(measurement)
            item = QListWidgetItem(f"{name} (扫速: {sr})")
            item.setData(Qt.UserRole, id(measurement))
            self.cdl_list.addItem(item)

    def _calc_cdl(self):
        """计算 Cdl 和 ECSA。"""
        if len(self._cdl_measurements) < 2:
            self._add_all_to_cdl_list(show_message=False)
            if len(self._cdl_measurements) < 2:
                QMessageBox.warning(
                    self,
                    "提示",
                    "至少需要 2 个不同扫速的 CV 数据。\n"
                    "请确认已导入多个 CV 文件，且文件元数据或电位-时间曲线可识别扫速。",
                )
                return

        try:
            self._sort_cdl_measurements()
            self._rebuild_cdl_list()
            cdl, r2, df_dv, scan_rates = calc_cdl(self._cdl_measurements)
            ecsa = calc_ecsa(cdl, specific_capacitance=self.spin_specific_c.value())

            sr_str = ", ".join([f"{sr:.4f}" for sr in scan_rates])
            self.txt_cdl.setText(
                f"Cdl / ECSA 计算结果:\n\n"
                f"双电层电容 (Cdl): {cdl:.6f} F\n"
                f"线性拟合 R²: {r2:.4f}\n"
                f"电化学活性面积 (ECSA): {ecsa:.4f} cm²\n\n"
                f"比电容: {self.spin_specific_c.value()} mF/cm²\n"
                f"扫描速率: {sr_str}\n"
            )

            # 绘制 Cdl 拟合图
            self.plot_widget.clear()
            ax = self.plot_widget.ax
            ax.plot(scan_rates, df_dv, 'o-', color='b', linewidth=1.5)
            # 线性拟合线
            x_fit = np.linspace(min(scan_rates), max(scan_rates), 50)
            y_fit = cdl * x_fit  # slope = Cdl
            ax.plot(x_fit, y_fit, 'r--', alpha=0.7, label=f'Cdl = {cdl:.6f} F')
            ax.set_xlabel("扫描速率 (V/s)")
            ax.set_ylabel("Δj/2 (A)")
            title = self._plot_title()
            if title:
                ax.set_title(title)
            ax.legend()
            apply_publication_style(ax)
            set_auto_limits(ax, scan_rates, df_dv)
            self.plot_widget.refresh()
            self._fig_created = True
            self.btn_export_plot.setEnabled(True)

        except Exception as e:
            message = self._format_cdl_error(e)
            self.txt_cdl.setText(message)
            self.result_tabs.setCurrentIndex(1)
            QMessageBox.critical(self, "计算错误", message)

    def _format_cdl_error(self, error):
        message = str(error).strip()
        if CDL_IRREGULAR_SCAN_MESSAGE in message:
            return (
                "Cdl 计算失败:\n"
                "CV 数据扫描模式不规则，或未包含完整的正向/反向扫描。\n"
                "请确认每个 CV 文件至少包含一圈完整扫描后再计算。"
            )
        if "scan_rate 无效" in message:
            return (
                "Cdl 计算失败:\n"
                "列表中有 CV 数据缺少有效扫速。请确认文件元数据包含 scan_rate，"
                "或重新导入/添加带扫速的数据。"
            )
        if "非法拉第区没有足够的采样点" in message:
            return (
                "Cdl 计算失败:\n"
                "所选 CV 数据在中间电位窗口内采样点不足。请使用包含完整扫描范围的 CV 数据。"
            )
        if "至少需要 2 个不同扫描速率" in message:
            return "Cdl 计算失败:\n至少需要 2 个不同扫速的 CV 数据。"
        if "cdl 必须为正数" in message:
            return "Cdl 计算失败:\n拟合得到的 Cdl 不是正值，请检查所选 CV 数据和扫速。"
        return f"Cdl 计算失败:\n{message or '未知错误'}"

    def _export_plot(self):
        """导出图表。"""
        if not self._fig_created:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存图表", "cv_plot.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)"
        )
        if path:
            self.plot_widget.save_figure(path)

    def add_cdl_measurement(self, measurement):
        """外部添加测量到 Cdl 列表。"""
        self.set_measurement(measurement)
        self._add_to_cdl_list()
