# LATEST_HANDOFF — V0.6.3

## What changed
根据用户第二轮实机结果体验，V0.6.3 调整 Automation Result 生命周期与 Excel 交互：
1. 新 SAMPLE 默认正式结果恢复为 Avg / Min / Max；Std 仍可选，Count 继续只做内部采样元数据。
2. `Run All` 不再清空已有 Results；连续多轮测试会继续追加结果。
3. 全部 Case 完成后仍清空 Run Runtime 表并自动切换到 Results。
4. 顶部 `Export CSV` 移除。Results 页增加 `Copy Results`，一键把完整表头和所有结果按 TSV 复制到系统剪贴板，可直接粘贴 Excel。
5. Results 页增加 `Clear Results`；只有用户确认后才清空全部累计结果。

## Compatibility
- V0.6.2 已保存且显式 `statistics=[avg]` 的计划仍保持 Avg-only；只有新建/缺省 SAMPLE 使用 Avg/Min/Max 默认。
- 内部仍计算 Count/Avg/Min/Max/Std，因此 legacy CALCULATE/ASSERT 兼容路径不变。
- JLinkWorker、Polling、WAIT STABLE、Parameter Matrix、Memory/Watch/Scope 均未重构。

## Verification
- compileall: PASS
- pytest: 87 passed
- Qt clipboard/button smoke: PENDING_ENVIRONMENT (PySide6 unavailable here)
- Real J-Link automation: PENDING_HARDWARE

## First user smoke
1. 新建 SAMPLE，确认默认勾选 Avg / Min / Max，Std 不默认勾。
2. 跑 2~3 个 Case；完成后 Run 表应清空，Results 保留 Avg/Min/Max。
3. 不清 Result，再点 Run All；旧结果应保留，新结果继续追加。
4. Results → Copy Results；直接粘贴 Excel，应按列/行落表且包含表头。
5. Results → Clear Results；确认后才清空全部历史结果。

## Do not regress
不要在 `_run_all()` 恢复 `self._results.clear()`；Run Runtime 与 Results 生命周期必须分开。不要把内部 Count/current/stable_spread 再泄漏到 Results。保留 single J-Link owner、V0.5.5 Memory/Watch 与 V0.4.23 Scope 高性能路径。
