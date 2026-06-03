# Echem Analyzer 使用说明书

## 1. 软件简介

Echem Analyzer 是一款面向电化学/催化科研人员的数据后处理工具，适用于从电化学工作站导出的 LSV、CV、EIS、CA、CP 等数据的整理、分析、绘图和批量汇总。

- 版本: v0.1.0
- 开源协议: MIT
- GitHub: https://github.com/Wildskytree/echem-analyzer
- 主要形态: 桌面 GUI、命令行 CLI、Python 核心库
- 技术栈: PySide6、Matplotlib、NumPy、SciPy、openpyxl

软件重点解决以下工作:

- 将 CHI Instruments、CorrTest CSStudio 和通用 CSV/TSV 文本数据导入统一的数据模型。
- 对 LSV/ORR 曲线进行电位换算、电流归一化、E1/2、E_onset、Tafel 和 K-L 分析。
- 对 CV 曲线进行峰检测、Cdl 和 ECSA 计算。
- 对 EIS 数据绘制 Nyquist/Bode 图，并快速估算 Rs/Rct。
- 对 CA/CP 稳定性数据计算保持率、衰减拟合和分段统计。
- 对文件夹数据执行统一 recipe、批量出图、Excel 汇总和 Origin 文本导出。

当前版本定位为“数据后处理”工具，不连接或控制电化学工作站。

## 2. 安装指南

### 2.1 Windows exe 安装

Windows 用户可优先从 GitHub Releases 下载打包好的 exe:

1. 打开 https://github.com/Wildskytree/echem-analyzer/releases
2. 下载最新 Release 中的 Windows 可执行文件，例如 `EchemAnalyzer.exe`。
3. 双击 exe 启动软件。

如果系统阻止未知来源程序运行，请确认文件来自项目官方 Release 页面后再选择继续运行。

### 2.2 源码安装

环境要求:

- Python 3.9+
- 建议使用虚拟环境
- GUI 模式需要 PySide6

从源码安装:

```bash
git clone https://github.com/Wildskytree/echem-analyzer.git
cd echem-analyzer
python -m venv .venv
source .venv/bin/activate
pip install -e ".[gui,test]"
```

Windows PowerShell:

```powershell
git clone https://github.com/Wildskytree/echem-analyzer.git
cd echem-analyzer
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[gui,test]"
```

如果只需要核心库和命令行:

```bash
pip install -e .
```

如果 GUI 启动时报缺少 PySide6:

```bash
pip install PySide6
```

### 2.3 启动软件

源码安装后，在项目根目录运行:

```bash
python main.py
```

安装命令行入口后，可运行:

```bash
echem --help
```

也可以通过主入口进入 CLI:

```bash
python main.py --cli --help
```

## 3. 快速入门

### 3.1 启动界面

启动 GUI 后，软件会显示启动屏并加载分析模块。主窗口包含菜单栏、快捷工具栏、状态栏和七个主要标签页:

- 数据浏览
- LSV
- CV 分析
- EIS
- 稳定性
- 批量处理
- 项目

建议先进入“数据浏览”标签页导入数据，再进入对应分析标签页。

### 3.2 导入数据文件

支持两种常用方式:

- 拖拽导入: 将 `.txt` 或 `.csv` 文件从文件管理器拖入“数据浏览”页面。
- 快捷键导入: 按 `Ctrl+O`，选择一个或多个数据文件。

也可以点击“数据浏览”页的“导入文件”按钮，或通过菜单“文件 -> 导入文件...”导入。

### 3.3 使用数据浏览器

导入成功后，数据会显示在“测量数据列表”中。选择一条数据后，下方“数据预览”表格会显示最多 1000 行数据，用于快速确认列识别、技术类型和数值范围是否正确。

数据浏览器常用操作:

- 搜索框: 按文件名或列表字段过滤数据。
- 删除选中: 移除当前选中的数据。
- 清空: 清空当前会话中的所有导入数据。
- 右键菜单: 可快速进入对应分析页，或手动修改数据类型。
- 快速开始区域: 根据已导入数据类型快速打开 LSV、CV、EIS 或稳定性分析页。

如果自动识别的数据类型不符合预期，可在数据浏览器中右键选择“修改数据类型”。

## 4. 功能模块详解

### 4.1 数据导入

#### 支持格式

当前版本支持:

- CHI Instruments 文本文件: `.txt`
- CorrTest CSStudio 文本文件: `.txt`
- 通用 CSV/TSV 文本数据: 逗号、制表符、分号或空白符分隔

说明:

- GUI 文件选择器主要筛选 `.txt` 和 `.csv`。如果数据是 `.tsv`，可另存为 `.csv` 后导入，或在 Python API 中直接调用 `parse_csv()`。
- CHI 文本会自动尝试 UTF-8、GBK、GB2312、Latin-1 等编码。
- CorrTest CSStudio 文件若包含 `CSStudioFile` 或 gzip/base64 元数据头，可自动解析实验类型、扫速、面积等信息。

#### 自动识别的数据类型

软件会根据表头和数据特征识别:

- LSV
- CV
- EIS
- CA
- CP

常见列名建议:

| 数据类型 | 推荐列 |
| --- | --- |
| LSV/CV | `Potential/V`, `Current/A`, `Time/s` |
| EIS | `Frequency/Hz`, `Z'`, `Z"` |
| CA | `Time/s`, `Current/A` |
| CP | `Time/s`, `Potential/V`, `Current/A` |

#### 批量导入文件夹

在“数据浏览”页点击“导入文件夹”，软件会扫描所选文件夹第一层中的 `.txt` 和 `.csv` 文件并批量导入。

在“批量处理”页也可选择输入文件夹并点击“加载文件”。批量处理页同样默认扫描 `.txt` 和 `.csv`。

注意: 当前 GUI 不递归扫描子文件夹。核心 API 的 `BatchProcessor.load_folder(..., recursive=True)` 支持递归，但 GUI 暂未开放该选项。

### 4.2 LSV/ORR 分析

LSV 标签页用于常规线性扫描伏安和 ORR 曲线分析。

基本流程:

1. 在“数据浏览”导入 LSV 数据。
2. 切换到“LSV”标签页。
3. 在“当前文件”下拉框选择数据。
4. 设置处理参数。
5. 点击“执行分析”。
6. 查看 LSV 曲线、微分曲线和结果表。

#### 电位换算到 RHE

默认启用“转换到 RHE”。支持参比电极:

- `Ag/AgCl`
- `SCE`
- `Hg/HgO`
- `RHE`

换算公式:

```text
E_RHE = E_meas + E_offset + 0.05916 * (T / 298.15) * pH
```

默认 offset:

- Ag/AgCl: 0.197 V
- SCE: 0.241 V
- Hg/HgO: 0.098 V
- RHE: 0 V

如果原始电位已经是 RHE，可选择 `RHE` 或取消“转换到 RHE”。

#### iR 补偿

可启用“iR 补偿”:

```text
E_corrected = E - I * Rs * 补偿比例
```

其中 `I` 使用归一化前的电流，单位 A；`Rs` 单位 Ω。若项目中已有 EIS 数据，可点击“从 EIS 获取 Rs”，软件会从第一条 EIS 数据快速估算并填入 Rs。

#### 电流归一化

可选模式:

- 不归一化: 纵轴为 `I / A`
- 按面积: `j = I * 1000 / area`，单位 `mA/cm^2`
- 按质量: `I * 1000 / (loading * area)`，单位 `mA/mg`

请根据实际几何面积和催化剂负载量填写参数。

#### 平滑

可启用 Savitzky-Golay 平滑，参数包括窗口和阶数。LSV 常用窗口为 7-31，阶数常用 2 或 3。平滑会改变曲线细节，正式定量前应谨慎使用并保留原始数据。

#### E1/2 自动检测

启用 ORR 专项分析后，软件会自动检测半波电位 E1/2:

1. 比较曲线前 30% 和后 30% 的电流绝对值。
2. 选择更接近扩散平台的一端。
3. 取平台区平均电流为极限电流 `j_L`。
4. 插值寻找 `j = j_L / 2` 对应电位。
5. 根据平台区线性程度给出高、中、低置信度。

结果表显示:

- ORR 半波电位 E1/2
- ORR 极限电流
- 置信度

#### E_onset 自动检测

E_onset 使用切线法估算:

1. 按电位升序排列数据。
2. 计算 `dI/dE`。
3. 找到最陡变化点。
4. 在该点附近线性拟合切线。
5. 与前 10% 数据均值基线求交点。

如果 E_onset 不合理，通常需要检查基线区、噪声、背景电流和电位窗口。

#### Tafel 斜率计算

Tafel 分析依赖自动计算的 `j_L`。软件会计算动力学电流 `j_k`，对 `log10(|j_k|)` 和电位进行线性区搜索，并输出 Tafel 斜率，单位 `mV/dec`。

还原反应的斜率可能带负号。写论文或报告时请按所在领域约定说明符号或使用绝对值。

#### K-L 分析

点击“执行 K-L 分析”可进行 Koutecky-Levich 分析。

使用条件:

- 至少 3 组不同转速 LSV 数据。
- 每条数据元数据中需要 `rotation_rpm`。
- 多条曲线的电位范围需要有交集。

软件会将不同转速曲线插值到公共电位网格，在半波电位附近做 `1/j` 对 `1/sqrt(omega)` 线性回归，并输出电子转移数 `n` 和截距。

若提示缺少转速，请检查原始文件头是否包含 `rpm` 或 `rotation` 信息。

#### 其他 LSV 工具

- 读取电位: 在指定电位处插值读取电流或电流密度。
- 多曲线叠加对比: 同时绘制当前项目中的 LSV 曲线。
- 微分曲线 `dI/dE`: 用于辅助观察拐点和噪声。
- 手动峰检测: 按 5% prominence 检测阳极/阴极峰，并写入结果表。

### 4.3 CV 分析

CV 标签页用于循环伏安峰检测、Cdl 和 ECSA 计算。

#### 峰检测

操作步骤:

1. 导入 CV 数据。
2. 切换到“CV 分析”标签页。
3. 选择当前文件。
4. 选择峰检测方向。
5. 点击“峰检测与分析”。

峰检测方向:

- `both`: 同时检测氧化峰和还原峰。
- `oxidative`: 仅检测氧化峰。
- `reductive`: 仅检测还原峰。

算法会根据电位变化方向拆分正向和反向扫描:

- 正向扫描中检测正电流峰，标记为氧化峰。
- 反向扫描中检测负电流峰，标记为还原峰。

结果表显示峰类型、峰电位和峰电流，图中会标注检测到的峰。

#### Cdl 计算

Cdl 需要多条不同扫速的 CV:

1. 在“当前文件”中选择一条 CV。
2. 点击“添加当前 CV 到 Cdl 列表”。
3. 重复添加至少 2 条不同扫速 CV。
4. 设置比电容，默认 `0.04 mF/cm^2`。
5. 点击“计算 Cdl / ECSA”。

也可点击“自动添加全部 CV”，软件会把能识别扫速的 CV 自动加入列表。

算法流程:

1. 识别每条 CV 的扫描速率，优先使用 `metadata["scan_rate"]`，否则尝试由电位-时间曲线估算。
2. 将 CV 拆分为正向和反向扫描。
3. 在电位范围中点附近的非法拉第区取样。
4. 计算正反向电流差的一半 `Delta j / 2`。
5. 对 `Delta j / 2` 与扫描速率进行线性拟合，斜率为 Cdl。

输出包括:

- Cdl，单位 F
- 拟合 R2
- ECSA，单位 cm^2
- 扫描速率列表

#### ECSA 计算

ECSA 公式:

```text
ECSA = Cdl / Cs
```

其中 `Cs` 为单位面积比电容，GUI 中单位为 `mF/cm^2`。常见参考值:

- 多晶 Pt 酸性体系: 约 0.02 mF/cm^2
- 多晶 Au 酸性体系: 约 0.03 mF/cm^2
- 金属氧化物碱性体系: 约 0.04-0.06 mF/cm^2

请根据材料体系和文献依据设置比电容。

### 4.4 EIS 分析

EIS 标签页用于阻抗谱查看和基础参数估算。

基本流程:

1. 导入 EIS 数据。
2. 切换到“EIS”标签页。
3. 选择当前 EIS 文件。
4. 点击“分析 EIS 数据”。
5. 查看 Nyquist 图、Bode 图和结果表。

#### Nyquist 图

Nyquist 图使用:

- 横轴: `Z' / ohm`
- 纵轴: `-Z'' / ohm`

软件会自动设置坐标范围，并在图中标注 Rs 和 Rct。

#### Bode 图

Bode 图包含:

- `|Z| / ohm` 对频率
- 相位角对频率

频率轴使用对数坐标。频率必须为正，且至少有 2 个有效点。

#### Rs/Rct 估计

当前版本为快速估算:

- Rs: 若有频率数据，取最高频 5 个点的 `Z'` 均值；否则取前 5% `Z'` 均值。
- Rct: 取低频端后 10% `Z'` 均值，再减去 Rs。

结果表显示:

- Rs
- Rct
- `Z'` 范围
- `-Z''` 范围
- 频率范围
- 数据点数

注意: 当前 EIS 模块不是完整等效电路非线性拟合工具，不输出 CPE、Warburg、拟合误差、残差或 Kramers-Kronig 检验。正式发表时建议使用专用 EIS 拟合软件或专业 Python 阻抗库进一步分析。

### 4.5 稳定性分析（CA/CP）

稳定性标签页用于 CA 和 CP 时间序列。

- CA: I-t 或 j-t 曲线，电流保持率。
- CP: E-t 曲线，电位保持率，可选 iR 补偿。

基本流程:

1. 导入 CA 或 CP 数据。
2. 切换到“稳定性”标签页。
3. 选择当前文件。
4. 设置时间单位、纵轴模式、电极面积、保持率方式和分段长度。
5. 点击“执行稳定性分析”。
6. 查看稳定性曲线、保持率与拟合、指标结果和分段统计。

#### 电流保持率

CA 可显示原始电流 `I / A` 或电流密度 `j / mA/cm^2`。电流密度使用:

```text
j = I * 1000 / area
```

对于阴极电流等负值曲线，建议开启“保持率使用绝对幅值”，软件会基于 `|I|` 或 `|j|` 计算保持率。

#### 指数衰减拟合

保持率拟合模型:

```text
y = a * exp(-t / tau) + c
```

输出指标包括:

- 曲线类型
- 数据点数
- 持续时间
- 最大值或最大绝对值
- 最终值
- 最终保持率
- 观测半衰期 t1/2
- 拟合参数 a、tau、c
- 拟合 t1/2
- 拟合 R2

如果数据点过少、保持率几乎不变，或曲线不适合指数衰减模型，拟合结果可能显示 N/A。

#### 分段统计

分段长度默认 1 小时，可改为 0.5 h、2 h 或其他值。软件按固定时间段统计:

- 起始时间
- 结束时间
- 均值
- 方差
- 点数

分段统计适合评估长时间稳定性测试中的漂移和波动。

### 4.6 批量处理

批量处理标签页适合对一个文件夹的数据统一处理和导出。

基本流程:

1. 打开“批量处理”标签页。
2. 在“输入”中选择数据文件夹。
3. 点击“加载文件”。
4. 设置统一 Recipe。
5. 选择输出文件夹。
6. 选择图片格式。
7. 按需要勾选 Excel 报告和 Origin 数据导出。
8. 点击“运行批量处理”。

#### 文件夹批量导入

批量页会加载文件夹第一层中的 `.txt` 和 `.csv` 文件。加载日志会显示成功导入的文件名和自动识别的数据类型。

#### 统一 Recipe 设置

GUI 当前暴露的 recipe:

- 转换到 RHE: 参比电极、pH。
- 面积归一化: 电极面积。

核心库还支持背景扣除 `subtract_background`，但 v0.1.0 的批量 GUI 尚未提供空白文件选择控件。

#### Excel 汇总导出

勾选“导出 Excel 报告”后，输出:

```text
分析报告.xlsx
```

报告列包括:

- sample_name
- technique
- E1/2
- j_L
- Tafel_slope
- Cdl
- ECSA
- file_hash

说明: 批量 GUI 当前没有选择多扫速 CV 列表的入口，因此批量报告中的 Cdl/ECSA 通常为 N/A。需要 Cdl/ECSA 时，建议在 CV 分析页手动计算，或使用 Python API 传入 CV 列表生成报告。

#### 批量出图

可选图片格式:

- png
- pdf
- svg
- tiff

默认会把 LSV/CV 曲线导出为比较图:

```text
lsv_comparison.<format>
```

#### Origin 数据导出

勾选“导出数据到 Origin (.txt)”后，会输出制表符分隔文本。

普通电化学数据列:

- potential
- current
- time，如存在

EIS 数据列:

- frequency
- z_real
- z_imag

## 5. 图表设置

### 5.1 期刊尺寸预设

核心绘图样式内置:

- ACS_SINGLE
- ACS_DOUBLE
- RSC
- WILEY

这些预设包含图宽、自动高度、字体大小、线宽和 DPI 设置。CLI `plot` 命令可通过 `--style` 指定样式。

示例:

```bash
echem plot examples/sample_chi_lsv.txt --style ACS_DOUBLE --dpi 300 -o lsv_plot.png
```

说明: 核心 LSV 绘图函数支持 `acs_single`、`acs_double`、`rsc`、`wiley` 等小写别名；CLI 中建议直接使用大写内部名称。

### 5.2 色盲友好配色

期刊样式使用色盲友好的 8 色调色板，适合多曲线对比。GUI 分析页也使用区分度较高的 Matplotlib 颜色绘图。

建议多曲线图中仍控制曲线数量，避免图例过长或颜色重复。

### 5.3 导出格式

GUI 图表常见导出格式:

- TIFF
- PNG
- SVG
- PDF

建议:

- 组会和快速交流: PNG
- 论文投稿位图: TIFF
- 矢量排版和后期编辑: SVG 或 PDF

图表上方 Matplotlib 工具栏还支持放大、平移、恢复视图和保存当前图。

### 5.4 结果表导出

各分析页结果表支持:

- 复制结果: 复制为制表符分隔文本，可直接粘贴到 Excel 或 Origin。
- 导出结果: 保存为 CSV 或 `.xlsx`。

CSV 使用 UTF-8 with BOM，便于 Windows Excel 识别中文。

## 6. 项目管理

项目标签页提供项目保存、加载、会话历史和 HTML 报告导出。

### 6.1 保存项目

点击“保存项目 (.echemproj)”或使用 `Ctrl+S`。软件会保存:

- 软件版本
- 保存时间
- 当前会话历史

当前 `.echemproj` 不保存完整导入数据和所有分析状态。请保留原始数据文件和导出的结果文件。

### 6.2 加载项目

点击“加载项目 (.echemproj)”选择项目文件。加载后会恢复会话历史，并追加一条“项目已加载”的记录。

### 6.3 会话历史

导入文件、保存项目、加载项目、导出报告等操作会写入会话历史。可在项目页查看或清除历史。

### 6.4 HTML 报告导出

点击“导出 HTML 报告”，软件会生成一个包含版本、生成时间和会话历史的 HTML 文件。

当前 HTML 报告不自动嵌入所有分析曲线和结果表。如需归档完整结果，请同时导出图表、CSV/Excel 结果和批量报告。

## 7. 命令行模式（CLI）

安装后命令为 `echem`。也可运行:

```bash
python main.py --cli <command>
```

查看帮助:

```bash
echem --help
echem <command> --help
```

### 7.1 `echem import`

用途: 导入文件或文件夹并显示导入结果。

```bash
echem import <path>
```

参数:

- `<path>`: 文件或文件夹路径。

示例:

```bash
echem import examples/sample_chi_lsv.txt
echem import examples/
```

文件夹导入会尝试加载支持的数据文件，并显示导入数量。

### 7.2 `echem info`

用途: 显示单个数据文件信息。

```bash
echem info <path>
```

输出:

- 技术类型
- 数据点数
- 电位范围
- 电流范围
- 文件哈希

示例:

```bash
echem info examples/sample_chi_lsv.txt
```

### 7.3 `echem process`

用途: 处理单个数据文件，可执行 RHE 换算、面积归一化、LSV 分析并输出图。

```bash
echem process <path> [--rhe REF] [--ph PH] [--area AREA] [-o OUTPUT]
```

参数:

- `<path>`: 数据文件路径。
- `--rhe REF`: 参比电极类型，例如 `Ag/AgCl`、`SCE`、`Hg/HgO`、`RHE`。
- `--ph PH`: 电解液 pH，默认 0.0。
- `--area AREA`: 电极面积，单位 cm^2。
- `-o, --output OUTPUT`: 输出图表路径。

示例:

```bash
echem process examples/sample_chi_lsv.txt --rhe Ag/AgCl --ph 13 --area 0.196 -o output/lsv.png
```

对 LSV 数据，命令会尝试输出 E1/2、j_L 和 Tafel 斜率。

### 7.4 `echem batch`

用途: 批量处理文件夹。

```bash
echem batch <folder> [-o OUTPUT] [--rhe REF] [--ph PH] [--area AREA] [-f FIGURES]
```

参数:

- `<folder>`: 数据文件夹路径。
- `-o, --output OUTPUT`: Excel 汇总文件路径，默认 `results.xlsx`。
- `--rhe REF`: 参比电极类型。
- `--ph PH`: 电解液 pH，默认 0.0。
- `--area AREA`: 电极面积，单位 cm^2。
- `-f, --figures FIGURES`: 图片输出文件夹。

示例:

```bash
echem batch examples/ --rhe Ag/AgCl --ph 13 --area 0.196 -o results.xlsx --figures figures/
```

### 7.5 `echem plot`

用途: 为单个文件生成图表。

```bash
echem plot <path> [--style STYLE] [--dpi DPI] [-o OUTPUT]
```

参数:

- `<path>`: 数据文件路径。
- `--style STYLE`: 期刊风格，建议 `ACS_SINGLE`、`ACS_DOUBLE`、`RSC`、`WILEY`。
- `--dpi DPI`: 图片 DPI，默认 300。
- `-o, --output OUTPUT`: 输出图片路径，默认 `plot.png`。

示例:

```bash
echem plot examples/sample_chi_lsv.txt --style ACS_DOUBLE --dpi 300 -o lsv_plot.png
```

## 8. 快捷键一览

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl+O` | 导入文件 |
| `Ctrl+Shift+O` | 导入文件夹 |
| `Ctrl+S` | 保存项目 |
| `Ctrl+Q` | 退出 |
| `Ctrl+T` | 切换暗色主题 |

说明: v0.1.0 中“加载项目”菜单项也绑定了 `Ctrl+O`，如果快捷键行为与预期不一致，请直接点击“项目”页中的加载按钮。

## 9. 更新检测

Echem Analyzer 启动 GUI 后会在后台请求 GitHub 最新 Release:

```text
https://api.github.com/repos/Wildskytree/echem-analyzer/releases/latest
```

如果检测到高于当前 `v0.1.0` 的版本，会弹窗提示:

- 最新版本号
- 当前版本号
- Release 下载链接

更新检测失败时会静默忽略，不影响软件使用。若网络环境无法访问 GitHub，可手动打开项目 Release 页面检查更新:

https://github.com/Wildskytree/echem-analyzer/releases

## 10. 常见问题（FAQ）

### 10.1 为什么文件导入失败？

常见原因:

- 文件不是 `.txt` 或 `.csv`。
- 文件不是文本格式，例如二进制 `.mpr`、`.DTA`。
- 表头无法识别。
- 数据列不是纯数值。
- EIS 文件缺少频率、Z' 或 Z''。
- 文件编码异常。

建议先在仪器软件中导出 ASCII、TXT 或 CSV，并保留清晰列名。

### 10.2 为什么 `.xlsx`、`.mpt`、`.DTA` 不能直接导入？

当前版本桌面导入器主要支持 CHI/CorrTest 文本和通用 CSV。其他厂商格式请先导出为文本或 CSV。

### 10.3 为什么 LSV 的 E1/2 是 N/A 或不合理？

可能原因:

- 数据点少于 10。
- 曲线没有明显扩散平台。
- 背景电流未扣除。
- 电位窗口未覆盖半波区。
- 电流方向或电位扫描方向异常。

建议先检查原始曲线、电极面积、RHE 换算参数和背景扣除情况。

### 10.4 为什么 Tafel 斜率计算失败？

Tafel 需要可靠的 `j_L` 和足够的动力学区数据。若有效点少于 20，或数据点过于接近极限电流，计算会失败。请先确认 E1/2 和极限电流是否合理。

### 10.5 为什么 K-L 分析提示缺少转速？

K-L 需要至少 3 条带 `rotation_rpm` 元数据的 LSV。请确认文件头包含 `rpm` 或 `rotation` 信息。仅文件名包含转速时，当前 GUI 不一定能自动写入该元数据。

### 10.6 为什么 CV 峰检测漏峰或误检？

峰检测依赖 prominence 自动阈值。噪声、基线漂移、峰过宽、峰过小或扫描段不完整都会影响结果。建议先确认 CV 是否包含完整正扫和反扫，必要时选择单一方向检测。

### 10.7 为什么 Cdl 计算失败？

常见原因:

- Cdl 列表少于 2 条 CV。
- CV 缺少有效扫速。
- 扫速不是不同值。
- CV 不包含完整正扫和反扫。
- 中间电位窗口采样点不足。
- 拟合得到的 Cdl 非正。

建议导入多条不同扫速、完整循环的 CV，并确认文件头包含 scan rate。

### 10.8 为什么 EIS 的 Rs/Rct 和专用软件结果不同？

Echem Analyzer v0.1.0 中 Rs/Rct 是快速估算，不是等效电路拟合。专用 EIS 软件通常使用电路模型、非线性拟合和误差评估，因此结果可能不同。

### 10.9 为什么稳定性保持率超过 100%？

可能是曲线后期幅值大于初期幅值，也可能是负电流取绝对值后幅值增加，或存在气泡、噪声尖峰。建议结合原始曲线和分段统计判断。

### 10.10 保存项目后再加载，为什么数据没有恢复？

当前 `.echemproj` 保存的是版本、时间和会话历史，不保存完整 measurement 数据。请保留原始文件，并导出图表、CSV/Excel 和批量报告作为结果归档。

### 10.11 为什么批量报告的 Cdl/ECSA 是 N/A？

批量 GUI 当前没有选择多扫速 CV 列表的入口。请在“CV 分析”页手动计算 Cdl/ECSA，或使用 Python API 调用 `generate_xlsx_with_cdl()` 并传入 CV 列表。

### 10.12 图表中文乱码怎么办？

请安装常用中文字体，例如:

- Microsoft YaHei
- SimHei
- Noto Sans CJK SC
- Source Han Sans SC
- WenQuanYi Zen Hei

安装后重启软件。

### 10.13 结果表可以复制到 Excel 或 Origin 吗？

可以。点击“复制结果”会复制制表符分隔文本，可直接粘贴到 Excel、Origin 或文档中。也可以使用“导出结果”保存为 CSV 或 `.xlsx`。

### 10.14 如何让数据更适合自动分析？

建议:

- 文件名包含样品名、测试类型、转速、扫速。
- 文件头保留 scan rate、rotation rate、electrode、temperature。
- 同一批数据使用一致电位窗口和采样密度。
- EIS 明确导出 frequency、Z'、Z''。
- 批量数据放在同一文件夹中，减少无关文件。
