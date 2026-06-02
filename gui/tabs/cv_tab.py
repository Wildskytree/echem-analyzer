"""CV 分析标签页。"""

import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QComboBox, QDoubleSpinBox, QGroupBox,
                               QFormLayout, QSplitter, QTextEdit, QMessageBox,
                               QFileDialog, QTabWidget, QTableWidget,
                               QTableWidgetItem, QHeaderView, QCheckBox,
                               QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt

from gui.widgets.plot_widget import PlotWidget
from gui.widgets.analysis_common import (
    apply_publication_style,
    configure_result_table,
    copy_table,
    export_table,
    measurement_label,
    measurement_name,
    set_auto_limits,
    technique_value,
)
from echem_core.analysis.cv import (
    CDL_IRREGULAR_SCAN_MESSAGE,
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
        self.cb_measurement.setMinimumWidth(420)
        self.cb_measurement.currentIndexChanged.connect(self._on_measurement_changed)
        selector_layout.addWidget(self.cb_measurement, 1)
        self.lbl_selected = QLabel("未选择 CV 数据")
        selector_layout.addWidget(self.lbl_selected)
        main_layout.addLayout(selector_layout)

        # 左侧控制面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # CV 参数
        param_group = QGroupBox("CV 分析参数")
        param_layout = QFormLayout()
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

        # Cdl / ECSA 部分
        cdl_group = QGroupBox("Cdl / ECSA 计算")
        cdl_layout = QVBoxLayout()

        cdl_layout.addWidget(QLabel("选择不同扫速的 CV 数据用于 Cdl 计算:"))
        self.cdl_list = QListWidget()
        self.cdl_list.setSelectionMode(QListWidget.ExtendedSelection)
        cdl_layout.addWidget(QLabel("(从数据浏览器拖入或点击添加)"))
        self.btn_add_cdl = QPushButton("➕ 添加当前 CV 到 Cdl 列表")
        self.btn_add_cdl.clicked.connect(self._add_to_cdl_list)
        self.btn_clear_cdl = QPushButton("🗑️ 清空 Cdl 列表")
        self.btn_clear_cdl.clicked.connect(self._clear_cdl_list)
        self.btn_calc_cdl = QPushButton("📊 计算 Cdl / ECSA")
        self.btn_calc_cdl.clicked.connect(self._calc_cdl)

        cdl_layout.addWidget(self.cdl_list)
        cdl_layout.addWidget(self.btn_add_cdl)
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
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter, 1)

    def set_measurements(self, measurements, preferred=None):
        self._all_measurements = list(measurements)
        self._cv_measurements = [
            m for m in self._all_measurements if technique_value(m) == "CV"
        ]
        self._cdl_measurements = [m for m in self._cdl_measurements if m in self._cv_measurements]
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
            self.lbl_selected.setText(measurement_label(self._measurement))

    def _plot_current_curve(self):
        """Plot the selected CV curve without running peak detection."""
        if self._measurement is None:
            self.plot_widget.clear()
            self.plot_widget.refresh()
            self.peak_table.setRowCount(0)
            self._fig_created = False
            self.btn_export_plot.setEnabled(False)
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
            apply_publication_style(ax)
            set_auto_limits(ax, pot, cur)
            ax.legend(fontsize=8)
            self.peak_table.setRowCount(0)
            self.plot_widget.refresh()
            self._fig_created = True
            self.btn_export_plot.setEnabled(True)
        except Exception:
            self.plot_widget.clear()
            self.plot_widget.refresh()
            self.peak_table.setRowCount(0)
            self._fig_created = False
            self.btn_export_plot.setEnabled(False)

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
            name = self._measurement.metadata.get("sample_name", "未知")
            sr = self._measurement.metadata.get("scan_rate", "?")
            item = QListWidgetItem(f"{name} (扫速: {sr} V/s)")
            self.cdl_list.addItem(item)

    def _clear_cdl_list(self):
        """清空 Cdl 计算列表。"""
        self._cdl_measurements.clear()
        self.cdl_list.clear()

    def _rebuild_cdl_list(self):
        self.cdl_list.clear()
        for measurement in self._cdl_measurements:
            name = measurement.metadata.get("sample_name", "未知")
            sr = measurement.metadata.get("scan_rate", "?")
            self.cdl_list.addItem(QListWidgetItem(f"{name} (扫速: {sr} V/s)"))

    def _calc_cdl(self):
        """计算 Cdl 和 ECSA。"""
        if len(self._cdl_measurements) < 2:
            QMessageBox.warning(self, "提示", "至少需要 2 个不同扫速的 CV 数据。\n请先添加更多 CV 数据。")
            return

        try:
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
