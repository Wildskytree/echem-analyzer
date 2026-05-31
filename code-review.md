# Echem Analyzer 代码审查报告

审查范围：`/home/ubuntu/projects/echem-analyzer`

结论：项目结构已经覆盖 `io / model / processing / analysis / plotting / batch / cli` 这些核心模块，但当前更像原型版本。主要风险集中在数值算法的单位契约不一致、CV/Cdl 逻辑对常见数据失效、解析器未处理真实文件中的单位和无表头格式，以及测试完全缺失。下面的问题都可以直接转为 issue 或 PR。

## 验证结果

- `.venv/bin/python -m pytest`：收集到 `0` 个测试，pytest 以 exit code `5` 结束；当前没有实际自动化测试。
- `.venv/bin/python -m compileall -q echem_core examples`：通过，未发现语法错误。
- `.venv/bin/python examples/quickstart.py`：通过，但输出 `Tafel 斜率 = -1.5 mV/dec`，暴露 Tafel 单位问题。
- `.venv/bin/python -m echem_core.cli info examples/sample_chi_lsv.txt`：通过，但出现 `RuntimeWarning: 'echem_core.cli' found in sys.modules after import of package 'echem_core'`。
- `.venv/bin/python -m echem_core.cli plot ... --dpi 123`：命令显示使用 `dpi=123`，实际 PNG 元数据仍为约 `300 dpi`。
- `.venv/bin/python -m echem_core.cli batch examples ...`：能生成 Excel 和图；Excel 中 `Tafel_slope (mV/dec)` 为 `-1539.0`，与 CLI/quickstart 的 `-1.5` 不一致。
- 额外探针：
  - `unit_convert_current(np.array([1.0]), "A")` 和 `"mA"` 都抛 `ValueError`。
  - `unit_convert_potential(np.array([1.0]), "V")` 抛 `ValueError`。
  - 一个单圈三角波 CV 输入 `calc_cdl()` 会报“无法拆分为正向/反向扫描”。
  - 无表头 CSV `0.0,1e-6...` 在未传 `col_map` 时解析失败。
  - `Current/mA` CSV 被解析为 `[1.0, 2.0]`，没有转换到 A。

## 关键问题

### 1. Tafel 斜率返回量纲错误，CLI、README、Excel 三处互相矛盾

位置：

- `echem_core/analysis/lsv.py:263-313`
- `echem_core/batch/report.py:160`
- `echem_core/batch/report.py:197-204`
- `echem_core/cli.py:204-205`
- `examples/quickstart.py:58-59`
- `README.md:66-70`

`tafel_slope()` 当前执行的是 `log10(|j_k|) = slope * E + intercept`，所以 `res.slope` 的单位是 `dec/V`。但函数文档写的是 `dE/dlog|j_k|` 和 `V/dec`，CLI/README 又直接按 `mV/dec` 打印，Excel 报告再乘以 `1000`。同一样例数据中，quickstart 打印 `-1.5 mV/dec`，Excel 写 `-1539.0 mV/dec`，两者相差 1000 倍，而且都没有执行 `1/slope`。

建议：

- 明确 API 契约：推荐让 `tafel_slope()` 返回 `mV/dec`，内部拟合 `E = a * log10(|j_k|) + b`，或返回 `1000 / res.slope` 并处理符号。
- 将返回字段重命名为 `slope_mV_dec`，避免调用方重复换算。
- 为理想 Tafel 直线构造合成数据测试，断言 60/120 mV dec^-1 等已知斜率。
- 同步修正 `README.md`、`examples/quickstart.py`、`batch/report.py` 和 CLI 输出。

### 2. 单位转换函数对所有常用单位都失效

位置：

- `echem_core/processing/convert.py:95-110`
- `echem_core/processing/convert.py:113-128`

`unit_convert_current()` 和 `unit_convert_potential()` 先把输入单位转小写，但 `factors` 字典使用 `"A"`, `"mA"`, `"V"`, `"mV"` 这些混合大小写键，导致 `"A"`, `"mA"`, `"V"` 等正常输入全部找不到。

建议：

- 将字典键统一为小写：`{"a": 1.0, "ma": 1e-3, "ua": 1e-6, "µa": 1e-6, "na": 1e-9}`，电位同理。
- 增加 `μA/uA/µA`、`mV/V` 的参数化测试。
- 解析器应调用这些函数，而不是只把原始数字塞进 `Measurement`。

### 3. Cdl 计算对常见单圈 CV 数据失效，反向扫描插值方向也不正确

位置：

- `echem_core/analysis/cv.py:163-178`
- `echem_core/analysis/cv.py:278-288`

`_split_cv()` 要求至少两个符号变化才返回正/反向扫描。一个标准单圈 CV 只有一次电位方向反转，因此会返回空数组，`calc_cdl()` 无法工作。即使因重复顶点产生两个符号变化，反向扫描段也可能只剩很短片段。

另外，`np.interp(common_pot, rev_pot, rev_cur)` 要求 `rev_pot` 单调递增，但当前代码刻意保留反向扫描为递减方向（`cv.py:189-190`），这会导致插值结果错误。

建议：

- 用第一个有效方向反转点拆分单圈 CV；多圈 CV 再按成对转折点拆周期。
- 插值前对每个分支按电位升序排序：`idx = np.argsort(branch_potential)`。
- `calc_cdl()` 增加显式参数 `potential_window=(lo, hi)`，不要默认只用电位中点 ±10%。
- 为单圈 CV、带重复顶点 CV、多圈 CV、降序起扫 CV 各加测试。

### 4. CLI 的处理结果没有用于出图，`--dpi` 参数实际无效

位置：

- `echem_core/cli.py:184-195`
- `echem_core/cli.py:210-215`
- `echem_core/cli.py:273-300`
- `echem_core/plotting/lsv_plot.py:365-396`

`cmd_process()` 已经把 `potential/current` 转换为 RHE 和电流密度，但保存图片时调用 `plot_lsv(m, save_path=output)`，传入的是未处理的 `Measurement`，所以输出图仍是原始电位/电流。`cmd_plot()` 接收 `--dpi` 并打印出来，但 `plot_lsv()` 的 `_save_figure()` 内部硬编码 `dpi = 300`，实际文件不会使用用户传入的 DPI。

建议：

- 在 CLI 中构造 `processed = m.copy_with_processed(potential, current, recipe)` 后再传给绘图和报告。
- 给 `plot_lsv()` 和 `_save_figure()` 增加 `dpi` 参数，并从 CLI 传入。
- 添加 CLI 集成测试：同一文件在 `--area` 后 y 轴和数值应为电流密度；`--dpi 123` 的 PNG 元数据应为 123 dpi。

### 5. CSV/CHI 解析器还不能可靠兼容真实仪器数据

位置：

- `echem_core/io/csv_parser.py:182-215`
- `echem_core/io/csv_parser.py:468-485`
- `echem_core/io/csv_parser.py:579-653`
- `echem_core/io/chi_parser.py:77-82`
- `echem_core/io/chi_parser.py:129`
- `echem_core/io/chi_parser.py:236-253`
- `echem_core/io/chi_parser.py:258-275`

具体问题：

- CSV 无表头时 `_find_header_row()` 返回 `0`，第一行数据被当作表头，未传 `col_map` 时没有默认 `Column_0/Column_1` 回退。
- `Current/mA`、`Potential/mV` 等列名中的单位没有被应用，数值会被当作 A/V 使用。
- `_parse_data_rows()` 直接 `np.array(data_rows, dtype=float)`，遇到行宽不一致的真实导出文件会报错；没有给出具体行号。
- CHI 表头解析用 `stripped.replace("\t", " ").split(",")`，制表符表头会变成一个列名；虽然后续有默认列回退，但列名和单位元数据会丢失。
- `Electrode, GC RDE...` 这类逗号分隔元数据不会被 `line.split(":")` 解析，样例文件中的电极信息也没有进入标准 metadata。
- `parse_folder()` 对 `.csv` 仍调用 `parse_chi_file()`，并通过 `print()` 静默跳过失败，调用方无法拿到失败列表。

建议：

- 用 `csv.Sniffer` 或 pandas/numpy 结构化读取替代手写分隔符逻辑；至少要返回失败行号和原因。
- 表头识别失败但首行全是数字时，自动生成列名并默认前两列为 potential/current。
- 解析列名单位并调用 `unit_convert_current()` / `unit_convert_potential()`。
- `parse_folder()` 应根据扩展名选择 CHI/CSV 解析器，并返回 `(loaded, errors)`。
- 收集真实 CHI 600/700/1100、Gamry、Autolab 导出样例作为 fixture。

### 6. E1/2 置信度和边界检查不足

位置：

- `echem_core/analysis/lsv.py:84-119`

`find_e_half()` 用平台区线性回归的 `R²` 作为平台质量。问题是，一条明显有斜率的直线也能得到接近 1 的 `R²`，这不代表扩散平台平坦。函数也没有检查 `j_L / 2` 是否落在观测电流范围内，`np.interp()` 会在越界时静默返回边界电位。

建议：

- 平台质量应同时检查斜率绝对值、平台区相对标准差、平台区长度和噪声。
- 若 `j_L/2` 不在当前范围内，应返回低置信度并给出原因，或抛出可解释异常。
- 增加“无平台”“半波越界”“强噪声”“正/反扫描方向不同”的测试。

### 7. 背景扣除按数组索引插值，不按电位对齐

位置：

- `echem_core/processing/background.py:20-28`
- `echem_core/batch/batch_processor.py:376-383`

当样品和空白长度不同，`subtract()` 用归一化索引 `0..1` 对齐，而不是用电位轴对齐。真实 LSV/CV 中不同采样率、不同电位窗口或反向扫描都会导致扣除错位。

建议：

- 改为 `subtract(sample_potential, sample_current, blank_potential, blank_current)`。
- 对 blank 电位排序后按样品电位插值，并检查重叠电位窗口。
- 对无重叠、部分重叠、方向相反的情况给出明确错误或裁剪策略。

### 8. Koutecky-Levich 分析有单位和零值风险

位置：

- `echem_core/analysis/lsv.py:398-421`

K-L 方程中的常数默认给出的是 A/cm² 量纲，但项目常用 current density 是 mA/cm²。当前 `inv_j.append(1.0 / abs(j_at_e))` 没有单位换算，计算出的电子转移数可能偏差 1000 倍。代码也没有检查 `rpm <= 0` 或 `j_at_e == 0`。

建议：

- 明确 `measurements_by_rpm` 的电流单位，最好参数化 `current_unit="mA/cm2"` 并内部统一到 A/cm²。
- 对 `rpm <= 0`、`j_at_e` 接近 0、斜率负值等情况显式报错。
- 增加合成 K-L 数据测试，断言电子转移数接近 2 或 4。

## 结构和依赖

### 已创建的模块

核心目录都存在：`model`、`io`、`processing`、`analysis`、`plotting`、`batch`、`cli`。但实现完整性不一致：

- README 宣称支持 EIS Nyquist/Bode 图，但 `plotting/` 只有 LSV/CV，没有 EIS 绘图入口。
- `echem_core/plotting/__init__.py:6-26` 只导出 CV 和 style，未导出 `plot_lsv()` / `plot_lsv_comparison()`。
- `echem_core/io/__init__.py`、`echem_core/analysis/__init__.py`、`echem_core/batch/__init__.py` 为空，不利于稳定公开 API。
- `tests/` 只有 `tests/__init__.py`，没有测试模块。

### 导入关系

没有发现会阻止导入的硬循环依赖，`compileall` 通过。但 `echem_core/__init__.py:1` 一次性导入 `cli`，导致 `python -m echem_core.cli` 出现 RuntimeWarning。顶层包导入也会提前加载 matplotlib 相关模块，增加 import 成本和副作用。

建议：

- `echem_core/__init__.py` 只保留版本号和轻量公共对象，不导入 `cli`。
- 各子包 `__init__.py` 明确导出稳定 API。
- CLI 继续保持函数内懒导入即可。

## 数据模型

位置：

- `echem_core/model/measurement.py:66-79`
- `echem_core/model/measurement.py:81-121`
- `echem_core/model/measurement.py:123-165`
- `echem_core/io/csv_parser.py:591-624`

优点：

- 原始数组复制并设置只读，避免调用方直接改原始数据。
- `metadata` 和 `processing_recipe` 返回深拷贝，外部不容易误改内部状态。
- `copy_with_processed()` 记录 recipe，方向是合理的。

问题：

- `technique` 和 `file_hash` 仍是公开可写字段，严格说对象并非完全只读。
- EIS 数据被塞进 `raw_potential=frequency`、`raw_current=z_real`、`raw_time=z_imag`，语义不清，会影响 `cmd_info()`、绘图和后续处理。
- `copy_with_processed()` 只能保存 processed potential/current，不能表达处理后的 time/frequency/Z_imag。
- 批处理归一化后没有更新 metadata 中的 `area_cm2`，导致绘图轴标签无法判断当前数据是否为电流密度。

建议：

- 保留 Measurement 的只读原始数组设计，但为 EIS 增加明确字段或单独 `EISMeasurement`。
- 把 `technique`、`file_hash` 做成只读 property，或使用 frozen dataclass 加内部 builder。
- `copy_with_processed()` 支持 `metadata_updates`，处理面积归一化时写入 `area_cm2` 和当前电流单位。

## 绘图和报告

位置：

- `echem_core/plotting/lsv_plot.py:184-194`
- `echem_core/plotting/lsv_plot.py:365-396`
- `echem_core/plotting/cv_plot.py:297-299`
- `echem_core/plotting/styles.py:106-115`
- `echem_core/batch/report.py:37-43`
- `echem_core/batch/report.py:213-222`
- `echem_core/batch/batch_processor.py:244-248`

问题：

- LSV y 轴在无 `area_cm2` 时标为 `I / mA`，但原始电流单位是 A；面积归一化后 metadata 又未更新，可能仍标错。
- `_save_figure()` 固定 300 dpi，调用方无法控制。
- `plot_cv()` 保存文件时不创建父目录，行为与 `plot_lsv()` 不一致。
- `JournalStyle.apply()` 修改全局 `matplotlib.rcParams`，会影响同一进程后续图。
- `report._safe_analysis()` 吞掉所有异常，只写 `N/A`，报告中没有失败原因。
- `generate_xlsx()` 对 CV 永远写 `Cdl/ECSA = N/A`；`generate_xlsx_with_cdl()` 又把一个全局 Cdl/ECSA 写到所有行，没有按样品分组。
- `batch_processor.export_figures()` 中 `m.metadata.get("sample_name", default)` 在标准 metadata 里会返回 `None`，可能生成 `None.png`。

建议：

- 在 Measurement metadata 中维护 `current_unit` 和 `potential_reference`。
- 所有绘图函数统一接受 `dpi`、创建父目录、返回保存路径。
- `JournalStyle.apply()` 改为局部 rc_context 或只设置当前 figure/axes。
- Excel 报告增加 `analysis_status` / `analysis_error` 列。
- 按 sample/group 计算 Cdl/ECSA，并把用于计算的 CV 文件列出来。

## CLI 设计

位置：

- `echem_core/cli.py:65-69`
- `echem_core/cli.py:179-182`
- `echem_core/cli.py:197-207`
- `echem_core/cli.py:236-268`
- `echem_core/cli.py:298-300`

问题：

- 解析失败时多处 `except Exception` 直接回退或只打印错误，用户看不到具体是 CHI 失败还是 CSV 失败。
- `process` 只对 LSV 做分析，CV/EIS 没有对应命令分支。
- `plot` 永远调用 `plot_lsv()`，即使输入是 CV/EIS。
- `batch` 没有接收 recipe 文件，复杂处理链只能通过几个命令行参数表达。

建议：

- 增加 `--format auto|chi|csv` 和 `--verbose`。
- `plot` 根据 `m.technique` 分发到 LSV/CV/EIS 绘图。
- 增加 `echem process --save-csv processed.csv`，方便验证处理结果。
- 增加 `echem batch --recipe recipe.yml`，并把 recipe 写入报告。

## 性能

位置：

- `echem_core/analysis/lsv.py:284-301`
- `echem_core/io/chi_parser.py:36-40`
- `echem_core/io/csv_parser.py:101-104`

问题：

- Tafel 线性区扫描是双重循环，窗口数量随数据量接近 O(n^2)。普通 500 点没问题，但高采样数据或批处理大量文件会变慢。
- 文件哈希一次性 `f.read()` 读全文件，大文件可以改为分块读取。

建议：

- Tafel 扫描先固定窗口长度或用 rolling regression，再扩展候选区间。
- 哈希函数改为按 1-4 MB chunk 更新。

## 测试覆盖

当前没有实际测试，这是最影响维护的短板。建议先补以下测试：

- `Measurement`：数组只读、长度校验、metadata 深拷贝、recipe 追加。
- `convert`：RHE 换算、A/mA/uA/nA、V/mV、非法单位。
- `csv_parser`：有表头、无表头、CSV/TSV/分号、Current/mA、Potential/mV、EIS 列、坏行错误。
- `chi_parser`：真实 CHI LSV/CV/EIS fixtures、中文/GBK、逗号和冒号 metadata。
- `lsv`：E1/2 合成 sigmoid、无平台、Tafel 已知斜率、K-L 已知电子数。
- `cv`：单圈/多圈 CV 拆分、Cdl 已知斜率、ECSA 单位。
- `plotting`：保存 png/svg/pdf/tiff、DPI 生效、CV/LSV 分发。
- `cli`：`info/process/plot/batch` 的 smoke tests。

## 最优先改进的 3 个问题

1. 先修数值契约：Tafel 斜率单位、`unit_convert_*()`、Cdl 拆分/插值、K-L 单位。这些会直接输出错误科研结论。
2. 补测试和 fixture：至少覆盖 README 中承诺的 CHI/CSV/LSV/CV/EIS 主路径，否则后续改动没有安全网。
3. 统一处理后数据流：CLI、batch、report、plotting 都应使用同一个 processed `Measurement`，并通过 metadata 记录单位、参比电极、面积、recipe。

## 下一步建议添加的功能

- EIS Nyquist/Bode 绘图和 Randles 等效电路拟合；README 已经承诺 EIS 图，但当前缺入口。
- 处理后数据导出：`processed.csv`、recipe JSON/YAML、Excel 附录曲线数据。
- 批处理 recipe 文件：支持背景扣除、RHE、归一化、Cdl/ECSA 分组计算。
- 非法拉第区间选择：为 Cdl 提供显式电位窗口、自动窗口质量评估和图上标注。
- 真实仪器格式 fixture 集：CHI、Gamry、Autolab、BioLogic 至少各一组，用于回归测试。
