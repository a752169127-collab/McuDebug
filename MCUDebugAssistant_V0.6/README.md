# MCU Debug Assistant V0.6.16 — AI Documentation Layout

V0.6.x 在 V0.5.5 的 **Watch + Scope + Symbol-aware Memory Explorer** 基础上新增第一版无代码 **Test Automation Studio**。目标不是让用户写 Python/YAML，而是通过参数矩阵和可配置 Workflow，把 MCU 运行时变量读写、稳态判断、统计、人工测量和结果导出编排成自动测试用例。


## V0.6.16 重点

- 本版是工程治理版本，不改变 J-Link/Watch/Scope/Memory/Test Automation 运行行为。
- 历史 `RELEASE_REPORT_*.md` 全部归档到 `docs/releases/`，根目录不再随着版本增长堆满 Release 文件。
- 项目状态统一归档到 `docs/state/`；架构/ADR/已知陷阱统一放到 `docs/architecture/`；Workflow/Checklist/AI 辅助说明统一放到 `docs/development/`。
- 根目录保留 `README.md / START_HERE_FOR_NEW_AI.md / AGENTS.md / SKILL.md / CHANGELOG.md` 作为人和 AI 的稳定入口。
- 新增 `docs/README.md` 与 `docs/releases/README.md`，AI 可以先读当前状态和索引，再按需读取相关历史报告，避免每次把全部版本历史塞进上下文。



## V0.6.15 重点

- Memory Symbols 右键新增 `Add to Scope`，保留 `Add to Watch / Copy Symbol`；Raw Memory 选中地址也可直接 Add to Scope。
- Watch Variable 右键新增 `Add to Scope / Open in Memory / Copy Symbol`。
- Scope Channel 右键新增 `Open in Memory / Add to Watch / Copy Symbol`；RTT 通道没有 AXF 地址时只允许 Copy，避免把 target-defined channel 误当成可寻址 Symbol。
- `Open in Memory` 会优先用“完整 Symbol 名 + 地址”双重匹配 AXF/DWARF：匹配成功时进入 Semantic Symbols 导航并一次性定位/选中目标；手工命名 Watch 行则安全退回 Raw address，不猜 Symbol。
- 所有跨模块动作只传递 `name/address/type` 的本地 Symbol 描述，不创建第二个 J-Link Worker/Session，不改变 single-owner 架构。


## V0.6.14 重点

- 修复 Symbols View 输入/选择 Symbol 后目标行缺少明确视觉定位的问题：显式 Symbol 导航会一次性把目标成员滚到中间并高亮选中。
- Auto/Manual Refresh 仍不会把 viewport 拉回导航 anchor；刷新只保持“真实 selection”，不再把仅有 currentIndex 的旧行重新选回来。
- 在 Symbols 表格空白区域单击会同时 `clearSelection()` 和清除 current index，后续刷新也不会重新出现该选中行。
- 不改变 Semantic Memory 的 bounded single-block ReadMemEx、AXF/DWARF 解码和 single J-Link owner。

## V0.6.13 重点

- 修复 Symbols View 在 Auto Refresh/Refresh 返回新 block 后反复重建 Model、重新 `scrollTo(anchor, PositionAtCenter)`，导致用户向下滚动后自动弹回导航 Symbol 的问题。
- Symbol 导航只允许**首次**把目标成员滚到中间；后续刷新只更新 Value，并保持用户当前 vertical/horizontal viewport。
- 导航时不再留下一个“系统强制选中”的变量行；用户自己点击的选择仍可保留，刷新不会借这个选择把视图拉回去。
- cached refresh 不再无意义重建相同 Symbol model，减少 UI churn；目标读取策略仍是单个 bounded block，不增加 J-Link I/O。

## V0.6.12 重点

- Memory 新增 `View: Auto / Raw / Symbols`：`Auto` 下通过 Symbol/成员导航时进入 typed Symbol 视图，手动数值地址导航保持经典 Raw/CE 视图；也可以手动固定 Raw 或 Symbols。
- `Symbols` 视图按 AXF/DWARF **真实标量成员**逐行显示：`Address / Symbol / Type / Value`，例如 `BlowerParamsObj.m_BiasAD[0]...[3]` 会分别显示并按各自 `uint16` 解码，而不是继续依赖 `+00/+02/...` 偏移猜值。
- 同一屏附近不同类型成员可以同时正确解释：`uint8/uint16/uint32/float/double/...` 各按自己的 type size 从共享 raw block 中解码。
- Symbol 视图仍只做一次 bounded block read（默认最多 2 KiB），然后本地按 SymbolIndex 切片解码；**不会每个成员单独 ReadMemEx**，不改变 Single J-Link Owner。
- DWARF 成员优先于同地址 ELF size-guess fallback，减少 `struct/array` 成员与原始对象名重复；DWARF 不可用时仍可退化显示可解释的 ELF scalar。
- Symbol 视图双击变量可复用现有 typed edit，右键可 `Add to Watch / Copy Symbol`；Raw 视图的 Hex/Text/批量复制/直接编辑能力全部保留。

## V0.6.11 重点

- Memory `Auto Refresh` 从 +/- SpinBox 改为可编辑工程预设下拉：`100 / 200 / 500 / 1000 / 2000 / 5000 ms`，默认 `1000 ms`；仍允许手输 `100~10000 ms`。
- Watch `Sample every` 改为：`10 / 20 / 50 / 100 / 200 / 500 / 1000 / 2000 ms`，默认 `100 ms`；仍允许手输 `1~60000 ms`。
- Scope `Sampling` 改为：`10 / 20 / 50 / 100 / 200 / 500 / 1000 / 2000 / 5000 Hz`，默认 `1000 Hz`；仍允许手输 `1~10000 Hz`。
- Scope `Buffer` 改为：`1 / 2 / 5 / 10 / 15 / 30 / 60 / 120 s`，默认 `30 s`；保留既有 120 s 上限，避免在高采样率下超出当前 1.5M-point Ring 的已验证产品边界。
- Scope `FPS` 同步统一为可编辑预设：`15 / 30 / 60 / 90 / 120 / 144 FPS`，默认 `60 FPS`；仍允许自定义 `1~144 FPS`。
- 新增统一 `IntPresetComboBox`：下拉选常用值，特殊值直接输入；不再用单步 `+1/-1` 箭头改变工程参数。旧 settings 的整数值仍通过 `value()/setValue()` 兼容恢复。

## V0.6.10 重点

- J-Link Connection 改为可折叠配置面板：未连接时展开；连接成功后自动折叠成一行状态摘要，保留 `+` 展开按钮和常驻 `Disconnect`。
- 已连接时手动展开仍可查看 DLL/Device/Interface/Speed，但配置控件继续锁定，避免误改当前 Session。断开后自动重新展开。
- Test Automation UI 精简：Parameter/Workflow/Run/Results 隐藏 Qt 默认行号；Workflow 删除重复 `#` 列，仅保留 `Step / Summary`；Results 保留业务 `Case` 列。
- 以上均为 Presentation/UI 改动，不改变 J-Link single-owner、Watch/Scope/Memory/Test Automation 数据链。

## V0.6.9 重点

- Memory History 新增常驻 `Delete History` 按钮：选择历史项后即使下拉框关闭，也能删除单条记录；`Clear History` 继续负责全部清空。
- 从 History 选择已有 Symbol/地址只负责导航，**不再把该项移动到历史列表顶部**，历史顺序保持稳定。
- 新输入并成功导航的 Symbol/地址仍会按现有 MRU 规则记录；只有“选择已有历史”不触发重排。
- 右键 History context menu 不再作为主删除交互，规避 Windows/PySide6 下 ComboBox popup 打开二级菜单时自动收起的问题。

- 修复剩余的 Symbol Enter 竞态：`QCompleter` 选择变量后，Memory 历史 `QComboBox` 不再因为同一个 Enter 额外激活旧历史项，因此不会再从目标变量跳成 `__lit__00000000` 之类旧记录。
- Symbol 候选确认只走 `QCompleter.activated`；普通 Enter 只解析编辑框里的完整 Symbol 或原始地址，不再根据 popup/current index 猜候选。
- V0.6.8 已建立单条 History 删除能力；V0.6.9 将主入口改为常驻 `Delete History` 按钮，Delete 键作为辅助，`Clear History` 负责全部清空。
- 修复旧设置导致 Symbol 列仍然保持窄手动宽度的问题：V0.6.8 用新的 `symbol_width_mode` 做一次迁移，旧配置默认恢复自动适应当前可见完整 Symbol；之后用户新手动拖宽仍可持久化。
- Symbol 导航继续优先显示完整 Symbol 名；只有手动输入数值地址时编辑框才显示 `0xXXXXXXXX`。

### 继承的 V0.6.x 能力

- V0.6.7 曾收敛 Memory 键盘候选路径；V0.6.8 进一步隔离 editable Combo History activation，修掉实机仍能复现的 Enter 二次导航。
- Symbol 导航后 Address / Symbol 编辑框优先保留完整 Symbol 名；只有用户明确输入原始数值地址时才显示 `0x...`。
- Memory 主视图 Symbol 列默认按当前可见行最长 Symbol 自动扩展，历史/补全 popup 也在 AXF/History 更新时自动按内容调整列宽；不需要为了看完整成员名手动拉宽。
- Watch `Set Value` 改为在 Qt delegate 的 `setModelData()` 正式提交路径触发写入：Enter 和鼠标失焦统一，同样值重新输入也会再次写 MCU；未编辑单元格不会误写。

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
- `pytest -q`: 136 passed
- Test Automation pure-core / static integration regression: PASS
- Qt Runtime Smoke: `PENDING_ENVIRONMENT`（当前执行环境无 PySide6）
- Real AXF + J-Link Automation run: `PENDING_HARDWARE`
- External instrument automatic acquisition: **not implemented in V0.6.9**，当前使用 `MANUAL INPUT`。

详细状态见 `docs/state/TEST_STATUS.md`、`docs/state/LATEST_HANDOFF.md`、`docs/releases/RELEASE_REPORT_V0.6.16.md`。



## V0.6.5 PySide6 Combo Signal Compatibility
- 修复 Memory Address/Symbol 历史下拉在 PySide6/Qt6 启动阶段崩溃：`QComboBox.activated` 在当前绑定中只暴露 `activated(int)`，不能使用旧式 `activated[str]` 选择重载。
- 历史选择现在通过 activated index 读取 `itemText(index)`，再复用原 `_goto()` 路径；MRU、AXF completer、J-Link 单 Owner 均不变。
- `QThread: Destroyed while thread is still running` 是构造阶段异常退出后的级联提示；主启动异常修复后不会由该路径触发。

## V0.6.4 Memory Navigation History
Memory `Address / Symbol` now keeps a persistent MRU drop-down of successful Symbol/address queries, with explicit clear and no per-key target I/O.
