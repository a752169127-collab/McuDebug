# MCU Debug Assistant V0.4.23 — High Performance Clean

V0.4.23 以 V0.4.21 的成熟功能和 AI 研发资产为基线，继续做 **Release 热路径减法**。
本版不重写 Scope 架构，不改变 HSS/RTT、Ring Buffer、Watch、AXF、Overlay/Stacked、Follow/Pause/Start 等产品语义。

## 核心变化

### 1. Presentation 从高频轮询改为一帧一回调

```text
Absolute Presentation Deadline
          ↓
next_delay_ms()
          ↓
Single-shot Qt PreciseTimer
          ↓
_viewport_tick()
          ↓
Render / Follow / Paint
          ↓
arm next deadline
```

V0.4.21 在 144 FPS 下使用 2 ms persistent driver，理论约 500 次 timer callback/s，
只有约 144 次需要真正 presentation。V0.4.23 目标接近 **144 次 callback/s**。
60 FPS 同理从约 200 次 polling callback/s 收敛到约 60 次 presentation callback/s。
这是调度唤醒数量的理论减少，不等同于实机 FPS 提升百分比。

### 2. Release append 热路径继续减法

- Start 前仍按 requested Hz × Buffer 预分配 Ring Buffer。
- `append_samples()` 不再每批比较 capacity 并构造 live-resize warning。
- 默认 Scope 热路径继续保持无 watchdog / event-loop probe / debugger detector / 高频 stage profiling。

## 保留的高性能架构

- single J-Link owner Worker
- HSS/RTT acquisition batching + Actual Hz
- CPU Raster
- Single-ViewBox logical-lane Stacked
- preallocated NumPy Ring Buffer
- Render Cache + visible-window peak-preserving reduction
- Transform Follow
- heavy curve refresh 与 viewport FPS 分离
- LiveLatencyGuard
- fixed-geometry/throttled Hover
- bounded/batched GUI product log

## AI 长期开发约束

`AGENTS.md` / `WORKFLOW.md` / `SKILL.md` 已同步 V0.4.23：
- 最小修改
- 不过度分析
- 没有证据不重构稳定区
- 临时诊断不进入 Release 热路径
- 自动测试通过且达到 Acceptance Criteria 后停止开发

## Performance validation

正式性能只在非 debugger 环境评价：

```text
run_performance.bat
```

或：

```text
python main.py
```

真实 J-Link / HSS / RTT 高刷与长时间性能仍需硬件 A/B，状态为 `PENDING_HARDWARE`。
