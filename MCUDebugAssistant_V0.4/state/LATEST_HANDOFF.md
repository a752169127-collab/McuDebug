# LATEST_HANDOFF

## 当前版本
V0.4.23 — High Performance Clean（基于 V0.4.21）。

## 本轮完成
- 保留 V0.4.21 已完成的 watchdog / event-loop / debugger / stage profiling 清理。
- Scope Presentation 从 persistent 2~8 ms polling 改为 single-shot PreciseTimer + absolute deadline。
- missed frame 直接 skip，不 catch-up burst。
- Pause/idle 使用 20 Hz presentation clock。
- `append_samples()` 删除每批 Ring capacity 诊断比较和 warning 构造；Start 预分配策略不变。
- 产品功能/协议/架构边界未扩大。
- `AGENTS.md`、`WORKFLOW.md`、`SKILL.md`、Docs/State 已同步“最小修改、不过度分析、达标即停”。

## 自动验证
- compileall PASS
- pytest **39 passed**
- presentation pacing regression PASS
- release cleanup regression PASS
- Qt smoke：PENDING_ENVIRONMENT（当前运行容器未安装 PySide6）
- Confidence: `VERIFIED_AUTOMATED` for current pure-Python/static checks

## 必须做的实机验证
使用真实 Windows + PySide6 + J-Link，在 **RUN / 非 VS Code F5** 环境验证：

1. HSS 1000 Hz requested / Actual Hz
2. Overlay：60 / 120 / 144 FPS
3. Stacked：3+ channels，60 / 120 / 144 FPS
4. Follow
5. 左键拖动 / Zoom / View All
6. Pause / Resume / Show-Hide / CSV Export
7. Watch + Scope 基础兼容
8. 30 s 连续运行
9. 5 min 连续运行
10. 前景/后台切换

如果以上 RUN 模式正常：标记 `PERF-SCOPE-V043-HARDWARE = VERIFIED_USER_HARDWARE` 并停止继续优化。
如果出现 single-shot timer starvation，再用最小证据复现；不要直接恢复整套旧 watchdog/instrumentation。
