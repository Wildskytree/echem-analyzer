# Komiya et al. 2026: CoNiFe-LDH 启停循环老化表征整理

文献：Hiroki Komiya, Keisuke Obata, Tengisbold Gankhuyag, Kazuhiro Takanabe, "Redox-Durable Co-Ni-Fe Layered Double Hydroxide Anode for Stable Oxygen Evolution under Industrially Relevant Cycling", ACS Applied Materials & Interfaces 2026, 18, 6, 9829-9840. DOI: https://doi.org/10.1021/acsami.5c22446

说明：ACS 全文和 SI PDF 目前被访问控制拦截，工作区中的 `paper_komiya2026.pdf` 也只是 Cloudflare 验证页，不是论文 PDF。以下内容基于 ACS/PubMed/Crossref/Semantic Scholar/OpenAlex 可访问元数据、ACS 页面暴露的摘要和 SI 目录，以及对 NiFe/CoFe/CoNiFe-LDH OER 老化机理的合理归纳。不能核验的具体数值和图号没有写死。

## 一句话结论

这篇文章不是只做常规恒电流稳定性，而是专门把 LDH 阳极放在反复 on-off/start-stop 条件下，比较 NiFe-LDH、CoFe-LDH 和 CoNiFe-LDH 的红氧循环耐受性。核心结论是：NiFe-LDH 初始 OER 活性高，但启停循环比恒定 OER 更容易让它失活；CoFe-LDH 在间歇运行下最差，主要和结构剧烈变化及 Fe 溶出有关；CoNiFe-LDH 最耐久，因为 Co/Ni 共存带来更稳定的中间结构框架和更稳健的 Ni redox 行为。

## 可确认的摘要要点

1. 研究对象：精细合成的 NiFe-LDH、CoFe-LDH、CoNiFe-LDH。
2. 工况关注点：工业相关 OER，特别是可再生电力耦合时的反复启动/停机循环。
3. 主要方法：operando Raman、operando X-ray absorption spectroscopy (XAS) 和电化学分析。
4. NiFe-LDH：在反复 on-off 循环下比恒定 OER 操作更严重衰退，归因于催化剂导电性下降、Ni 氧化受抑和非晶化。
5. CoFe-LDH：间歇运行中 OER 性能衰退最严重，归因于较大的结构变化和显著 Fe dissolution。
6. CoNiFe-LDH：显示最好耐久性，原因是结构稳定性和 redox robustness 更高；Co 使 Ni 更容易氧化，并帮助维持 Ni 的 redox ability。
7. 工业相关验证：CoNiFe-LDH 在 600 mA cm^-2、60 degC 条件下表现出值得注意的 on-off durability。

## 启停循环测试协议

可确认的是，文章比较了两类耐久性测试：

1. constant OER operation：持续 OER 条件下运行，用作常规耐久性参照。
2. repeated on-off cycling / intermittent operation：反复在 OER 工作状态和停止/低负载状态之间切换，用来模拟电解槽随可再生电力波动发生的启动和停机。

从摘要和 SI 目录可以确认，他们记录了 Co_xNi_100-xFe-LDH/carbon paper 在 durability testing 中的 current density 和 potential profiles，并比较了循环前后以及 on-off 过程中的 CV。可访问资料没有给出每个 on/off 段的具体持续时间、下限电位或休止方式。因此更稳妥的表述是：该协议本质上是强制催化剂在还原态 hydroxide 和 OER 阳极氧化态 oxyhydroxide 之间反复红氧转换，而不是单纯长时间保持阳极电位。

这个设计对 Ni/Co/Fe-LDH 很关键：每次停机或降电位会让高价 Ni/Co oxyhydroxide 部分还原；每次启动又要重新氧化生成活性相。反复体相/表面 redox、层间离子/水迁移、局部溶解-再沉积和导电网络改变共同构成老化压力。

## ACS 页面可确认的 SI 图表/内容条目

ACS 页面列出的 Supporting Information 内容包括以下项目；这些基本就是该文分析老化机制时用到的图表类型：

| SI 条目 | 对启停老化分析的用途 |
|---|---|
| Co_xNi_100-xFe-LDH molar ratio | 确认 Co/Ni/Fe 组成，建立组成-耐久性关系 |
| XRD patterns of various LDH | 确认初始 LDH 晶相/层状结构，辅助判断结构稳定性 |
| FT-IR spectrum | 确认 LDH 中 OH、层间阴离子/水等结构特征 |
| Tafel slope analysis | 比较 OER 动力学是否因组成或老化改变 |
| Current density and potential profiles during durability testing | 直接评估恒定 OER 与 on-off cycling 下的电位漂移/失活 |
| CV profiles before/after constant OER and during on-off cycling | 跟踪 Ni/Co redox 峰、氧化还原可逆性和活性相生成能力 |
| ICP analysis | 定量金属溶出，尤其用于证明 CoFe-LDH 的 Fe dissolution |
| Reduction charge quantification | 用还原电荷量化可逆高价物种/活性 redox 库的保留程度 |
| Operando Raman spectra of various LDH | 原位跟踪 hydroxide 到 oxyhydroxide、结构变化和非晶化 |
| Ex-situ XANES spectra | 补充比较循环后金属价态变化 |
| Ex-situ XPS | 分析表面价态、表面组成和循环后元素/化学态变化 |
| Bode diagrams | 来自 EIS，用于判断导电性/电荷传输是否恶化 |
| Line scan of EDX | 看循环后元素分布、局部浸出或结构/组成不均 |
| Cation additive study | 判断溶出/再沉积或外源金属离子对稳定性的影响 |
| CV at elevated temperature during on-off cycling | 在更接近工业温度下考察 redox 循环稳定性 |
| pH-dependent stability assessment | 分析碱度/局部质子传输对稳定性的影响 |
| Loading amount dependence | 排除或评估催化层厚度、传质、电阻带来的表观失活 |
| Potential window-dependent stability | 说明 redox 循环电位窗口越深/越宽，结构和 redox 损伤可能越强 |

## 表征手段及发现

| 方法 | 他们看什么 | 主要发现/机理指向 |
|---|---|---|
| Chronopotentiometry/current-potential durability profiles | on-off 循环和 constant OER 下的电位随时间变化 | NiFe-LDH 在 on-off 条件下比恒定 OER 更严重衰退；CoNiFe-LDH 电位漂移最小或保持更稳定；CoFe-LDH 在间歇运行下衰退最明显 |
| CV | Ni/Co redox 峰、OER 前氧化过程、循环前后电荷 | NiFe-LDH 经启停后 Ni 氧化被抑制，说明可参与 OER 活化的 Ni redox 库被削弱；CoNiFe-LDH 能保持更好的 redox response；Co 的存在让 Ni 更容易氧化 |
| Reduction charge quantification | 对高价 oxyhydroxide 还原电荷积分 | 还原电荷下降可对应可逆高价 Ni/Co 物种减少；NiFe-LDH 启停后 redox charge 损失更大，CoNiFe-LDH 保留更好 |
| Operando Raman | 工作电位下 M-O 振动、NiOOH/CoOOH 相关特征、晶态到非晶态变化 | NiFe-LDH 在 redox cycling 后出现非晶化/结构劣化；CoFe-LDH 出现较大结构变化；CoNiFe-LDH 的 Raman 演变更可逆，说明结构框架更稳定 |
| Operando XAS | Ni/Co/Fe K-edge 价态和局域配位随电位变化 | NiFe-LDH 的 Ni 氧化受到抑制；CoNiFe-LDH 中 Co-Ni 电子相互作用有利于 Ni 氧化，并维持 redox ability；CoNiFe-LDH 的局域结构变化更温和 |
| Ex-situ XANES | 循环后平均价态/氧化态对比 | 支持 operando XAS 的价态结论：启停循环后 NiFe 的可氧化 Ni 库下降，而 CoNiFe 更能维持氧化还原状态 |
| Ex-situ XPS | 表面元素比例、Ni/Co/Fe 价态、OH/oxide 组分 | 用来确认表面化学态和组成变化；可支持 Fe 浸出、Ni 氧化受抑、Co/Ni 共存改变电子结构等判断 |
| ICP | 电解液或样品中溶出的金属量 | CoFe-LDH 的显著 Fe dissolution 是其间歇运行失活的重要证据；CoNiFe-LDH 应表现出更低的破坏性金属流失 |
| EIS/Bode diagrams | 电荷传输、电导/阻抗变化 | NiFe-LDH 启停后导电性下降，是性能衰退原因之一；CoNiFe-LDH 更能维持电荷传输 |
| XRD | 初始 LDH 晶相、层状结构完整性 | 证明各 LDH 初始结构；结合 Raman/XAS 可判断 CoNiFe 具有介于 NiFe 与 CoFe 之间、更稳定的结构框架 |
| FT-IR | OH、层间阴离子/水等 LDH 化学结构 | 主要是初始结构确认，不是老化机制的核心证据 |
| EDX line scan / 形貌元素分析 | 元素空间分布、循环后局部流失或重分布 | 用于支持 Fe 浸出、组成不均或 CoNiFe 组成保持更均匀的判断 |
| pH/loading/potential-window dependence | 老化对碱度、催化层厚度、redox 深度的敏感性 | 说明启停失活不是单一活性问题，而与层间/催化层传输、电位窗口诱发的 redox strain 和溶解过程耦合 |

## NiFe-LDH、CoFe-LDH、CoNiFe-LDH 对比

| 材料 | 初始/常规表现 | 启停循环下表现 | 主要老化证据 | 机制判断 |
|---|---|---|---|---|
| NiFe-LDH | OER 活性最高或很高 | on-off 下比 constant OER 严重衰退 | CV/redox charge 显示 Ni 氧化受抑；EIS 显示导电性下降；Raman 显示非晶化 | 高活性 NiFe 相在反复 redox 中结构和导电网络受损，导致活性相难以重新充分氧化 |
| CoFe-LDH | 活性可观但不如优化 NiFe/CoNiFe | 间歇运行中衰退最严重 | ICP 显示 Fe dissolution；Raman/XAS 指向结构变化大 | CoFe 框架在启停 redox 中结构重排/Fe 流失更剧烈，活性位和导电/配位环境同时恶化 |
| CoNiFe-LDH | 活性和稳定性折中更好 | on-off durability 最好，并在 600 mA cm^-2、60 degC 下仍表现稳定 | CV/redox charge 保持较好；operando XAS/Raman 显示 redox 和结构更稳；EIS 不易恶化 | Co/Ni 共存形成更稳定的中间结构框架，Co 改变电子相互作用，使 Ni 更容易氧化并维持可逆 redox |

## 老化机制链条

1. 启动阶段：电位升高，Ni/Co 从 hydroxide 态氧化为 oxyhydroxide 活性相。
2. 停机阶段：电位降低或电流关闭，高价 oxyhydroxide 部分还原。
3. 反复 redox：晶格呼吸、层间离子迁移、水/OH- 重排和局部 pH 变化反复发生。
4. NiFe-LDH 的问题：redox 循环后导电性下降，Ni 不再容易被氧化，Raman 显示非晶化，最终 OER 启动/运行电位升高。
5. CoFe-LDH 的问题：结构变化更大，Fe 明显溶出，活性 Fe 位点和框架稳定性同时损失。
6. CoNiFe-LDH 的优势：Co/Ni/Fe 三元框架缓冲 redox-induced structural strain；Co 调节 Ni 的氧化行为，使 Ni redox 更容易、更可逆，因而抗启停老化。

## 这篇文章的方法学价值

这篇文献的重点不是证明 CoNiFe-LDH 活性最高，而是证明“恒电流稳定”不能代表“启停稳定”。对 NiFe-LDH 这类 redox-active OER 催化剂，真正接近可再生电力场景的老化分析至少要同时看：

1. on-off 电化学协议，而不只是恒电流/恒电位；
2. CV/redox charge，判断活性相还能否反复生成；
3. operando Raman/XAS，直接看结构和价态是否可逆；
4. ICP/XPS/EDX，判断金属是否溶出或表面组成是否漂移；
5. EIS/Bode，判断性能下降是否来自导电/电荷传输恶化；
6. 高电流、高温、pH、loading、potential window 等边界条件。

## 参考来源

- ACS DOI 页面和 SI 目录：https://pubs.acs.org/doi/10.1021/acsami.5c22446
- PubMed 条目：https://pubmed.ncbi.nlm.nih.gov/41641666/
- Crossref DOI 元数据：https://api.crossref.org/works/10.1021/acsami.5c22446
- Semantic Scholar 元数据：https://api.semanticscholar.org/graph/v1/paper/DOI:10.1021/acsami.5c22446
- OpenAlex 元数据：https://api.openalex.org/works/https://doi.org/10.1021/acsami.5c22446
