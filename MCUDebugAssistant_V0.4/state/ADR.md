# ADR

## ADR-001 — Single J-Link Owner
所有 J-Link DLL 访问由单 Worker/Owner 承担。

## ADR-002 — Raw / Display Separation
显示变换不能修改 Raw Data。

## ADR-003 — Sampling / UI Decoupling
Acquisition、Curve Update、Table Refresh、Presentation FPS 分离。

## ADR-004 — Single ViewBox Stacked
Stacked 使用 Logical Lanes 减少多 ViewBox/Axis 成本。

## ADR-005 — CPU Raster Main Renderer
QOpenGLWidget 实机无优势，CPU Raster 作为主路径。

## ADR-006 — Instrument Before Rewrite
不明 Stall 优先测量，不连续凭猜测重写多个层。

## ADR-007 — Release Performance Outside Debugger
正式高刷性能必须使用 RUN 模式，不以 debugpy/pydevd 结果验收。

## ADR-008 — Release Scope Has No Default Stall Instrumentation
正式 Scope 默认路径不创建 performance watchdog、诊断写线程或额外
event-loop Timer，也不持续执行 Worker/Paint/Presentation 分段计时。
未来如需恢复诊断，必须使用显式且默认关闭的开关；关闭时不得安装
诊断 Timer/线程/Signal，也不得在热路径构造日志或更新时间统计。


## ADR-009 — Release Presentation Uses Single-shot Absolute Deadlines
V0.4.23 将 V0.4.20/V0.4.21 的高频 persistent timer polling 替换为 single-shot `Qt.PreciseTimer` + floating-point absolute deadline。

理由：persistent driver 的必要性主要来自 debugger 阶段 timer-starvation 观察；在 Release 路径中它会产生明显多于目标 FPS 的 Qt timer callbacks。Single-shot 方案让 timer callback 数量接近 presentation frame 数，同时继续 skip missed slots、禁止 catch-up burst。

回退条件：只有新的 **RUN/非 debugpy** 实机证据证明 single-shot timer delivery 不可靠，才允许重新评估 persistent driver；不得直接恢复旧 Stall instrumentation。
