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


def main():
    if "--cli" in sys.argv:
        # 启动 CLI 模式
        from echem_core.cli import main as cli_main
        sys.argv.remove("--cli")
        sys.exit(cli_main())
    else:
        # 启动 GUI 模式
        from gui.main_window import run_app
        run_app()


if __name__ == "__main__":
    main()
