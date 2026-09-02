# ARCHITECTURE

## Layer 1 — Device Interface
J-Link backend / 单 Session Owner。

## Layer 2 — Acquisition
Watch sampling / HSS / RTT / timestamp & payload decode / Memory block read-write。

## Layer 3 — Symbol
ELF / DWARF / symbol model / rebind / Memory SymbolIndex / Address-Bar Symbol Completion。

## Layer 4 — Raw Data
Scope Preallocated Ring Buffer / stats / CSV / cursor source；Memory Explorer 保留当前原始 bytes block。

## Layer 5 — Display Preparation
Scope: visible range / peak preserve / Render Cache / Gain Offset / lane mapping。
Memory: visible read window / typed formatting / text decoding / symbol annotation / changed-byte diff / byte-range selection / direct edit。

## Layer 6 — Test Automation Orchestration
Parameter Matrix / Workflow / Stable Detector / Sample Statistics / Manual Measurement / Calculate / Assert / Result Export。

该层只编排已有 Runtime 能力，不直接拥有 Probe Session。V0.6.0 通过 MainWindow Signal 把自动化读写请求交给唯一 `JLinkWorker`。

## Layer 7 — Presentation
Qt / pyqtgraph Scope + 自绘 `QAbstractScrollArea` Memory Explorer + Test Automation Studio。


## Test Automation V0.6.x 数据链

```text
Parameter Matrix
(List / Range / Cartesian / Zip)
          ↓
Generated Test Cases
          ↓
      Workflow
 SET / WAIT / WAIT STABLE
 SAMPLE / MANUAL INPUT / SAVE RESULT
          ↓
 AXF/DWARF SymbolIndex
          ↓
 MainWindow queued Signal
          ↓
 Single JLinkWorker
   ├─ typed WriteMemEx
   └─ bounded variable snapshot ReadMemEx
          ↓
 Test Context / Statistics
          ↓
 Results Table / TSV Clipboard
```

### Execution semantics
- Matrix 决定 Case 数据，Workflow 只定义 Case 执行步骤；禁止把具体产品场景编码进引擎。
- V0.6.0 自动化使用 request/response polling。Run 开始时 MainWindow 停止 Watch 和 Scope 的连续采样，让同一 J-Link Owner 的时序更可预测。
- `WAIT STABLE` 当前使用 Window 内 `Max-Min <= Threshold`；支持多个 Signal、Hold、Timeout，以及 Continue/Skip/Stop。
- `SAMPLE` 在稳定后重新进入独立统计窗口，输出 `Count/Avg/Min/Max/Std`，不会把稳态检测历史直接当最终测量结果。
- `MANUAL INPUT` 是 Measurement Source 的第一版实现；未来 PF300/VT650 等 Adapter 应替换数据源，不改变 Workflow。
- Test Plan 禁止任意 Python `eval/exec`。`${Parameter}` 只做 Token 替换。V0.6.1 默认编辑器不再暴露 CALCULATE/ASSERT/WAIT UNTIL；旧计划仍由兼容路径执行。

### Memory Explorer 数据链

```text
Vertical virtual row (32-bit address space)
          ↓
35 ms scroll debounce
          ↓
Visible rows + margin (<= 2048 B planned)
          ↓
MainWindow Signal
          ↓
Single JLinkWorker
          ↓
JLINK_ReadMemEx
          ↓
Raw bytes block
          ├─ Hex / typed display
          ├─ ASCII / UTF-8 / UTF-16LE / GBK
          ├─ changed-byte compare
          └─ AXF/DWARF SymbolIndex annotation
```

Worker 额外对 Memory Explorer block request 做 4096 B 上限保护。

### Symbol → Address 跳转链

```text
AXF / ELF / DWARF load
        ↓ once
SymbolIndex + flat completion model
        ↓
Address / Symbol 输入
        ↓ local MatchContains only
Symbol / Type / Address 下拉列表
        ↓ Enter
exact_name(symbol path)
        ↓
0xXXXXXXXX → Memory goto / visible read
```

键入过程中不调用 J-Link，也不重新解析 AXF；只有用户确认跳转后，Memory View 才按既有 visible-window 规则发起读取。

### Memory Write

```text
Hex direct type / Text type / Paste / Double-click dialog
                    ↓
               MainWindow Signal
                    ↓
               JLinkWorker
                    ↓
            JLINK_WriteMemEx
                    ↓ full byte count
          WRITE=OK + local cache patch
```

Memory Explorer 的 direct edit 不再增加第二个确认框：Hex/Text 键入本来就是直接编辑，双击弹窗的 OK 即确认。独立 Typed R/W 表单仍可保留显式确认。默认不追加 ReadMemEx Verify；若用户要确认目标实时值，使用 F5/Read 作为独立读取。

## Scope V0.4.23 Presentation

```text
PresentationPacer absolute deadline
        ↓
Single-shot PreciseTimer
        ↓
_viewport_tick()
        ↓
arm next deadline
```

Scope Acquisition Rate、Heavy Curve Refresh、Presentation FPS 继续彼此独立。

## 不可破坏依赖原则
- GUI 不直接调用 J-Link。
- Watch / Scope / Memory / Test Automation 不各自拥有 Session。
- Memory Explorer 不全地址扫描，不把连续滚动变成无界 queued ReadMemEx。
- Peripheral memory 不做后台扫描/大范围 speculative prefetch。
- Scope Raw/Display 分离保持不变。
- Automation Matrix / Workflow 分离；外部仪器 Adapter 不把具体设备逻辑写进通用 Test Engine。

### V0.5.5 Presentation / Watch Commit

```text
Memory Symbol/Hex divider drag
        ↓
local symbol_width_px
        ↓
column geometry + horizontal scrollbar + repaint
        ↓
NO AXF parse / NO J-Link I/O
```

```text
Watch Set Value textEdited
        ↓ dirty=true
Enter OR focus-out(editingFinished)
        ↓ dirty guard / commitData
QTable item committed
        ↓ next event-loop turn
write_requested(row_id)
        ↓
Single JLinkWorker → WriteMemEx
```

未发生 `textEdited` 的 focus-out 不产生写请求；dirty 在首次 commit 前清零，防止 Return 与 editingFinished 对同一次编辑重复触发。

### V0.6.1 Dynamic Step Editor
Step 类型切换时，旧 body 中可能包含 `QFormLayout/QHBoxLayout`。清理必须递归遍历 `QLayoutItem.layout()` 与 `QLayoutItem.widget()`，否则旧 Label 会继续作为 child widget 存活并叠在新表单上。该修复只影响 UI 生命周期，不改变 Test Engine/J-Link 时序。


### V0.6.2 Runtime Context / Result Projection
Automation 执行期 `_context` 是内部运行状态，不等同于最终 Test Result。SAMPLE 可在 `_context` 中保留 Count/Avg/Min/Max/Std 供兼容节点使用，但每个 Case 只通过显式 `case_output_keys` 投影到 Results/CSV。V0.6.3 新 SAMPLE 默认注册 `.avg/.min/.max`；Std 需要用户显式选择，`.count` 不作为用户结果。Run 完成后只清空 Runtime 表并切到 Results，正式 Results 不随新 Run 自动清空。


### V0.6.3 Persistent Result History / Clipboard Surface
Results 是用户明确积累的测试记录，不属于一次 Run 的临时状态。`Run All` 只重置 Case 执行状态，不清空 `_results`；新的 Case 继续 append。只有 Results 页的 `Clear Results` 在用户确认后重置结果表。

复制采用 TSV：

```text
Result Table → headers + rows → TAB columns / LF rows → QApplication clipboard → Excel paste
```

这样避免每轮测试都弹文件保存对话框，同时保持结果表与 Excel 的直接二维映射。Run/Runtime 表仍属于瞬时执行视图，全部 Case 完成后清空。
