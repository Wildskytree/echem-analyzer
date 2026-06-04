# -*- mode: python ; coding: utf-8 -*-
"""
Echem Analyzer PyInstaller spec file.
"""

import sys
import os
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include assets directory if it exists
        ('assets', 'assets'),
    ],
    hiddenimports=[
        # Data format parsers
        'echem_core.io.chi_parser',
        'echem_core.io.csv_parser',
        'echem_core.io.csstudio_parser',
        'echem_core.io.universal_parser',
        # Core processing modules
        'echem_core.processing.convert',
        'echem_core.processing.normalize',
        'echem_core.processing.smooth',
        'echem_core.processing.background',
        # Analysis modules
        'echem_core.analysis.lsv',
        'echem_core.analysis.cv',
        'echem_core.analysis.eis',
        'echem_core.analysis.stability',
        'echem_core.analysis.kl',
        # Plotting modules
        'echem_core.plotting.styles',
        'echem_core.plotting.lsv_plot',
        'echem_core.plotting.cv_plot',
        'echem_core.plotting.eis_plot',
        'echem_core.plotting.stability_plot',
        # Batch processing
        'echem_core.batch.processor',
        'echem_core.batch.report',
        # CLI
        'echem_core.cli',
        # GUI modules
        'gui.main_window',
        'gui.app_info',
        'gui.splash',
        'gui.tabs.data_browser_tab',
        'gui.tabs.lsv_tab',
        'gui.tabs.cv_tab',
        'gui.tabs.eis_tab',
        'gui.tabs.stability_tab',
        'gui.tabs.batch_tab',
        'gui.tabs.project_tab',
        'gui.widgets.plot_widget',
        'gui.widgets.measurement_list',
        'gui.widgets.analysis_common',
        'gui.widgets.multi_curve_overlay',
        'gui.dialogs',
        # Other
        'matplotlib',
        'matplotlib.backends.backend_qtagg',
        'matplotlib.backends.backend_pdf',
        'matplotlib.backends.backend_svg',
        'matplotlib.backends.backend_tiff',
        'numpy',
        'scipy',
        'openpyxl',
        'lmfit',
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'test',
        'unittest',
        'distutils',
        'setuptools',
        'pydoc',
        'email',
        'http',
        'urllib',
        'xml',
        'xmlrpc',
        'pdb',
        'doctest',
        'asyncio',
        'concurrent',
        'multiprocessing',
        'logging.config',
        'logging.handlers',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EchemAnalyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window for GUI mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)
