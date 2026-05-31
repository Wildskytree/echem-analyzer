"""
LSV (Linear Sweep Voltammetry) plotting functions.

Provides publication-quality plotting for LSV/ORR measurements including
automatic E₁/₂ annotation and multi-curve overlays.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from echem_core.analysis.lsv import find_e_half
from echem_core.model import Measurement
from echem_core.plotting.styles import JournalStyle, get_style


# ────────────────────────────────────────────────────────────────
# Colour / marker cycles for multi-measurement overlays
# ────────────────────────────────────────────────────────────────

_DEFAULT_COLORS: list = [
    "#1f77b4",  # blue
    "#d62728",  # red
    "#2ca02c",  # green
    "#ff7f0e",  # orange
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#17becf",  # cyan
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#bcbd22",  # yellow-green
]

_DEFAULT_LINESTYLES: list = [
    "-",
    "--",
    "-.",
    ":",
    (0, (3, 1, 1, 1)),
    (0, (5, 2)),
    (0, (3, 1, 1, 1, 1, 1)),
]


# ─── Normalise style name lookups ──────────────────────────────

_STYLE_NAME_ALIASES: Dict[str, str] = {
    "acs_double": "ACS_DOUBLE",
    "acs_single": "ACS_SINGLE",
    "rsc": "RSC",
    "wiley": "WILEY",
}


def _resolve_style(style: Union[str, JournalStyle]) -> JournalStyle:
    """Resolve a style name or return the style object directly."""
    if isinstance(style, JournalStyle):
        return style
    key = style.lower().replace("-", "_")
    mapped = _STYLE_NAME_ALIASES.get(key, key.upper())
    try:
        return get_style(mapped)
    except KeyError:
        # Fall back to raw name
        return get_style(style)


# ────────────────────────────────────────────────────────────────
# Helper: extract potential / current from a Measurement
# ────────────────────────────────────────────────────────────────


def _get_plot_data(
    measurement: Measurement,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return ``(potential, current)`` arrays for plotting.

    Prefers processed data (background-corrected, normalised, etc.) over
    raw data when available.
    """
    if measurement.processed_potential is not None and measurement.processed_current is not None:
        return measurement.processed_potential, measurement.processed_current
    return measurement.raw_potential, measurement.raw_current


def _ensure_matplotlib_backend() -> None:
    """Switch to a non-interactive backend if no display is available."""
    import os
    if os.environ.get("DISPLAY", "") == "" and os.name != "nt":
        try:
            plt.switch_backend("Agg")
        except Exception:
            pass


# ────────────────────────────────────────────────────────────────
# Main plotting functions
# ────────────────────────────────────────────────────────────────


def plot_lsv(
    measurement: Union[Measurement, Sequence[Measurement]],
    style: Union[str, JournalStyle] = "acs_double",
    title: Optional[str] = None,
    save_path: Optional[Union[str, Path]] = None,
    show_e_half: bool = True,
) -> Figure:
    """
    Plot potential vs current density for one or more LSV measurements.

    Parameters
    ----------
    measurement : Measurement or list of Measurement
        A single measurement or a sequence of measurements to overlay.
    style : str or JournalStyle
        Journal style preset name (e.g. ``'acs_double'``) or a
        :class:`JournalStyle` instance.  Default ``'acs_double'``.
    title : str, optional
        Figure title.  If omitted, no title is shown.
    save_path : str or Path, optional
        File path to save the figure.  Extension determines format:
        ``.tiff`` / ``.tif``, ``.png``, ``.svg``, ``.pdf``.
    show_e_half : bool
        Whether to mark the half-wave potential with a dashed vertical
        line and annotation.  Default ``True``.

    Returns
    -------
    matplotlib.figure.Figure
        The generated figure.

    Raises
    ------
    TypeError
        If *measurement* is not a :class:`Measurement` or sequence thereof.
    ValueError
        If *measurement* is an empty sequence.
    """
    _ensure_matplotlib_backend()

    # ── Normalise input to a list ──────────────────────────────
    if isinstance(measurement, Measurement):
        measurements: List[Measurement] = [measurement]
    elif isinstance(measurement, Sequence) and not isinstance(measurement, (str, bytes)):
        measurements = list(measurement)
        if len(measurements) == 0:
            raise ValueError("measurement sequence must not be empty.")
    else:
        raise TypeError(
            f"Expected Measurement or sequence of Measurements, "
            f"got {type(measurement).__name__}."
        )

    # ── Resolve style ──────────────────────────────────────────
    journal_style = _resolve_style(style)

    # ── Create figure & apply styling ──────────────────────────
    fig, ax = plt.subplots()
    journal_style.apply(ax)

    n_curves = len(measurements)
    colors = _DEFAULT_COLORS * (n_curves // len(_DEFAULT_COLORS) + 1)
    linestyles = _DEFAULT_LINESTYLES * (n_curves // len(_DEFAULT_LINESTYLES) + 1)

    for i, m in enumerate(measurements):
        potential, current = _get_plot_data(m)
        label = m.metadata.get("sample_name", None)
        ax.plot(
            potential,
            current,
            color=colors[i],
            linestyle=linestyles[i],
            linewidth=journal_style.line_width,
            label=label,
        )

    # ── Labels ─────────────────────────────────────────────
    ax.set_xlabel(r"$E$ / V vs. RHE")
    # Use current-density label if area is known, else raw current
    has_area = False
    for m in measurements:
        area = m.metadata.get("area_cm2")
        if area is not None and area > 0:
            has_area = True
            break
    ax.set_ylabel(
        r"$j$ / mA cm$^{-2}$" if has_area else r"$I$ / mA"
    )

    if title:
        ax.set_title(title)

    # ── Legend if multiple measurements ────────────────────
    has_labels = any(m.metadata.get("sample_name") for m in measurements)
    if n_curves > 1 and has_labels:
        ax.legend()

    # ── E₁/₂ annotation ────────────────────────────────────
    if show_e_half:
        _annotate_e_half(ax, measurements)

    fig.tight_layout()

    # ── Save ─────────────────────────────────────────────────
    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        _save_figure(fig, save_path)

    return fig


def plot_lsv_comparison(
    measurements: Sequence[Measurement],
    labels: Sequence[str],
    style: Union[str, JournalStyle] = "acs_double",
    save_path: Optional[Union[str, Path]] = None,
) -> Figure:
    """
    Plot multiple LSV measurements on the same axes for direct comparison.

    Parameters
    ----------
    measurements : sequence of Measurement
        The LSV measurements to compare.
    labels : sequence of str
        Legend labels for each measurement.  Must have the same length
        as *measurements*.
    style : str or JournalStyle
        Journal style preset or instance.  Default ``'acs_double'``.
    save_path : str or Path, optional
        File path to save the figure.  Extension determines format.

    Returns
    -------
    matplotlib.figure.Figure

    Raises
    ------
    ValueError
        If the lengths of *measurements* and *labels* differ.
    """
    if len(measurements) != len(labels):
        raise ValueError(
            f"Number of measurements ({len(measurements)}) must match "
            f"number of labels ({len(labels)})."
        )

    _ensure_matplotlib_backend()
    journal_style = _resolve_style(style)

    fig, ax = plt.subplots()
    journal_style.apply(ax)

    colors = _DEFAULT_COLORS * (len(measurements) // len(_DEFAULT_COLORS) + 1)
    linestyles = _DEFAULT_LINESTYLES * (len(measurements) // len(_DEFAULT_LINESTYLES) + 1)

    for i, (m, lbl) in enumerate(zip(measurements, labels)):
        potential, current = _get_plot_data(m)
        ax.plot(
            potential,
            current,
            color=colors[i],
            linestyle=linestyles[i],
            linewidth=journal_style.line_width,
            label=lbl,
        )

    has_area = False
    for m in measurements:
        area = m.metadata.get("area_cm2")
        if area is not None and area > 0:
            has_area = True
            break
    ax.set_xlabel(r"$E$ / V vs. RHE")
    ax.set_ylabel(r"$j$ / mA cm$^{-2}$" if has_area else r"$I$ / mA")
    ax.legend()

    fig.tight_layout()

    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        _save_figure(fig, save_path)

    return fig


# ────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────


def _annotate_e_half(
    ax: plt.Axes,
    measurements: List[Measurement],
) -> None:
    """
    Compute and annotate the half-wave potential for each measurement.

    Draws a vertical dashed line at E₁/₂ and places a text annotation
    near the line.
    """
    y_min, y_max = ax.get_ylim()
    x_min, x_max = ax.get_xlim()

    for i, m in enumerate(measurements):
        potential, current = _get_plot_data(m)
        if len(potential) < 10:
            continue

        try:
            e_half, j_L, confidence = find_e_half(potential, current)
        except (ValueError, RuntimeError):
            continue

        # Dashed vertical line at E₁/₂
        ax.axvline(
            x=e_half,
            color=_DEFAULT_COLORS[i % len(_DEFAULT_COLORS)],
            linestyle="--",
            linewidth=0.8,
            alpha=0.7,
            zorder=2,
        )

        # Annotation position
        text_x_offset = (x_max - x_min) * 0.02
        if e_half > (x_min + x_max) / 2:
            text_x = e_half - text_x_offset
            ha = "right"
        else:
            text_x = e_half + text_x_offset
            ha = "left"

        text_y = y_min + 0.90 * (y_max - y_min)
        badge = {"high": "", "medium": " ~", "low": " ?"}.get(confidence, "")

        ax.annotate(
            f"$E_{{1/2}}$ = {e_half:.3f} V{badge}",
            xy=(e_half, text_y),
            xytext=(text_x, text_y),
            fontsize=7.5,
            color=_DEFAULT_COLORS[i % len(_DEFAULT_COLORS)],
            ha=ha,
            va="center",
            annotation_clip=True,
            arrowprops=dict(
                arrowstyle="-",
                color=_DEFAULT_COLORS[i % len(_DEFAULT_COLORS)],
                lw=0.5,
                alpha=0.5,
            ),
        )

    ax.set_ylim(y_min, y_max)


def _save_figure(fig: Figure, path: Path) -> None:
    """
    Save the figure to disk, inferring format from extension.

    Supports ``.tiff`` / ``.tif``, ``.png``, ``.svg``, ``.pdf``.
    """
    ext = path.suffix.lower()

    fmt_map: Dict[str, str] = {
        ".tiff": "tiff",
        ".tif": "tiff",
        ".png": "png",
        ".svg": "svg",
        ".pdf": "pdf",
    }

    fmt = fmt_map.get(ext)
    if fmt is None:
        raise ValueError(
            f"Unsupported file extension {ext!r}. "
            f"Supported: {', '.join(fmt_map)}"
        )

    dpi = 300
    save_kwargs: Dict[str, object] = {
        "format": fmt,
        "dpi": dpi,
        "bbox_inches": "tight",
    }
    if fmt == "tiff":
        save_kwargs["pil_kwargs"] = {"compression": "tiff_lzw"}
    fig.savefig(path, **save_kwargs)


__all__ = [
    "plot_lsv",
    "plot_lsv_comparison",
]
