"""EIS 分析标签页。"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGroupBox,
    QSplitter,
    QMessageBox,
    QFileDialog,
    QTabWidget,
    QTableWidget,
    QComboBox,
)
from PySide6.QtCore import Qt

from gui.widgets.plot_widget import PlotWidget
from gui.widgets.analysis_common import (
    apply_publication_style,
    configure_result_table,
    copy_table,
    export_table,
    format_float,
    measurement_label,
    measurement_name,
    set_auto_limits,
    set_table_rows,
    technique_value,
)
from echem_core.analysis.eis import bode_data, estimate_rct, estimate_rs, nyquist_data


class EISTab(QWidget):
    """EIS 分析标签页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_measurements = []
        self._eis_measurements = []
        self._measurement = None
        self._fig_created = False
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("当前文件:"))
        self.cb_measurement = QComboBox()
        self.cb_measurement.setMinimumWidth(420)
        self.cb_measurement.currentIndexChanged.connect(self._on_measurement_changed)
        selector_layout.addWidget(self.cb_measurement, 1)
        self.lbl_selected = QLabel("未选择 EIS 数据")
        selector_layout.addWidget(self.lbl_selected)
        main_layout.addLayout(selector_layout)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout(action_group)
        self.btn_analyze = QPushButton("分析 EIS 数据")
        self.btn_analyze.clicked.connect(self._run_analysis)
        self.btn_export = QPushButton("导出图表")
        self.btn_export.clicked.connect(self._export_plot)
        self.btn_export.setEnabled(False)
        self.btn_copy = QPushButton("复制结果")
        self.btn_copy.clicked.connect(lambda: copy_table(self.result_table))
        self.btn_export_results = QPushButton("导出结果")
        self.btn_export_results.clicked.connect(
            lambda: export_table(self.result_table, self, "eis_results.csv")
        )
        action_layout.addWidget(self.btn_analyze)
        action_layout.addWidget(self.btn_export)
        action_layout.addWidget(self.btn_copy)
        action_layout.addWidget(self.btn_export_results)
        left_layout.addWidget(action_group)
        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.plot_tabs = QTabWidget()

        self.nyquist_plot = PlotWidget(figsize=(5.5, 5.2))
        self.bode_plot = PlotWidget(figsize=(6.2, 5.2))
        self.plot_tabs.addTab(self.nyquist_plot, "Nyquist 图")
        self.plot_tabs.addTab(self.bode_plot, "Bode 图")
        right_layout.addWidget(self.plot_tabs, 3)

        self.result_table = QTableWidget()
        configure_result_table(self.result_table, ["参数", "数值", "单位", "说明"])
        right_layout.addWidget(self.result_table, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        main_layout.addWidget(splitter, 1)

    def set_measurements(self, measurements, preferred=None):
        self._all_measurements = list(measurements)
        self._eis_measurements = [
            m for m in self._all_measurements if technique_value(m) == "EIS"
        ]
        target = preferred if preferred in self._eis_measurements else self._measurement
        if target not in self._eis_measurements:
            target = self._eis_measurements[0] if self._eis_measurements else None

        self.cb_measurement.blockSignals(True)
        self.cb_measurement.clear()
        for measurement in self._eis_measurements:
            self.cb_measurement.addItem(measurement_label(measurement), measurement)
        if target is not None:
            self.cb_measurement.setCurrentIndex(self._eis_measurements.index(target))
        self.cb_measurement.blockSignals(False)
        self._measurement = target
        self._update_selected_label()
        self._run_analysis(silent=True)

    def set_measurement(self, measurement):
        self.set_measurements(self._all_measurements or [measurement], preferred=measurement)

    def _on_measurement_changed(self, _index=None):
        self._measurement = self.cb_measurement.currentData()
        self._update_selected_label()
        self._run_analysis(silent=True)

    def _update_selected_label(self):
        if self._measurement is None:
            self.lbl_selected.setText("未选择 EIS 数据")
        else:
            self.lbl_selected.setText(measurement_label(self._measurement))

    def _extract_eis_arrays(self, measurement):
        meta = measurement.metadata
        frequency = np.asarray(meta.get("frequency", measurement.raw_potential), dtype=float)
        z_real = np.asarray(meta.get("z_real", measurement.raw_current), dtype=float)
        z_imag_raw = meta.get("z_imag", measurement.raw_time)
        if z_imag_raw is None:
            raise ValueError("无法从测量数据中提取 Z'' 虚部数据。")
        z_imag = np.asarray(z_imag_raw, dtype=float)

        n = min(len(frequency), len(z_real), len(z_imag))
        frequency = frequency[:n]
        z_real = z_real[:n]
        z_imag = z_imag[:n]
        mask = np.isfinite(frequency) & np.isfinite(z_real) & np.isfinite(z_imag)
        if np.count_nonzero(mask) < 2:
            raise ValueError("EIS 有效数据点不足。")
        return frequency[mask], z_real[mask], z_imag[mask]

    def _run_analysis(self, checked=False, silent=False):
        if self._measurement is None:
            self.nyquist_plot.clear()
            self.bode_plot.clear()
            self.nyquist_plot.refresh()
            self.bode_plot.refresh()
            set_table_rows(self.result_table, [])
            self.btn_export.setEnabled(False)
            if not silent:
                QMessageBox.warning(self, "提示", "请先选择 EIS 数据。")
            return

        try:
            frequency, z_real, z_imag = self._extract_eis_arrays(self._measurement)
            zr, neg_zi = nyquist_data(z_real, z_imag)

            self.nyquist_plot.clear()
            ax = self.nyquist_plot.ax
            ax.plot(zr, neg_zi, marker="o", markersize=4, linewidth=1.2, color="#1f77b4")
            ax.set_xlabel("Z' / Ω")
            ax.set_ylabel("-Z'' / Ω")
            ax.set_title(f"Nyquist - {measurement_name(self._measurement)}")
            apply_publication_style(ax)
            set_auto_limits(ax, zr, neg_zi, margin=0.1, equal=False)
            ax.autoscale_view(tight=False, scaley=True, scalex=True)
            finite = np.isfinite(zr) & np.isfinite(neg_zi)
            if np.any(finite):
                finite_zr = zr[finite]
                finite_neg_zi = neg_zi[finite]
                xmin, xmax = float(np.min(finite_zr)), float(np.max(finite_zr))
                ymin, ymax = float(np.min(finite_neg_zi)), float(np.max(finite_neg_zi))
                data_xrange = xmax - xmin
                data_yrange = ymax - ymin
                axis_xrange = abs(float(ax.get_xlim()[1] - ax.get_xlim()[0]))
                axis_yrange = abs(float(ax.get_ylim()[1] - ax.get_ylim()[0]))
                if (
                    np.isfinite(axis_xrange)
                    and np.isfinite(axis_yrange)
                    and (
                        axis_xrange > data_xrange * 100.0
                        or axis_yrange > data_yrange * 100.0
                    )
                ):
                    ax.relim()
                    ax.autoscale(enable=True, axis="both", tight=True)
                    xpad = max(data_xrange * 0.05, 2.0)
                    ypad = max(data_yrange * 0.05, 2.0)
                    ax.set_xlim(xmin - xpad, xmax + xpad)
                    ax.set_ylim(ymin - ypad, ymax + ypad)

            rs = estimate_rs(z_real, frequency)
            rct = estimate_rct(z_real, z_imag, rs)
            ax.text(
                0.03,
                0.97,
                f"Rs = {rs:.3g} Ω\nRct = {rct:.3g} Ω",
                transform=ax.transAxes,
                va="top",
                ha="left",
                fontsize=9,
                bbox={"facecolor": "white", "edgecolor": "#cfd6df", "alpha": 0.85},
            )
            self.nyquist_plot.refresh()

            self.bode_plot.clear()
            valid_freq = frequency > 0
            if np.count_nonzero(valid_freq) >= 2:
                freq, z_mod, phase = bode_data(
                    frequency[valid_freq], z_real[valid_freq], z_imag[valid_freq]
                )
                order = np.argsort(freq)
                freq = freq[order]
                z_mod = z_mod[order]
                phase = phase[order]

                ax1 = self.bode_plot.figure.add_subplot(211)
                ax2 = self.bode_plot.figure.add_subplot(212, sharex=ax1)
                ax1.semilogx(freq, z_mod, color="#1f77b4", linewidth=1.5)
                ax2.semilogx(freq, phase, color="#d62728", linewidth=1.5)
                ax1.set_ylabel("|Z| / Ω")
                ax2.set_xlabel("频率 / Hz")
                ax2.set_ylabel("相位 / °")
                apply_publication_style(ax1)
                apply_publication_style(ax2)
                log_freq = np.log10(freq)
                f_pad = (float(np.max(log_freq)) - float(np.min(log_freq))) * 0.05
                if f_pad <= 0 or not np.isfinite(f_pad):
                    f_pad = 0.2
                ax1.set_xlim(10 ** (float(np.min(log_freq)) - f_pad), 10 ** (float(np.max(log_freq)) + f_pad))
                for axis, values in ((ax1, z_mod), (ax2, phase)):
                    ymin, ymax = float(np.min(values)), float(np.max(values))
                    yrange = ymax - ymin
                    if yrange <= 0 or not np.isfinite(yrange):
                        yrange = max(abs(ymin) * 0.1, 1.0)
                    axis.set_ylim(ymin - yrange * 0.1, ymax + yrange * 0.1)
                self.bode_plot.figure.tight_layout()
            self.bode_plot.refresh()

            rows = [
                ["Rs", format_float(rs, 4), "Ω", "最高频区实部均值估算"],
                ["Rct", format_float(rct, 4), "Ω", "低频实部均值减 Rs"],
                ["Z' 范围", f"{np.min(zr):.4g} ~ {np.max(zr):.4g}", "Ω", "用于 Nyquist 自动坐标"],
                ["-Z'' 范围", f"{np.min(neg_zi):.4g} ~ {np.max(neg_zi):.4g}", "Ω", "用于 Nyquist 自动坐标"],
                ["频率范围", f"{np.min(frequency):.4g} ~ {np.max(frequency):.4g}", "Hz", "有效频率范围"],
                ["数据点数", str(len(z_real)), "点", "过滤非有限值后"],
            ]
            set_table_rows(self.result_table, rows)
            self._fig_created = True
            self.btn_export.setEnabled(True)
        except Exception as exc:
            if not silent:
                QMessageBox.critical(self, "分析错误", f"EIS 分析失败:\n{exc}")

    def _export_plot(self):
        if not self._fig_created:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存图表",
            "eis_plot.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;TIFF (*.tiff)",
        )
        if not path:
            return
        current_plot = self.plot_tabs.currentWidget()
        if isinstance(current_plot, PlotWidget):
            current_plot.save_figure(path)
