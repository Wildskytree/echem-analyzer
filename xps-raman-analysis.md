# XPS 与拉曼光谱分析软件市场/可行性判断

> 视角：催化/电化学方向科研人员  
> 判断基准日期：2026-05-31  
> 结论先行：值得做，但不要一上来做“替代 CasaXPS、Avantage、LabSpec、WiRE 的全功能软件”。更务实的方向是做 Echem Analyzer 的表征数据扩展模块，先解决催化科研里最重复、最容易出错、最能节省时间的后处理问题：批量导入、统一基线、统一峰参数、统一作图、统一导出、和电化学结果放在同一张样品表里。

## 0. 总体判断

这件事有真实需求，但市场不是空白市场。

XPS 和拉曼都有成熟工具。XPS 里，CasaXPS 是很多课题组实际使用的标准工具，Thermo Avantage 这类原厂软件和仪器绑定很深；拉曼里，HORIBA LabSpec、Renishaw WiRE 直接控制仪器，并且带 mapping、数据库检索、去荧光、去 cosmic ray、PCA 降噪等功能。Origin/OriginPro 又占住了大量科研作图和峰拟合的通用场景。Python 生态里，lmfit、pybaselines、Rampy、RamanSPy 这类库已经能提供很多算法积木。

所以机会不在“再做一个通用峰拟合器”。机会在：

- 面向催化材料的固定工作流，而不是面向所有谱学用户的通用平台。
- 把电化学活性、XPS 价态/元素比例、拉曼 D/G 或 mapping 指标放到同一个 sample-centric 项目里。
- 对一批样品使用同一套 recipe，自动输出论文图、组会图和 Excel 汇总表。
- 让处理过程可追溯：原始文件 hash、基线方法、拟合模型、参数约束、峰面积/峰高计算方式都能回看。
- 提供中文、离线、Windows 友好的工具链，降低非编程用户门槛。

一句话：可以做成一个很有用的小工具，不要幻想一开始吃掉 XPS/拉曼商业软件市场。

## 1. 现有工具格局

### 1.1 XPS 工具

| 工具 | 当前位置 | 强项 | 对 Echem Analyzer 的启示 |
|---|---|---|---|
| Thermo Scientific Avantage | 原厂 XPS 控制、处理和报告软件 | 和 Thermo 仪器深度绑定，覆盖采集、处理、报告、知识库/识谱辅助 | 不要和原厂软件竞争仪器控制；优先吃“导出后处理”和跨样品汇总 |
| CasaXPS | XPS/Auger 等表面分析数据处理工具，很多课题组熟悉 | 背景类型、线型、定量报告、谱图/成像处理都很完整 | XPS 深水区已经有强工具；新工具必须靠垂直工作流和可复现批处理取胜 |
| XPSPeak 4.1 | 老牌免费 XPS 分峰软件 | 简单、免费、很多学生知道 | 说明“免费峰拟合”本身没有壁垒；现代体验、批处理、可追溯才是机会 |
| KoXPD/KolXPD | 面向 XPS、XPD、ARPES、NEXAFS 等谱学测量和处理 | 覆盖更专业的光电子谱场景 | 不是催化用户的日常主流入口，但说明专业谱学软件的复杂度很高 |
| Python 库，例如 lmfit、pyspectra、pybaselines | 算法和数据处理积木 | 非线性拟合、参数约束、基线校正、通用谱图预处理 | 适合作为底层引擎；但单独的库不能解决普通科研用户的完整工作流 |

XPS 的现实情况是：成熟工具很强，但很多催化用户仍然在“Avantage/CasaXPS 拟合一下，Origin 重新画图，Excel 手动整理比例，PPT 手动拼图”。这个流程能用，但重复、难追溯、容易每篇文章换一套处理方式。

### 1.2 拉曼工具

| 工具 | 当前位置 | 强项 | 对 Echem Analyzer 的启示 |
|---|---|---|---|
| HORIBA LabSpec | HORIBA 拉曼系统的软件平台 | 仪器控制、采集、处理、显示、fast mapping、kinetics、高通量等 | 原厂软件覆盖采集端很强；新工具应从导出数据后的批处理切入 |
| Renishaw WiRE | Renishaw 拉曼系统的软件平台 | 仪器控制、背景/荧光去除、基底/溶剂扣除、cosmic ray 去除、PCA 降噪、数据库识别、mapping | 不要复制 WiRE；应做跨样品、跨电化学结果的论文数据整理 |
| Origin/OriginPro 及相关插件/模板 | 通用科研作图和峰分析工具 | 峰识别、基线、积分、拟合、批量模板、作图强 | 用户已经会用 Origin；新工具要输出 Origin 友好的表格，同时减少重复劳动 |
| RamanSPy、Rampy、pybaselines 等 Python 库 | 开源谱学分析库 | Raman 数据结构、预处理、基线、平滑、峰参数、mapping 支持 | 可以复用算法思想或依赖，但要包装成非编程用户能用的流程 |

拉曼比 XPS 更适合作为第一阶段切入点，因为 D 峰/G 峰比、峰位、FWHM、mapping 热图这些指标更接近“工程化批处理”。XPS 的分峰更依赖化学判断，自动化风险更高。

### 1.3 这些工具的共同痛点

共同痛点不是“不能拟合峰”，而是下面这些更贴近科研日常的问题：

- 数据分散：电化学、XPS、拉曼通常在不同仪器、不同电脑、不同软件里处理，最后靠 Excel/PPT 人肉合并。
- 批处理弱：单张谱图可以处理，几十个样品、多个处理条件、多个循环或多个 mapping 区域就很费时间。
- 可追溯性弱：很多结果只保存在截图、PPT、Origin 工程或 CasaXPS 工程里，几个月后很难确认当时用了什么基线、约束、线型和积分方式。
- 图表重做多：原厂软件导出的图经常不能直接进论文，还要去 Origin、Illustrator 或 PowerPoint 里重画。
- 跨仪器格式麻烦：同一个课题组可能 CHI 做电化学，外测 XPS，中心平台做拉曼，文件格式和导出字段都不统一。
- 学习曲线高：CasaXPS、Avantage、LabSpec、WiRE 都有自己的概念体系；新学生通常是照师兄师姐的模板操作，容易把模板当原理。
- 拟合自由度太大：尤其 XPS，峰位、FWHM、背景、线型、分裂峰约束稍微变一下，半定量结论就可能变。
- 缺少“催化论文视角”：现有工具多以谱图本身为中心，不以“样品系列、处理条件、活性指标、价态变化、结构缺陷指标”这个论文叙事为中心。

## 2. 做这类软件的难点

### 2.1 XPS 分峰拟合不是普通曲线拟合

XPS 最大的坑是：数学上拟合得很好，不代表化学上合理。

主要难点包括：

- 背景模型复杂：Linear、Shirley、Tougaard、Smart background、样条背景等选择会明显影响峰面积。
- 线型选择复杂：Gaussian-Lorentzian 混合、Voigt、Doniach-Sunjic、不对称峰、金属态拖尾等都可能出现。
- 自旋轨道分裂约束：例如 2p、3d 区域通常要约束峰间距、面积比、FWHM，不能把每个峰完全自由地拟合。
- 荷电校正和结合能校准：C 1s 284.8 eV 不是所有体系都能无脑使用，导电载体、原位/准原位、表面污染都会影响解释。
- 半定量依赖校正因子：RSF、仪器 transmission function、采样深度、表面粗糙度、元素分布都影响元素比例。
- 催化材料经常峰重叠：过渡金属 2p 卫星峰、氧空位/羟基/吸附水、N 物种、S/P 掺杂、金属氧化态混合，靠全自动分峰很危险。
- 结果有主观性：两个熟练用户可能都能给出“看起来合理”的拟合，但峰数和归属不同。

因此，如果做 XPS 模块，产品表达必须克制：

- 可以叫“assisted fitting”或“可追溯拟合工作流”，不要叫“自动价态判断”。
- 必须显示模型、约束、残差、峰面积计算方式和警告。
- 最好提供“模板 + 人工确认”，而不是全自动给结论。
- 对价态分析要输出“候选归属”和“引用/备注字段”，不要替用户写死化学结论。

### 2.2 拉曼分析相对容易，但也不是无脑峰识别

拉曼的难点集中在预处理和一致性：

- 荧光背景会严重抬高基线，尤其生物质碳、聚合物、含有机残留样品、低结晶碳材料。
- Cosmic ray 尖峰会影响自动峰识别和峰高。
- 平滑参数过强会改变峰高、FWHM 和弱峰。
- D/G 比到底用峰高、峰面积、拟合峰面积还是积分面积，需要在同一批样品里固定。
- mapping 数据量大，且要处理坐标网格、坏点、空白区域、归一化、mask、色标一致性。
- 不同仪器的激光波长、曝光、积分次数、物镜、功率和光斑会影响强度，不能把不同条件的数据简单比较。

拉曼模块更适合先做成“规则明确的批处理工具”：

- 统一基线校正。
- 统一 D/G 区间。
- 统一峰识别或峰拟合模型。
- 统一输出 ID/IG、峰位、FWHM、峰面积、mapping 热图。
- 保存 recipe，保证同一篇文章所有样品处理方式一致。

### 2.3 原始格式解析会比算法更烦

真正拖进度的往往不是拟合算法，而是文件格式。

XPS 可能遇到：

- VAMAS `.vms` / `.vamas`。
- CasaXPS 工程或导出文本。
- Thermo Avantage 导出表。
- Kratos、PHI、Specs、Scienta Omicron 等厂商格式。
- 测试平台只给 Excel、CSV、PDF，甚至只给截图。

拉曼可能遇到：

- Renishaw `.wdf`。
- HORIBA LabSpec 导出文本、CSV 或专有格式。
- `.spc`。
- mapping 文件中坐标、光谱矩阵、元数据分散保存。
- 只有两列 txt，但列名、单位、分隔符、编码都不统一。

务实策略：

1. 第一阶段只支持“导出的 CSV/TXT/Excel 两列谱图”和“长表 mapping 数据”，不要一开始死磕所有原始格式。
2. 对 XPS 优先支持 VAMAS 和常见导出文本，但把专有二进制格式放到后面。
3. 对拉曼优先支持 Renishaw/HORIBA 的可导出格式，再考虑 `.wdf`、`.spc`。
4. 建一个 importer registry，让每个格式解析器独立发展，不污染核心分析逻辑。
5. 明确要求用户提供样例文件和期望输出，否则格式支持会变成无底洞。

### 2.4 和现有工具比，真正优势在哪里

不要把优势写成“我们拟合更准”。这很难证明，也容易被专家质疑。

更可信的优势是：

- 更懂催化工作流：样品 ID、前驱体、热处理、负载量、电解液、活性指标、XPS 元素比例、拉曼 D/G 指标在同一个项目里。
- 更适合批量：一套 recipe 处理一组样品，输出一张汇总表和一组统一风格图。
- 更可追溯：每个结果能追到原始文件、处理步骤和拟合参数。
- 更适合论文出图：直接给 ACS/RSC/Wiley 尺寸、色盲友好配色、TIFF/SVG/PDF、可编辑数据。
- 更低门槛：中文说明、催化示例、常见材料模板，例如碳材料 D/G、Ni/Fe/Co 基催化剂常见 XPS 区域。
- 更开放：底层用 Python 科学栈，便于高级用户检查和二次开发。
- 更容易和 Echem 数据联动：活性提升是否对应 Ni3+/Ni2+ 比例、缺陷程度、碳载体石墨化程度、氧空位相关峰等。

同样要承认边界：

- 不可能短期内超过 CasaXPS 的 XPS 专业深度。
- 不应该替代 Avantage、LabSpec、WiRE 的仪器控制和原厂生态。
- 不会比 Origin 更通用。
- 如果没有真实用户数据和专家反馈，XPS 自动拟合很容易做成“看起来很智能，实际不可信”的功能。

## 3. 和 Echem Analyzer 的关系

### 3.1 独立工具，还是 Echem Analyzer 插件/模块

建议第一阶段做成 Echem Analyzer 的一个 spectroscopy 模块，而不是马上独立成新产品。

理由：

- 用户重叠度高：催化/电化学用户本来就同时看 LSV/CV/EIS、XPS、Raman。
- 产品叙事更清楚：不是“又一个谱图软件”，而是“催化数据后处理工作台”。
- Echem Analyzer 已经有批处理、recipe、期刊作图、CLI 的雏形，可以直接复用产品心智。
- 早期获客更自然：先让现有电化学用户上传 XPS/Raman 导出文件，验证需求。

但架构上不要把谱学逻辑硬塞进电化学模型里。长期可以这样理解：

- 产品层叫 Echem Analyzer 或 Catalyst Analyzer 都可以。
- 核心层应该拆成 electrochem、spectroscopy、common 三块。
- 如果 spectroscopy 模块后来用户量独立增长，再拆成独立桌面入口或独立包。

### 3.2 代码复用程度

可复用的部分不少，但不能直接复用当前的 `Measurement` 模型。

可以复用或改造成通用能力的部分：

- 文件导入模式：当前已有 CHI/CSV parser，可以扩展成 importer registry。
- recipe 思路：当前 `Measurement.copy_with_processed()` 保存处理步骤，这个思想很适合谱学。
- 批处理：文件夹导入、统一 recipe、Excel 汇总、批量出图。
- 绘图模板：ACS/RSC/Wiley 尺寸、配色、DPI、导出格式。
- CLI 入口：适合高级用户和自动化处理。
- 测试策略：每个 parser 和每个分析函数都应有样例数据测试。

需要新建的能力：

- `Spectrum`：一维谱图，包含 x 轴、y 轴、单位、谱种、元数据、处理 recipe。
- `SpectrumMap`：mapping 数据，包含 x/y 空间坐标、波数轴、强度矩阵、mask、空间分辨率。
- 谱学通用预处理：裁剪、平滑、重采样、归一化、基线校正、cosmic ray 去除。
- 峰拟合引擎：Gaussian、Lorentzian、Voigt、Pseudo-Voigt、GL 混合、XPS 不对称峰、Shirley/Tougaard 背景。
- 约束系统：峰位范围、FWHM 范围、面积比、峰间距、共享参数、固定/浮动参数。
- 拟合报告：参数、误差、残差、R2/chi-square、AIC/BIC、警告、导出表。
- 材料模板：Raman D/G、XPS C 1s/N 1s/O 1s/metal 2p 等常用模板。

### 3.3 建议架构

不要在当前结构里直接新增一堆 `xps.py`、`raman.py` 就结束。更稳的方向是逐步抽出 common 层。

建议目标结构：

```text
echem_core/
  common/
    model/
      source_file.py
      recipe.py
      sample.py
    processing/
      baseline.py
      smoothing.py
      normalize.py
    plotting/
      styles.py
      export.py
    io/
      registry.py
      tabular.py

  electrochem/
    io/
    processing/
    analysis/
    plotting/

  spectroscopy/
    model/
      spectrum.py
      spectrum_map.py
    io/
      csv_spectrum.py
      excel_spectrum.py
      vamas.py
      wdf.py
    processing/
      baseline.py
      cosmic_ray.py
      calibration.py
    fitting/
      backgrounds.py
      lineshapes.py
      constraints.py
      fit_engine.py
    analysis/
      xps.py
      raman.py
    plotting/
      spectrum_plot.py
      map_plot.py
```

项目数据层建议以 `Sample` 为中心，而不是以文件为中心：

```text
Sample
  sample_id: NiFe-LDH-400
  synthesis: ...
  electrochem:
    lsv: ...
    cv: ...
    eis: ...
  xps:
    survey: ...
    regions:
      Ni 2p: ...
      Fe 2p: ...
      O 1s: ...
  raman:
    spectra: ...
    mapping: ...
  summary:
    overpotential_10mA: ...
    tafel_slope: ...
    ni3_ni2_ratio: ...
    oxygen_vacancy_fraction: ...
    id_ig: ...
```

这样做的价值是：用户最后不是想保存“一个拟合文件”，而是想回答“这个样品为什么活性更好”。软件要围绕这个问题组织数据。

### 3.4 底层依赖建议

可以优先用成熟 Python 库，不要从零写所有算法：

- `lmfit`：非线性拟合、参数边界、参数约束、组合模型。
- `scipy.signal`：平滑、峰识别、滤波。
- `pybaselines`：谱学基线校正。
- `rampy`：Raman/IR/XAS 等谱学处理函数，可参考其 baseline、smooth、peak fitting 工作流。
- `ramanspy`：如果重点做 Raman mapping 和对象模型，可以参考其数据结构和 pipeline 思路。
- `pandas/openpyxl`：批量结果表。
- `matplotlib`：继续沿用当前绘图体系。

XPS 的专用线型、Shirley/Tougaard 背景、双峰约束、报告格式可能需要自己封装，因为通用库不会替你处理 XPS 领域规则。

## 4. 务实建议

### 4.1 值不值得做

值得做，但只值得以“小步验证”的方式做。

建议判断：

| 方向 | 判断 |
|---|---|
| 做完整 XPS 商业软件 | 不建议，难度高、专家门槛高、竞品强、验证周期长 |
| 做完整拉曼原厂软件替代品 | 不建议，采集和仪器控制不是你的优势 |
| 做 XPS/Raman 通用峰拟合器 | 价值有限，类似工具和库很多，差异化弱 |
| 做催化数据联合后处理模块 | 建议，和 Echem Analyzer 用户强相关，差异化更清楚 |
| 先做 Raman D/G + mapping 批处理 | 建议，技术风险较低，容易做出用户能感知的时间节省 |
| 做 XPS assisted fitting + 可追溯报告 | 可以做，但要克制，先从常见导出格式和常见元素区域开始 |

如果目标是开源影响力和小额商业化，这个方向比单纯电化学更有故事，因为它覆盖“活性-结构-价态”的完整催化论文链条。  
如果目标是做大公司级商业软件，单人/小团队不现实。

### 4.2 XPS + Raman + 电化学联合分析是不是催化圈真实痛点

是真实痛点，但付费意愿未必天然强。

真实痛点来自这些场景：

- 做一组催化剂：不同煅烧温度、不同掺杂比例、不同电解液处理、不同循环后样品。
- 电化学看到了活性变化，需要 XPS 支持价态变化、元素比例变化、表面重构。
- Raman 看缺陷、石墨化程度、碳载体 D/G、某些金属氧化物/硫化物/磷化物相变或中间体信号。
- 最终论文需要把 LSV/Tafel/CV/EIS、XPS 分峰、Raman 谱图、mapping、柱状统计放在同一逻辑里。

现在很多人的流程是：

1. 电化学数据在 CHI/BioLogic/Excel/Origin 处理。
2. XPS 在 Avantage/CasaXPS 处理。
3. Raman 在 LabSpec/WiRE/Origin 处理。
4. 指标手动抄到 Excel。
5. 图重新在 Origin 或 PPT 里统一风格。
6. 返修时再找原始文件和处理参数。

这确实痛，但要注意两点：

- 很多用户已经习惯忍受这个流程，不一定主动找新软件。
- XPS/拉曼数据经常来自测试中心，用户拿到的可能是处理后的图或 Excel，不一定有完整原始文件。

所以卖点不能是“更科学地分析 XPS/Raman”，而应该是：

- 少手动整理。
- 少重复作图。
- 少忘记处理参数。
- 少在多软件之间复制粘贴。
- 一批样品的表征指标能和电化学指标自动对齐。

这个卖点更真实，也更容易让催化用户愿意试用。

### 4.3 第一阶段做什么

第一步不要做“XPS 全自动分峰”。建议做一个 spectroscopy MVP，范围控制在 4 到 8 周能完成真实 demo。

MVP 名称可以叫：

```text
Echem Analyzer Spectroscopy Module
```

第一阶段功能建议：

1. 通用谱图导入
   - 支持 CSV/TXT/Excel 两列谱图。
   - 支持一批文件按文件名解析 sample_id。
   - 支持用户手动列映射：x 轴、intensity、sample_id、x/y mapping 坐标。

2. Raman D/G 批处理
   - 基线校正：poly、ALS/arPLS、rubberband 至少选两到三种。
   - 平滑：Savitzky-Golay，可关闭。
   - 峰区设置：D 峰、G 峰、2D 峰可配置。
   - 输出：ID/IG，峰位，FWHM，峰面积，峰高。
   - 图：单谱图、叠图、D/G 柱状图、mapping 热图。
   - recipe：保存所有参数。

3. XPS 轻量辅助
   - 先支持导出后的 region 数据，不碰复杂原厂二进制。
   - 支持能量校准、裁剪、归一化、Linear/Shirley 背景。
   - 支持 Gaussian/Lorentzian/Pseudo-Voigt/GL 简单模型。
   - 支持手动添加峰和参数边界。
   - 输出拟合参数和分峰图。
   - 明确标注“辅助拟合，不自动判断价态”。

4. 联合样品表
   - 把 Raman 指标、XPS 指标、电化学指标按 sample_id 合并。
   - 输出 Excel 汇总和统一风格图片。
   - 支持一键生成 `summary.xlsx` 和 `figures/`。

5. 示例数据和教程
   - 一个碳材料 Raman D/G 示例。
   - 一个 Ni/Fe/Co 催化剂 XPS 区域拟合示例。
   - 一个 ORR/OER 电化学 + XPS + Raman 联合汇总示例。

第一阶段不要做：

- 仪器控制。
- 全格式原始文件解析。
- 自动价态判定。
- 自动写论文结论。
- XPS 元素数据库大而全。
- 复杂 3D mapping/化学计量学平台。

### 4.4 验证方式

这个方向必须用真实数据验证，不能靠想象。

建议做一个很小的验证闭环：

1. 找 5 个催化/电化学用户，每人要 1 组真实数据。
2. 每组数据至少包含电化学 + XPS 或电化学 + Raman。
3. 记录他们现在从原始数据到论文图要花多久。
4. 用 MVP 跑同样数据，比较是否能节省 30% 以上整理时间。
5. 问一个具体问题：如果这个工具能稳定处理你们课题组数据，你愿不愿意每年付 199 到 399 元个人版，或课题组付 999 到 2999 元？

如果多数用户只是说“挺有意思”，但不愿意把下一篇文章的数据放进来，那就不要继续扩大。

如果有 2 到 3 个课题组愿意持续给数据、提需求、用它出组会图，这个方向就值得继续。

### 4.5 最推荐的路线

推荐路线：

1. 先做 Raman D/G 和普通谱图批处理。
2. 同时做 XPS region 数据导入和可追溯绘图。
3. 等有用户后，再做 XPS assisted fitting。
4. 最后再考虑 VAMAS、WDF、SPC 等格式和更多厂商支持。

原因很简单：

- Raman D/G 更容易做出稳定 MVP。
- XPS 拟合更容易被专家质疑，需要真实反馈慢慢打磨。
- 用户最先感知到的价值往往不是“拟合算法更高级”，而是“一批样品不用重复点几十遍，不用手动抄表，不用重画图”。

## 5. 最终建议

可以扩展，但定位要收窄：

> Echem Analyzer 不应变成“大而全的谱学软件”，而应变成“催化科研数据后处理工作台”。XPS 和拉曼模块的目标不是替代 CasaXPS、Avantage、LabSpec、WiRE，而是接管这些软件之后的批量整理、统一作图、可追溯报告和多表征联合分析。

最务实的第一步是：

```text
做一个支持 CSV/TXT/Excel 的 Raman D/G 批处理 + XPS region 导入/作图 MVP，
把结果和现有电化学指标按 sample_id 合并导出。
```

如果这个 MVP 能让真实催化用户少花半天整理一批样品的数据，就继续做。  
如果只是做了一个“又能拟合峰”的工具，就很难有市场。

## 参考资料

- [Thermo Scientific Avantage XPS Software](https://www.thermofisher.cn/cn/en/home/industrial/spectroscopy-elemental-isotope-analysis/surface-analysis/xpssimplified/instruments/avantage-data-system.html)
- [CasaXPS XPS Analysis Software](https://casaxps.com/)
- [KolXPD spectroscopy data measurement and processing](https://alfa.kolibrik.net/en/solutions-products/kolxpd)
- [Renishaw WiRE Raman software](https://www.renishaw.com/en/raman-software--9450)
- [Renishaw WiRE Raman software: analysis](https://www.renishaw.com/cs/raman-software-analysis--25909)
- [HORIBA LabSpec 6 Spectroscopy Suite Software](https://www.horiba.com/pol/scientific/products/detail/action/show/Product/labspec-6-spectroscopy-suite-software-1843/)
- [OriginLab Peak Analysis](https://www.originlab.com/index.aspx?go=Products%2FOrigin%2FDataAnalysis%2FPeakAnalysis)
- [OriginLab Origin for Spectroscopy](https://www.originlab.com/index.aspx?go=Solutions%2FApplications%2FSpectroscopy)
- [lmfit documentation](https://lmfit.github.io/lmfit-py/)
- [pybaselines documentation](https://pybaselines.readthedocs.io/)
- [Rampy documentation](https://rampy.readthedocs.io/)
- [RamanSPy paper](https://pubs.acs.org/doi/10.1021/acs.analchem.4c00383)
- [KherveFitting XPS and Raman fitting software](https://github.com/KherveFitting/KherveFitting)
