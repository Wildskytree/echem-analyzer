"""多曲线对比叠加组件。

提供可复用的多曲线对比面板和对话框，支持：
- 每条数据独立设置处理参数
- 勾选/取消勾选控制显示
- 所有选中曲线绘制在同一坐标轴
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from gui.widgets.analysis_common import measurement_label, measurement_name, technique_value


# ──────────────────────────────────────────────
# 数据处理参数定义
# ──────────────────────────────────────────────


@dataclass
class CurveProcessingParams:
    """单条曲线的处理参数。"""

    # 显示控制
    visible: bool = True
    label_override: str = ""

    # RHE 转换
    to_rhe: bool = True
    reference: str = "Ag/AgCl"
    ph: float = 13.0
    temperature: float = 298.15

    # iR 补偿
    ir_enabled: bool = False
    rs: float = 0.0
    ir_percent: int = 100

    # 归一化
    normalize_mode: str = "不归一化"  # "不归一化" | "按面积 (mA/cm²)" | "按质量 (mA/mg)"
    area: float = 0.196
    loading: float = 0.2

    # 平滑
    smooth: bool = False
    smooth_window: int = 11
    smooth_order: int = 2


def default_lsv_params() -> CurveProcessingParams:
    """返回 LSV 的默认处理参数。"""
    return CurveProcessingParams(
        to_rhe=True,
        reference="Ag/AgCl",
        ph=13.0,
        temperature=298.15,
        ir_enabled=False,
        rs=0.0,
        ir_percent=100,
        normalize_mode="不归一化",
        area=0.196,
        loading=0.2,
        smooth=False,
        smooth_window=11,
        smooth_order=2,
    )


@dataclass
class StabilityProcessingParams:
    """单条稳定性曲线的处理参数。"""

    visible: bool = True
    label_override: str = ""
    time_unit: str = "小时 (h)"
    value_mode: int = 1  # 0=原始, 1=电流密度
    area: float = 0.196
    ir_enabled: bool = False
    rs: float = 0.0


# ──────────────────────────────────────────────
# 单条曲线配置卡片
# ──────────────────────────────────────────────


class CurveConfigCard(QFrame):
    """单条曲线的配置卡片，包含处理参数控件。"""

    visibility_changed = Signal(str, bool)  # measurement_key, visible
    params_changed = Signal(str)  # measurement_key

    def __init__(
        self,
        measurement: Any,
        params: CurveProcessingParams,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._measurement = measurement
        self._params = params
        self._key = self._make_key(measurement)
        self._expanded = False
        self._setup_ui()

    @staticmethod
    def _make_key(measurement: Any) -> str:
        """生成测量数据的唯一键。"""
        name = measurement_name(measurement)
        h = measurement.file_hash or str(id(measurement))
        return f"{name}::{h}"

    @property
    def measurement(self) -> Any:
        return self._measurement

    @property
    def measurement_key(self) -> str:
        return self._key

    @property
    def params(self) -> CurveProcessingParams:
        return self._params

    def _setup_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # ── 头部行：勾选框 + 名称 + 展开按钮 ──
        header = QHBoxLayout()
        header.setSpacing(6)

        self.chk_visible = QCheckBox()
        self.chk_visible.setChecked(self._params.visible)
        self.chk_visible.toggled.connect(self._on_visibility_toggled)
        header.addWidget(self.chk_visible)

        name = measurement_label(self._measurement)
        self.lbl_name = QLabel(name)
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header.addWidget(self.lbl_name, 1)

        self.btn_expand = QPushButton("设置 ▼")
        self.btn_expand.setFixedWidth(70)
        self.btn_expand.setCheckable(True)
        self.btn_expand.clicked.connect(self._toggle_expand)
        header.addWidget(self.btn_expand)

        layout.addLayout(header)

        # ── 展开后的参数控件 ──
        self._detail_widget = QWidget()
        self._detail_widget.setVisible(False)
        detail_layout = QVBoxLayout(self._detail_widget)
        detail_layout.setContentsMargins(24, 4, 4, 4)
        detail_layout.setSpacing(2)

        # 标签覆盖
        label_row = QHBoxLayout()
        label_row.addWidget(QLabel("图例标签:"))
        self.txt_label = QLineEdit(self._params.label_override)
        self.txt_label.setPlaceholderText("留空使用默认名称")
        self.txt_label.textChanged.connect(lambda: self._emit_params_changed())
        label_row.addWidget(self.txt_label, 1)
        detail_layout.addLayout(label_row)

        # RHE 转换组
        rhe_group = QGroupBox("RHE 转换")
        rhe_group.setFlat(True)
        rhe_layout = QFormLayout(rhe_group)
        rhe_layout.setContentsMargins(0, 2, 0, 2)

        self.chk_rhe = QCheckBox("转换到 RHE")
        self.chk_rhe.setChecked(self._params.to_rhe)
        self.chk_rhe.toggled.connect(lambda: self._emit_params_changed())
        rhe_layout.addRow("", self.chk_rhe)

        self.cb_ref = QComboBox()
        self.cb_ref.addItems(["Ag/AgCl", "SCE", "Hg/HgO", "RHE"])
        self.cb_ref.setCurrentText(self._params.reference)
        self.cb_ref.currentTextChanged.connect(lambda: self._emit_params_changed())
        rhe_layout.addRow("参比电极:", self.cb_ref)

        self.spin_ph = QDoubleSpinBox()
        self.spin_ph.setRange(-2, 16)
        self.spin_ph.setValue(self._params.ph)
        self.spin_ph.setSingleStep(0.1)
        self.spin_ph.valueChanged.connect(lambda: self._emit_params_changed())
        rhe_layout.addRow("pH:", self.spin_ph)

        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(250, 380)
        self.spin_temp.setValue(self._params.temperature)
        self.spin_temp.setSuffix(" K")
        self.spin_temp.valueChanged.connect(lambda: self._emit_params_changed())
        rhe_layout.addRow("温度:", self.spin_temp)
        detail_layout.addWidget(rhe_group)

        # iR 补偿组
        ir_group = QGroupBox("iR 补偿")
        ir_group.setFlat(True)
        ir_layout = QFormLayout(ir_group)
        ir_layout.setContentsMargins(0, 2, 0, 2)

        self.chk_ir = QCheckBox("启用 iR 补偿")
        self.chk_ir.setChecked(self._params.ir_enabled)
        self.chk_ir.toggled.connect(lambda: self._emit_params_changed())
        ir_layout.addRow("", self.chk_ir)

        self.spin_rs = QDoubleSpinBox()
        self.spin_rs.setRange(0.0, 1_000_000.0)
        self.spin_rs.setDecimals(4)
        self.spin_rs.setSuffix(" Ω")
        self.spin_rs.setValue(self._params.rs)
        self.spin_rs.valueChanged.connect(lambda: self._emit_params_changed())
        ir_layout.addRow("Rs:", self.spin_rs)

        self.spin_ir_percent = QSpinBox()
        self.spin_ir_percent.setRange(1, 100)
        self.spin_ir_percent.setValue(self._params.ir_percent)
        self.spin_ir_percent.setSuffix(" %")
        self.spin_ir_percent.valueChanged.connect(lambda: self._emit_params_changed())
        ir_layout.addRow("补偿百分比:", self.spin_ir_percent)
        detail_layout.addWidget(ir_group)

        # 归一化组
        norm_group = QGroupBox("归一化")
        norm_group.setFlat(True)
        norm_layout = QFormLayout(norm_group)
        norm_layout.setContentsMargins(0, 2, 0, 2)

        self.cb_norm = QComboBox()
        self.cb_norm.addItems(["不归一化", "按面积 (mA/cm²)", "按质量 (mA/mg)"])
        self.cb_norm.setCurrentText(self._params.normalize_mode)
        self.cb_norm.currentTextChanged.connect(lambda: self._emit_params_changed())
        norm_layout.addRow("归一化:", self.cb_norm)

        self.spin_area = QDoubleSpinBox()
        self.spin_area.setRange(0.0001, 10_000.0)
        self.spin_area.setValue(self._params.area)
        self.spin_area.setSuffix(" cm²")
        self.spin_area.valueChanged.connect(lambda: self._emit_params_changed())
        norm_layout.addRow("电极面积:", self.spin_area)

        self.spin_loading = QDoubleSpinBox()
        self.spin_loading.setRange(0.0001, 10_000.0)
        self.spin_loading.setValue(self._params.loading)
        self.spin_loading.setSuffix(" mg/cm²")
        self.spin_loading.valueChanged.connect(lambda: self._emit_params_changed())
        norm_layout.addRow("负载量:", self.spin_loading)
        detail_layout.addWidget(norm_group)

        # 平滑组
        smooth_group = QGroupBox("Savitzky-Golay 平滑")
        smooth_group.setFlat(True)
        smooth_layout = QFormLayout(smooth_group)
        smooth_layout.setContentsMargins(0, 2, 0, 2)

        self.chk_smooth = QCheckBox("启用平滑")
        self.chk_smooth.setChecked(self._params.smooth)
        self.chk_smooth.toggled.connect(lambda: self._emit_params_changed())
        smooth_layout.addRow("", self.chk_smooth)

        self.spin_sw = QSpinBox()
        self.spin_sw.setRange(3, 501)
        self.spin_sw.setValue(self._params.smooth_window)
        self.spin_sw.setSingleStep(2)
        self.spin_sw.valueChanged.connect(lambda: self._emit_params_changed())
        smooth_layout.addRow("窗口:", self.spin_sw)

        self.spin_so = QSpinBox()
        self.spin_so.setRange(1, 5)
        self.spin_so.setValue(self._params.smooth_order)
        self.spin_so.valueChanged.connect(lambda: self._emit_params_changed())
        smooth_layout.addRow("阶数:", self.spin_so)
        detail_layout.addWidget(smooth_group)

        layout.addWidget(self._detail_widget)

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self._detail_widget.setVisible(self._expanded)
        self.btn_expand.setText("设置 ▲" if self._expanded else "设置 ▼")

    def _on_visibility_toggled(self, checked: bool):
        self._params.visible = checked
        self.visibility_changed.emit(self._key, checked)

    def _emit_params_changed(self):
        # 从控件更新参数
        self._sync_params_from_ui()
        self.params_changed.emit(self._key)

    def sync_params_from_ui(self):
        """从 UI 控件读取值更新参数对象。"""
        self._sync_params_from_ui()

    def _sync_params_from_ui(self):
        self._params.visible = self.chk_visible.isChecked()
        self._params.label_override = self.txt_label.text().strip()
        self._params.to_rhe = self.chk_rhe.isChecked()
        self._params.reference = self.cb_ref.currentText()
        self._params.ph = self.spin_ph.value()
        self._params.temperature = self.spin_temp.value()
        self._params.ir_enabled = self.chk_ir.isChecked()
        self._params.rs = self.spin_rs.value()
        self._params.ir_percent = self.spin_ir_percent.value()
        self._params.normalize_mode = self.cb_norm.currentText()
        self._params.area = self.spin_area.value()
        self._params.loading = self.spin_loading.value()
        self._params.smooth = self.chk_smooth.isChecked()
        self._params.smooth_window = self.spin_sw.value()
        self._params.smooth_order = self.spin_so.value()

    def update_from_params(self, params: CurveProcessingParams):
        """从外部参数对象更新 UI 控件。"""
        self._params = params
        self.chk_visible.setChecked(params.visible)
        self.txt_label.setText(params.label_override)
        self.chk_rhe.setChecked(params.to_rhe)
        self.cb_ref.setCurrentText(params.reference)
        self.spin_ph.setValue(params.ph)
        self.spin_temp.setValue(params.temperature)
        self.chk_ir.setChecked(params.ir_enabled)
        self.spin_rs.setValue(params.rs)
        self.spin_ir_percent.setValue(params.ir_percent)
        self.cb_norm.setCurrentText(params.normalize_mode)
        self.spin_area.setValue(params.area)
        self.spin_loading.setValue(params.loading)
        self.chk_smooth.setChecked(params.smooth)
        self.spin_sw.setValue(params.smooth_window)
        self.spin_so.setValue(params.smooth_order)


# ──────────────────────────────────────────────
# 多曲线对比对话框
# ──────────────────────────────────────────────


class MultiCurveComparisonDialog(QDialog):
    """多曲线对比配置对话框。

    显示所有指定类型的测量数据，每条数据可以独立配置处理参数，
    并通过勾选框控制可见性。
    """

    def __init__(
        self,
        measurements: List[Any],
        technique_type: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._measurements = list(measurements)
        self._technique_type = technique_type
        self._cards: List[CurveConfigCard] = []
        self._params_map: Dict[str, CurveProcessingParams] = {}
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(f"多曲线对比配置 - {self._technique_type}")
        self.setMinimumSize(520, 500)
        self.resize(580, 600)

        layout = QVBoxLayout(self)

        title_label = QLabel(
            f"共 {len(self._measurements)} 条 {self._technique_type} 数据，"
            "勾选需要显示的数据并单独设置处理参数："
        )
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # 快捷操作行
        quick_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_deselect_all = QPushButton("全不选")
        self.btn_deselect_all.clicked.connect(self._deselect_all)
        self.btn_copy_global = QPushButton("从全局参数初始化")
        self.btn_copy_global.clicked.connect(self._copy_global_params)
        quick_layout.addWidget(self.btn_select_all)
        quick_layout.addWidget(self.btn_deselect_all)
        quick_layout.addWidget(self.btn_copy_global)
        quick_layout.addStretch()
        layout.addLayout(quick_layout)

        # 滚动区域放置所有曲线卡片
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setSpacing(8)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)

        for m in self._measurements:
            params = self._get_or_create_params(m)
            card = CurveConfigCard(m, params)
            card.visibility_changed.connect(self._on_card_visibility_changed)
            self._cards.append(card)
            self._scroll_layout.addWidget(card)

        self._scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.lbl_summary = QLabel("")
        self._update_summary()
        btn_layout.addWidget(self.lbl_summary, 1)

        self.btn_apply = QPushButton("✅ 应用并显示对比图")
        self.btn_apply.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def _get_or_create_params(self, measurement) -> CurveProcessingParams:
        key = CurveConfigCard._make_key(measurement)
        if key not in self._params_map:
            self._params_map[key] = default_lsv_params()
        return self._params_map[key]

    def _on_card_visibility_changed(self, key: str, visible: bool):
        self._update_summary()

    def _update_summary(self):
        visible_count = sum(
            1 for card in self._cards if card.chk_visible.isChecked()
        )
        self.lbl_summary.setText(
            f"已选中 {visible_count}/{len(self._cards)} 条数据"
        )

    def _select_all(self):
        for card in self._cards:
            card.chk_visible.setChecked(True)
        self._update_summary()

    def _deselect_all(self):
        for card in self._cards:
            card.chk_visible.setChecked(False)
        self._update_summary()

    def _copy_global_params(self):
        """将所有卡片的参数重置为默认值。"""
        for card in self._cards:
            default = default_lsv_params()
            card.update_from_params(default)
        QMessageBox.information(self, "已初始化", "所有曲线已使用默认处理参数。")

    def get_configurations(self) -> Dict[str, Tuple[Any, CurveProcessingParams]]:
        """获取所有配置结果。

        Returns:
            Dict[str, Tuple[measurement, params]]: 键为 measurement_key 的配置映射。
        """
        result = {}
        for card in self._cards:
            card.sync_params_from_ui()
            result[card.measurement_key] = (card.measurement, card.params)
        return result

    def get_visible_configurations(self) -> Dict[str, Tuple[Any, CurveProcessingParams]]:
        """仅返回可见曲线的配置。"""
        return {
            k: v
            for k, v in self.get_configurations().items()
            if v[1].visible
        }


# ──────────────────────────────────────────────
# 标签页集成辅助函数
# ──────────────────────────────────────────────


def apply_lsv_processing(
    measurement: Any,
    params: CurveProcessingParams,
) -> Tuple[np.ndarray, np.ndarray]:
    """使用给定的参数对 LSV 数据进行处理，返回 (potential, current)。"""
    from scipy.signal import savgol_filter

    from echem_core.processing.convert import current_density, current_to_mass_activity, to_rhe

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

    # iR 补偿
    if params.ir_enabled and params.rs > 0:
        ir_fraction = params.ir_percent / 100.0
        pot = pot - cur_a * params.rs * ir_fraction

    # RHE 转换
    if params.to_rhe:
        pot = to_rhe(
            pot,
            reference=params.reference,
            pH=params.ph,
            temperature=params.temperature,
        )

    # 归一化
    if params.normalize_mode.startswith("按面积"):
        cur = current_density(cur_a, params.area)
    elif params.normalize_mode.startswith("按质量"):
        cur = current_to_mass_activity(
            cur_a,
            loading_mg_cm2=params.loading,
            area_cm2=params.area,
        )
    else:
        cur = cur_a

    # 平滑
    if params.smooth and cur.size >= 5:
        try:
            window = min(
                params.smooth_window,
                cur.size if cur.size % 2 == 1 else cur.size - 1,
            )
            order = min(params.smooth_order, max(1, window - 2))
            if window <= order:
                window = order + 2
            if window % 2 == 0:
                window += 1
            if window <= cur.size and window >= 3:
                cur = savgol_filter(cur, window, order)
        except Exception:
            pass

    return pot, cur


def lsv_y_label(params: CurveProcessingParams) -> str:
    """根据参数返回纵轴标签。"""
    if params.normalize_mode.startswith("按面积"):
        return "j / mA cm⁻²"
    if params.normalize_mode.startswith("按质量"):
        return "质量活性 / mA mg⁻¹"
    return "I / A"


def lsv_x_label(params: CurveProcessingParams) -> str:
    """根据参数返回横轴标签。"""
    return "E / V vs. RHE" if params.to_rhe else "E / V"


def get_legend_label(measurement: Any, params: CurveProcessingParams) -> str:
    """获取曲线的图例标签。"""
    if params.label_override:
        return params.label_override
    return measurement_name(measurement)


# ──────────────────────────────────────────────
# 稳定性曲线处理
# ──────────────────────────────────────────────


def apply_stability_processing(
    measurement: Any,
    params: StabilityProcessingParams,
) -> Tuple[np.ndarray, np.ndarray, str]:
    """使用给定的参数对稳定性数据进行处理，返回 (time, y, tech)。"""
    from echem_core.processing.convert import current_density

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
        if params.ir_enabled and params.rs > 0:
            y = y - current * params.rs
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
        if params.value_mode == 1:
            y = current_density(y, params.area)

    # 过滤非有限值
    from gui.widgets.analysis_common import finite_xy

    time, y = finite_xy(time, y)
    if time.size < 2:
        raise ValueError("有效时间序列数据点不足。")

    order = np.argsort(time)
    return time[order], y[order], tech


# ──────────────────────────────────────────────
# 简化版多曲线对比对话框（适用于 CV / EIS）
# ──────────────────────────────────────────────


class SimpleCurveCheckItem(QFrame):
    """简化版单条曲线勾选项。"""

    def __init__(
        self,
        measurement: Any,
        checked: bool = True,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._measurement = measurement
        self._setup_ui(checked)

    def _setup_ui(self, checked: bool):
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.chk_visible = QCheckBox()
        self.chk_visible.setChecked(checked)
        layout.addWidget(self.chk_visible)

        self.lbl_name = QLabel(measurement_label(self._measurement))
        self.lbl_name.setWordWrap(True)
        layout.addWidget(self.lbl_name, 1)

    @property
    def measurement(self) -> Any:
        return self._measurement

    @property
    def is_checked(self) -> bool:
        return self.chk_visible.isChecked()


class SimpleComparisonDialog(QDialog):
    """简化版多曲线对比对话框（适用于 CV / EIS / 其他无处理参数的标签页）。"""

    def __init__(
        self,
        measurements: List[Any],
        technique_type: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._measurements = list(measurements)
        self._technique_type = technique_type
        self._items: List[SimpleCurveCheckItem] = []
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(f"多曲线对比 - {self._technique_type}")
        self.setMinimumSize(400, 350)
        self.resize(460, 400)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"共 {len(self._measurements)} 条 {self._technique_type} 数据，勾选需要叠加显示的曲线："))

        # 快捷操作
        quick_layout = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_all.clicked.connect(self._select_all)
        btn_none = QPushButton("全不选")
        btn_none.clicked.connect(self._deselect_all)
        quick_layout.addWidget(btn_all)
        quick_layout.addWidget(btn_none)
        quick_layout.addStretch()
        layout.addLayout(quick_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        clayout = QVBoxLayout(content)
        clayout.setSpacing(4)
        for m in self._measurements:
            item = SimpleCurveCheckItem(m)
            self._items.append(item)
            clayout.addWidget(item)
        clayout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        btn_layout = QHBoxLayout()
        self.lbl_summary = QLabel("")
        self._update_summary()
        btn_layout.addWidget(self.lbl_summary, 1)
        btn_apply = QPushButton("✅ 应用并显示")
        btn_apply.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_apply)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _update_summary(self):
        visible = sum(1 for it in self._items if it.is_checked)
        self.lbl_summary.setText(f"已选中 {visible}/{len(self._items)} 条数据")

    def _select_all(self):
        for it in self._items:
            it.chk_visible.setChecked(True)
        self._update_summary()

    def _deselect_all(self):
        for it in self._items:
            it.chk_visible.setChecked(False)
        self._update_summary()

    def get_visible_measurements(self) -> List[Any]:
        return [it.measurement for it in self._items if it.is_checked]
