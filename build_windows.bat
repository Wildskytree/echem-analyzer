@echo off
REM Echem Analyzer Windows 打包脚本
REM 使用 PyInstaller 构建单文件 .exe

echo ============================================
echo  Echem Analyzer - Windows 打包工具
echo ============================================

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请安装 Python 3.8+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 安装构建依赖...
pip install pyinstaller
if %errorlevel% neq 0 (
    echo [错误] PyInstaller 安装失败
    pause
    exit /b 1
)

REM 确保 gui 依赖已安装
pip install PySide6 matplotlib numpy scipy openpyxl lmfit

REM 清理旧构建
echo [2/3] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 构建
echo [3/3] 打包为 EchemAnalyzer.exe...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "EchemAnalyzer" ^
    --add-data "echem_core;echem_core" ^
    --hidden-import "echem_core" ^
    --hidden-import "echem_core.io" ^
    --hidden-import "echem_core.model" ^
    --hidden-import "echem_core.analysis" ^
    --hidden-import "echem_core.processing" ^
    --hidden-import "echem_core.plotting" ^
    --hidden-import "echem_core.batch" ^
    --hidden-import "echem_core.spectroscopy" ^
    --hidden-import "PySide6" ^
    --hidden-import "matplotlib" ^
    --hidden-import "numpy" ^
    --hidden-import "scipy" ^
    --hidden-import "openpyxl" ^
    --hidden-import "lmfit" ^
    main.py

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo  构建成功！
    echo  输出: dist\EchemAnalyzer.exe
    echo ============================================
) else (
    echo.
    echo [错误] 构建失败
)

pause
