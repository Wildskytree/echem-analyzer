"""CV（循环伏安法）绘图函数。

提供循环伏安曲线的绘制、峰标注和多曲线叠加比较功能。
"""

from __future__ import annotations

from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from echem_core.analysis.cv import find_peaks
from echem_core.model.measurement import Measurement
from echem_core.plotting.styles import JournalStyle, get_style, list_styles


# ── 内部辅助函数 ──────────────────────────────────────────────────────────


def _get_data(measurement: Measurement):
    """获取测量数据的电位和电流数组（优先使用处理后的数据）。

    Parameters
    ----------
    measurement : Measurement
        电化学测量对象。

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (potential, current) 数组对。
    """
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
    return potential, current


def _split_cycles(
    potential: np.ndarray, current: np.ndarray
) -> List[Dict[str, np.ndarray]]:
    """将多周期 CV 数据拆分为各个循环。

    通过检测电位信号的方向转折点，将完整数据拆分为多个循环。
    每个循环包含正向扫描（电位升高）和反向扫描（电位降低）。

    Parameters
    ----------
    potential : np.ndarray
        电位数组（V）。
    current : np.ndarray
        电流数组（A）。

    Returns
    -------
    list[dict]
        循环列表，每个元素为包含以下键的字典：

        - ``"forward_potential"``: 正向扫描电位
        - ``"forward_current"``: 正向扫描电流
        - ``"backward_potential"``: 反向扫描电位
        - ``"backward_current"``: 反向扫描电流
    """
    # 计算电位方向变化
    diff = np.diff(potential)
    signs = np.sign(diff)
    sign_changes = np.where(np.diff(signs, prepend=signs[0]) != 0)[0]

    # 无法识别方向变化 → 回退为单个循环
    if len(sign_changes) < 2:
        mid = len(potential) // 2
        fwd_pot, fwd_cur = potential[:mid], current[:mid]
        rev_pot, rev_cur = potential[mid:], current[mid:]
        # 确保方向正确
        if fwd_pot[-1] < fwd_pot[0]:
            fwd_pot, fwd_cur = fwd_pot[::-1], fwd_cur[::-1]
        if rev_pot[-1] > rev_pot[0]:
            rev_pot, rev_cur = rev_pot[::-1], rev_cur[::-1]
        return [
            {
                "forward_potential": fwd_pot,
                "forward_current": fwd_cur,
                "backward_potential": rev_pot,
                "backward_current": rev_cur,
            }
        ]

    # 收集所有方向分段
    segments: List[Dict] = []
    for i in range(len(sign_changes)):
        start = int(sign_changes[i - 1]) if i > 0 else 0
        end = int(sign_changes[i]) + 1
        if end - start < 3:
            continue
        seg_pot = potential[start:end]
        seg_cur = current[start:end]
        if seg_pot[-1] > seg_pot[0]:
            seg_type = "forward"
        elif seg_pot[-1] < seg_pot[0]:
            seg_type = "backward"
        else:
            continue
        segments.append({"type": seg_type, "potential": seg_pot, "current": seg_cur})

    # 将连续的正向 + 反向配对组合为完整循环
    cycles: List[Dict[str, np.ndarray]] = []
    i = 0
    while i < len(segments):
        if segments[i]["type"] == "forward":
            fwd = segments[i]
            if i + 1 < len(segments) and segments[i + 1]["type"] == "backward":
                rev = segments[i + 1]
                cycles.append(
                    {
                        "forward_potential": fwd["potential"],
                        "forward_current": fwd["current"],
                        "backward_potential": rev["potential"],
                        "backward_current": rev["current"],
                    }
                )
                i += 2
            else:
                i += 1
        else:
            i += 1

    # 未能配成任何循环时回退
    if not cycles:
        mid = len(potential) // 2
        cycles.append(
            {
                "forward_potential": potential[:mid],
                "forward_current": current[:mid],
                "backward_potential": potential[mid:],
                "backward_current": current[mid:],
            }
        )

    return cycles


# ── 公开 API ──────────────────────────────────────────────────────────────


def plot_cv(
    measurement: Measurement,
    style: str = "acs_double",
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    annotate_peaks: bool = False,
) -> Figure:
    """绘制循环伏安（CV）曲线。

    以电位为横坐标、电流为纵坐标绘制 CV 曲线。多周期测量时，不同循环
    使用不同颜色区分，正向扫描为实线、反向扫描为虚线。

    仅当 ``annotate_peaks=True`` 时，才使用
    :func:`echem_core.analysis.cv.find_peaks` 检测氧化峰和还原峰并标注。

    Parameters
    ----------
    measurement : Measurement
        电化学测量对象（必须为 CV 技术）。
    style : str, optional
        期刊绘图风格名称，例如 ``"acs_single"``、``"acs_double"``、
        ``"rsc"``、``"wiley"``。不区分大小写。默认为 ``"acs_double"``。
    title : str, optional
        图表标题。为 ``None`` 时自动选用样品名或默认标题。
    save_path : str, optional
        图片保存路径。若提供，根据文件扩展名推断保存格式
        （支持 png、pdf、svg、eps、jpg、tiff）。
    annotate_peaks : bool, optional
        是否在图上标注氧化峰和还原峰。默认为 ``False``，避免自动峰检测。

    Returns
    -------
    Figure
        Matplotlib 图形对象，可在后续继续修改。

    Raises
    ------
    TypeError
        ``measurement`` 不是 :class:`Measurement` 实例。
    KeyError
        指定的 ``style`` 名称未注册。

    Examples
    --------
    >>> from echem_core.model import Measurement, Technique
    >>> import numpy as np
    >>> pot = np.linspace(-0.5, 1.0, 500)
    >>> cur = np.sin(2 * np.pi * pot / 1.5) * 1e-3
    >>> m = Measurement(Technique.CV, pot, cur)
    >>> fig = plot_cv(m, style="acs_single", title="My CV")
    """
    if not isinstance(measurement, Measurement):
        raise TypeError(
            f"measurement 必须是 Measurement 实例，收到 {type(measurement).__name__}"
        )

    # ── 获取风格 ──────────────────────────────────────────────────────────
    js: JournalStyle = get_style(style.upper())

    # ── 获取数据 ──────────────────────────────────────────────────────────
    potential, current = _get_data(measurement)

    # ── 拆分循环 ──────────────────────────────────────────────────────────
    cycles = _split_cycles(potential, current)
    n_cycles = len(cycles)

    # ── 创建图形 ──────────────────────────────────────────────────────────
    fig, ax = plt.subplots()
    js.apply(ax)

    # ── 绘制各循环 ────────────────────────────────────────────────────────
    colors = js.colors
    for i, cycle in enumerate(cycles):
        color = colors[i % len(colors)]
        label = f"Cycle {i + 1}" if n_cycles > 1 else None

        # 正向扫描（实线）
        ax.plot(
            cycle["forward_potential"],
            cycle["forward_current"],
            color=color,
            linestyle="-",
            linewidth=js.line_width,
            label=label,
        )
        # 反向扫描（虚线）
        ax.plot(
            cycle["backward_potential"],
            cycle["backward_current"],
            color=color,
            linestyle="--",
            linewidth=js.line_width,
        )

    # ── 峰标注 ────────────────────────────────────────────────────────────
    if annotate_peaks:
        peaks = find_peaks(potential, current, direction="both")
        current_range = np.max(current) - np.min(current)
        offset = 0.05 * current_range if current_range > 0 else 0.01 * abs(np.mean(current))

        for peak in peaks:
            ep = peak["peak_potential"]
            ip = peak["peak_current"]

            if peak["peak_type"] == "oxidative":
                va = "bottom"
                label_y = ip + offset
                arrow_color = colors[1 % len(colors)]
            else:
                va = "top"
                label_y = ip - offset
                arrow_color = colors[2 % len(colors)]

            ax.annotate(
                f"{ep:.3f} V, {ip:.2e} A",
                xy=(ep, ip),
                xytext=(ep, label_y),
                fontsize=js.font_size - 2,
                ha="center",
                va=va,
                color=arrow_color,
                arrowprops=dict(arrowstyle="->", color=arrow_color, lw=0.8),
            )

    # ── 坐标轴标签 ────────────────────────────────────────────────────────
    ax.set_xlabel("Potential / V")
    ax.set_ylabel("Current / A")

    # ── 标题 ──────────────────────────────────────────────────────────────
    if title is not None:
        ax.set_title(title)
    elif measurement.metadata.get("sample_name"):
        ax.set_title(measurement.metadata["sample_name"])
    else:
        ax.set_title("Cyclic Voltammetry")

    # ── 图例（仅多周期） ──────────────────────────────────────────────────
    if n_cycles > 1:
        ax.legend(frameon=False, fontsize=js.font_size - 1)

    # ── 布局与保存 ────────────────────────────────────────────────────────
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=js.dpi, bbox_inches="tight")

    return fig


def plot_cv_comparison(
    measurements: List[Measurement],
    labels: Optional[List[str]] = None,
    style: str = "acs_double",
    save_path: Optional[str] = None,
) -> Figure:
    """叠加绘制多条循环伏安（CV）曲线用于比较。

    将多个测量对象的 CV 曲线绘制在同一张图上，便于直观对比不同样品、
    不同条件或不同扫描速率下的电化学行为。每条曲线使用不同颜色区分。

    Parameters
    ----------
    measurements : list[Measurement]
        待比较的测量对象列表。
    labels : list[str], optional
        每条曲线的图例标签。长度必须与 ``measurements`` 一致。
        为 ``None`` 时自动使用样品名称或 ``"Sample N"``。
    style : str, optional
        期刊绘图风格名称，例如 ``"acs_single"``、``"acs_double"``、
        ``"rsc"``、``"wiley"``。不区分大小写。默认为 ``"acs_double"``。
    save_path : str, optional
        图片保存路径。若提供，根据文件扩展名推断保存格式
        （支持 png、pdf、svg、eps、jpg、tiff）。为 ``None`` 时不保存。

    Returns
    -------
    Figure
        Matplotlib 图形对象，可在后续继续修改。

    Raises
    ------
    TypeError
        ``measurements`` 中的元素不是 :class:`Measurement` 实例。
    ValueError
        ``measurements`` 为空，或 ``labels`` 长度与 ``measurements`` 不一致。
    KeyError
        指定的 ``style`` 名称未注册。

    Examples
    --------
    >>> from echem_core.model import Measurement, Technique
    >>> import numpy as np
    >>> pot = np.linspace(-0.5, 1.0, 500)
    >>> m1 = Measurement(Technique.CV, pot, np.sin(2*np.pi*pot/1.5)*1e-3)
    >>> m2 = Measurement(Technique.CV, pot, np.sin(2*np.pi*pot/1.5)*2e-3)
    >>> fig = plot_cv_comparison([m1, m2], labels=["Slow", "Fast"])
    """
    if not measurements:
        raise ValueError("measurements 列表不能为空")

    for i, m in enumerate(measurements):
        if not isinstance(m, Measurement):
            raise TypeError(
                f"measurements[{i}] 必须是 Measurement 实例，"
                f"收到 {type(m).__name__}"
            )

    n = len(measurements)

    # ── 处理标签 ──────────────────────────────────────────────────────────
    if labels is not None:
        if len(labels) != n:
            raise ValueError(
                f"labels 的长度 ({len(labels)}) 必须与 measurements 的长度 ({n}) 一致"
            )
    else:
        labels = []
        for m in measurements:
            name = m.metadata.get("sample_name")
            labels.append(name if name else f"Sample {len(labels) + 1}")

    # ── 获取风格 ──────────────────────────────────────────────────────────
    js: JournalStyle = get_style(style.upper())

    # ── 创建图形 ──────────────────────────────────────────────────────────
    fig, ax = plt.subplots()
    js.apply(ax)

    # ── 绘制各曲线 ────────────────────────────────────────────────────────
    colors = js.colors
    for i, (m, label) in enumerate(zip(measurements, labels)):
        potential, current = _get_data(m)
        color = colors[i % len(colors)]

        ax.plot(
            potential,
            current,
            color=color,
            linewidth=js.line_width,
            label=label,
        )

    # ── 坐标轴标签与标题 ──────────────────────────────────────────────────
    ax.set_xlabel("Potential / V")
    ax.set_ylabel("Current / A")
    ax.set_title("Cyclic Voltammetry Comparison")

    # ── 图例 ──────────────────────────────────────────────────────────────
    ax.legend(frameon=False, fontsize=js.font_size)

    # ── 布局与保存 ────────────────────────────────────────────────────────
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=js.dpi, bbox_inches="tight")

    return fig


__all__ = [
    "plot_cv",
    "plot_cv_comparison",
]
