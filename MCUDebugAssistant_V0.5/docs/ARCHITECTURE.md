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

## Layer 6 — Presentation
Qt / pyqtgraph Scope + 自绘 `QAbstractScrollArea` Memory Explorer。

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
- Watch / Scope / Memory 不各自拥有 Session。
- Memory Explorer 不全地址扫描，不把连续滚动变成无界 queued ReadMemEx。
- Peripheral memory 不做后台扫描/大范围 speculative prefetch。
- Scope Raw/Display 分离保持不变。
