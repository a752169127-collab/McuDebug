# MCU Debug Assistant V0.6.6 — Test Automation Studio + Typed Memory Navigation

V0.6.x 在 V0.5.5 的 **Watch + Scope + Symbol-aware Memory Explorer** 基础上新增第一版无代码 **Test Automation Studio**。目标不是让用户写 Python/YAML，而是通过参数矩阵和可配置 Workflow，把 MCU 运行时变量读写、稳态判断、统计、人工测量和结果导出编排成自动测试用例。

## V0.6.6 重点

- Memory `Address / Symbol` 历史下拉升级为 `History / Type / Address` 三列，编辑框尺寸保持 320~520 px 不变。
- Symbol/成员跳转时，如果 AXF/DWARF 提供受支持的标量类型，Memory Display Type 会立即自动切换到该类型；例如 `uint8 -> UInt8`、`float -> Float`。
- 原始数值地址或 struct/array/unknown 类型不做类型猜测，继续保持当前 Memory Display Type。
- Workflow 新建步骤精简为：`SET / WAIT / WAIT STABLE / SAMPLE / MANUAL INPUT / SAVE RESULT`。
- 修复 Step Type 反复切换后旧表单 Label/Layout 残留导致的字体/文字重叠。
- V0.6.0 的 `WAIT UNTIL / CALCULATE / ASSERT` 仅为旧 Test Plan 兼容保留，不再出现在新建步骤列表。


- Automation Results 与 Runtime Context 分离，不再把内部执行字段整包显示/导出。
- SAMPLE 默认输出 `Avg / Min / Max`；`Std` 仍可按需勾选，`Count` 只作为内部采样元数据。
- 全部 Case 完成后自动切到 Results，并清掉最后一组 Runtime 明细。

### Parameter Matrix
- `List`：例如 `5000, 8000, 11000`。
- `Range`：例如 `5000 → 30000 / step 1000`。
- `Cartesian Product`：多个参数做全组合枚举。
- `Zip`：多个参数按行同步枚举。
- Preview Cases：运行前查看实际生成的测试 Case。

### No-code Workflow
当前支持这些通用步骤：
- `SET`：按 AXF/DWARF Symbol 写 MCU 变量，Value 可引用 `${RPM}` 等测试参数。
- `WAIT`：固定时间等待。
- `WAIT STABLE`：一个或多个变量按窗口 `Max-Min` 波动阈值判断稳态，支持 Hold、Polling、Timeout 和 Continue/Skip/Stop。
- `SAMPLE`：稳定后按指定时间/周期采样多个变量；内部统计 `Avg / Min / Max / Std / Count`，默认结果输出 `Avg / Min / Max`，`Std` 可选，`Count` 不作为普通结果列。
- `MANUAL INPUT`：暂停等待人工输入 PF300 / VT650 等外部设备读数；未来可替换为真实仪器 Adapter。
- `SAVE RESULT`：在 Workflow 中明确标记保存意图；Case 结束时结果始终落表。

### Execution / Result
- 每个 Case 自动执行相同 Workflow，然后进入下一个枚举点。
- Runtime 页只用于执行期观察当前 Case/步骤/上下文；全部完成后自动切换 Results。
- Results 页只显示 Parameter、用户选择的 Sample 统计、Manual Input 和显式输出，不再泄漏内部 Context 字段。
- 支持保存/打开 Test Plan JSON；Results 页一键复制完整 TSV 文本到剪贴板，可直接粘贴 Excel。
- Test Plan 会随应用设置持久化。
- 新一轮 Run 不自动清空已有 Results；结果持续累积，只有 Results 页的 `Clear Results` 才显式清空。
- 全部 Case 完成后只清空 Run Runtime 明细并自动切到 Results。

## 呼吸机稳态标定示例

```text
RPM = 5000 → 30000, step 1000
       ↓
SET Blower.TargetRpm = ${RPM}
       ↓
WAIT STABLE Pressure + Flow
       ↓
SAMPLE Pressure / Flow 3s
       ↓
MANUAL INPUT ExternalPressure / ExternalFlow
       ↓
       ↓
SAVE RESULT
       ↓
NEXT RPM
```

## 架构原则
- Test Automation UI 不直接访问 J-Link DLL。
- 自动测试读写仍全部经过唯一 `JLinkWorker`。
- V0.6.x 测试运行使用 request/response Memory Polling；开始自动化时停止连续 Watch / Scope 采样，避免三条链在同一 J-Link Owner 上互相竞争。
- AXF/DWARF 在加载时同步给 Automation，变量选择和解析是本地 Symbol 操作。
- 不提供任意 `eval()` / Python Script；参数只通过 `${Name}` Token 和结构化 Calculate/Assert 节点引用，保证 Test Plan 可审查、可保存、可复现。
- V0.5.x Memory visible-window、WriteMemEx-only、V0.4.23 Scope 高性能架构保持不变。

## 运行

```text
run.bat
```

## 当前验证状态
- `python -m compileall -q .`: PASS
- `pytest -q`: 97 passed
- Test Automation pure-core / static integration regression: PASS
- Qt Runtime Smoke: `PENDING_ENVIRONMENT`（当前执行环境无 PySide6）
- Real AXF + J-Link Automation run: `PENDING_HARDWARE`
- External instrument automatic acquisition: **not implemented in V0.6.6**，当前使用 `MANUAL INPUT`。

详细状态见 `state/TEST_STATUS.md`、`state/LATEST_HANDOFF.md`、`RELEASE_REPORT_V0.6.6.md`。



## V0.6.5 PySide6 Combo Signal Compatibility
- 修复 Memory Address/Symbol 历史下拉在 PySide6/Qt6 启动阶段崩溃：`QComboBox.activated` 在当前绑定中只暴露 `activated(int)`，不能使用旧式 `activated[str]` 选择重载。
- 历史选择现在通过 activated index 读取 `itemText(index)`，再复用原 `_goto()` 路径；MRU、AXF completer、J-Link 单 Owner 均不变。
- `QThread: Destroyed while thread is still running` 是构造阶段异常退出后的级联提示；主启动异常修复后不会由该路径触发。

## V0.6.4 Memory Navigation History
Memory `Address / Symbol` now keeps a persistent MRU drop-down of successful Symbol/address queries, with explicit clear and no per-key target I/O.
