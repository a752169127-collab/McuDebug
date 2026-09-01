# MCU Debug Assistant V0.4.23 — High Performance Clean Release Report

## 基线
- Base: V0.4.21
- 目标: 保留成熟功能，只做 Release Scope 热路径减法

## 主要修改
1. Presentation 从 persistent 2~8 ms polling timer 改为 single-shot `Qt.PreciseTimer` + absolute deadline。
2. 迟到帧直接 skip，不 catch-up burst。
3. Pause/idle 使用 20 Hz presentation clock。
4. `append_samples()` 删除每批 Ring capacity 比较和 live-resize warning 构造；Start 前预分配策略保持不变。
5. 保留 Ring Buffer、Render Cache、Transform Follow、CPU Raster、Single-ViewBox Stacked、LiveLatencyGuard。
6. 保留 V0.4.21 已完成的 Stall watchdog / event-loop probe / debugger detector / 高频 profiling 清理。
7. 更新 AGENTS / WORKFLOW / SKILL：最小修改、不过度分析、证据足够即停止、达标即 STOP。

## 调度层理论变化
- 60 FPS: 旧 persistent driver 约 200 callback/s → 新方案约 60 callback/s，理论 timer callback 数减少约 70%。
- 120 FPS: 旧 persistent driver 约 500 callback/s → 新方案约 120 callback/s，减少约 76%。
- 144 FPS: 旧 persistent driver 约 500 callback/s → 新方案约 144 callback/s，减少约 71%。

注意：这是 Qt presentation timer callback 数量的理论变化，不等同于实际 FPS 或 CPU 占用提升比例。

## 自动验证
- `python -m compileall -q .`: PASS
- `python -m pytest -q`: 39 passed
- Release diagnostic cleanup regression: PASS
- Presentation pacer regression: PASS
- Qt offscreen ScopePage smoke: PENDING_ENVIRONMENT（当前执行环境没有 PySide6）
- Real J-Link/HSS/RTT: PENDING_HARDWARE

## 实机验收建议
在 Windows 正常 RUN / `python main.py` / `run_performance.bat` 下验证：

- HSS requested 1000 Hz / Actual Hz
- Overlay: 60 / 120 / 144 FPS
- Stacked: 3+ channels, 60 / 120 / 144 FPS
- Follow
- 左键拖动
- Zoom
- View All
- Pause / Resume
- Show / Hide
- CSV Export
- Watch + Scope 基础兼容
- 连续运行 30 s
- 连续运行 5 min
- 前景/后台切换

如果以上通过，建议直接冻结 V0.4.23 为新的高性能基线，不继续无证据优化。
