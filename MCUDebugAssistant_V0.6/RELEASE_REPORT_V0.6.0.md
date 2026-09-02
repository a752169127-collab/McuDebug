# RELEASE REPORT — V0.6.0 Test Automation Studio

## Goal
用真实的“呼吸机多转速 → 等压力/流量稳态 → 取 MCU 平均值 → 人工输入外部设备值 → 自动进入下一转速”场景，提炼一套不绑定呼吸机业务的无代码 MCU 自动化测试编排层。

## Added
- `core/test_automation.py`
  - Parameter List / Range
  - Cartesian / Zip case generation
  - `${Parameter}` token resolution（无 eval）
  - multi-signal Max-Min StableDetector
  - Sample Avg/Min/Max/Std
  - Calculate / Assert helpers
- `ui/automation_page.py`
  - Parameter Matrix
  - Workflow Step editor
  - Run / Results UI
  - Plan JSON save/load
  - CSV export
  - AXF/DWARF Symbol completion
  - Manual external measurement input
- `JLinkWorker`
  - request/response automation snapshot
  - automation typed write
  - both remain inside the existing single J-Link owner thread
- MainWindow
  - new `Test Automation` tab
  - AXF symbol propagation
  - settings persistence
  - automation run starts exclusive polling mode and stops Watch/Scope continuous sampling

## Workflow nodes
`SET / WAIT / WAIT UNTIL / WAIT STABLE / SAMPLE / MANUAL INPUT / CALCULATE / ASSERT / SAVE RESULT`

## Parameter Matrix
- List
- Range
- Cartesian Product
- Zip
- Case Preview

## Preserved
- V0.5.5 Memory Symbol resize and Watch focus-out write behavior.
- V0.5.x Symbol-aware Memory Explorer and WriteMemEx-only default write.
- V0.4.23 Scope Rendering V2 / pacing / Ring Buffer architecture.
- Single J-Link Owner.

## Automated Verification
- compileall: PASS
- pytest: **75 passed**
- V0.6.0 Parameter Matrix / StableDetector / Statistics / Calculate / Assert regression: PASS
- static worker/UI architecture regression: PASS

## Pending
- Qt GUI Runtime Smoke: `PENDING_ENVIRONMENT` (PySide6 unavailable in release build environment)
- Real AXF/J-Link workflow run: `PENDING_HARDWARE`
- Long parameter sweeps and timeout behavior on real target: `PENDING_HARDWARE`
- PF300 / VT650 / other external instrument direct acquisition: future adapter work; V0.6.0 uses manual input.

## Suggested Hardware Smoke
1. Load a real AXF and connect J-Link.
2. Open Test Automation and replace placeholder symbols with real target variables.
3. Set RPM Parameter to a short list such as `5000, 6000, 7000`.
4. Run: SET → WAIT STABLE → SAMPLE → MANUAL INPUT → CALCULATE → SAVE.
5. Verify each SET changes the target once, no read-back verify occurs, and each case advances only after the configured condition/manual confirmation.
6. Check exported CSV statistics against Scope/Watch or an external instrument.
