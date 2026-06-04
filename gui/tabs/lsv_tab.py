"""通用 LSV 与 ORR 专项分析标签页。"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QFormLayout,
    QSplitter,
    QMessageBox,
    QFileDialog,
    QTabWidget,
    QTableWidget,
    QCheckBox,
    QSpinBox,
    QLineEdit,
    QSizePolicy,
    QDialog,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt

from gui.widgets.multi_curve_overlay import (
    CurveConfigCard,
    CurveProcessingParams,
    MultiCurveComparisonDialog,
    apply_lsv_processing,
    get_legend_label,
    lsv_x_label as overlay_x_label,
    lsv_y_label as overlay_y_label,
)
from gui.widgets.plot_widget import PlotWidget
from gui.widgets.analysis_common import (
    apply_publication_style,
    configure_result_table,
    copy_table,
    derivative_xy,
    export_curve_data,
    export_table,
    format_float,
    interpolate_at,
    labeled_help_widget,
    measurement_label,
    measurement_name,
    scrollable_panel,
    set_auto_limits,
    set_table_rows,
    technique_value,
    unique_sorted_xy,
)
from echem_core.analysis.eis import estimate_rs
from echem_core.analysis.lsv import find_e_half, find_e_onset, kl_plot, tafel_slope
from echem_core.processing.convert import (
    current_density,
    current_to_mass_activity,
    to_rhe,
)


class LSVTab(QWidget):
    """通用 LSV / ORR 分析标签页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_measurements = []
        self._lsv_measurements = []
        self._measurement = None
        self._fig_created = False
        self._last_rows = []
        # 多曲线对比配置
        self._comparison_mode = False
        self._comparison_configs: dict[str, tuple[object, CurveProcessingParams]] = {}
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("当前文件:"))
        self.cb_measurement = QComboBox()
        self.cb_measurement.setMinimumWidth(320)
        self.cb_measurement.currentIndexChanged.connect(self._on_measurement_changed)
        selector_layout.addWidget(self.cb_measurement, 1)
        self.lbl_selected = QLabel("未选择 LSV 数据")
        self.lbl_selected.setMinimumWidth(0)
        self.lbl_selected.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        selector_layout.addWidget(self.lbl_selected)
        main_layout.addLayout(selector_layout)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        proc_group = QGroupBox("数据处理")
        proc_layout = QFormLayout()
        proc_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.chk_to_rhe = QCheckBox("转换到 RHE")
        self.chk_to_rhe.setChecked(True)
        self.cb_reference = QComboBox()
        self.cb_reference.addItems(["Ag/AgCl", "SCE", "Hg/HgO", "RHE"])
        self.spin_ph = QDoubleSpinBox()
        self.spin_ph.setRange(-2, 16)
        self.spin_ph.setValue(13.0)
        self.spin_ph.setSingleStep(0.1)
        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(250, 380)
        self.spin_temp.setValue(298.15)
        self.spin_temp.setSuffix(" K")

        proc_layout.addRow("", self.chk_to_rhe)
        proc_layout.addRow(
            labeled_help_widget(
                self,
                "参比电极:",
                "参比电极说明",
                "RHE 换算公式: E_RHE = E_ref + E_offset + 0.05916*(T/298.15)*pH。\n"
                "常用 offset: Ag/AgCl=0.197 V, SCE=0.241 V, Hg/HgO=0.098 V, RHE=0 V。",
            ),
            self.cb_reference,
        )
        proc_layout.addRow(
            labeled_help_widget(
                self,
                "pH:",
                "pH 说明",
                "pH 会通过能斯特项进入 RHE 换算。25°C 下每增加 1 个 pH，"
                "换算电位增加约 0.05916 V。",
            ),
            self.spin_ph,
        )
        proc_layout.addRow("温度:", self.spin_temp)

        self.chk_ir = QCheckBox("启用 iR 补偿")
        self.spin_rs = QDoubleSpinBox()
        self.spin_rs.setRange(0.0, 1_000_000.0)
        self.spin_rs.setDecimals(4)
        self.spin_rs.setSuffix(" Ω")
        self.spin_rs.setValue(0.0)
        self.spin_ir_percent = QSpinBox()
        self.spin_ir_percent.setRange(1, 100)
        self.spin_ir_percent.setValue(100)
        self.spin_ir_percent.setSuffix(" %")
        self.btn_use_eis_rs = QPushButton("从 EIS 获取 Rs")
        self.btn_use_eis_rs.clicked.connect(self._fill_rs_from_eis)
        proc_layout.addRow(
            labeled_help_widget(
                self,
                "iR 补偿:",
                "iR 补偿说明",
                "使用溶液电阻 Rs 修正欧姆降: E_corrected = E - i*Rs。\n"
                "这里的 i 使用归一化前的电流，单位为 A；Rs 单位为 Ω。",
            ),
            self.chk_ir,
        )
        proc_layout.addRow("Rs:", self.spin_rs)
        proc_layout.addRow("iR补偿百分比:", self.spin_ir_percent)
        proc_layout.addRow("", self.btn_use_eis_rs)

        self.cb_normalize = QComboBox()
        self.cb_normalize.addItems(["不归一化", "按面积 (mA/cm²)", "按质量 (mA/mg)"])
        self.spin_area = QDoubleSpinBox()
        self.spin_area.setRange(0.0001, 10_000.0)
        self.spin_area.setValue(0.196)
        self.spin_area.setSuffix(" cm²")
        self.spin_loading = QDoubleSpinBox()
        self.spin_loading.setRange(0.0001, 10_000.0)
        self.spin_loading.setValue(0.2)
        self.spin_loading.setSuffix(" mg/cm²")
        proc_layout.addRow(
            labeled_help_widget(
                self,
                "归一化:",
                "归一化说明",
                "面积归一化: j = I*1000/area，单位 mA/cm²。\n"
                "质量归一化: I*1000/(loading*area)，单位 mA/mg。",
            ),
            self.cb_normalize,
        )
        proc_layout.addRow("电极面积:", self.spin_area)
        proc_layout.addRow("负载量:", self.spin_loading)

        self.chk_smooth = QCheckBox("Savitzky-Golay 平滑")
        self.spin_window = QSpinBox()
        self.spin_window.setRange(3, 501)
        self.spin_window.setValue(11)
        self.spin_window.setSingleStep(2)
        self.spin_order = QSpinBox()
        self.spin_order.setRange(1, 5)
        self.spin_order.setValue(2)
        smooth_tip = (
            "Savitzky-Golay 平滑用于降低电流噪声，同时尽量保留峰形和斜率。\n"
            "窗口: 每次局部多项式拟合使用的数据点数，需大于阶数；程序会自动调整为奇数。"
            "\nLSV 常用 7-31，噪声较大可增大，过大会抹平真实特征。\n"
            "阶数: 局部多项式阶数，常用 2 或 3；一般不建议超过 4。"
        )
        proc_group.setToolTip(smooth_tip)
        self.chk_smooth.setToolTip(smooth_tip)
        self.spin_window.setToolTip(smooth_tip)
        self.spin_order.setToolTip(smooth_tip)
        proc_layout.addRow("", self.chk_smooth)
        proc_layout.addRow("窗口:", self.spin_window)
        proc_layout.addRow("阶数:", self.spin_order)
        proc_group.setLayout(proc_layout)
        left_layout.addWidget(proc_group)

        analysis_group = QGroupBox("分析选项")
        analysis_layout = QFormLayout()
        analysis_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.spin_read_potential = QDoubleSpinBox()
        self.spin_read_potential.setRange(-10.0, 10.0)
        self.spin_read_potential.setDecimals(4)
        self.spin_read_potential.setSingleStep(0.01)
        self.spin_read_potential.setSuffix(" V")
        self.spin_peak_start_potential = QDoubleSpinBox()
        self.spin_peak_start_potential.setRange(-10.0, 10.0)
        self.spin_peak_start_potential.setDecimals(4)
        self.spin_peak_start_potential.setSingleStep(0.01)
        self.spin_peak_start_potential.setValue(1.0)
        self.spin_peak_start_potential.setSuffix(" V")
        self.chk_derivative = QCheckBox("计算微分曲线 dI/dE")
        self.chk_orr = QCheckBox("启用 ORR 专项分析")
        self.chk_orr.setChecked(True)
        analysis_layout.addRow("读取电位:", self.spin_read_potential)
        analysis_layout.addRow("峰检测起始电位:", self.spin_peak_start_potential)
        analysis_layout.addRow("", self.chk_derivative)
        analysis_layout.addRow("", self.chk_orr)
        analysis_group.setLayout(analysis_layout)
        left_layout.addWidget(analysis_group)

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

        self.btn_process = QPushButton("执行分析")
        self.btn_process.clicked.connect(self._run_analysis)
        self.btn_detect_peaks = QPushButton("手动峰检测")
        self.btn_detect_peaks.clicked.connect(self._run_peak_detection)
        self.btn_kl = QPushButton("执行 K-L 分析")
        self.btn_kl.clicked.connect(self._run_kl)
        self.btn_copy = QPushButton("复制结果")
        self.btn_copy.clicked.connect(lambda: copy_table(self.result_table))
        self.btn_export_results = QPushButton("导出结果")
        self.btn_export_results.clicked.connect(
            lambda: export_table(self.result_table, self, "lsv_results.csv")
        )
        self.btn_export_plot = QPushButton("导出图表")
        self.btn_export_plot.clicked.connect(self._export_plot)
        self.btn_export_plot.setEnabled(False)
        self.btn_export_curve = QPushButton("导出曲线数据 (CSV)")
        self.btn_export_curve.clicked.connect(self._export_curve_data)
        self.btn_export_curve.setEnabled(False)
        for btn in (
            self.btn_process,
            self.btn_detect_peaks,
            self.btn_kl,
            self.btn_copy,
            self.btn_export_results,
            self.btn_export_plot,
            self.btn_export_curve,
        ):
            left_layout.addWidget(btn)
        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("图表标题:"))
        self.txt_plot_title = QLineEdit("LSV 曲线")
        self.txt_plot_title.setPlaceholderText("留空则不显示标题")
        self.txt_plot_title.editingFinished.connect(
            lambda: self._run_analysis(silent=True)
        )
        title_layout.addWidget(self.txt_plot_title, 1)
        right_layout.addLayout(title_layout)
        self.plot_tabs = QTabWidget()
        self.plot_widget = PlotWidget(figsize=(6.5, 4.4))
        self.derivative_plot = PlotWidget(figsize=(6.5, 4.4))
        self.plot_tabs.addTab(self.plot_widget, "LSV 曲线")
        self.plot_tabs.addTab(self.derivative_plot, "微分曲线")
        right_layout.addWidget(self.plot_tabs, 3)

        self.result_table = QTableWidget()
        configure_result_table(self.result_table, ["指标", "数值", "单位", "说明"])
        right_layout.addWidget(self.result_table, 2)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(scrollable_panel(left_panel, min_width=380))
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([380, 1000])
        main_layout.addWidget(splitter, 1)

    def set_measurements(self, measurements, preferred=None):
        self._all_measurements = list(measurements)
        self._lsv_measurements = [
            m for m in self._all_measurements if technique_value(m) == "LSV"
        ]
        target = preferred if preferred in self._lsv_measurements else self._measurement
        if target not in self._lsv_measurements:
            target = self._lsv_measurements[0] if self._lsv_measurements else None

        self.cb_measurement.blockSignals(True)
        self.cb_measurement.clear()
        for measurement in self._lsv_measurements:
            self.cb_measurement.addItem(measurement_label(measurement), measurement)
        if target is not None:
            self.cb_measurement.setCurrentIndex(self._lsv_measurements.index(target))
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
            self.lbl_selected.setText("未选择 LSV 数据")
        else:
            label = measurement_label(self._measurement)
            self.lbl_selected.setText(label)
            self.lbl_selected.setToolTip(label)

    def _current_curve_set(self):
        if self._comparison_mode:
            return [
                m for m in self._lsv_measurements
                if CurveConfigCard._make_key(m) in self._comparison_configs
                and self._comparison_configs[CurveConfigCard._make_key(m)][1].visible
            ]
        return [self._measurement] if self._measurement is not None else []

    def _prepare_curve(self, measurement):
        # 使用全局 UI 参数处理（对比模式由调用方自行处理）
        pot = np.asarray(
            measurement.processed_potential
            if measurement.processed_potential is not None
            else measurement.raw_potential,
            dtype=float,
        ).copy()
        cur_a = np.asarray(
            measurement.processed_current
            if measurement.processed_current is not None
            else measurement.raw_current,
            dtype=float,
        ).copy()

        if self.chk_ir.isChecked() and self.spin_rs.value() > 0:
            ir_fraction = self.spin_ir_percent.value() / 100.0
            pot = pot - cur_a * self.spin_rs.value() * ir_fraction

        if self.chk_to_rhe.isChecked():
            pot = to_rhe(
                pot,
                reference=self.cb_reference.currentText(),
                pH=self.spin_ph.value(),
                temperature=self.spin_temp.value(),
            )

        norm = self.cb_normalize.currentText()
        if norm.startswith("按面积"):
            cur = current_density(cur_a, self.spin_area.value())
        elif norm.startswith("按质量"):
            cur = current_to_mass_activity(
                cur_a,
                loading_mg_cm2=self.spin_loading.value(),
                area_cm2=self.spin_area.value(),
            )
        else:
            cur = cur_a

        if self.chk_smooth.isChecked() and cur.size >= 5:
            try:
                from scipy.signal import savgol_filter

                window = min(self.spin_window.value(), cur.size if cur.size % 2 == 1 else cur.size - 1)
                order = min(self.spin_order.value(), max(1, window - 2))
                if window <= order:
                    window = order + 2
                if window % 2 == 0:
                    window += 1
                if window <= cur.size and window >= 3:
                    cur = savgol_filter(cur, window, order)
            except Exception:
                pass
        return pot, cur

    def _y_label(self):
        # 对比模式下使用第一条可见曲线的参数决定坐标轴标签
        if self._comparison_mode and self._comparison_configs:
            visible = [
                v[1] for v in self._comparison_configs.values() if v[1].visible
            ]
            if visible:
                return overlay_y_label(visible[0])
        norm = self.cb_normalize.currentText()
        if norm.startswith("按面积"):
            return "j / mA cm⁻²"
        if norm.startswith("按质量"):
            return "质量活性 / mA mg⁻¹"
        return "I / A"

    def _x_label(self):
        if self._comparison_mode and self._comparison_configs:
            visible = [
                v[1] for v in self._comparison_configs.values() if v[1].visible
            ]
            if visible:
                return overlay_x_label(visible[0])
        return "E / V vs. RHE" if self.chk_to_rhe.isChecked() else "E / V"

    def _plot_title(self):
        return self.txt_plot_title.text().strip()

    # ── 多曲线对比 ──

    def _open_comparison_dialog(self, checked=False):
        if not self._lsv_measurements:
            QMessageBox.warning(self, "提示", "当前没有可用的 LSV 数据进行对比。")
            return

        dialog = MultiCurveComparisonDialog(
            self._lsv_measurements, "LSV", self
        )

        # 如果已有配置，同步到对话框
        if self._comparison_configs:
            for card in dialog._cards:
                key = card.measurement_key
                if key in self._comparison_configs:
                    card.update_from_params(self._comparison_configs[key][1])

        if dialog.exec() == QDialog.Accepted:
            self._comparison_configs = dialog.get_configurations()
            visible = dialog.get_visible_configurations()
            if not visible:
                QMessageBox.warning(self, "提示", "没有选择任何可见曲线，请至少勾选一条。")
                return
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
            visible_count = sum(
                1 for v in self._comparison_configs.values() if v[1].visible
            )
            self.lbl_comparison_status.setText(
                f"🔵 对比模式 ({visible_count}/{len(self._lsv_measurements)} 条曲线)"
            )
            self.lbl_comparison_status.setStyleSheet(
                "color: #1f77b4; font-weight: bold;"
            )
            self.btn_exit_comparison.setVisible(True)
        else:
            self.lbl_comparison_status.setText("单数据模式")
            self.lbl_comparison_status.setStyleSheet("color: #888; font-style: italic;")
            self.btn_exit_comparison.setVisible(False)

    def _detect_peaks(self, potential, current):
        try:
            from scipy.signal import find_peaks as scipy_find_peaks
        except Exception:
            return []

        potential = np.asarray(potential, dtype=float)
        current = np.asarray(current, dtype=float)
        threshold = self.spin_peak_start_potential.value()
        mask = potential >= threshold
        pot_sorted, cur_sorted = unique_sorted_xy(potential[mask], current[mask])
        if cur_sorted.size < 5:
            return []
        span = float(np.max(cur_sorted) - np.min(cur_sorted))
        if span <= 0 or not np.isfinite(span):
            return []
        prominence = span * 0.05
        peaks = []
        pos_idx, _ = scipy_find_peaks(cur_sorted, prominence=prominence)
        neg_idx, _ = scipy_find_peaks(-cur_sorted, prominence=prominence)
        for idx in pos_idx:
            peaks.append(("阳极峰", float(pot_sorted[idx]), float(cur_sorted[idx])))
        for idx in neg_idx:
            peaks.append(("阴极峰", float(pot_sorted[idx]), float(cur_sorted[idx])))
        peaks.sort(key=lambda row: row[1])
        return peaks

    def _run_analysis(self, checked=False, silent=False):
        if self._measurement is None:
            self.plot_widget.clear()
            self.derivative_plot.clear()
            self.plot_widget.refresh()
            self.derivative_plot.refresh()
            set_table_rows(self.result_table, [])
            self.btn_export_plot.setEnabled(False)
            if not silent:
                QMessageBox.warning(self, "提示", "请先选择 LSV 数据。")
            return

        try:
            curves = self._current_curve_set()
            selected_pot, selected_cur = self._prepare_curve(self._measurement)
            rows = []

            self.plot_widget.clear()
            ax = self.plot_widget.ax
            all_x = []
            all_y = []
            for measurement in curves:
                # 对比模式下使用各自独立的处理参数
                if self._comparison_mode:
                    key = CurveConfigCard._make_key(measurement)
                    cfg = self._comparison_configs.get(key)
                    if cfg is not None:
                        pot, cur = apply_lsv_processing(measurement, cfg[1])
                    else:
                        pot, cur = self._prepare_curve(measurement)
                else:
                    pot, cur = self._prepare_curve(measurement)
                    cfg = None
                all_x.append(pot)
                all_y.append(cur)
                # 对比模式下使用自定义标签
                if self._comparison_mode:
                    label = get_legend_label(measurement, cfg[1]) if cfg else measurement_name(measurement)
                else:
                    label = measurement_name(measurement)
                ax.plot(pot, cur, linewidth=1.6, label=label)

            ax.set_xlabel(self._x_label())
            ax.set_ylabel(self._y_label())
            title = self._plot_title()
            if title:
                ax.set_title(title)
            apply_publication_style(ax)
            if all_x:
                set_auto_limits(ax, np.concatenate(all_x), np.concatenate(all_y))
            ax.legend(fontsize=8)

            try:
                e_onset = find_e_onset(selected_pot, selected_cur)
                rows.append(["起始电位 E_onset", format_float(e_onset), "V", "切线法自动估算"])
                ax.axvline(e_onset, color="#d62728", linestyle="--", linewidth=1.0, alpha=0.8)
            except Exception as exc:
                rows.append(["起始电位 E_onset", "N/A", "V", f"计算失败: {exc}"])

            read_e = self.spin_read_potential.value()
            try:
                read_i = interpolate_at(selected_pot, selected_cur, read_e)
                rows.append([f"{read_e:.4f} V 处电流", format_float(read_i, 6, abs(read_i) < 1e-3), self._y_label().split("/")[-1].strip(), "线性插值读取"])
                ax.scatter([read_e], [read_i], s=42, color="#1f77b4", zorder=5)
            except Exception as exc:
                rows.append([f"{read_e:.4f} V 处电流", "N/A", self._y_label().split("/")[-1].strip(), str(exc)])

            rows.append(["电位范围", f"{np.nanmin(selected_pot):.4f} ~ {np.nanmax(selected_pot):.4f}", "V", "处理后的范围"])
            rows.append(["电流范围", f"{np.nanmin(selected_cur):.6g} ~ {np.nanmax(selected_cur):.6g}", self._y_label().split("/")[-1].strip(), "处理后的范围"])

            if self.chk_orr.isChecked():
                try:
                    e_half, j_l, confidence = find_e_half(selected_pot, selected_cur)
                    conf_map = {"high": "高", "medium": "中", "low": "低"}
                    rows.append(["ORR 半波电位 E1/2", format_float(e_half), "V", f"置信度: {conf_map.get(confidence, confidence)}"])
                    rows.append(["ORR 极限电流", format_float(j_l, 6), self._y_label().split("/")[-1].strip(), "平台区均值"])
                    ax.axvline(e_half, color="#9467bd", linestyle=":", linewidth=1.1, alpha=0.9)
                    try:
                        slope, intercept, r2, start, end = tafel_slope(selected_pot, selected_cur, j_l)
                        rows.append(["Tafel 斜率", format_float(slope, 2), "mV/dec", f"R²={r2:.4f}, 点 {start}~{end}"])
                    except Exception as exc:
                        rows.append(["Tafel 斜率", "N/A", "mV/dec", f"计算失败: {exc}"])
                except Exception as exc:
                    rows.append(["ORR 专项分析", "N/A", "", f"计算失败: {exc}"])

            self.plot_widget.refresh()

            self.derivative_plot.clear()
            dax = self.derivative_plot.ax
            derivative_drawn = False
            for measurement in curves:
                # 对比模式下使用各自独立的处理参数
                if self._comparison_mode:
                    key = CurveConfigCard._make_key(measurement)
                    cfg = self._comparison_configs.get(key)
                    if cfg is not None:
                        pot, cur = apply_lsv_processing(measurement, cfg[1])
                    else:
                        pot, cur = self._prepare_curve(measurement)
                else:
                    pot, cur = self._prepare_curve(measurement)
                    cfg = None
                try:
                    dpot, dcur = derivative_xy(pot, cur)
                    if self._comparison_mode:
                        dlabel = get_legend_label(measurement, cfg[1]) if cfg else measurement_name(measurement)
                    else:
                        dlabel = measurement_name(measurement)
                    dax.plot(dpot, dcur, linewidth=1.4, label=dlabel)
                    derivative_drawn = True
                except Exception:
                    continue
            dax.set_xlabel(self._x_label())
            dax.set_ylabel(f"d({self._y_label().split('/')[0].strip()})/dE")
            if title:
                dax.set_title(f"{title} - 微分曲线")
            apply_publication_style(dax)
            if derivative_drawn:
                line_x = np.concatenate([line.get_xdata() for line in dax.lines])
                line_y = np.concatenate([line.get_ydata() for line in dax.lines])
                set_auto_limits(dax, line_x, line_y)
                dax.legend(fontsize=8)
            self.derivative_plot.refresh()
            if self.chk_derivative.isChecked():
                self.plot_tabs.setCurrentWidget(self.derivative_plot)

            self._last_rows = rows
            set_table_rows(self.result_table, rows)
            self._fig_created = True
            self.btn_export_plot.setEnabled(True)
            self.btn_export_curve.setEnabled(True)
        except Exception as exc:
            if not silent:
                QMessageBox.critical(self, "分析错误", f"执行 LSV 分析时出错:\n{exc}")

    def _run_peak_detection(self, checked=False):
        if self._measurement is None:
            QMessageBox.warning(self, "提示", "请先选择 LSV 数据。")
            return

        try:
            self._run_analysis(silent=True)
            selected_pot, selected_cur = self._prepare_curve(self._measurement)
            peaks = self._detect_peaks(selected_pot, selected_cur)

            rows = list(self._last_rows)
            ax = self.plot_widget.ax
            if peaks:
                for idx, (kind, ep, ip) in enumerate(peaks[:8], start=1):
                    rows.append([
                        f"{kind} {idx}",
                        f"E={ep:.4f}, I={ip:.6g}",
                        "V, 电流",
                        "手动触发，按 5% prominence 检测",
                    ])
                    ax.scatter([ep], [ip], s=38, zorder=5)
            else:
                rows.append(["峰检测", "未检出明显峰", "", "手动触发，按 5% prominence 检测"])

            self._last_rows = rows
            set_table_rows(self.result_table, rows)
            self.plot_widget.refresh()
            self._fig_created = True
            self.btn_export_plot.setEnabled(True)
            self.btn_export_curve.setEnabled(True)
        except Exception as exc:
            QMessageBox.critical(self, "峰检测失败", str(exc))

    def _fill_rs_from_eis(self):
        eis_measurements = [m for m in self._all_measurements if technique_value(m) == "EIS"]
        if not eis_measurements:
            QMessageBox.information(self, "未找到 EIS", "当前项目中没有可用于估算 Rs 的 EIS 数据。")
            return

        selected = self._choose_eis_measurement(eis_measurements)
        if selected is None:
            return

        measurement = selected
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

    def _choose_eis_measurement(self, eis_measurements):
        if len(eis_measurements) == 1:
            return eis_measurements[0]

        dialog = QDialog(self)
        dialog.setWindowTitle("选择 EIS 数据")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("选择用于估算 Rs 的 EIS 数据:"))
        cb = QComboBox()
        for m in eis_measurements:
            cb.addItem(measurement_label(m), m)
        cb.setCurrentIndex(0)
        layout.addWidget(cb)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        return cb.currentData()

    def _run_kl(self):
        rpm_curves = {}
        missing = 0
        for measurement in self._lsv_measurements:
            rpm = measurement.metadata.get("rotation_rpm")
            if rpm is None:
                missing += 1
                continue
            try:
                rpm_value = float(rpm)
            except (TypeError, ValueError):
                missing += 1
                continue
            rpm_curves[rpm_value] = self._prepare_curve(measurement)

        if len(rpm_curves) < 3:
            QMessageBox.warning(
                self,
                "K-L 分析",
                f"至少需要 3 组带 rotation_rpm 元数据的 LSV 数据。\n"
                f"当前可用: {len(rpm_curves)}，缺少转速: {missing}。",
            )
            return

        try:
            n, intercept = kl_plot(rpm_curves)
            rows = list(self._last_rows)
            rows.extend([
                ["K-L 电子转移数 n", format_float(n, 2), "", f"使用 {len(rpm_curves)} 组转速"],
                ["K-L 截距", format_float(intercept, 6), "cm²/mA", "对应 1/j_k"],
            ])
            self._last_rows = rows
            set_table_rows(self.result_table, rows)
        except Exception as exc:
            QMessageBox.critical(self, "K-L 分析失败", str(exc))

    def _export_plot(self):
        if not self._fig_created:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存图表",
            "lsv_plot.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;TIFF (*.tiff)",
        )
        if not path:
            return
        current_plot = self.plot_tabs.currentWidget()
        if isinstance(current_plot, PlotWidget):
            current_plot.save_figure(path)

    def _export_curve_data(self):
        if self._measurement is None:
            QMessageBox.warning(self, "提示", "请先选择 LSV 数据。")
            return
        curves = self._current_curve_set()
        if not curves:
            return

        def _get_curve_data(measurement):
            if self._comparison_mode:
                key = CurveConfigCard._make_key(measurement)
                cfg = self._comparison_configs.get(key)
                if cfg is not None:
                    return apply_lsv_processing(measurement, cfg[1])
            return self._prepare_curve(measurement)

        pot, cur = _get_curve_data(curves[0])
        headers = ["Potential/V"]
        columns = []
        if len(curves) == 1:
            headers = ["Potential/V", "Current/A"]
            columns = [pot, cur]
        else:
            for i, measurement in enumerate(curves):
                p, c = _get_curve_data(measurement)
                if i == 0:
                    columns.append(p)
                else:
                    columns.append(np.full_like(p, np.nan))
                columns.append(c)
                headers.append(f"Current_{measurement_name(measurement)}/A")
        export_curve_data(self, "lsv_curve_data.csv", columns, headers)

    def get_current_data(self):
        if self._measurement is None:
            return None, None
        return self._prepare_curve(self._measurement)
