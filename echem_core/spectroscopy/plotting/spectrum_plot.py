"""光谱绘图函数。

提供光谱曲线的绘制、峰标注和多曲线叠加比较功能。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from echem_core.plotting.styles import JournalStyle, get_style
from echem_core.spectroscopy.model.spectrum import Spectrum


# ── 内部辅助函数 ──────────────────────────────────────────────────────────


def _get_data(spectrum: Spectrum) -> Tuple[np.ndarray, np.ndarray]:
    """获取光谱的 x/y 数据（优先使用处理后的数据）。

    Parameters
    ----------
    spectrum : Spectrum
        光谱对象。

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (x, y) 数组对。
    """
    x = (
        spectrum.processed_x
        if spectrum.processed_x is not None
        else spectrum.raw_x
    )
    y = (
        spectrum.processed_y
        if spectrum.processed_y is not None
        else spectrum.raw_y
    )
    return x, y


def _default_xlabel(spectrum: Spectrum) -> str:
    """根据光谱技术生成默认 x 轴标签。

    Parameters
    ----------
    spectrum : Spectrum
        光谱对象。

    Returns
    -------
    str
        默认 x 轴标签。
    """
    tech = spectrum.technique.value
    unit = spectrum.x_unit

    label_map: Dict[str, str] = {
        "Raman": "Raman shift",
        "XPS": "Binding energy",
        "UV-vis": "Wavelength",
        "FTIR": "Wavenumber",
        "NMR": "Chemical shift",
        "MS": "m/z",
        "PL": "Wavelength",
        "XRD": "2θ",
    }
    base = label_map.get(tech, "x")
    return f"{base} / {unit}" if unit else base


def _default_ylabel(spectrum: Spectrum) -> str:
    """根据光谱技术生成默认 y 轴标签。

    Parameters
    ----------
    spectrum : Spectrum
        光谱对象。

    Returns
    -------
    str
        默认 y 轴标签。
    """
    unit = spectrum.y_unit
    tech = spectrum.technique.value

    label_map: Dict[str, str] = {
        "Raman": "Intensity",
        "XPS": "Intensity / CPS",
        "UV-vis": "Absorbance",
        "FTIR": "Transmittance",
        "NMR": "Intensity",
        "MS": "Abundance",
        "PL": "Intensity / CPS",
        "XRD": "Intensity / CPS",
    }
    base = label_map.get(tech, "Intensity")
    return f"{base} / {unit}" if unit else base


# ── 公开 API ──────────────────────────────────────────────────────────────


def plot_spectrum(
    spectrum: Spectrum,
    style: str = "acs_double",
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    annotate_peaks: Optional[List[Tuple[float, str]]] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
) -> Figure:
    """绘制单条光谱曲线。

    以 x 为横坐标、y 为纵坐标绘制光谱曲线。自动优先使用处理后的
    （processed）数据，若不可用则回退到原始数据。

    可通过 ``annotate_peaks`` 参数手动指定需要标注的峰位置和标签。

    Parameters
    ----------
    spectrum : Spectrum
        光谱对象。
    style : str, optional
        期刊绘图风格名称，例如 ``\"acs_single\"``、``\"acs_double\"``、
        ``\"rsc\"``、``\"wiley\"``。不区分大小写。默认为 ``\"acs_double\"``。
    title : str, optional
        图表标题。为 ``None`` 时自动选用样品名或默认标题。
    save_path : str, optional
        图片保存路径。若提供，根据文件扩展名推断保存格式
        （支持 png、pdf、svg、eps、jpg、tiff）。为 ``None`` 时不保存。
    annotate_peaks : list[tuple[float, str]], optional
        需要标注的峰列表，每个元素为 ``(x_position, label)`` 二元组，
        例如 ``[(1500.0, "D band"), (1580.0, "G band")]``。
        为 ``None`` 时不进行标注。
    xlabel : str, optional
        x 轴标签。为 ``None`` 时根据光谱技术自动生成。
    ylabel : str, optional
        y 轴标签。为 ``None`` 时根据光谱技术自动生成。

    Returns
    -------
    Figure
        Matplotlib 图形对象，可在后续继续修改。

    Raises
    ------
    TypeError
        ``spectrum`` 不是 :class:`Spectrum` 实例。
    KeyError
        指定的 ``style`` 名称未注册。

    Examples
    --------
    >>> from echem_core.spectroscopy.model.spectrum import Spectrum
    >>> import numpy as np
    >>> x = np.linspace(100, 2000, 1000)
    >>> y = np.exp(-((x - 1500) ** 2) / 20000)
    >>> s = Spectrum("Raman", x, y, x_unit="cm⁻¹", y_unit="a.u.")
    >>> fig = plot_spectrum(s, style="acs_single", title="Raman Spectrum")
    """
    if not isinstance(spectrum, Spectrum):
        raise TypeError(
            f"spectrum 必须是 Spectrum 实例，收到 {type(spectrum).__name__}"
        )

    # ── 获取风格 ──────────────────────────────────────────────────────────
    js: JournalStyle = get_style(style.upper())

    # ── 获取数据 ──────────────────────────────────────────────────────────
    x, y = _get_data(spectrum)

    # ── 创建图形 ──────────────────────────────────────────────────────────
    fig, ax = plt.subplots()
    js.apply(ax)

    # ── 绘制光谱 ──────────────────────────────────────────────────────────
    ax.plot(x, y, color=js.colors[0], linewidth=js.line_width)

    # ── 峰标注 ────────────────────────────────────────────────────────────
    if annotate_peaks is not None:
        y_range = np.max(y) - np.min(y)
        offset = 0.05 * y_range if y_range > 0 else 0.01 * float(np.mean(np.abs(y)))

        for x_pos, label in annotate_peaks:
            # 查找 x_pos 附近最近数据点的 y 值
            idx = np.argmin(np.abs(x - x_pos))
            y_pos = y[idx]

            ax.annotate(
                label,
                xy=(x_pos, y_pos),
                xytext=(x_pos, y_pos + offset),
                fontsize=js.font_size - 1,
                ha="center",
                va="bottom",
                color=js.colors[1 % len(js.colors)],
                arrowprops=dict(arrowstyle="->", color=js.colors[1 % len(js.colors)], lw=0.8),
            )

    # ── 坐标轴标签 ────────────────────────────────────────────────────────
    ax.set_xlabel(xlabel if xlabel is not None else _default_xlabel(spectrum))
    ax.set_ylabel(ylabel if ylabel is not None else _default_ylabel(spectrum))

    # ── 标题 ──────────────────────────────────────────────────────────────
    if title is not None:
        ax.set_title(title)
    elif spectrum.metadata.get("sample_name"):
        ax.set_title(spectrum.metadata["sample_name"])
    else:
        ax.set_title(f"{spectrum.technique.value} Spectrum")

    # ── 布局与保存 ────────────────────────────────────────────────────────
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=js.dpi, bbox_inches="tight")

    return fig


def plot_spectra_comparison(
    spectra: List[Spectrum],
    labels: Optional[List[str]] = None,
    style: str = "acs_double",
    save_path: Optional[str] = None,
    title: Optional[str] = None,
) -> Figure:
    """叠加绘制多条光谱曲线用于比较。

    将多个光谱对象绘制在同一张图上，便于直观对比不同样品或不同条件下
    的光谱特征。每条曲线使用不同颜色区分。

    Parameters
    ----------
    spectra : list[Spectrum]
        待比较的光谱对象列表。
    labels : list[str], optional
        每条曲线的图例标签。长度必须与 ``spectra`` 一致。
        为 ``None`` 时自动使用样品名称或 ``\"Sample N\"``。
    style : str, optional
        期刊绘图风格名称，例如 ``\"acs_single\"``、``\"acs_double\"``、
        ``\"rsc\"``、``\"wiley\"``。不区分大小写。默认为 ``\"acs_double\"``。
    save_path : str, optional
        图片保存路径。若提供，根据文件扩展名推断保存格式
        （支持 png、pdf、svg、eps、jpg、tiff）。为 ``None`` 时不保存。
    title : str, optional
        图表标题。为 ``None`` 时使用默认标题。

    Returns
    -------
    Figure
        Matplotlib 图形对象，可在后续继续修改。

    Raises
    ------
    TypeError
        ``spectra`` 中的元素不是 :class:`Spectrum` 实例。
    ValueError
        ``spectra`` 为空，或 ``labels`` 长度与 ``spectra`` 不一致。
    KeyError
        指定的 ``style`` 名称未注册。

    Examples
    --------
    >>> from echem_core.spectroscopy.model.spectrum import Spectrum
    >>> import numpy as np
    >>> x = np.linspace(100, 2000, 1000)
    >>> s1 = Spectrum("Raman", x, np.exp(-((x - 1500)**2) / 20000))
    >>> s2 = Spectrum("Raman", x, np.exp(-((x - 1350)**2) / 15000))
    >>> fig = plot_spectra_comparison([s1, s2], labels=["Sample A", "Sample B"])
    """
    if not spectra:
        raise ValueError("spectra 列表不能为空")

    for i, s in enumerate(spectra):
        if not isinstance(s, Spectrum):
            raise TypeError(
                f"spectra[{i}] 必须是 Spectrum 实例，"
                f"收到 {type(s).__name__}"
            )

    n = len(spectra)

    # ── 处理标签 ──────────────────────────────────────────────────────────
    if labels is not None:
        if len(labels) != n:
            raise ValueError(
                f"labels 的长度 ({len(labels)}) 必须与 spectra 的长度 ({n}) 一致"
            )
    else:
        labels = []
        for s in spectra:
            name = s.metadata.get("sample_name")
            labels.append(name if name else f"Sample {len(labels) + 1}")

    # ── 获取风格 ──────────────────────────────────────────────────────────
    js: JournalStyle = get_style(style.upper())

    # ── 创建图形 ──────────────────────────────────────────────────────────
    fig, ax = plt.subplots()
    js.apply(ax)

    # ── 绘制各曲线 ────────────────────────────────────────────────────────
    colors = js.colors
    for i, (s, label) in enumerate(zip(spectra, labels)):
        x, y = _get_data(s)
        color = colors[i % len(colors)]

        ax.plot(
            x,
            y,
            color=color,
            linewidth=js.line_width,
            label=label,
        )

    # ── 坐标轴标签与标题 ──────────────────────────────────────────────────
    ref_spectrum = spectra[0]
    ax.set_xlabel(_default_xlabel(ref_spectrum))
    ax.set_ylabel(_default_ylabel(ref_spectrum))
    ax.set_title(title if title is not None else f"{ref_spectrum.technique.value} Spectra Comparison")

    # ── 图例 ──────────────────────────────────────────────────────────────
    ax.legend(frameon=False, fontsize=js.font_size)

    # ── 布局与保存 ────────────────────────────────────────────────────────
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=js.dpi, bbox_inches="tight")

    return fig


__all__ = [
    "plot_spectrum",
    "plot_spectra_comparison",
]
