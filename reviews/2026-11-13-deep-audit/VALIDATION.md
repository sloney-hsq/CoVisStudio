# 本轮审查验证

- 范围：只读源码和研究文档审查；新增本目录报告、测试输出及隔离的构建产物。
- 后端：`.venv/Scripts/python.exe -m pytest -q`，283 passed，221.28 秒。一个 FastAPI/TestClient 的依赖弃用警告。
- 前端：40 tests passed。完整输出见 `frontend-tests.txt`。
- 前端生产构建：成功，输出在本审查目录的 `frontend-build/`，未覆盖运行中的应用 dist。构建提示 ECharts 大包，未将其当作功能故障。
- 本轮没有调用真实模型、TTS 或收费 API，没有启动或重启应用服务。
- 上述测试不能代替当前真实模型验收、人工核听或用户实验。个别子代理的小型离线复现另见对应报告。
- 源码基线：`source-hashes-before.csv`。项目未初始化 Git，不能以 git status 证明修改隔离。

## 工作区并行修改后的复核

140 个受审文件中，15 个在审查期间发生变化（详见 `source-hash-check.csv`）；本审查未编辑应用源码。已保留这些并行修改，并将当前 140 个文件复制到 `source-snapshot/`，不含凭证或数据集。

- 当前后端重新执行：**298 passed**，229.88 秒，原依赖弃用警告仍在。见 `backend-tests-current.txt`。
- 当前前端重新执行：**40 passed**。见 `frontend-tests-current.txt`。
- 当前生产构建：成功，隔离目录 `frontend-build-current/`，见 `frontend-build-current.txt`。
- 原始283项测试记录仍保留，不替换、不冒充当前版本。
- 主审在当前版本再次运行 ASR 顺序复现，见 `asr-order-reproduction-current.json`；结果仍为残句起答1次/不起答0次。
- 两次测试进程均已正常退出；没有启动或终止用户应用服务，没有连接真实模型。
- 收尾再次比较140个受审文件与本审查快照：0个变化，见 `source-hash-final.csv`。50份Axx报告均存在并已列入索引。
- 工作区并行工作新增的两次真实调用另有档案。本审查只读核对其一成一败、19.890/33.750秒及原始边界，没有发起这些调用，也未合并改写旧八次成绩。
