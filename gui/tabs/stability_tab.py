"""CA/CP 稳定性分析标签页。"""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from echem_core.analysis.eis import estimate_rs
from echem_core.processing.convert import current_density
from gui.widgets.analysis_common import (
    apply_publication_style,
    configure_result_table,
    copy_table,
    export_table,
    finite_xy,
    format_float,
    labeled_help_widget,
    measurement_label,
    measurement_name,
    set_auto_limits,
    set_table_rows,
    technique_value,
)
from gui.widgets.plot_widget import PlotWidget


class StabilityTab(QWidget):
    """Chronoamperometry / Chronopotentiometry 稳定性分析标签页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_measurements = []
        self._stability_measurements = []
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
        self.lbl_selected = QLabel("未选择 CA/CP 数据")
        selector_layout.addWidget(self.lbl_selected)
        main_layout.addLayout(selector_layout)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        proc_group = QGroupBox("数据处理")
        proc_layout = QFormLayout()

        self.lbl_curve_type = QLabel("曲线类型: 自动识别")
        proc_layout.addRow("识别结果:", self.lbl_curve_type)

        self.cb_time_unit = QComboBox()
        self.cb_time_unit.addItems(["秒 (s)", "分钟 (min)", "小时 (h)"])
        self.cb_time_unit.setCurrentIndex(2)
        proc_layout.addRow("时间单位:", self.cb_time_unit)

        self.cb_value_mode = QComboBox()
        self.cb_value_mode.addItems([
            "CA: 原始电流 / CP: 电位",
            "CA: 电流密度 (mA/cm²) / CP: 电位",
        ])
        self.cb_value_mode.setCurrentIndex(1)
        proc_layout.addRow(
            labeled_help_widget(
                self,
                "纵轴模式:",
                "纵轴模式说明",
                "CA 数据显示 I-t 或 j-t；选择电流密度时使用 j = I*1000/面积。\n"
                "CP 数据自动显示 E-t，纵轴模式不会改变 CP 的电位单位。",
            ),
            self.cb_value_mode,
        )

        self.spin_area = QDoubleSpinBox()
        self.spin_area.setRange(0.0001, 10000.0)
        self.spin_area.setDecimals(4)
        self.spin_area.setValue(0.196)
        self.spin_area.setSuffix(" cm²")
        proc_layout.addRow("电极面积:", self.spin_area)

        self.chk_ir = QCheckBox("启用 iR 补偿")
        self.spin_rs = QDoubleSpinBox()
        self.spin_rs.setRange(0.0, 1_000_000.0)
        self.spin_rs.setDecimals(4)
        self.spin_rs.setSuffix(" Ω")
        self.spin_rs.setValue(0.0)
        self.btn_use_eis_rs = QPushButton("从 EIS 获取 Rs")
        self.btn_use_eis_rs.clicked.connect(self._fill_rs_from_eis)
        proc_layout.addRow(
            labeled_help_widget(
                self,
                "iR 补偿:",
                "iR 补偿说明",
                "CP 电位按 E_corrected = E - I*Rs 修正欧姆降。\n"
                "CA 的主曲线是电流或电流密度，iR 补偿不会改变 CA 纵轴。",
            ),
            self.chk_ir,
        )
        proc_layout.addRow("Rs:", self.spin_rs)
        proc_layout.addRow("", self.btn_use_eis_rs)
        proc_group.setLayout(proc_layout)
        left_layout.addWidget(proc_group)

        analysis_group = QGroupBox("分析选项")
        analysis_layout = QFormLayout()
        self.chk_overlay = QCheckBox("同类型多曲线叠加对比")
        self.chk_overlay.setChecked(True)
        self.chk_abs_retention = QCheckBox("保持率使用绝对幅值")
        self.chk_abs_retention.setChecked(True)
        self.spin_segment_hours = QDoubleSpinBox()
        self.spin_segment_hours.setRange(0.01, 10000.0)
        self.spin_segment_hours.setDecimals(2)
        self.spin_segment_hours.setValue(1.0)
        self.spin_segment_hours.setSuffix(" h")
        analysis_layout.addRow("", self.chk_overlay)
        analysis_layout.addRow(
            labeled_help_widget(
                self,
                "保持率:",
                "保持率说明",
                "保持率按 j(t)/j_max 或 E(t)/E_max 计算。\n"
                "启用绝对幅值时，阴极电流等负值曲线会按幅值计算，避免符号导致保持率失真。",
            ),
            self.chk_abs_retention,
        )
        analysis_layout.addRow(
            labeled_help_widget(
                self,
                "分段长度:",
                "分段统计说明",
                "默认每 1 小时统计一次均值和方差；可改成 0.5 h、2 h 或更长时间段。",
            ),
            self.spin_segment_hours,
        )
        analysis_group.setLayout(analysis_layout)
        left_layout.addWidget(analysis_group)

        self.btn_process = QPushButton("执行稳定性分析")
        self.btn_process.clicked.connect(self._run_analysis)
        self.btn_copy = QPushButton("复制当前表格")
        self.btn_copy.clicked.connect(lambda: copy_table(self._current_table()))
        self.btn_export_results = QPushButton("导出指标结果")
        self.btn_export_results.clicked.connect(
            lambda: export_table(self.result_table, self, "stability_results.csv")
        )
        self.btn_export_stats = QPushButton("导出分段统计")
        self.btn_export_stats.clicked.connect(
            lambda: export_table(self.stats_table, self, "stability_segment_stats.csv")
        )
        self.btn_export_plot = QPushButton("导出图表")
        self.btn_export_plot.clicked.connect(self._export_plot)
        self.btn_export_plot.setEnabled(False)
        for btn in (
            self.btn_process,
            self.btn_copy,
            self.btn_export_results,
            self.btn_export_stats,
            self.btn_export_plot,
        ):
            left_layout.addWidget(btn)
        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.plot_tabs = QTabWidget()
        self.raw_plot = PlotWidget(figsize=(6.5, 4.2))
        self.retention_plot = PlotWidget(figsize=(6.5, 4.2))
        self.plot_tabs.addTab(self.raw_plot, "稳定性曲线")
        self.plot_tabs.addTab(self.retention_plot, "保持率与拟合")
        right_layout.addWidget(self.plot_tabs, 3)

        self.result_tabs = QTabWidget()
        self.result_table = QTableWidget()
        configure_result_table(self.result_table, ["文件", "指标", "数值", "单位", "说明"])
        self.stats_table = QTableWidget()
        configure_result_table(
            self.stats_table,
            ["文件", "类型", "时间段", "起始 (h)", "结束 (h)", "均值", "方差", "点数"],
        )
        self.result_tabs.addTab(self.result_table, "指标结果")
        self.result_tabs.addTab(self.stats_table, "分段统计")
        right_layout.addWidget(self.result_tabs, 2)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        main_layout.addWidget(splitter, 1)

        for widget in (
            self.cb_time_unit,
            self.cb_value_mode,
            self.spin_area,
            self.chk_ir,
            self.spin_rs,
            self.chk_overlay,
            self.chk_abs_retention,
            self.spin_segment_hours,
        ):
            signal = getattr(widget, "valueChanged", None)
            if signal is not None:
                signal.connect(lambda *_args: self._run_analysis(silent=True))
            signal = getattr(widget, "currentIndexChanged", None)
            if signal is not None:
                signal.connect(lambda *_args: self._run_analysis(silent=True))
            signal = getattr(widget, "toggled", None)
            if signal is not None:
                signal.connect(lambda *_args: self._run_analysis(silent=True))

    def set_measurements(self, measurements, preferred=None):
        self._all_measurements = list(measurements)
        self._stability_measurements = [
            m for m in self._all_measurements if technique_value(m) in ("CA", "CP")
        ]
        target = preferred if preferred in self._stability_measurements else self._measurement
        if target not in self._stability_measurements:
            target = self._stability_measurements[0] if self._stability_measurements else None

        self.cb_measurement.blockSignals(True)
        self.cb_measurement.clear()
        for measurement in self._stability_measurements:
            self.cb_measurement.addItem(measurement_label(measurement), measurement)
        if target is not None:
            self.cb_measurement.setCurrentIndex(self._stability_measurements.index(target))
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
            self.lbl_selected.setText("未选择 CA/CP 数据")
            self.lbl_curve_type.setText("曲线类型: 自动识别")
            return

        tech = technique_value(self._measurement)
        self.lbl_selected.setText(measurement_label(self._measurement))
        if tech == "CP":
            self.lbl_curve_type.setText("CP / E-t，电位随时间")
        else:
            self.lbl_curve_type.setText("CA / I-t，电流随时间")

    def _current_table(self):
        return self.stats_table if self.result_tabs.currentWidget() is self.stats_table else self.result_table

    def _current_curve_set(self):
        if self._measurement is None:
            return []
        if not self.chk_overlay.isChecked():
            return [self._measurement]

        selected_tech = technique_value(self._measurement)
        return [
            m for m in self._stability_measurements
            if technique_value(m) == selected_tech
        ]

    def _time_scale(self):
        text = self.cb_time_unit.currentText()
        if text.startswith("小时"):
            return 3600.0, "t / h"
        if text.startswith("分钟"):
            return 60.0, "t / min"
        return 1.0, "t / s"

    def _y_label(self, tech: str):
        if tech == "CP":
            return "E / V (iR 补偿)" if self.chk_ir.isChecked() and self.spin_rs.value() > 0 else "E / V"
        if self.cb_value_mode.currentIndex() == 1:
            return "j / mA cm⁻²"
        return "I / A"

    def _y_symbol(self, tech: str):
        if tech == "CP":
            return "E"
        return "j" if self.cb_value_mode.currentIndex() == 1 else "I"

    def _prepare_curve(self, measurement):
        tech = technique_value(measurement)
        potential = np.asarray(
            measurement.processed_potential
            if measurement.processed_potential is not None
            else measurement.raw_potential,
            dtype=float,
        )
        current = np.asarray(
            measurement.processed_current
            if measurement.processed_current is not None
            else measurement.raw_current,
            dtype=float,
        )

        if tech == "CP":
            time = (
                np.asarray(measurement.raw_time, dtype=float)
                if measurement.raw_time is not None
                else np.arange(potential.size, dtype=float)
            )
            y = potential.copy()
            n = min(time.size, y.size, current.size)
            time = time[:n]
            y = y[:n]
            current = current[:n]
            if self.chk_ir.isChecked() and self.spin_rs.value() > 0:
                y = y - current * self.spin_rs.value()
        else:
            time = (
                np.asarray(measurement.raw_time, dtype=float)
                if measurement.raw_time is not None
                else potential
            )
            y = current.copy()
            n = min(time.size, y.size)
            time = time[:n]
            y = y[:n]
            if self.cb_value_mode.currentIndex() == 1:
                y = current_density(y, self.spin_area.value())

        time, y = finite_xy(time, y)
        if time.size < 2:
            raise ValueError("有效时间序列数据点不足。")
        order = np.argsort(time)
        return time[order], y[order], tech

    def _retention_curve(self, y):
        y_arr = np.asarray(y, dtype=float)
        if self.chk_abs_retention.isChecked():
            ref = float(np.nanmax(np.abs(y_arr)))
            if not math.isfinite(ref) or ref == 0:
                raise ValueError("保持率基准为 0，无法计算。")
            return np.abs(y_arr) / ref, ref, "最大绝对幅值"

        ref = float(np.nanmax(y_arr))
        if not math.isfinite(ref) or ref == 0:
            raise ValueError("保持率基准为 0，无法计算。")
        return y_arr / ref, ref, "最大值"

    @staticmethod
    def _decay_model(t, a, tau, c):
        return a * np.exp(-t / tau) + c

    def _fit_decay(self, time_seconds, retention):
        x, y = finite_xy(time_seconds, retention)
        if x.size < 4:
            raise ValueError("有效数据点不足，无法进行指数拟合。")
        x = x - float(np.min(x))
        span = float(np.max(x) - np.min(x))
        if span <= 0 or not math.isfinite(span):
            raise ValueError("时间跨度不足，无法进行指数拟合。")
        if float(np.max(y) - np.min(y)) <= 1e-9:
            raise ValueError("保持率变化过小，无法稳定拟合指数衰减。")

        from scipy.optimize import curve_fit

        tail_count = max(3, y.size // 10)
        c0 = float(np.nanmean(y[-tail_count:]))
        a0 = float(y[0] - c0)
        if abs(a0) < 1e-9:
            a0 = float(np.max(y) - np.min(y))
        tau0 = max(span / 3.0, 1.0)
        popt, _ = curve_fit(
            self._decay_model,
            x,
            y,
            p0=(a0, tau0, c0),
            bounds=([-np.inf, 1e-12, -np.inf], [np.inf, np.inf, np.inf]),
            maxfev=20000,
        )
        fitted = self._decay_model(x, *popt)
        ss_res = float(np.sum((y - fitted) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = float("nan") if ss_tot == 0 else 1.0 - ss_res / ss_tot
        return {
            "a": float(popt[0]),
            "tau": float(popt[1]),
            "c": float(popt[2]),
            "r2": r2,
        }

    def _empirical_half_life(self, time_seconds, retention):
        x, y = finite_xy(time_seconds, retention)
        if x.size < 2:
            return None
        order = np.argsort(x)
        x = x[order] - float(np.min(x))
        y = y[order]
        below = np.where(y <= 0.5)[0]
        if below.size == 0:
            return None
        idx = int(below[0])
        if idx == 0:
            return float(x[0])
        x0, x1 = float(x[idx - 1]), float(x[idx])
        y0, y1 = float(y[idx - 1]), float(y[idx])
        if y1 == y0:
            return x1
        ratio = (0.5 - y0) / (y1 - y0)
        return x0 + ratio * (x1 - x0)

    def _segment_rows(self, measurement, time_seconds, y, tech):
        segment_h = self.spin_segment_hours.value()
        rel_h = (time_seconds - float(np.min(time_seconds))) / 3600.0
        duration = float(np.max(rel_h)) if rel_h.size else 0.0
        segment_count = max(1, int(math.ceil(duration / segment_h)))
        rows = []
        name = measurement_name(measurement)

        for idx in range(segment_count):
            start = idx * segment_h
            end = (idx + 1) * segment_h
            if idx == segment_count - 1:
                mask = (rel_h >= start) & (rel_h <= end)
            else:
                mask = (rel_h >= start) & (rel_h < end)
            values = y[mask]
            values = values[np.isfinite(values)]
            if values.size == 0:
                continue
            variance = float(np.var(values, ddof=1)) if values.size > 1 else 0.0
            display_end = min(end, duration) if idx == segment_count - 1 else end
            rows.append([
                name,
                tech,
                f"{idx + 1}",
                format_float(start, 3),
                format_float(display_end, 3),
                format_float(float(np.mean(values)), 6, abs(float(np.mean(values))) < 1e-3),
                format_float(variance, 6, variance < 1e-3),
                str(values.size),
            ])
        return rows

    def _append_metric_rows(
        self,
        rows,
        measurement,
        time_seconds,
        y,
        retention,
        ref,
        ref_desc,
        fit_result,
        fit_error=None,
    ):
        name = measurement_name(measurement)
        tech = technique_value(measurement)
        symbol = self._y_symbol(tech)
        unit = self._y_label(tech).split("/")[-1].strip()
        duration_h = (float(np.max(time_seconds)) - float(np.min(time_seconds))) / 3600.0
        final_retention = float(retention[-1]) * 100.0

        rows.extend([
            [name, "曲线类型", "CA / I-t" if tech == "CA" else "CP / E-t", "", "按测量技术自动识别"],
            [name, "数据点数", str(time_seconds.size), "点", "过滤非有限值后"],
            [name, "持续时间", format_float(duration_h, 4), "h", "以首个时间点为 0"],
            [name, f"{symbol}_max", format_float(ref, 6, abs(ref) < 1e-3), unit, ref_desc],
            [name, f"最终 {symbol}", format_float(float(y[-1]), 6, abs(float(y[-1])) < 1e-3), unit, "最后一个有效点"],
            [name, "最终保持率", format_float(final_retention, 2), "%", f"{symbol}(t)/{symbol}_max"],
        ])

        observed_half = self._empirical_half_life(time_seconds, retention)
        if observed_half is None:
            rows.append([name, "观测半衰期 t1/2", "N/A", "h", "曲线未降至 50%"])
        else:
            rows.append([name, "观测半衰期 t1/2", format_float(observed_half / 3600.0, 4), "h", "保持率首次到达 50%"])

        if fit_result is None:
            rows.append([name, "指数衰减拟合", "N/A", "", fit_error or "拟合未完成"])
            return

        fit_half = fit_result["tau"] * math.log(2.0)
        rows.extend([
            [name, "拟合 a", format_float(fit_result["a"], 6), "", "y = a*exp(-t/tau) + c，y 为保持率"],
            [name, "拟合 tau", format_float(fit_result["tau"] / 3600.0, 4), "h", "指数衰减时间常数"],
            [name, "拟合 c", format_float(fit_result["c"], 6), "", "长时间保持率平台"],
            [name, "拟合 t1/2", format_float(fit_half / 3600.0, 4), "h", "tau*ln(2)"],
            [name, "拟合 R²", format_float(fit_result["r2"], 4), "", "指数衰减拟合优度"],
        ])

    def _run_analysis(self, checked=False, silent=False):
        if self._measurement is None:
            self.raw_plot.clear()
            self.retention_plot.clear()
            self.raw_plot.refresh()
            self.retention_plot.refresh()
            set_table_rows(self.result_table, [])
            set_table_rows(self.stats_table, [])
            self.btn_export_plot.setEnabled(False)
            if not silent:
                QMessageBox.warning(self, "提示", "请先选择 CA 或 CP 数据。")
            return

        try:
            curves = self._current_curve_set()
            if not curves:
                raise ValueError("没有可分析的 CA/CP 数据。")

            time_scale, time_label = self._time_scale()
            primary_tech = technique_value(self._measurement)

            self.raw_plot.clear()
            self.retention_plot.clear()
            raw_ax = self.raw_plot.ax
            retention_ax = self.retention_plot.ax

            result_rows = []
            stats_rows = []
            raw_x_all = []
            raw_y_all = []
            retention_x_all = []
            retention_y_all = []

            for measurement in curves:
                time_seconds, y, tech = self._prepare_curve(measurement)
                rel_seconds = time_seconds - float(np.min(time_seconds))
                plot_x = rel_seconds / time_scale
                retention, ref, ref_desc = self._retention_curve(y)

                line, = raw_ax.plot(
                    plot_x,
                    y,
                    linewidth=1.5,
                    label=measurement_name(measurement),
                )
                retention_ax.plot(
                    plot_x,
                    retention * 100.0,
                    linewidth=1.5,
                    color=line.get_color(),
                    label=measurement_name(measurement),
                )

                fit_result = None
                fit_error = None
                try:
                    fit_result = self._fit_decay(rel_seconds, retention)
                    fit_x = np.linspace(0.0, float(np.max(rel_seconds)), 300)
                    fit_y = self._decay_model(
                        fit_x,
                        fit_result["a"],
                        fit_result["tau"],
                        fit_result["c"],
                    )
                    retention_ax.plot(
                        fit_x / time_scale,
                        fit_y * 100.0,
                        linestyle="--",
                        linewidth=1.1,
                        color=line.get_color(),
                        alpha=0.8,
                    )
                except Exception as exc:
                    fit_error = str(exc)

                self._append_metric_rows(
                    result_rows,
                    measurement,
                    rel_seconds,
                    y,
                    retention,
                    ref,
                    ref_desc,
                    fit_result,
                    fit_error,
                )
                stats_rows.extend(self._segment_rows(measurement, time_seconds, y, tech))

                raw_x_all.append(plot_x)
                raw_y_all.append(y)
                retention_x_all.append(plot_x)
                retention_y_all.append(retention * 100.0)

            raw_ax.set_xlabel(time_label)
            raw_ax.set_ylabel(self._y_label(primary_tech))
            raw_ax.set_title("CA 稳定性曲线" if primary_tech == "CA" else "CP 稳定性曲线")
            apply_publication_style(raw_ax)
            if raw_x_all:
                set_auto_limits(raw_ax, np.concatenate(raw_x_all), np.concatenate(raw_y_all))
            raw_ax.legend(fontsize=8)

            retention_ax.set_xlabel(time_label)
            retention_ax.set_ylabel("保持率 / %")
            retention_ax.set_title("保持率与指数衰减拟合")
            apply_publication_style(retention_ax)
            if retention_x_all:
                set_auto_limits(
                    retention_ax,
                    np.concatenate(retention_x_all),
                    np.concatenate(retention_y_all),
                )
            retention_ax.legend(fontsize=8)

            self.raw_plot.refresh()
            self.retention_plot.refresh()
            set_table_rows(self.result_table, result_rows)
            set_table_rows(self.stats_table, stats_rows)
            self._fig_created = True
            self.btn_export_plot.setEnabled(True)
        except Exception as exc:
            if not silent:
                QMessageBox.critical(self, "分析错误", f"稳定性分析失败:\n{exc}")

    def _fill_rs_from_eis(self):
        eis_measurements = [m for m in self._all_measurements if technique_value(m) == "EIS"]
        if not eis_measurements:
            QMessageBox.information(self, "未找到 EIS", "当前项目中没有可用于估算 Rs 的 EIS 数据。")
            return

        measurement = eis_measurements[0]
        meta = measurement.metadata
        z_real = np.asarray(meta.get("z_real", measurement.raw_current), dtype=float)
        frequency = np.asarray(meta.get("frequency", measurement.raw_potential), dtype=float)
        try:
            rs = estimate_rs(z_real, frequency)
        except Exception:
            rs = estimate_rs(z_real)
        self.spin_rs.setValue(float(rs))
        self.chk_ir.setChecked(True)
        QMessageBox.information(self, "已填入 Rs", f"已从 {measurement_name(measurement)} 估算 Rs = {rs:.4f} Ω。")

    def _export_plot(self):
        if not self._fig_created:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存图表",
            "stability_plot.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;TIFF (*.tiff)",
        )
        if not path:
            return
        current_plot = self.plot_tabs.currentWidget()
        if isinstance(current_plot, PlotWidget):
            current_plot.save_figure(path)

    def get_current_data(self):
        if self._measurement is None:
            return None, None
        time_seconds, y, _tech = self._prepare_curve(self._measurement)
        return time_seconds, y
