# Echem Analyzer 产品与架构设计

> 目标用户：催化、电化学和燃料电池方向科研人员
> 设计基准日期：2026-05-31

## 0. 产品判断摘要

这类软件最值得切入的不是"替代所有仪器原厂软件"，而是解决原厂软件之后的高重复劳动：批量导入、统一清洗、统一计算、统一作图、统一导出、保留可追溯分析流程。

务实定位：
- 第一阶段做"电化学数据后处理工作台"，不直接控制仪器
- 先服务论文图和组会图，不急着做 LIMS 或完整 ELN
- 先把 LSV/CV/CA 和基础 EIS 处理做到稳定
- 中国市场优先做 Windows 离线桌面版
- 长期架构要把核心库独立，GUI/CLI/SaaS 调用同一套核心

## 1. 核心功能设计

### 1.1 数据导入

| 厂商/软件 | 优先支持格式 |
|---|---|
| CH Instruments / CHI | .txt, .csv, ASCII 导出 |
| BioLogic EC-Lab | .mpt, 后续 .mpr |
| Metrohm Autolab NOVA | ASCII/CSV/Excel 导出 |
| Gamry Echem Analyst | .DTA, .csv/.txt |
| 通用表格 | .csv, .tsv, .xlsx（列映射）|

### 1.2 数据处理
- 单位转换、电位换算（Ag/AgCl、Hg/HgO、SCE、RHE）
- iR 校正、窗口截取、重采样/插值、平滑（SG/移动平均/LOWESS）
- 基线校正：空白扣除、载体扣除、电容背景扣除、多段基线
- 归一化：几何面积、负载量、金属含量、BET、ECSA

### 1.3 分析功能
**LSV/ORR：** E_onset、E1/2、j_L、动力学电流 j_k、Tafel 斜率、K-L (n)、RRDE (H2O2%)
**CV：** 峰值识别、Delta Ep、积分电荷、Cdl、ECSA、稳定性保持率
**EIS：** Nyquist/Bode、Rs/Rct 初估（MVP）；等效电路拟合/DRT（进阶）
**CA/CP：** 保持率、半衰期、指数衰减拟合

### 1.4 可视化
预置模板：ORR LSV、CV ECSA、Tafel、K-L、EIS、CA 稳定性
期刊尺寸预设、彩色友好 palette、导出 TIFF/PNG/SVG/PDF

### 1.5 批量处理
文件夹导入 → 自动识别命名规则 → 设 recipe → 批量应用 → 出 results.xlsx + figures + report

## 2. 技术架构建议

**推荐路线：离线优先桌面应用 + Python 核心库 + CLI**

| 形态 | 结论 |
|---|---|
| 桌面应用 (PySide6/Qt) | MVP 首选 |
| Web app / SaaS | 第二阶段做可选云同步 |
| CLI | 作为核心引擎入口保留 |
| Jupyter 插件 | 高级用户补充 |

**科学栈：** pandas/polars, numpy, scipy, pybaselines, matplotlib, impedance.py, SQLite + Parquet

## 3. 盈利模式分析（重点）

### 推荐组合策略

**第 1 年：Freemium + Academic Pro + 小额定制 + 培训**
**第 2 年：Research Group License + 企业版 + 仪器格式定制**
**第 3 年：可选云协作 + 私有化部署 + 厂商 OEM**

### Freemium 分层

| 免费 | 付费 |
|---|---|
| 单文件导入 | 批量处理文件夹 |
| 基础单位/电位换算 | 高级 publication-ready 模板 |
| 单文件基础作图 | E1/2/Tafel/Cdl/ECSA 自动批量计算 |
| PNG/SVG/CSV 导出 | EIS 拟合、KK 检验、DRT |
| 每项目≤20 measurement | PDF/HTML 自动报告 |
| | 无限制项目和测量 |

### License 订阅定价（中国市场）

| 版本 | 建议价格 |
|---|---|
| Free | 0 元 |
| Academic Personal（学生/博后） | 199-399 元/年 |
| Academic Pro（PI/核心用户） | 999-1,999 元/席/年 |
| Research Group（5-10 席） | 3,999-9,999 元/组/年 |
| Commercial Pro（企业工程师） | 4,999-9,999 元/席/年 |
| Enterprise（私有部署） | 5-30 万元/年 |

### 定制开发 - 早期现金流来源
- 仪器格式解析器：1-5 万元/格式
- 课题组分析模板：0.5-3 万元
- 企业报告/批处理：5-20 万元
- 仪器厂商 OEM/白标：10-100 万元

### 其他模式
- **培训/咨询：** 线上课 99-499 元/人，课题组内训 3,000-20,000 元/场
- **开源+企业版：** 核心解析器 MIT 开源，GUI/批处理/高级 EIS 闭源

### 模式对比

| 模式 | 收入潜力 | 获客难度 | 适合阶段 |
|---|---|---|---|
| Freemium | 中 | 低 | 早期到长期 |
| 桌面 License | 中高 | 中 | MVP 后 |
| SaaS | 高 | 高 | 产品验证后 |
| 定制开发 | 中高 | 中 | 早期现金流 |
| 培训咨询 | 中 | 低中 | 早期获客 |
| 开源+企业版 | 中高 | 中 | 长期生态 |

## 4. 竞品分析

| 工具 | 优势 | 我们的机会 |
|---|---|---|
| EC-Lab | 控仪器强 | 做跨品牌后处理 |
| Autolab NOVA | 实时采集成熟 | 不替代 NOVA，接管后处理 |
| Gamry Echem Analyst | 生态完整 | 统一报告+批处理 |
| ZView | EIS 拟合标准 | 不正面挑战，做初筛+导出 |
| Origin/OriginPro | 科研作图标准 | 做 Origin 前置清洗和分析 |
| 自己写脚本 | 灵活免费 | GUI 降低门槛，流程可复现 |

## 5. MVP 路线图（3-4 个月）

**MVP 范围：**
- Windows 桌面版 + 本地项目文件
- 导入 CHI、BioLogic、Gamry、Autolab、通用 CSV
- LSV/ORR：电位换算、归一化、背景扣除、E1/2、Tafel
- CV：cycle 拆分、峰值、Cdl/ECSA
- CA：保持率、稳定性
- EIS：Nyquist/Bode、Rs/Rct 初估（不拟合）
- 图表导出 PNG/TIFF/SVG/PDF
- 批处理：文件夹导入→recipe→Excel 汇总
- 结果可追溯：recipe JSON + 文件 hash

**不做：** 仪器控制、云协作、ELN、自动写论文、AI 分析

## 6. 中国市场特点
- CHI/辰华国产仪器多，必须优先适配
- Origin 和 Excel 使用惯性强，不要强迫迁移
- 学生流动快，PI 愿为"组内流程统一"付费
- 对发票、合同、对公付款、离线激活有要求
- 渠道：微信群、B 站、公众号、仪器代理商

## 7. 第一年执行计划
- 0-1月：收集真实文件，明确标准流程
- 1-3月：完成数据模型、4类导入、核心分析、图表模板
- 3-4月：封闭测试
- 4-6月：发布 Windows 免费版、中文教程
- 6-12月：上线批处理/高级模板/EIS拟合、推出 Academic Pro / Research Group License
