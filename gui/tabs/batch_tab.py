"""批量处理标签页。"""

import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QLineEdit, QGroupBox, QFormLayout,
                               QTextEdit, QMessageBox, QFileDialog,
                               QProgressBar, QCheckBox, QComboBox,
                               QDoubleSpinBox, QListWidget, QListWidgetItem,
                               QSplitter)
from PySide6.QtCore import Qt, QThread, Signal

from echem_core.batch.batch_processor import BatchProcessor, export_data_for_origin
from echem_core.batch.report import generate_xlsx_with_cdl
from gui.widgets.analysis_common import scrollable_panel


class BatchWorker(QThread):
    """后台执行批量处理的线程。"""
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, processor, recipe, output_dir, export_format, export_origin=False):
        super().__init__()
        self.processor = processor
        self.recipe = recipe
        self.output_dir = output_dir
        self.export_format = export_format
        self.export_origin = export_origin

    def run(self):
        try:
            self.progress.emit("正在应用处理配方...")
            self.processor.apply_recipe(self.recipe)
            self.progress.emit(f"处理完成: {len(self.processor.measurements)} 个文件")

            self.progress.emit("正在导出图表...")
            saved = self.processor.export_figures(
                output_dir=self.output_dir,
                style="acs_double",
                format=self.export_format,
            )
            self.progress.emit(f"已导出 {len(saved)} 张图表")

            origin_saved = []
            if self.export_origin:
                self.progress.emit("正在导出 Origin 数据...")
                origin_saved = export_data_for_origin(
                    self.processor.measurements,
                    self.output_dir,
                )
                self.progress.emit(f"已导出 {len(origin_saved)} 个 Origin 数据文件")

            message = f"批量处理成功完成！\n导出 {len(saved)} 张图到 {self.output_dir}"
            if self.export_origin:
                message += f"\n导出 {len(origin_saved)} 个 Origin 数据文件到 {self.output_dir}"
            self.finished.emit(True, message)
        except Exception as e:
            self.finished.emit(False, f"处理失败: {e}")


class BatchTab(QWidget):
    """批量处理标签页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._processor = BatchProcessor()
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)

        # 左侧配置
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # 输入文件夹
        input_group = QGroupBox("📂 输入")
        input_layout = QVBoxLayout(input_group)
        input_row = QHBoxLayout()
        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText("选择包含数据文件的文件夹...")
        self.btn_browse_input = QPushButton("浏览...")
        self.btn_browse_input.clicked.connect(self._browse_input)
        input_row.addWidget(self.txt_input)
        input_row.addWidget(self.btn_browse_input)
        input_layout.addLayout(input_row)
        self.btn_load = QPushButton("加载文件")
        self.btn_load.clicked.connect(self._load_files)
        input_layout.addWidget(self.btn_load)
        left_layout.addWidget(input_group)

        # 处理配方
        recipe_group = QGroupBox("⚙️ 处理配方")
        recipe_layout = QFormLayout()

        self.chk_to_rhe = QCheckBox("转换到 RHE")
        self.chk_to_rhe.setChecked(True)
        self.cb_ref = QComboBox()
        self.cb_ref.addItems(["Ag/AgCl", "SCE", "Hg/HgO", "RHE"])
        self.spin_ph = QDoubleSpinBox()
        self.spin_ph.setRange(0, 16)
        self.spin_ph.setValue(13.0)
        recipe_layout.addRow("", self.chk_to_rhe)
        recipe_layout.addRow("参比电极:", self.cb_ref)
        recipe_layout.addRow("pH:", self.spin_ph)

        self.chk_normalize = QCheckBox("面积归一化")
        self.chk_normalize.setChecked(True)
        self.spin_area = QDoubleSpinBox()
        self.spin_area.setRange(0.001, 100)
        self.spin_area.setValue(0.196)
        self.spin_area.setSuffix(" cm²")
        recipe_layout.addRow("", self.chk_normalize)
        recipe_layout.addRow("电极面积:", self.spin_area)

        recipe_group.setLayout(recipe_layout)
        left_layout.addWidget(recipe_group)

        # 输出配置
        output_group = QGroupBox("💾 输出")
        output_layout = QVBoxLayout(output_group)
        output_row = QHBoxLayout()
        self.txt_output = QLineEdit()
        self.txt_output.setPlaceholderText("输出文件夹...")
        self.btn_browse_out = QPushButton("浏览...")
        self.btn_browse_out.clicked.connect(self._browse_output)
        output_row.addWidget(self.txt_output)
        output_row.addWidget(self.btn_browse_out)
        output_layout.addLayout(output_row)

        self.cb_format = QComboBox()
        self.cb_format.addItems(["png", "pdf", "svg", "tiff"])
        output_layout.addWidget(QLabel("图片格式:"))
        output_layout.addWidget(self.cb_format)

        self.chk_export_xlsx = QCheckBox("导出 Excel 报告")
        self.chk_export_xlsx.setChecked(True)
        output_layout.addWidget(self.chk_export_xlsx)

        self.chk_export_origin = QCheckBox("导出数据到Origin (.txt)")
        output_layout.addWidget(self.chk_export_origin)

        output_group.setLayout(output_layout)
        left_layout.addWidget(output_group)

        self.btn_run = QPushButton("▶ 运行批量处理")
        self.btn_run.clicked.connect(self._run_batch)
        self.btn_run.setEnabled(False)
        self.btn_run.setStyleSheet("font-weight: bold; padding: 8px;")
        left_layout.addWidget(self.btn_run)
        left_layout.addStretch()

        # 右侧：进度和日志
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定模式
        self.progress_bar.hide()
        right_layout.addWidget(self.progress_bar)

        log_group = QGroupBox("📋 处理日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        right_layout.addWidget(log_group)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(scrollable_panel(left, min_width=360))
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 720])
        layout.addWidget(splitter)

    def _browse_input(self):
        folder = QFileDialog.getExistingDirectory(self, "选择数据文件夹")
        if folder:
            self.txt_input.setText(folder)

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if folder:
            self.txt_output.setText(folder)

    def _load_files(self):
        folder = self.txt_input.text()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "提示", "请选择有效的文件夹。")
            return
        self.log_text.clear()
        try:
            self._processor.load_folder(folder, verbose=True)
            self.log_text.append(f"已加载 {len(self._processor.measurements)} 个测量文件\n")
            for m in self._processor.measurements:
                self.log_text.append(f"  ✓ {m.metadata.get('sample_name', '?')} ({m.technique.value})")
            self.btn_run.setEnabled(len(self._processor.measurements) > 0)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    def _run_batch(self):
        out_dir = self.txt_output.text()
        if not out_dir:
            QMessageBox.warning(self, "提示", "请指定输出文件夹。")
            return
        if not self._processor.measurements:
            QMessageBox.warning(self, "提示", "请先加载数据文件。")
            return

        # 构建配方
        steps = []
        if self.chk_to_rhe.isChecked():
            steps.append({
                "step": "to_rhe",
                "params": {
                    "reference": self.cb_ref.currentText(),
                    "pH": self.spin_ph.value(),
                }
            })
        if self.chk_normalize.isChecked():
            steps.append({
                "step": "normalize_by_area",
                "params": {"area_cm2": self.spin_area.value()}
            })
        recipe = {"steps": steps}

        export_format = self.cb_format.currentText()
        self.progress_bar.show()
        self.btn_run.setEnabled(False)
        self.log_text.append("\n开始批量处理...")

        self._worker = BatchWorker(
            self._processor,
            recipe,
            out_dir,
            export_format,
            export_origin=self.chk_export_origin.isChecked(),
        )
        self._worker.progress.connect(lambda msg: self.log_text.append(msg))
        self._worker.finished.connect(self._on_batch_finished)
        self._worker.start()

    def _on_batch_finished(self, success, message):
        self.progress_bar.hide()
        self.btn_run.setEnabled(True)
        self.log_text.append(f"\n{message}")
        if success and self.chk_export_xlsx.isChecked():
            try:
                xlsx_path = os.path.join(self.txt_output.text(), "分析报告.xlsx")
                generate_xlsx_with_cdl(
                    self._processor.measurements,
                    [],
                    xlsx_path,
                )
                self.log_text.append(f"Excel 报告已保存: {xlsx_path}")
            except Exception as e:
                self.log_text.append(f"Excel 报告生成失败: {e}")
        if not success:
            QMessageBox.critical(self, "批量处理失败", message)
