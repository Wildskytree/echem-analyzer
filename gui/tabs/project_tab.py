"""项目管理标签页。"""

import os
import json
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QTextEdit, QMessageBox, QFileDialog,
                               QGroupBox, QListWidget, QListWidgetItem,
                               QSplitter)
from PySide6.QtCore import Qt


class ProjectTab(QWidget):
    """项目管理标签页。

    提供项目保存/加载、会话历史和报告导出功能。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_log = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)

        # 左侧
        left = QWidget()
        left_layout = QVBoxLayout(left)

        project_group = QGroupBox("💼 项目管理")
        proj_layout = QVBoxLayout(project_group)
        self.btn_save_project = QPushButton("💾 保存项目 (.echemproj)")
        self.btn_save_project.clicked.connect(self._save_project)
        self.btn_load_project = QPushButton("📂 加载项目 (.echemproj)")
        self.btn_load_project.clicked.connect(self._load_project)
        self.btn_export_report = QPushButton("📊 导出 HTML 报告")
        self.btn_export_report.clicked.connect(self._export_report)
        proj_layout.addWidget(self.btn_save_project)
        proj_layout.addWidget(self.btn_load_project)
        proj_layout.addWidget(self.btn_export_report)
        left_layout.addWidget(project_group)

        session_group = QGroupBox("📋 会话历史")
        session_layout = QVBoxLayout(session_group)
        self.session_list = QListWidget()
        self.lbl_session_count = QLabel("当前会话: 0 条记录")
        session_layout.addWidget(self.lbl_session_count)
        session_layout.addWidget(self.session_list)
        self.btn_clear_session = QPushButton("清除历史")
        self.btn_clear_session.clicked.connect(self._clear_session)
        session_layout.addWidget(self.btn_clear_session)
        left_layout.addWidget(session_group)

        left_layout.addStretch()

        # 右侧
        right = QWidget()
        right_layout = QVBoxLayout(right)
        info_group = QGroupBox("ℹ️ 应用信息")
        info_layout = QVBoxLayout(info_group)
        self.txt_info = QTextEdit()
        self.txt_info.setReadOnly(True)
        self.txt_info.setHtml("""
        <h2>Echem Analyzer</h2>
        <p><b>版本:</b> 0.1.0</p>
        <p><b>描述:</b> 电化学数据分析工具</p>
        <p><b>技术栈:</b> PySide6 + Matplotlib + NumPy/SciPy</p>
        <p><b>支持的分析:</b></p>
        <ul>
        <li>LSV: E₁/₂, E_onset, Tafel 斜率, K-L 分析</li>
        <li>CV: 峰检测, Cdl, ECSA</li>
        <li>EIS: Nyquist, Bode 图, Rs/Rct</li>
        <li>CA/CP 稳定性: 保持率, 指数衰减拟合, 分段统计</li>
        <li>批量处理与报告导出</li>
        </ul>
        <p><b>主要数据格式:</b> CHI Instruments (.txt), CSV</p>
        <p><b>快捷键:</b> Ctrl+O 导入文件, Ctrl+S 保存项目</p>
        """)
        info_layout.addWidget(self.txt_info)
        right_layout.addWidget(info_group)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

    def log_event(self, event: str):
        """记录一条会话事件。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._session_log.append(f"[{timestamp}] {event}")
        self.session_list.addItem(f"[{timestamp}] {event}")
        self.lbl_session_count.setText(f"当前会话: {len(self._session_log)} 条记录")

    def _save_project(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存项目", "project.echemproj",
            "Echem Analyzer Project (*.echemproj);;所有文件 (*)")
        if not path:
            return
        try:
            data = {
                "version": "0.1.0",
                "timestamp": datetime.now().isoformat(),
                "session_log": self._session_log,
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log_event(f"项目已保存: {os.path.basename(path)}")
            QMessageBox.information(self, "保存成功", f"项目已保存到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def _load_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载项目", "",
            "Echem Analyzer Project (*.echemproj);;所有文件 (*)")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._session_log = data.get("session_log", [])
            self.session_list.clear()
            for entry in self._session_log:
                self.session_list.addItem(entry)
            self.lbl_session_count.setText(f"当前会话: {len(self._session_log)} 条记录")
            self.log_event(f"项目已加载: {os.path.basename(path)}")
            QMessageBox.information(self, "加载成功",
                                   f"项目已加载 (版本 {data.get('version', '?')})")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    def _export_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出报告", "分析报告.html",
            "HTML (*.html);;所有文件 (*)")
        if not path:
            return
        try:
            html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Echem Analyzer 报告</title>
<style>
body {{ font-family: sans-serif; margin: 40px; }}
h1 {{ color: #2c3e50; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background-color: #3498db; color: white; }}
tr:nth-child(even) {{ background-color: #f2f2f2; }}
</style></head>
<body>
<h1>Echem Analyzer 分析报告</h1>
<p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<h2>会话历史</h2>
<ul>
"""
            for entry in self._session_log:
                html += f"<li>{entry}</li>\n"
            html += "</ul>\n</body>\n</html>"

            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
            self.log_event(f"HTML 报告已导出: {os.path.basename(path)}")
            QMessageBox.information(self, "导出成功", f"报告已保存到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _clear_session(self):
        self._session_log.clear()
        self.session_list.clear()
        self.lbl_session_count.setText("当前会话: 0 条记录")
