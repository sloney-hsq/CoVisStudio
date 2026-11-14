# 相关工作核验记录

核验日期：2026-11-13。只写入已在一手摘要页、作者/机构全文或官方文档核对的作者和题名。arXiv 均按预印本引用，不补造录用会议。网页检索未调用模型服务或付费 API。本表是定位和论证边界记录，不是系统综述。

| 键 | 一手来源与可获得性 | 可引用内容及比较边界 |
|---|---|---|
| datatone | [作者 PDF](https://zcliu.cs.umd.edu/datatone/DataTone-UIST15.pdf)，全文；UIST 2015，首页 DOI 10.1145/2807442.2807478 | 摘要与系统章节：暴露歧义决策，以交互控件修正解释，并将修正作为后续查询约束。不能把“保留有效条件”或“交互纠歧”笼统当成本项目首创。 |
| eviza | [Tableau Research PDF](https://www.tableau.com/sites/default/files/2023-01/uist4832-setlurA_0.pdf)，13 页全文；UIST 2016，首页 DOI | 摘要、§1：围绕已有可视化进行连续查询对话、过滤和选择，支持语用及多模态输入。直接相关的是上下文中的指代表达，不是仅从空白生成图表。 |
| grounding | [Clark 作者主页所存全文](https://web.stanford.edu/~clark/1990s/Clark%2C%20H.H.%20_%20Brennan%2C%20S.E.%20_Grounding%20in%20communication_%201991.pdf)，可读全文；1991 | 开篇及 Grounding in Conversation：共同基础需在交互中更新；表达被发出不代表对方已理解。用于解释共同参照，不作为系统有效性的实验证据。 |
| cleo | [arXiv v5](https://arxiv.org/abs/2603.02050v5)、[全文 §4.1.2](https://arxiv.org/html/2603.02050v5#S4.SS1.SSS2)；v1 2026-03-02，v5 2026-09-20；全文已读相关节 | 用户可在执行中追加语音，代理下一轮更新计划；检测并区分用户与代理画布修改。与本项目并发修订和保留用户工作高度重叠，不能宣称首次支持执行中干预。其研究对象为设计共创，本文拟具体研究历史分析对象复用时的当前条件继承。 |
| voca | [arXiv v1](https://arxiv.org/abs/2610.04706v1)、[HTML 全文](https://arxiv.org/html/2610.04706v1)；2026-10-03；全文相关节可读 | §4 协调语音与画布动作；§7.3.4 区分追加信息与修改已有内容；§8.1 明确当前修订主要用新增和注释，部署研究不支持因果比较。与“语音+共享画布”高度重叠，但不能据此说其验证了历史品类/当前区域日期的分离执行。 |
| commsketch | [arXiv v1](https://arxiv.org/abs/2609.37813v1)、[HTML 全文](https://arxiv.org/html/2609.37813v1)；2026-09-29；全文可读 | §3.3 并行捕获草图和语音，§4.2 分析共享设计前提和感知对齐。不要把两模态同时输入等同于代理输出期间持续接收分析修订。HTML 残留 ACM 2018/XXXX 模板字段，不用作正式出版信息。 |
| charteditbench | [arXiv v1](https://arxiv.org/abs/2602.15758v1)、[HTML 全文](https://arxiv.org/html/2602.15758v1)；2026-02-17；全文可读 | §3.1、§3.4 多轮代码图表修改及执行/视觉/逻辑评估，§5 多轮累积误差。不能把“多轮图表编辑”或“不能只看模型话术”单独作为创新；本文应强调运行中修订的证据时间边界及引用与编辑作用域。 |
| speechvis | [会议官方预印本](https://ecmlpkdd-storage.s3.eu-central-1.amazonaws.com/preprints/2025/research/preprint_ecml_pkdd_2025_research_988.pdf)，18 页全文；[会议书目](https://mlanthology.org/ecmlpkdd/2025/zhang2025ecmlpkdd-speechtovisualization/)，ECML PKDD 2025、437–453、DOI 已核对 | 摘要与方法：语音问题到可视化的端到端任务和建模。适合作为语音驱动生成的基线背景，不能替代持续协作、历史证据引用与修订执行研究。 |
| fdbv3 | [arXiv v1](https://arxiv.org/abs/2604.04847v1)、[HTML 全文](https://arxiv.org/html/2604.04847v1)；2026-04-06；全文可读，work in progress | §3、§4 真实人声不流利现象和链式工具调用，准确率/时延/轮次指标；§6.3 自我修正仍困难。本文不应宣称首次结合全双工和工具调用；独特测量需求在于真实图表提交、呈现与语音交付分离。 |
| duplexagent | [arXiv v1](https://arxiv.org/abs/2610.11299v1)、[HTML 全文](https://arxiv.org/html/2610.11299v1)；2026-10-08；全文可读 | §3.1：任务标识、版本和替换状态决定迟到结果是否可交付；图3为 Snake→Tetris，§3.2 为定时交互模拟。直接覆盖旧任务失效与交付控制，不能把 epoch/撤权本身视为论文独创。本文不实现其递归 harness 优化，也不应暗示拥有相同系统级 benchmark。 |
| olist | [数据发布者 Kaggle 页](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)，页面可打开但检索器无可读正文 | 数据题名与发布者身份已定位；没有从该页核验初始发布日期、版本或精确样本数，Bib 不补写年份。论文实际数据口径须另引本项目数据实现和离线查询证据，勿用公共页代替本地口径验证。 |
| qwenrealtime | [官方客户端事件文档](https://www.alibabacloud.com/help/en/model-studio/client-events)，正文可读，动态文档 | `conversation.item.create` 返回 function_call_output 后由 `response.create` 续答；另有 response.cancel 与图像缓冲事件。仅支持传输接口描述，文档存在不证明本项目识别、取消或分析成功。 |

## 可用于正文的比较表述

自然语言可视分析已有通过控件显式纠正歧义并维持约束的方法（DataTone），以及围绕已有图表连续提问与修订查询的交互（Eviza）。它们说明分析上下文及解释修正并非新的问题。本文聚焦一个更窄的执行问题：用户引用历史图表中的对象集合时，哪些历史内容作为证据被继承，哪些当前区域、日期和指标仍然有效。

并发共创也已有直接相关先例。CLEO 在代理执行期间接纳用户操作及后续语音，并选择性更新计划；VoCa 协调语音、视觉对象和注意引导；CommSketch 研究同步言语如何表达草图中的设计意图。因此，“可以打断”或“语音与画布共存”不足以构成贡献。本文提出把历史证据来源、当前编辑目标和保留条件显式分离，并将其落实到同一执行编译器及可复查提交记录；其效益仍须在共享全双工能力的 B0/B2 比较中验证。

ChartEditBench 已研究多轮图表修改及执行和视觉评估；Full-Duplex-Bench-v3 已评估带不流利表达的语音工具使用；DuplexAgent-RSI 已用任务版本与状态阻止过时结果交付。本文据此将图表的成功提交、实际渲染和输出样本进度分别记录，关注分析修订后的引用错误、有效条件丢失和修复成本。该定位是设计与评估计划，不是已获得的人体实验结论。

## 写作禁区及本轮限制

- B0 和 B2 都是 full-duplex；不能写成半双工/全双工效果比较，也不能把历史 unbound_preview 当作本轮主研究第三条件。
- 现有技术日志不等于共同理解、用户阅读、实际听到或用户意图评分；工作集证据包不等于冻结 provider 的原生内部历史。
- 本轮未开展正式参与者实验，不能写“显著降低错误/修复成本”。主张宜为明确的问题定义、机制、实现和可复查验证边界。
- 已获得上述一手摘要和相关全文，不存在以检索失败为由补造作者或会议的条目。仅 Olist 正文不可读，故公开页的精确样本数/日期未作核验。VoCa arXiv 摘要将 DOI 标为 pending registration，Bib 仅保留可访问 arXiv URL。

