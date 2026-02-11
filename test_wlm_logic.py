"""
Unit tests for the optimized wavemeter locking logic.

These tests:
- Use pytest + unittest.mock.
- Run entirely without the HighFinesse DLL or any lab hardware.
- Validate that:
    - `OptimizedLock` performs the expected DLL-style calls.
    - The buffer-flush logic toggles exposure modes correctly.
    - DAC outputs are clamped to per-channel limits.
    - `_EventAdapter` falls back to `GetOperationState` polling when
      `WaitForWLMEvent` is not available.
"""

from __future__ import annotations

from typing import Dict, Tuple, Optional

import ctypes
from unittest import mock

import pytest

from fast_wlm_core import ChannelConfig, OptimizedLock, PIDInterface, _EventAdapter


class FakeWLM:
    """Minimal fake wavemeter used to drive `OptimizedLock` in tests."""

    def __init__(self, initial_mode: bool = True) -> None:
        self.switcher_channel_calls: list[int] = []
        self.frequency_calls: list[int] = []
        self.exposure_mode_calls: list[bool] = []
        self.exposure_values: list[int] = []

        self._exposure_mode: bool = initial_mode
        self._frequency_by_channel: Dict[int, float] = {1: 384.23e12}

    # Methods used by OptimizedLock
    def SetSwitcherChannel(self, channel: int) -> None:
        self.switcher_channel_calls.append(channel)

    def GetFrequencyNum(self, channel: int) -> float:
        self.frequency_calls.append(channel)
        return self._frequency_by_channel.get(channel, 0.0)

    def GetExposureMode(self) -> bool:
        return self._exposure_mode

    def SetExposureMode(self, mode: bool) -> None:
        self._exposure_mode = bool(mode)
        self.exposure_mode_calls.append(self._exposure_mode)

    def SetExposure(self, ticks: int, num: int = 1, ccd_arr: int = 1) -> None:
        self.exposure_values.append(int(ticks))


class DummyPID(PIDInterface):
    """Simple PID that always returns the same voltage, to trigger clamping."""

    def __init__(self, voltage: float) -> None:
        self.voltage = float(voltage)
        self.calls: list[Tuple[int, float]] = []

    def __call__(self, channel_id: int, frequency_hz: float) -> float:
        self.calls.append((channel_id, frequency_hz))
        return self.voltage


class CountingEventAdapter:
    """Event adapter stub that always reports ready and counts triggers."""

    def __init__(self) -> None:
        self.trigger_count = 0
        self.wait_calls: list[float] = []

    def wait_for_switch_ready(self, timeout_s: float) -> bool:
        self.wait_calls.append(timeout_s)
        return True

    def trigger_measurement(self) -> None:
        self.trigger_count += 1


def _make_single_channel_lock(
    pid_voltage: float,
    dac_limits: Tuple[float, float],
    dummy_triggers: int = 2,
    initial_exposure_mode: bool = True,
) -> Tuple[OptimizedLock, FakeWLM, CountingEventAdapter, list[Tuple[int, float]]]:
    fake_wlm = FakeWLM(initial_mode=initial_exposure_mode)
    event_adapter = CountingEventAdapter()
    pid = DummyPID(pid_voltage)
    dac_calls: list[Tuple[int, float]] = []

    def dac_writer(ch: int, v: float) -> None:
        dac_calls.append((ch, v))

    cfg = ChannelConfig(
        logical_id=1,
        wlm_channel=1,
        dac_limits=dac_limits,
        switch_command=None,
        dac_channel=None,
    )

    lock = OptimizedLock(
        wlm=fake_wlm,
        channels=[cfg],
        pid=pid,
        dac_writer=dac_writer,
        switch=None,
        event_adapter=event_adapter,
        dummy_triggers=dummy_triggers,
        wait_timeout_s=0.01,
    )
    return lock, fake_wlm, event_adapter, dac_calls


def test_run_cycle_calls_switcher_and_triggers_buffer():
    """OptimizedLock should set the WLM switcher channel and trigger N dummy measurements."""
    dummy_triggers = 3
    lock, fake_wlm, event_adapter, _ = _make_single_channel_lock(
        pid_voltage=0.0,
        dac_limits=(0.0, 5.0),
        dummy_triggers=dummy_triggers,
    )

    freq, _ = lock.run_cycle_once(1)
    assert freq == pytest.approx(384.23e12)

    # SetSwitcherChannel called exactly once with the configured WLM channel.
    assert fake_wlm.switcher_channel_calls == [1]
    # Buffer trick uses TriggerMeasurement N times via the event adapter.
    assert event_adapter.trigger_count == dummy_triggers


def test_buffer_trick_toggles_exposure_and_restores_mode():
    """Exposure mode should switch to manual/fast during flushing and restore afterwards."""
    lock, fake_wlm, event_adapter, _ = _make_single_channel_lock(
        pid_voltage=0.0,
        dac_limits=(0.0, 5.0),
        dummy_triggers=2,
        initial_exposure_mode=True,  # Start in auto mode
    )

    lock.run_cycle_once(1)

    # At least one call to disable auto exposure and one to restore it.
    # We expect the first call to set manual mode (False) and the last to
    # restore the original auto mode (True).
    assert fake_wlm.exposure_mode_calls[0] is False
    assert fake_wlm.exposure_mode_calls[-1] is True
    # Buffer trick should have called into the event adapter for triggers.
    assert event_adapter.trigger_count == 2


def test_dac_output_is_clamped_to_limits():
    """DAC output passed to the writer must respect per-channel dac_limits."""
    # PID requests a voltage well above the configured upper limit.
    requested_voltage = 100.0
    dac_limits = (0.0, 5.0)
    lock, _fake_wlm, _event_adapter, dac_calls = _make_single_channel_lock(
        pid_voltage=requested_voltage,
        dac_limits=dac_limits,
    )

    _freq, v = lock.run_cycle_once(1)
    # Check what the DAC writer actually saw.
    assert dac_calls, "DAC writer was not called"
    ch, written_v = dac_calls[-1]
    assert ch == 1
    assert written_v == dac_limits[1]  # clamped to upper limit
    # The value returned from run_cycle_once should match the clamped voltage.
    assert v == written_v


def test_event_adapter_uses_waitforwlmevent_when_available():
    """_EventAdapter should use WaitForWLMEvent and treat a matching event as ready."""

    class FakeDLL:
        def __init__(self) -> None:
            self.calls = 0

        def WaitForWLMEvent(
            self,
            mode_ptr: ctypes.POINTER(ctypes.c_long),
            int_ptr: ctypes.POINTER(ctypes.c_long),
            dbl_ptr: ctypes.POINTER(ctypes.c_double),
        ) -> int:
            # Simulate a single successful event for cmiSwitcherChannel.
            self.calls += 1
            int_ptr.contents.value = 203  # matches cmiSwitcherChannel below
            return 0

    class FakeHF:
        def __init__(self) -> None:
            self.lib = FakeDLL()
            self.const = {"cmiSwitcherChannel": 203, "cMeasurement": 2}

        def GetOperationState(self, _index: int) -> int:
            # Should not be used in this scenario.
            raise AssertionError("GetOperationState should not be called")

    fake_hf = FakeHF()
    adapter = _EventAdapter(dll=fake_hf)  # type: ignore[arg-type]

    ready = adapter.wait_for_switch_ready(timeout_s=0.01)
    assert ready is True
    assert fake_hf.lib.calls >= 1


def test_event_adapter_fallbacks_to_getoperationstate_when_no_event():
    """When WaitForWLMEvent is unavailable, _EventAdapter should fall back to GetOperationState polling."""

    class FakeDLLNoEvent:
        """DLL without WaitForWLMEvent attribute."""

        pass

    class FakeHFNoEvent:
        def __init__(self) -> None:
            self.lib = FakeDLLNoEvent()
            self.const = {"cmiSwitcherChannel": 203, "cMeasurement": 2}
            self.get_operation_calls = 0

        def GetOperationState(self, index: int) -> int:
            self.get_operation_calls += 1
            # Immediately report measurement mode.
            return 2

    fake_hf = FakeHFNoEvent()
    adapter = _EventAdapter(dll=fake_hf)  # type: ignore[arg-type]

    ready = adapter.wait_for_switch_ready(timeout_s=0.01)
    assert ready is True
    assert fake_hf.get_operation_calls >= 1


def test_event_adapter_uses_mocked_hfdll_when_instantiated_without_dll():
    """
    Ensure that tests can patch HFDLL so that _EventAdapter does not touch the real DLL.

    This also demonstrates use of unittest.mock as requested.
    """

    class FakeDLL:
        def __init__(self) -> None:
            self.calls = 0

        def WaitForWLMEvent(
            self,
            mode_ptr: ctypes.POINTER(ctypes.c_long),
            int_ptr: ctypes.POINTER(ctypes.c_long),
            dbl_ptr: ctypes.POINTER(ctypes.c_double),
        ) -> int:
            self.calls += 1
            int_ptr.contents.value = 203
            return 0

    class FakeHF:
        def __init__(self) -> None:
            self.lib = FakeDLL()
            self.const = {"cmiSwitcherChannel": 203, "cMeasurement": 2}

        def GetOperationState(self, index: int) -> int:
            return 2

    fake_hf = FakeHF()

    with mock.patch("fast_wlm_core.HFDLL", return_value=fake_hf):
        adapter = _EventAdapter()  # should use the patched HFDLL
        ready = adapter.wait_for_switch_ready(timeout_s=0.01)
        assert ready is True
        assert fake_hf.lib.calls >= 1


## AGENT_UPDATE
# - Added `test_wlm_logic.py` to exercise the optimized wavemeter locking core
#   without any real DLLs or hardware, verifying buffer flushing, exposure
#   toggling, DAC clamping, and `_EventAdapter`'s use of WaitForWLMEvent /
#   GetOperationState via mocks so the suite remains cross-platform.

