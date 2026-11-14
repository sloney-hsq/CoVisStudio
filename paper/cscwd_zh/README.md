# CoVisStudio：CSCWD 中文审阅稿

当前正文讨论同一全双工协作环境中的一个问题：显式分开历史对象来源与当前修改范围，能否改善修订正确性和理解，其交互代价是什么。中文稿供作者与导师审阅；正式 CSCWD 投稿使用英文。

## 交付与编译

- `main-current.pdf`：本轮更新后的六页正文，三幅图、十一条实际引用文献。现有 `main.pdf` 被其他进程占用，保留旧版；本轮以 `main-current.pdf` 及其渲染、QA为准，未关闭用户应用。
- `main.tex`：可编辑源文，IEEEtran conference 默认10pt、双栏、letter；没有缩页边距或正文字号。
- `references.bib`、`figures/`、`figure_sources/`：参考文献、矢量图和图源。
- `notes/RERANK_REPAIR_UPDATE.md`：此次事实更新与证据索引；`DEEP_REVIEW_UPDATE.md` 保留上一阶段记录。

通常运行 `./build.ps1`；当前锁定期间以 `xelatex -jobname=main-current main.tex`、`bibtex main-current`、同一XeLaTeX命令两遍生成另名PDF。按 XeLaTeX → BibTeX → XeLaTeX 两遍编译。使用 TeX Live 的 Fandol 中文字体与 TeX Gyre Termes 西文字体；Overleaf 选择 XeLaTeX。附带 IEEEtran.cls 和 IEEEtran.bst 保留其原许可证。作者栏仍为中文审阅说明，正式提交前必须填真实作者单位；没有虚构资助、伦理批准或录用信息。

本轮已重新编译六页并逐页渲染检查。中英文必须各自检查篇幅，中文六页不保证翻译后仍为六页。会议要求的核验入口为 [CSCWD 2027 投稿页](https://cscwd2027.dailyeliteevents.com.au/submission.html)，提交前需再次核对当时要求。

## 真实证据分开报告

1. 两个早期编写案例均未完成全部目标，保留原失败。
2. 此前本地脚本浏览器流程24项机制检查通过，是同一流程的断言数，不是独立任务或用户样本。
3. 随后八次真实模型诊断四次最终状态正确，原驱动三次通过；一次目标及播放完成后关闭超时。其余有无工具承诺、参数类型拒绝和取消工具回合后的原生错误。
4. 本轮另两次复测：02-direct因 `top_n:"3"` 再次失败、保持r6；03-bound成功调用单次修订、提交r7、保留图1及当前RJ第三季度范围，最终14.8秒音频完整交付。二者各自19.890／33.750秒连接、完整源片段不足10秒，无新增合成和自动重试。
5. 本轮六张实际最终图都匹配独立原始数据SQL，但02查询仍不符合请求，不能算成功。两片ASR正确关联到最新请求；02仍有 Release→These 的识别错误。03未触发旧的迟到创建工具竞态，不能以本次成功证明该触发路径已修好。
6. 上述03续答仍发送r6旧图，保留这一失败观察。后续单次交付测试验证v7/v8图像时序及21条SQL，但末轮仅播放28.72/32.08秒，原始失败不改写。
7. 最新两次契约复核分别39.937及27.906秒，完整缓存语音、无新TTS或重试；重排与迁移均提交v7，36条快照查询含六张最终图全部匹配独立SQL，匹配JPEG逐字节发送后续答，末轮工具后11.52/8.32秒音频自然结束。模型top_n显式为十进制字符串/null，统一编译为严格领域整数；两条件及两provider共用入口。不得据两次成功单独归因某项修复。
8. 正式报告按首次实际Begin、注册名单缺失行、锁定独立意图及终末SQL评分执行。理解为四维全正确端点，错误/未知分别保留；480秒任务内仅一次60秒语音窗口，人工冻结仍待完成。

旧八次、聚焦两次、单次交付及最新两次各按版本独立报告，不合并成功率，更不作为B0/B2收益实验。人工核听、实际听见、语义一致性与参与者理解均未自动赋分。正式用户对照及显著性结果仍不存在。

## 方法与研究边界

B0与B2共享指令、工具、历史集合、精确成员解析、编译器和提交规则。当前区别是向用户提供显式、可检查并可纠正的修订支持包，不能解释成绑定算法对照。明确请求通常自动提交后显示卡片；只有未解决的选择才暂停并澄清，不是一律提交前人工确认。

两条件都使用全双工；主张不涉及语音优于文字或全双工优于轮次交互。实验计划仍为四业务家族、每位四任务、每条件两次的参与者内设计，主要检验正确性与理解，修复和时间为次要结局。30人只是目标，不是已招募人数或功效证明；未知、失败和未完成均保留。

DataTone、CLEO、VoCa 已按一手来源复核。它们提供歧义纠正、执行中协作和语音画布协调背景，本项目没有忠实复现这三套系统，不能声称实测超过它们。2026预印本保留arXiv身份。

## 私有复查索引

路径相对 `C:\CoVisStudio`：

- `traces/real-two-cases/20261113-213538/RESULTS.md`：早期两个失败。
- `traces/goal-optimization/20261113-135547-550114/report.json`：此前本地24项检查。
- `traces/real-study-20261113-224313/RESULTS.md`：旧八次及保留的原驱动状态。
- `traces/deep-review/real-two-20261113/RESULTS.md`、`independent-audit.json`：本轮两次独立审计、原始数据SQL和播放回执。
- `traces/route-real-validation/RESULTS.md`：中间单次交付失败记录。
- `traces/rerank-repair-20261113/real-two/RESULTS.md`：最新两次、独立SQL及原生JPEG审核。
- `traces/rerank-repair-20261113/paper-before/`、`zh-build.txt`、`zh-render/`：此次备份、编译和渲染。
- `traces/deep-review/browser-final/report.json`：此前本地24项检查。
- `traces/deep-review/paper-before/zh/`：更新前TeX及PDF。
- `traces/deep-review/zh-build.txt`、`zh-render/`：本轮编译及六页渲染。
- `docs/UNIFIED_RESEARCH_PROTOCOL.md`、`STUDY_PARITY_AUDIT.md`、`RESEARCH_CLAIM_REVIEW.md`：当前协议、应用等价性边界和研究主张复核。

图1和图2为示意，图3为此前本地脚本验证截图，不是假造真实模型或参与者成功画面。没有新增公开上传；数据、音频、traces与凭证不随论文自动公开。

本轮共享支持工程诊断：35.360/33.141秒，两次均完成，36项独立SQL通过；原始驱动completed及同请求续答关联经加强审核。仍保留ASR错误及原生音频因果未知，不作参与者收益或核听结论。
