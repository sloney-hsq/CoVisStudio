# 本轮论文更新与证据边界

日期：2026-11-13。只更新中文main.tex、README及本说明；编译生成main.pdf。本轮不调用API、不读取凭证、不修改运行时。中英文由两个协作任务分别编译核对。

## 正文实际变更

- 摘要、验证、讨论与结论增加本轮两次真实复测，独立于旧八次、早期两例及此前本地检查。不合并分母，不报告用户效果。
- 02-direct：19.890秒，rerank参数top_n仍为字符串，失败后停止，r6未改；源语音Release fixed categories被识别成These fixed categories。03-bound：33.750秒，实际调用revise_analysis，内部复用preview/apply编译，一次r7提交，图1完整不变，图2/3保留RJ、第三季度和指标，最终355200/355200个24kHz样本完整交付（14.8秒）。
- 两次完整源片段均不足10秒，使用已有音频，无新TTS、截断或自动重试；真实晚到ASR两片均合并至最新请求。旧迟到response.created工具回合竞态本轮未触发，不能宣称该特定路径已真实验收。
- 六张实际最终图均通过现有独立oracle的原始CSV SQL；02旧source数值正确但请求未完成，03source和数值均满足请求。软件播放完成不批准人工听见、核听或理解。
- 03的r7提交后仍发送r6图像，r7仅本地capture；随后运行时修复与本地检查不追溯改写这次真实记录，也没有付费复测。最新本地浏览器报告位于traces/deep-review/browser-final/report.json（24项通过）；正文不靠新增单测数量扩张研究结果。
- 方法明确B0/B2共享成员绑定与编译器；处理变量是可见、可纠正的支持包，不是绑定算法。明确请求通常先提交后显示卡，未解决的选择才澄清。应用层等价审计通过不等于冻结原生历史。
- DataTone补充部分约束维持纠正；CLEO表述改为核实的用户动作跟踪与选择性计划调整，删除不必要的未核实唤名语音细节；VoCa表述为协调画布和探索性部署。保留十一条引用、三图、双条件研究和既有统计计划。

## 证据索引

所有路径相对C:/CoVisStudio：

- traces/deep-review/real-two-20261113/report原件位于各试次目录；RESULTS.md、independent-audit.json、audit_new_trials.py可离线复查。
- traces/real-study-20261113-224313/为旧八次，原始3通过/5失败不改写。
- traces/deep-review/paper-before/zh/保留修改前main.tex/main.pdf。
- traces/deep-review/zh-build.txt为完整编译；zh-render/page-1.png至page-6.png为逐页检查。

## 版式检查

build.ps1完整执行成功；pdfinfo确认六页、letter 612×792pt；IEEEtran conference默认10pt与双栏未改变。正文三幅图、十一条被引用参考文献。日志无Overfull；少量Underfull来自窄表和英文书目，未见内容裁切、重叠或缺字。已渲染并目视全部六页，末页两栏在相近高度结束。没有缩字号、负间距或缩边距凑页数。

正式投稿仍需真实作者与单位，参与者数据尚不存在，理解、核听和方法收益保持待验证。所有模型服务的最终停止与全局收尾由主任务核验；本中文编译任务不擅自停止其他正在工作的进程。
