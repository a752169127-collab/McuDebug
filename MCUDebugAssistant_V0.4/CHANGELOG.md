# V0.4.12 — Long-Run Latency Guard

## 目标
解决 V0.4.11 实机长期运行后的两个剩余问题：

1. Scope 窗口失去前台焦点后，144 FPS 模式容易下降到约 60~70 Paint FPS；
2. 长时间运行中偶发整个 GUI 短暂停住，随后又恢复。

## 主要修改

### Windows Live Latency Guard
实时 Scope 启动后进入低延迟运行区间：

- `timeBeginPeriod(1)` 请求 1 ms Windows timer resolution；
- `SetProcessInformation(ProcessPowerThrottling)` 清除 ExecutionSpeed / IgnoreTimerResolution 节流位；
- Process Priority 使用 `ABOVE_NORMAL_PRIORITY_CLASS`；
- GUI presentation thread 使用 `THREAD_PRIORITY_ABOVE_NORMAL`；
- 暂停采样时恢复 timer / process / thread priority。

不会使用 HIGH / REALTIME priority，避免抢占系统关键线程。

### 实时区间禁用 Python cyclic GC
采样启动前先主动 `gc.collect()`，随后实时采样期间 `gc.disable()`：

- 普通 Python 引用计数仍然工作；
- NumPy 数组仍会正常释放；
- 只把不可预测的 cyclic-GC stop-the-world collection 移出高刷新路径。

暂停后恢复 GC，并延迟 300 ms 在空闲状态执行一次收集。

### 删除 GPU 实验
真实板测试已经证明 `QGraphicsView + QOpenGLWidget` 对当前 Scope 比 CPU Raster 更慢，因此：

- 删除 GPU 复选框；
- 删除 OpenGL viewport 切换；
- 删除 `gpu_render` 持久化配置；
- Scope 只保留已验证正确的 CPU Raster + Single ViewBox 路线。

### 增强性能诊断
状态栏从单一 Paint FPS 扩展为：

`P:<paint>/<target> T:<presentation> 1%:<low> J:<jitter> Stall:<count>/<max_ms> pts:<geometry> FG/BG`

用于区分：

- `T` 也下降：GUI event loop / Windows timer scheduling 被拖慢；
- `T` 正常但 `P` 下降：Qt/DWM paint coalescing / raster throughput；
- `Stall` 增加：真正发生了几十~几百 ms 的 GUI event-loop stop。

长停顿超过阈值时还会写入 Log。
