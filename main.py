#!/usr/bin/env python3
"""
Echem Analyzer — 电化学数据分析桌面应用

启动入口。支持三种模式：
1. 无参数: 启动 GUI 窗口
2. --cli: 启动 CLI 模式
"""

import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _run_gui():
    """Create the QApplication early so the splash screen appears before imports."""
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    from PySide6.QtWidgets import QApplication, QStyleFactory

    from gui.app_info import APP_DISPLAY_VERSION, APP_NAME, APP_ORGANIZATION
    from gui.splash import SplashScreen

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_DISPLAY_VERSION)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setStyle(QStyleFactory.create("Fusion"))

    splash = SplashScreen(APP_NAME, APP_DISPLAY_VERSION)
    splash.show()
    splash.show_progress(10, "初始化应用...")
    app.processEvents()

    splash.show_progress(25, "加载分析模块...")
    app.processEvents()
    from gui.main_window import run_app

    run_app(app=app, splash=splash)


def main():
    if "--cli" in sys.argv:
        # 启动 CLI 模式
        from echem_core.cli import main as cli_main
        sys.argv.remove("--cli")
        sys.exit(cli_main())
    else:
        # 启动 GUI 模式
        _run_gui()


if __name__ == "__main__":
    main()
