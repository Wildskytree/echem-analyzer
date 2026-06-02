"""测量数据列表/文件浏览器控件。"""

from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QHeaderView,
                               QAbstractItemView)
from PySide6.QtCore import Qt, Signal


class MeasurementTreeWidget(QTreeWidget):
    """显示导入测量数据的树形/列表控件。

    每一行代表一个 Measurement 对象，显示文件名、技术类型、数据点数等。
    """

    measurement_selected = Signal(object)  # Measurement
    measurements_selected = Signal(list)   # List[Measurement]

    COLUMNS = ["文件名", "技术类型", "数据点数", "已处理", "日期"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(self.COLUMNS)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setRootIsDecorated(False)
        self.setSortingEnabled(True)
        header = self.header()
        for i in range(len(self.COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self._measurements = {}
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def add_measurement(self, measurement):
        """添加一个 Measurement 对象到列表。"""
        item = QTreeWidgetItem(self)
        meta = measurement.metadata
        name = meta.get("sample_name", "未知")
        tech = measurement.technique.value if hasattr(measurement.technique, 'value') else str(measurement.technique)
        points = len(measurement.raw_potential)
        processed = "是" if measurement.processed_potential is not None else "否"
        date = meta.get("date", "") or ""
        item.setText(0, name)
        item.setText(1, tech)
        item.setText(2, str(points))
        item.setText(3, processed)
        item.setText(4, str(date)[:20] if date else "")
        self._measurements[id(measurement)] = measurement
        # 存储 ID 以便检索
        item.setData(0, Qt.UserRole, id(measurement))

    def select_measurement(self, measurement):
        """选中指定 Measurement。"""
        target_id = id(measurement)
        self.clearSelection()
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.data(0, Qt.UserRole) == target_id:
                item.setSelected(True)
                self.setCurrentItem(item)
                scroll_hint = QAbstractItemView.PositionAtCenter
                self.scrollToItem(item, scroll_hint)
                break

    def get_selected_measurements(self):
        """获取当前选中的 Measurement 对象列表。"""
        items = self.selectedItems()
        result = []
        for item in items:
            mid = item.data(0, Qt.UserRole)
            for mid_key, m in self._measurements.items():
                if mid_key == mid:
                    result.append(m)
                    break
        return result

    def get_all_measurements(self):
        """获取所有 Measurement 对象列表。"""
        return list(self._measurements.values())

    def clear_measurements(self):
        """清空所有数据。"""
        self.clear()
        self._measurements.clear()

    def remove_selected(self):
        """移除选中的项并返回对应测量对象。"""
        removed = []
        for item in self.selectedItems():
            mid = item.data(0, Qt.UserRole)
            if mid in self._measurements:
                removed.append(self._measurements.pop(mid))
            self.takeTopLevelItem(self.indexOfTopLevelItem(item))
        return removed

    def _on_selection_changed(self):
        """选择变化时发出信号。"""
        selected = self.get_selected_measurements()
        if len(selected) == 1:
            self.measurement_selected.emit(selected[0])
        if selected:
            self.measurements_selected.emit(selected)
