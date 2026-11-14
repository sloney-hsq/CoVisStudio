# 研究主张复核：把连续修订做成可检验的问题

审查日期：2026-11-13。本文件只复核研究论证、一手文献和现有实现，不改变运行时、不调用付费 API、不新增实验条件。本轮读取 `UNIFIED_RESEARCH_PROTOCOL.md`、`STUDY_PARITY_AUDIT.md`、旧版 `RESEARCH_PLAN.md`，并核对 `backend/app.py`、`backend/revisions.py` 与前端修订卡入口。当前研究设计以 [统一协议](UNIFIED_RESEARCH_PROTOCOL.md) 为准；旧方案中的三组消融和混合模型不能直接拼接为当前方案。

## 建议采用的完整论证

研究对象是**人在持续分析中，对已有证据和当前图表提出局部修订的过程**。例如，用户先在 SP 发现一组值得关注的品类，再切换到 MG 检查服务情况，随后要求“沿用那组品类，但仍计算 MG，只改两张服务图”。这里同时存在三个不同对象：成员来自哪次证据、本次作用于哪些当前图表、哪些计算条件仍有效。将历史图整体恢复、沿用当前动态排名、改错目标图，都可能产生数值自洽却不符合请求的结果。

动机应落在这个具体困难上：语音讲解、公开图表与在途计算并不总在同一进度；用户会边看边明确问题，并在完成前更改分析方向。停掉声音只能处理输出竞争，无法决定“那组”指谁，也不能证明新查询保留了正确条件。因此需要把对象来源、目标范围和条件变化变成用户能检查并继续纠正的共同参照。

主问题保持为：**在相同全双工分析环境中，显式呈现证据来源、当前修订目标以及保留／解除条件，能否改善修订正确性和用户对结果的理解，代价是什么？** 全双工提供执行中介入的环境；本研究不估计它相对文字或轮流交互的独立优势。

方法可写成一条清晰链条：从实际保存的图表或集合确定成员来源，以当前图表为计算基础，仅修改明确字段，经私有候选和版本／权限检查发布真实 Olist 结果，再把来源、目标及条件差异呈现为可纠正的修订记录。`use_evidence` 复用品类身份并清除动态排名；`keep_current` 保留当前选择规则，动态规则仍可能重新排名；`rerank` 明确解除固定集合。模型仍负责理解用户并选择证据；编译器不保证这个选择正确。

## 当前实现真正支持什么对照

两主条件共享相同工具、历史、保存集合、候选解析、提示和成员绑定编译器。`prepare_revision()` 对 direct 与 bound_revision 都执行真实成员绑定；`revise_analysis` 对明确请求直接计算并提交。前端 `revisionAvailable` 对 direct 隐藏主要修订入口和卡片，对 bound 显示来源、目标、前后条件、保留字段及结果成员。`needs_confirmation` 才阻止自动应用并要求解决未明确选择。

因此当前可估计的是**在共享可靠执行能力上，提供显式、可检查和可纠正的修订支持这一整体包的效果**。不能将 B0 描述成不会绑定成员，不能把组间差异归因为新的绑定算法，也不能宣称分离了卡片、解释结构或确认步骤各自的效果。直接执行路径的卡片通常在提交后可见；“每次提交前都让用户核验”与代码不符。

B0 仍可从真实回执和 Journey 查看变更；两组内部回执都可能含修订结构。这不会自动使对照无效，但必须冻结用户实际可见的信息差异。卡片生成、可见、打开、成功确认分别记录；自动提交后的卡片主要支持理解与后续纠正，不应算作提交前预防错误的证据。两组共享模型输入时，不能直接将第一条用户反馈之前的模型选错率差异解释成卡片改善了模型推理。

## 一手工作核验及准确定位

以下三个原始来源本轮均成功读取；没有以二手摘要代替全文，也没有失败获取后补写能力。检索只覆盖这三项，不能据此宣称覆盖全领域或“首次”。

| 原始工作 | 本轮核实的重叠 | 对本项目的直接约束 |
| --- | --- | --- |
| [DataTone，UIST 2015，作者公开 PDF](https://www.zcliu.cs.umd.edu/datatone/DataTone-UIST15.pdf) | 混合主动的歧义管理、可交互纠正控件，以及用部分约束保留跨查询纠正。见摘要、贡献及界面说明。 | “让用户纠正自然语言解释”“保持已明确约束”不能作为新发明。增量须具体到跨版本对象来源与当前计算范围的区分及其实证效果。 |
| [CLEO：When to Hand Off, When to Work Together，arXiv 全文](https://arxiv.org/html/2603.02050) | 在共享 Figma 工作区观察执行中介入；第二原型跟踪用户动作并选择性修改计划，两次设计探针研究分析协作行为。见摘要与第 3–5 节。 | 并发协作和介入在途工作已有直接先例。本文应研究数据分析中特定的成员／范围语义和后果；不能把 CLEO 称为对话式数据分析基线或已被本系统超越。 |
| [VoCa：Designing Speech–Canvas Interaction，arXiv 全文](https://arxiv.org/html/2610.04706) | 协调语音与画布创建、注释和注意引导；18 人五天探索性部署，讨论内容修订和协调困难。原文第 8 节明确部署不隔离单项设计效果。 | “语音＋画布＋多轮引用”不足以支撑新颖性。可检验的增量是查询语义明确的局部修订与同环境强基线对照；不要把其部署结果解释为因果优势。 |

这三篇提供继承关系和问题背景，不构成本项目的实验参赛系统。B0 是本项目内的现代强基线，结果只能写成相对 B0 的效果，不能写成优于 DataTone、CLEO 或 VoCa。上述差异是研究定位判断，不是已证明的独占能力。

## 最可能使论文失效的问题与具体处理

1. **处理变量写错。** 旧方案仍把 bound 的绑定能力列为区别，当前代码已共享。论文方法图、条件表及讨论应统一为现有支持包；保留共享编译器作为公平执行基础。不要为了恢复旧故事而削弱 B0。
2. **缺少独立意图真值。** 最终图正确、SQL 正确或模型复述流畅，都不能证明用户原本指这组成员。先由两位编码者根据用户原话、明确选择与当时证据标注来源、成员、目标、改变及保留／解除条件，保留无法判断；之后才按该意图运行独立 SQL。编码者不能从模型卡片或最终图反推意图。
3. **自然任务可能几乎不需要播放上下文。** “第一版 SP 的集合”凭显式标签即可解析，不能证明利用了已播放语义。保留全部分配任务；对确实依赖已播放内容的指代另作描述性人工分析。若自然过程很少出现，收窄为跨版本修订支持，不能筛出少数成功打断后宣称全双工特有价值。
4. **执行可靠性可能淹没机制效果。** 旧八次作者诊断同时有无工具却声称完成、字符串 `top_n` 和原生续接失败；这些是不同故障。最新授权实测由主任务另行记录，本文件不预判结果。正式收集必须让两组共享相同可靠版本和失败规则；保留失败，不用“实际查询数值正确”替代请求完成，也不靠重试取最好一次。
5. **曝光、理解和代价不能互相替代。** 卡片可见不代表阅读，四项回答填写齐全不代表理解正确，Undo 次数不等于修复成本。理解按同一问题和冻结人工量表评分；修复须有被纠正的问题及对应互动证据，区别正常探索和主动改目标。多一次点击既可能是负担，也可能避免后续修复，应连同最终结果报告。
6. **任务和语音预算尚未闭合。** 480 秒任务与 60 秒开发语音上限是两个时钟。两组应冻结相同、在上限内可完成的语音窗口和指导，不能将超时／未完成者排除后比较成功者时长。30 个分配槽是目标规模，不是功效保证。

原生 provider 历史可以采用两组相同的保留策略；这本身并不要求新增隔离框架。现有归档不能证明历史已按实际播放位置冻结。正式材料应如实声明共同保留策略、实际送入内容和不可控制边界，避免把应用证据包命名成完整模型上下文冻结。已有本地 parity 证明指定输入下的应用一致性，未证明自然语音的模型选择或用户体验相等。

## 沿用现有 B0/B2 设计与统计

仅采用统一协议的两个参与者条件：B0 强直接编辑基线、B2 显式修订支持；共享全双工、模型、工具、历史、集合、渲染、取消和预算。沿用四个业务家族及匹配版本、每位四试次、每条件两次、平衡家族／版本／顺序的参与者内分配。历史 unbound_preview 不进入新的参与者条件；不增加模态、延迟、候选数或反馈策略因素。不强迫参与者制造打断或说特定指代。

两项主要结局为修订正确性与理解；以参与者层面的配对差异为主，结合平衡分配处理家族、版本和顺序，报告效应量及按参与者聚类的不确定区间。若两项均为验证性检验，联合使用 Holm 校正。修复与时间为次要结局，保留未完成和限时情况，不只统计成功任务时长。重复请求和同一人的四任务不当作独立参与者。

所有分配任务进入主要分析，包括未重叠、失败、未完成与意图未知。以分配的尝试为主要记录，重做另存并注明原因；未知不默认为失败也不悄悄删除，同时给出已知成功和未知数量，以及未知全失败／全成功的成功率上下界。冻结评分量表、实际语音窗口、有意义效果与精度依据后再收集。旧 RESEARCH_PLAN 的“正确性与修复次数为两主要结局＋混合模型”是历史设计，不能作为看到结果后的替代显著性路线。

## 可以交付的贡献与结论措辞

当前可辩护的是：一个把历史成员来源与当前计算条件分开执行、并支持检查与纠正的可运行分析原型；一套区分意图符合、数据计算、公开提交、实际显示和语音交付的可复查验证方法；已经保留的真实作者诊断揭示的具体失效。后两者仍需用实际记录限定范围，测试数量不等于研究贡献。

尚未证明：支持包降低错误、改善理解或减少修复；用户因持续语音形成了更好的分析问题；播放位置信息对引用必不可少；系统优于上述相关工作或适用于任意数据集。

论文可用的核心贡献句是：“我们设计一种在持续语音分析中显式区分证据来源与当前修订范围的协作支持，并在共享执行能力的强基线下检验其对修订正确性、理解及交互代价的影响。”实验完成前保留“检验”，不提前写“提升”。若只改善理解，就报告理解收益；若正确性提升但耗时增加，就报告权衡；若区间过宽，就说明证据不足。这个论证不需要新增模型、重试机制或实验因素，需要的是对当前机制和真实使用后果给出一致证据。


## Terminal intent and repair analysis clarification

The fixed primary outcomes are final-intent consistency and interface-assisted
interpretation (final revision correctness and understanding). High pilot accuracy
must not trigger replacement of either primary after inspecting outcomes.

The human terminal lock includes ALL still-active per-view requirements, including
earlier unfulfilled requests. A later scoped goal change supersedes only the affected
requirements; superseded goals are not required at task end, and earlier legal commits
remain legitimate. `intent.view_overrides` maps a target view ID to optional
`source_patch`, `members`, `retained_fields`, and `released_fields` overrides using the
existing coding fields. Thus view 2 may release fixed members for a revenue ranking
while view 3 retains a fixed cohort. Annotations and SQL oracles are private and never
enter model input or public tool schemas. Missing or unresolved intent remains unknown.

Episode order uses original onset event indices, not annotation creation time. A later
annotated analytical episode, including unknown intent, blocks an older terminal
selection. Adding a newer episode makes an existing older selection unknown until
reviewed. Coders must inspect coverage of all participant analytical changes before
locking the terminal intent; this ordering check does not infer unannotated goals,
classify ASR text, or certify human coverage. Existing earlier episode scores remain
historical local assessments, not simultaneous terminal goals.

Manual coding distinguishes repair, deliberate goal change and exploration. Report
the repair funnel with explicit denominators: all assigned tasks; human-confirmed
initial errors; correction attempts; verified successful corrections. Retain unknowns
at each stage. These post-treatment subsets are descriptive, not causal comparisons
among error cases, card users or successful repairs. All assignments remain primary.
A card cannot influence an action before actual exposure and opportunity to use it;
this is not blanket first-commit parity after earlier support in a multi-step task.
