"""GUI 分析页共享工具。"""

from __future__ import annotations

import csv
import math
import os
from typing import Iterable, List, Sequence

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)


def technique_value(measurement) -> str:
    tech = getattr(measurement, "technique", "")
    return tech.value if hasattr(tech, "value") else str(tech)


def measurement_name(measurement) -> str:
    meta = measurement.metadata
    return str(meta.get("sample_name") or meta.get("filename") or "未命名数据")


def measurement_date(measurement) -> str:
    date = measurement.metadata.get("date") or ""
    return str(date).strip()[:20]


def measurement_label(measurement) -> str:
    date = measurement_date(measurement)
    suffix = f", {date}" if date else ""
    return f"{measurement_name(measurement)} ({technique_value(measurement)}{suffix})"


def finite_xy(x, y):
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    return x_arr[mask], y_arr[mask]


def unique_sorted_xy(x, y):
    x_arr, y_arr = finite_xy(x, y)
    if x_arr.size == 0:
        return x_arr, y_arr
    order = np.argsort(x_arr)
    x_sorted = x_arr[order]
    y_sorted = y_arr[order]
    unique_x, unique_idx = np.unique(x_sorted, return_index=True)
    return unique_x, y_sorted[unique_idx]


def interpolate_at(x, y, target: float) -> float:
    x_sorted, y_sorted = unique_sorted_xy(x, y)
    if x_sorted.size < 2:
        raise ValueError("有效数据点不足，无法插值读取。")
    if target < float(np.min(x_sorted)) or target > float(np.max(x_sorted)):
        raise ValueError("目标电位不在当前数据范围内。")
    return float(np.interp(target, x_sorted, y_sorted))


def derivative_xy(x, y):
    x_sorted, y_sorted = unique_sorted_xy(x, y)
    if x_sorted.size < 3:
        raise ValueError("有效数据点不足，无法计算微分曲线。")
    return x_sorted, np.gradient(y_sorted, x_sorted)


def apply_publication_style(ax):
    ax.tick_params(direction="in", top=True, right=True, width=1.0)
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)
    ax.grid(True, color="#d7dce2", linewidth=0.7, alpha=0.7)


def set_auto_limits(ax, x, y, margin: float = 0.1, equal: bool = False):
    x_arr, y_arr = finite_xy(x, y)
    if x_arr.size == 0 or y_arr.size == 0:
        return

    xmin, xmax = float(np.min(x_arr)), float(np.max(x_arr))
    ymin, ymax = float(np.min(y_arr)), float(np.max(y_arr))
    xrange = xmax - xmin
    yrange = ymax - ymin

    if not np.isfinite(xrange) or xrange <= 0:
        pad = max(abs(xmin) * 0.1, 1.0)
        xmin -= pad
        xmax += pad
        xrange = xmax - xmin
    if not np.isfinite(yrange) or yrange <= 0:
        pad = max(abs(ymin) * 0.1, 1.0)
        ymin -= pad
        ymax += pad
        yrange = ymax - ymin

    if equal:
        center_x = (xmin + xmax) / 2.0
        center_y = (ymin + ymax) / 2.0
        xpad = max(xrange * margin, 2.0)
        ypad = max(yrange * margin, 2.0)
        span = max(xrange + xpad * 2.0, yrange + ypad * 2.0)
        if span <= 0 or not np.isfinite(span):
            span = 4.0
        half = span / 2.0
        ax.set_xlim(center_x - half, center_x + half)
        ax.set_ylim(center_y - half, center_y + half)
        ax.set_aspect("equal", adjustable="box")
        return

    xpad = max(xrange * margin, 2.0)
    ypad = max(yrange * margin, 2.0)
    ax.set_xlim(xmin - xpad, xmax + xpad)
    ax.set_ylim(ymin - ypad, ymax + ypad)


def make_help_button(parent: QWidget, title: str, message: str) -> QPushButton:
    btn = QPushButton("?")
    btn.setFixedWidth(28)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip(title)
    btn.clicked.connect(lambda: QMessageBox.information(parent, title, message))
    return btn


def labeled_help_widget(parent: QWidget, label: str, title: str, message: str) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(QLabel(label))
    layout.addWidget(make_help_button(parent, title, message))
    layout.addStretch()
    return widget


def configure_result_table(table: QTableWidget, headers: Sequence[str]):
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)


def set_table_rows(table: QTableWidget, rows: Iterable[Sequence[object]]):
    row_list = list(rows)
    table.setRowCount(len(row_list))
    for r, row in enumerate(row_list):
        for c, value in enumerate(row):
            text = "" if value is None else str(value)
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, c, item)
    table.resizeRowsToContents()


def copy_table(table: QTableWidget):
    rows: List[List[str]] = []
    headers = [
        table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) else ""
        for c in range(table.columnCount())
    ]
    rows.append(headers)
    selected = table.selectionModel().selectedRows() if table.selectionModel() else []
    row_indices = [idx.row() for idx in selected] or list(range(table.rowCount()))
    for r in row_indices:
        rows.append([
            table.item(r, c).text() if table.item(r, c) else ""
            for c in range(table.columnCount())
        ])
    text = "\n".join("\t".join(row) for row in rows)
    QApplication.clipboard().setText(text)


def export_table(table: QTableWidget, parent: QWidget, default_name: str):
    path, selected_filter = QFileDialog.getSaveFileName(
        parent,
        "导出结果",
        default_name,
        "CSV 文件 (*.csv);;Excel 工作簿 (*.xlsx)",
    )
    if not path:
        return

    headers = [
        table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) else ""
        for c in range(table.columnCount())
    ]
    rows = [
        [table.item(r, c).text() if table.item(r, c) else "" for c in range(table.columnCount())]
        for r in range(table.rowCount())
    ]

    lower = path.lower()
    if "xlsx" in selected_filter.lower() and not lower.endswith(".xlsx"):
        path += ".xlsx"
        lower = path.lower()
    elif not lower.endswith((".csv", ".xlsx")):
        path += ".csv"
        lower = path.lower()

    if lower.endswith(".xlsx"):
        try:
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            ws.title = "分析结果"
            ws.append(headers)
            for row in rows:
                ws.append(row)
            wb.save(path)
        except Exception as exc:
            QMessageBox.critical(parent, "导出失败", f"无法导出 Excel:\n{exc}")
        return

    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
    except Exception as exc:
        QMessageBox.critical(parent, "导出失败", f"无法导出 CSV:\n{exc}")


def format_float(value, digits: int = 4, scientific: bool = False) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if not math.isfinite(number):
        return "N/A"
    return f"{number:.{digits}e}" if scientific else f"{number:.{digits}f}"
