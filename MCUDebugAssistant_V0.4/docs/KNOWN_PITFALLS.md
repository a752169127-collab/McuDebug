# KNOWN_PITFALLS

1. HSS Timestamp 当数据 → 固定变量画成 ramp/triangle。
2. Watch 每采样点更新 Qt 表格 → GUI 卡。
3. AXF Search 每按键重建整个表 → 卡。
4. `np.concatenate` 整段历史 → 越跑越慢。
5. 多 PlotWidget / ViewBox Stacked → 高刷成本高。
6. 激进修改 QGraphicsView update mode → follower lane 显示异常。
7. QOpenGLWidget viewport → 实机不如 CPU Raster。
8. whole-buffer extrema fit 当前局部 Lane → 旧异常点撑坏 Y scale。
9. Mouse move 中 `QLabel.adjustSize()` → watchdog 抓到 stall。
10. VS Code debugpy/pydevd 会污染高刷性能结论。
11. Watchdog 长 stack 直接 append GUI Log 也可能干扰实时性。
12. live ring resize 不适合实时路径，应 Start 前预分配。
13. Stall 几百 ms 而所有 measured task 都 <10ms 时，不要继续优化已被排除模块。
14. 临时 watchdog、event-loop probe、逐帧/逐 poll 计时不能长期留在默认 Release 热路径。

15. 为绕过 debugger 阶段 timer starvation 而长期保留高频 persistent polling，会产生大量无效 Qt callback；Release 应优先一帧一回调，除非新的 RUN 证据证明不成立。
16. AI 性能优化容易过度分析/过度开发：已有证据足够时应最小修改、验证、达标即停。
