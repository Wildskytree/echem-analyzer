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
    QLineEdit,
    QSizePolicy,
    QDialog,
)
from PySide6.QtCore import Qt

from gui.widgets.multi_curve_overlay import CurveConfigCard, SimpleComparisonDialog
from gui.widgets.plot_widget import PlotWidget
from gui.widgets.analysis_common import (
    apply_publication_style,
    configure_result_table,
    copy_table,
    export_curve_data,
    export_table,
    format_float,
    measurement_label,
    measurement_name,
    scrollable_panel,
    set_table_rows,
    technique_value,
)
from echem_core.analysis.eis import (
    bode_data,
    estimate_rct,
    estimate_rs,
    impedance_axis_limits,
    nyquist_axis_limits,
    nyquist_data,
)


class EISTab(QWidget):
    """EIS 分析标签页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_measurements = []
        self._eis_measurements = []
        self._measurement = None
        self._fig_created = False
        self._comparison_mode = False
        self._comparison_configs: dict[str, list[object]] = {}
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("当前文件:"))
        self.cb_measurement = QComboBox()
        self.cb_measurement.setMinimumWidth(320)
        self.cb_measurement.currentIndexChanged.connect(self._on_measurement_changed)
        selector_layout.addWidget(self.cb_measurement, 1)
        self.lbl_selected = QLabel("未选择 EIS 数据")
        self.lbl_selected.setMinimumWidth(0)
        self.lbl_selected.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
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
        self.btn_export_curve = QPushButton("导出曲线数据 (CSV)")
        self.btn_export_curve.clicked.connect(self._export_curve_data)
        self.btn_export_curve.setEnabled(False)
        action_layout.addWidget(self.btn_analyze)
        action_layout.addWidget(self.btn_export)
        action_layout.addWidget(self.btn_export_curve)
        action_layout.addWidget(self.btn_copy)
        action_layout.addWidget(self.btn_export_results)
        left_layout.addWidget(action_group)

        # ── 多曲线对比 ──
        comparison_group = QGroupBox("多曲线对比")
        comparison_layout = QVBoxLayout(comparison_group)
        self.btn_comparison = QPushButton("📊 配置多曲线对比")
        self.btn_comparison.clicked.connect(self._open_comparison_dialog)
        comparison_layout.addWidget(self.btn_comparison)
        self.lbl_comparison_status = QLabel("单数据模式")
        self.lbl_comparison_status.setStyleSheet("color: #888; font-style: italic;")
        comparison_layout.addWidget(self.lbl_comparison_status)
        self.btn_exit_comparison = QPushButton("退出对比模式")
        self.btn_exit_comparison.clicked.connect(self._exit_comparison_mode)
        self.btn_exit_comparison.setVisible(False)
        comparison_layout.addWidget(self.btn_exit_comparison)
        left_layout.addWidget(comparison_group)

        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Nyquist 标题:"))
        self.txt_nyquist_title = QLineEdit("Nyquist 图")
        self.txt_nyquist_title.setPlaceholderText("留空则不显示标题")
        self.txt_nyquist_title.editingFinished.connect(
            lambda: self._run_analysis(silent=True)
        )
        title_layout.addWidget(self.txt_nyquist_title, 1)
        title_layout.addWidget(QLabel("Bode 标题:"))
        self.txt_bode_title = QLineEdit("Bode 图")
        self.txt_bode_title.setPlaceholderText("留空则不显示标题")
        self.txt_bode_title.editingFinished.connect(
            lambda: self._run_analysis(silent=True)
        )
        title_layout.addWidget(self.txt_bode_title, 1)
        right_layout.addLayout(title_layout)
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
        splitter.addWidget(scrollable_panel(left_panel, min_width=300))
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([300, 1100])
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

        # 数据变化时退出对比模式
        if self._comparison_mode:
            self._comparison_mode = False
            self._comparison_configs = {}
            self._update_comparison_ui()

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
            label = measurement_label(self._measurement)
            self.lbl_selected.setText(label)
            self.lbl_selected.setToolTip(label)

    def _current_curve_set(self):
        if self._comparison_mode:
            return [
                m for m in self._eis_measurements
                if CurveConfigCard._make_key(m) in self._comparison_configs
            ]
        return [self._measurement] if self._measurement is not None else []

    # ── 多曲线对比 ──

    def _open_comparison_dialog(self, checked=False):
        if not self._eis_measurements:
            QMessageBox.warning(self, "提示", "当前没有可用的 EIS 数据进行对比。")
            return

        dialog = SimpleComparisonDialog(self._eis_measurements, "EIS", self)
        if dialog.exec() == QDialog.Accepted:
            visible = dialog.get_visible_measurements()
            if not visible:
                QMessageBox.warning(self, "提示", "没有选择任何可见曲线，请至少勾选一条。")
                return
            self._comparison_configs = {
                CurveConfigCard._make_key(m): [m]
                for m in visible
            }
            self._comparison_mode = True
            self._update_comparison_ui()
            self._run_analysis(silent=True)

    def _exit_comparison_mode(self):
        self._comparison_mode = False
        self._comparison_configs = {}
        self._update_comparison_ui()
        self._run_analysis(silent=True)

    def _update_comparison_ui(self):
        if self._comparison_mode:
            visible_count = len(self._comparison_configs)
            self.lbl_comparison_status.setText(
                f"🔵 对比模式 ({visible_count}/{len(self._eis_measurements)} 条曲线)"
            )
            self.lbl_comparison_status.setStyleSheet(
                "color: #1f77b4; font-weight: bold;"
            )
            self.btn_exit_comparison.setVisible(True)
        else:
            self.lbl_comparison_status.setText("单数据模式")
            self.lbl_comparison_status.setStyleSheet("color: #888; font-style: italic;")
            self.btn_exit_comparison.setVisible(False)

    def _nyquist_title(self):
        return self.txt_nyquist_title.text().strip()

    def _bode_title(self):
        return self.txt_bode_title.text().strip()

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
            self.btn_export_curve.setEnabled(False)
            if not silent:
                QMessageBox.warning(self, "提示", "请先选择 EIS 数据。")
            return

        try:
            curves = self._current_curve_set()
            if not curves:
                raise ValueError("没有可分析的 EIS 数据。")

            self.nyquist_plot.clear()
            self.bode_plot.clear()
            nyquist_ax = self.nyquist_plot.ax

            all_zr = []
            all_neg_zi = []
            legend_data = {}

            for measurement in curves:
                frequency, z_real, z_imag = self._extract_eis_arrays(measurement)
                zr, neg_zi = nyquist_data(z_real, z_imag)

                name = measurement_name(measurement)
                nyquist_ax.plot(
                    zr, neg_zi, marker="o", markersize=4, linewidth=1.2,
                    label=name,
                )
                all_zr.append(zr)
                all_neg_zi.append(neg_zi)

                # 收集用于图例
                rs = estimate_rs(z_real, frequency)
                rct = estimate_rct(z_real, z_imag, rs)
                legend_data[name] = (rs, rct)

            nyquist_ax.set_xlabel("Z' / Ω")
            nyquist_ax.set_ylabel("-Z'' / Ω")
            title = self._nyquist_title()
            if title:
                nyquist_ax.set_title(title)

            # 合并所有数据用于坐标轴限制
            if all_zr:
                combined_zr = np.concatenate(all_zr)
                combined_neg_zi = np.concatenate(all_neg_zi)
                xlim, ylim = nyquist_axis_limits(combined_zr, combined_neg_zi, margin=0.08)
                nyquist_ax.set_xlim(*xlim)
                nyquist_ax.set_ylim(*ylim)

            if len(curves) > 1:
                nyquist_ax.legend(fontsize=8)

            # 显示第一条曲线的 Rs/Rct 或对比模式下的汇总
            if len(curves) == 1:
                first = curves[0]
                frequency, z_real, z_imag = self._extract_eis_arrays(first)
                rs = estimate_rs(z_real, frequency)
                rct = estimate_rct(z_real, z_imag, rs)
                nyquist_ax.text(
                    0.03, 0.97,
                    f"Rs = {rs:.3g} Ω\nRct = {rct:.3g} Ω",
                    transform=nyquist_ax.transAxes, va="top", ha="left",
                    fontsize=9,
                    bbox={"facecolor": "white", "edgecolor": "#cfd6df", "alpha": 0.85},
                )

            apply_publication_style(nyquist_ax)
            self.nyquist_plot.refresh()

            # Bode 图
            bode_data_list = []
            for measurement in curves:
                frequency, z_real, z_imag = self._extract_eis_arrays(measurement)
                valid = frequency > 0
                if np.count_nonzero(valid) >= 2:
                    freq, z_mod, phase = bode_data(
                        frequency[valid], z_real[valid], z_imag[valid]
                    )
                    order = np.argsort(freq)
                    bode_data_list.append({
                        "freq": freq[order],
                        "z_mod": z_mod[order],
                        "phase": phase[order],
                        "name": measurement_name(measurement),
                    })

            if bode_data_list:
                ax1 = self.bode_plot.figure.add_subplot(211)
                ax2 = self.bode_plot.figure.add_subplot(212, sharex=ax1)
                for bd in bode_data_list:
                    ax1.semilogx(bd["freq"], bd["z_mod"], linewidth=1.5, label=bd["name"])
                    ax2.semilogx(bd["freq"], bd["phase"], linewidth=1.5, label=bd["name"])
                title = self._bode_title()
                if title:
                    ax1.set_title(title)
                ax1.set_ylabel("|Z| / Ω")
                ax2.set_xlabel("频率 / Hz")
                ax2.set_ylabel("相位 / °")
                apply_publication_style(ax1)
                apply_publication_style(ax2)
                if len(bode_data_list) > 1:
                    ax1.legend(fontsize=7)
                    ax2.legend(fontsize=7)
                # 坐标轴范围
                all_freq = np.concatenate([bd["freq"] for bd in bode_data_list])
                all_z_mod = np.concatenate([bd["z_mod"] for bd in bode_data_list])
                all_phase = np.concatenate([bd["phase"] for bd in bode_data_list])
                log_freq = np.log10(all_freq)
                f_pad = (float(np.max(log_freq)) - float(np.min(log_freq))) * 0.05
                if f_pad <= 0 or not np.isfinite(f_pad):
                    f_pad = 0.2
                ax1.set_xlim(10 ** (float(np.min(log_freq)) - f_pad),
                             10 ** (float(np.max(log_freq)) + f_pad))
                ax1.set_ylim(*impedance_axis_limits(all_z_mod, margin=0.1))
                ax2.set_ylim(*impedance_axis_limits(all_phase, margin=0.1))
                self.bode_plot.figure.tight_layout()
            self.bode_plot.refresh()

            # 结果表（对比模式显示简略信息）
            if len(curves) == 1:
                first = curves[0]
                frequency, z_real, z_imag = self._extract_eis_arrays(first)
                zr, neg_zi = nyquist_data(z_real, z_imag)
                rs = estimate_rs(z_real, frequency)
                rct = estimate_rct(z_real, z_imag, rs)
                rows = [
                    ["Rs", format_float(rs, 4), "Ω", "最高频区实部均值估算"],
                    ["Rct", format_float(rct, 4), "Ω", "低频实部均值减 Rs"],
                    ["Z' 范围", f"{np.min(zr):.4g} ~ {np.max(zr):.4g}", "Ω", "用于 Nyquist 自动坐标"],
                    ["-Z'' 范围", f"{np.min(neg_zi):.4g} ~ {np.max(neg_zi):.4g}", "Ω", "用于 Nyquist 自动坐标"],
                    ["频率范围", f"{np.min(frequency):.4g} ~ {np.max(frequency):.4g}", "Hz", "有效频率范围"],
                    ["数据点数", str(len(z_real)), "点", "过滤非有限值后"],
                ]
            else:
                rows = [[f"对比模式: {len(curves)} 条曲线", "", "", "各曲线独立显示，坐标轴自动调整"]]
                for name, (rs, rct) in legend_data.items():
                    rows.append([f"  {name}: Rs", format_float(rs, 3), "Ω", ""])
                    rows.append([f"  {name}: Rct", format_float(rct, 3), "Ω", ""])

            set_table_rows(self.result_table, rows)
            self._fig_created = True
            self.btn_export.setEnabled(True)
            self.btn_export_curve.setEnabled(True)
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

    def _export_curve_data(self):
        """Export EIS curve data (Nyquist + Bode) as CSV."""
        if self._measurement is None:
            QMessageBox.warning(self, "提示", "请先选择 EIS 数据。")
            return
        try:
            frequency, z_real, z_imag = self._extract_eis_arrays(self._measurement)
            zr, neg_zi = nyquist_data(z_real, z_imag)
            valid = frequency > 0
            freq_b, z_mod, phase = bode_data(
                frequency[valid], z_real[valid], z_imag[valid]
            )
            export_curve_data(
                self, "eis_curve_data.csv",
                [frequency, z_real, z_imag, zr, neg_zi, freq_b, z_mod, phase],
                ["Frequency/Hz", "Z'/Ω", "Z''/Ω", "Z'_Nyquist/Ω", "-Z''_Nyquist/Ω",
                 "Frequency_Bode/Hz", "|Z|/Ω", "Phase/°"],
            )
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
