from __future__ import annotations

"""Low-latency runtime guard for live Scope presentation.

The Scope renderer is latency sensitive rather than throughput-only.  Windows
can reduce timer precision / execution speed for background processes, while
CPython's cyclic GC can introduce rare, unpredictable stop-the-world pauses.
This helper keeps those policies out of the UI code and makes activation /
restoration idempotent.

Normal reference-count based deallocation is *not* disabled by gc.disable();
NumPy arrays and ordinary temporary Python objects therefore continue to be
released promptly.  Only cyclic-GC collections are deferred until the live
capture ends.
"""

from dataclasses import dataclass
import ctypes
import gc
import os
import sys
from ctypes import wintypes


@dataclass(frozen=True)
class LatencyGuardStatus:
    active: bool
    timer_1ms: bool = False
    power_throttling_disabled: bool = False
    process_above_normal: bool = False
    gui_thread_above_normal: bool = False
    cyclic_gc_disabled: bool = False
    gil_switch_1ms: bool = False

    def short_text(self) -> str:
        if not self.active:
            return "latency=off"
        flags: list[str] = []
        if self.timer_1ms:
            flags.append("1ms")
        if self.power_throttling_disabled:
            flags.append("EcoOff")
        if self.process_above_normal:
            flags.append("P+")
        if self.gui_thread_above_normal:
            flags.append("T+")
        if self.cyclic_gc_disabled:
            flags.append("GCoff")
        if self.gil_switch_1ms:
            flags.append("GIL1ms")
        return "latency=" + ("/".join(flags) if flags else "on")


class LiveLatencyGuard:
    """Temporarily bias the process toward stable frame pacing.

    Windows-specific calls are best-effort and deliberately use ABOVE_NORMAL,
    never HIGH/REALTIME priority.  On non-Windows hosts the guard still manages
    cyclic GC, which keeps tests and future ports deterministic.
    """

    ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
    THREAD_PRIORITY_ABOVE_NORMAL = 1
    PROCESS_POWER_THROTTLING = 4
    PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
    PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
    PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION = 0x4

    class _POWER_THROTTLING_STATE(ctypes.Structure):
        _fields_ = [
            ("Version", wintypes.DWORD),
            ("ControlMask", wintypes.DWORD),
            ("StateMask", wintypes.DWORD),
        ]

    def __init__(self) -> None:
        self._active = False
        self._gc_was_enabled = False
        self._timer_started = False
        self._old_process_priority: int | None = None
        self._old_thread_priority: int | None = None
        self._power_throttling_changed = False
        self._old_switch_interval: float | None = None
        self._status = LatencyGuardStatus(False)

    @property
    def status(self) -> LatencyGuardStatus:
        return self._status

    def activate(self) -> LatencyGuardStatus:
        if self._active:
            return self._status

        # Collect before entering the latency-critical region, then defer cyclic
        # GC.  Reference counting remains fully active.
        self._gc_was_enabled = bool(gc.isenabled())
        try:
            gc.collect()
        except Exception:
            pass
        if self._gc_was_enabled:
            try:
                gc.disable()
            except Exception:
                pass

        gil_ok = False
        try:
            self._old_switch_interval = float(sys.getswitchinterval())
            sys.setswitchinterval(0.001)
            gil_ok = True
        except Exception:
            self._old_switch_interval = None

        timer_ok = power_ok = process_ok = thread_ok = False
        if os.name == "nt":
            timer_ok = self._activate_windows_timer()
            power_ok = self._disable_windows_power_throttling()
            process_ok = self._raise_windows_process_priority()
            thread_ok = self._raise_windows_thread_priority()

        self._active = True
        self._status = LatencyGuardStatus(
            True,
            timer_1ms=timer_ok,
            power_throttling_disabled=power_ok,
            process_above_normal=process_ok,
            gui_thread_above_normal=thread_ok,
            cyclic_gc_disabled=not gc.isenabled(),
            gil_switch_1ms=gil_ok,
        )
        return self._status

    def deactivate(self) -> LatencyGuardStatus:
        if not self._active:
            return self._status

        if os.name == "nt":
            self._restore_windows_thread_priority()
            self._restore_windows_process_priority()
            self._restore_windows_timer()
            # Intentionally do not re-enable Windows execution-speed throttling.
            # SetProcessInformation does not expose a reliable "restore previous
            # owner policy" query on all supported Windows builds.  Leaving this
            # debug tool opted out prevents focus/background transitions from
            # silently changing its timing behavior after the first capture.

        if self._old_switch_interval is not None:
            try:
                sys.setswitchinterval(float(self._old_switch_interval))
            except Exception:
                pass
            self._old_switch_interval = None

        if self._gc_was_enabled:
            try:
                gc.enable()
            except Exception:
                pass

        self._active = False
        self._status = LatencyGuardStatus(False, cyclic_gc_disabled=not gc.isenabled())
        return self._status

    def collect_idle(self) -> int:
        """Run a deferred cyclic collection outside the live capture path."""
        try:
            return int(gc.collect())
        except Exception:
            return 0

    def _activate_windows_timer(self) -> bool:
        try:
            winmm = ctypes.WinDLL("winmm", use_last_error=True)
            result = int(winmm.timeBeginPeriod(1))
            self._timer_started = result == 0
            return self._timer_started
        except Exception:
            return False

    def _restore_windows_timer(self) -> None:
        if not self._timer_started:
            return
        try:
            ctypes.WinDLL("winmm", use_last_error=True).timeEndPeriod(1)
        except Exception:
            pass
        self._timer_started = False

    def _disable_windows_power_throttling(self) -> bool:
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            # Clear both execution-speed throttling and the Windows 11 policy
            # that may ignore high-resolution timer requests for background /
            # occluded GUI processes.  This is the most relevant combination for
            # a waveform window that should keep the same pacing when focus moves
            # to another application.
            control = (
                self.PROCESS_POWER_THROTTLING_EXECUTION_SPEED
                | self.PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION
            )
            state = self._POWER_THROTTLING_STATE(
                self.PROCESS_POWER_THROTTLING_CURRENT_VERSION,
                control,
                0,
            )
            ok = bool(kernel32.SetProcessInformation(
                kernel32.GetCurrentProcess(),
                self.PROCESS_POWER_THROTTLING,
                ctypes.byref(state),
                ctypes.sizeof(state),
            ))
            self._power_throttling_changed = ok
            return ok
        except Exception:
            return False

    def _raise_windows_process_priority(self) -> bool:
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            process = kernel32.GetCurrentProcess()
            old = int(kernel32.GetPriorityClass(process))
            if old:
                self._old_process_priority = old
            return bool(kernel32.SetPriorityClass(process, self.ABOVE_NORMAL_PRIORITY_CLASS))
        except Exception:
            return False

    def _restore_windows_process_priority(self) -> None:
        if not self._old_process_priority:
            return
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), int(self._old_process_priority))
        except Exception:
            pass
        self._old_process_priority = None

    def _raise_windows_thread_priority(self) -> bool:
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            thread = kernel32.GetCurrentThread()
            old = int(kernel32.GetThreadPriority(thread))
            # THREAD_PRIORITY_ERROR_RETURN == 0x7fffffff
            if old != 0x7FFFFFFF:
                self._old_thread_priority = old
            return bool(kernel32.SetThreadPriority(thread, self.THREAD_PRIORITY_ABOVE_NORMAL))
        except Exception:
            return False

    def _restore_windows_thread_priority(self) -> None:
        if self._old_thread_priority is None:
            return
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.SetThreadPriority(kernel32.GetCurrentThread(), int(self._old_thread_priority))
        except Exception:
            pass
        self._old_thread_priority = None
