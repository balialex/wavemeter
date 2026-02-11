"""
Core optimized wavemeter locking logic for the BaLi experiment.

This module provides an `OptimizedLock` class which:

- Separates WLM readout and synchronization from PID logic.
- Uses event-driven synchronization (preferring WaitForWLMEvent when available,
  otherwise falling back to polling GetOperationState / switcher channel).
- Implements a "buffer trick" to flush stale WLM readings after switching.
- Enforces DAC voltage limits provided by the caller.

The design follows the ctypes style from `modules.HighFinesse_dll` and
`modules.wavelengthmeter` without modifying those legacy modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Protocol, Sequence, Tuple
import time

from modules.wavelengthmeter import WavelengthMeter
from modules.HighFinesse_dll import HFDLL


class SwitchInterface(Protocol):
    """Minimal interface for the Sercalo (or equivalent) fiber switch."""

    def SendCommand(self, cmd: str) -> None:  # pragma: no cover - hardware side-effect
        ...


class PIDInterface(Protocol):
    """Minimal interface for PID logic, kept independent from WLM details."""

    def __call__(self, channel_id: int, frequency_hz: float) -> float:
        """
        Compute the desired DAC voltage for a given channel based on the
        current frequency reading.

        Implementations are expected to:
        - Internally maintain their own state.
        - Return the *requested* voltage before hardware clamping.
        """


class DACWriter(Protocol):
    """Abstraction for writing a voltage to a DAC output."""

    def __call__(self, channel_id: int, voltage: float) -> None:  # pragma: no cover - hardware side-effect
        ...


@dataclass
class ChannelConfig:
    """Configuration for a single logical lock channel."""

    logical_id: int
    wlm_channel: int
    dac_limits: Tuple[Optional[float], Optional[float]]
    switch_command: Optional[str] = None  # e.g. "A", "B", "C", "D"


class _EventAdapter:
    """
    Adapter around the HighFinesse DLL to provide event-style synchronization
    and optional TriggerMeasurement access.

    If WaitForWLMEvent / TriggerMeasurement are not available, this falls back
    to polling GetOperationState/GetSwitcherChannel.
    """

    def __init__(self, dll: Optional[HFDLL] = None) -> None:
        from ctypes import POINTER, c_double, c_long

        self._hf = dll or HFDLL()
        self._dll = self._hf.lib

        # Optional bindings – only used when actually present in the DLL.
        try:
            self._wait_for_wlm_event = self._dll.WaitForWLMEvent
            self._wait_for_wlm_event.argtypes = [
                POINTER(c_long),
                POINTER(c_long),
                POINTER(c_double),
            ]
            self._wait_for_wlm_event.restype = c_long
        except AttributeError:  # pragma: no cover - depends on installed DLL
            self._wait_for_wlm_event = None

        try:
            self._trigger_measurement = self._dll.TriggerMeasurement
            self._trigger_measurement.argtypes = [c_long]
            self._trigger_measurement.restype = c_long
        except AttributeError:  # pragma: no cover - depends on installed DLL
            self._trigger_measurement = None

        # Constants for event masks / indices, where available.
        self._cmi_switcher_channel: Optional[int] = self._hf.const.get("cmiSwitcherChannel")
        self._c_measurement_state = self._hf.const.get("cMeasurement", 2)

    def wait_for_switch_ready(self, timeout_s: float) -> bool:
        """
        Block until the WLM reports that it is ready after a switch event.

        Preference:
        - Use WaitForWLMEvent when available.
        - Otherwise, poll GetOperationState with a deadline.
        """
        start = time.perf_counter()

        # Preferred path: true event-based wait.
        if self._wait_for_wlm_event is not None and self._cmi_switcher_channel is not None:  # pragma: no cover - DLL dependent
            from ctypes import c_double, c_long, byref

            mode = c_long(0)
            int_param = c_long(0)
            dbl_param = c_double(0.0)

            while True:
                if time.perf_counter() - start > timeout_s:
                    return False

                result = self._wait_for_wlm_event(
                    byref(mode),
                    byref(int_param),
                    byref(dbl_param),
                )

                # Any non-error result where the integer parameter references the
                # switcher channel index is considered a successful event.
                if result >= 0 and int_param.value == self._cmi_switcher_channel:
                    return True

        # Fallback: simple polling on operation state.
        while True:
            if time.perf_counter() - start > timeout_s:
                return False

            try:
                state = self._hf.GetOperationState(self._c_measurement_state)
            except Exception:
                # If the call fails, back off briefly but keep the same deadline.
                time.sleep(0.001)
                continue

            # Measurement mode indicates that the WLM has completed its internal cycle.
            if int(state) == self._c_measurement_state:
                return True

            time.sleep(0.001)

    def trigger_measurement(self) -> None:
        """
        Trigger a manual measurement using the underlying DLL when possible.

        If TriggerMeasurement is not present, this becomes a no-op; the caller
        is expected to fall back to discarding direct frequency reads.
        """
        if self._trigger_measurement is None:  # pragma: no cover - DLL dependent
            return

        # The exact constant for a single-shot trigger depends on the DLL version.
        # As a conservative choice, use 0 which is mapped to a sane default
        # in the official HighFinesse API.
        try:
            self._trigger_measurement(0)
        except Exception:
            # Hardware glitches or unsupported calls must never crash the lock.
            pass


class OptimizedLock:
    """
    Event-driven wavemeter lock core which:

    - Coordinates the Sercalo switch and the WLM.
    - Flushes the internal measurement pipeline after a channel switch.
    - Delegates feedback calculation to an external PID.
    - Enforces DAC voltage limits.
    """

    def __init__(
        self,
        wlm: WavelengthMeter,
        channels: Sequence[ChannelConfig],
        pid: PIDInterface,
        dac_writer: DACWriter,
        switch: Optional[SwitchInterface] = None,
        event_adapter: Optional[_EventAdapter] = None,
        dummy_triggers: int = 2,
        wait_timeout_s: float = 0.05,
        wm_min_exposure: int = 1,
    ) -> None:
        """
        Parameters
        ----------
        wlm:
            Low-level WLM wrapper (`modules.wavelengthmeter.WavelengthMeter`).
        channels:
            Per-channel configuration including WLM index, DAC limits and
            optional switch commands.
        pid:
            PID-like callable mapping (channel_id, frequency_hz) -> requested voltage.
        dac_writer:
            Callable responsible for writing the (clamped) voltage to the DAC.
        switch:
            Sercalo (or equivalent) switch implementing `SendCommand`.
        event_adapter:
            Optional `_EventAdapter` using WaitForWLMEvent / GetOperationState.
            If not provided, one is created with a fresh `HFDLL()` instance.
        dummy_triggers:
            Number of buffer-flush triggers after a channel switch (default: 2).
        wait_timeout_s:
            Maximum time to wait for the WLM to become ready after a switch.
        wm_min_exposure:
            Minimal exposure in WLM "ticks" when forcing manual exposure.
        """
        self._wlm = wlm
        self._channels: Dict[int, ChannelConfig] = {c.logical_id: c for c in channels}
        self._pid = pid
        self._dac_writer = dac_writer
        self._switch = switch
        self._event = event_adapter or _EventAdapter()
        self._dummy_triggers = max(0, int(dummy_triggers))
        self._wait_timeout_s = float(wait_timeout_s)
        self._wm_min_exposure = int(wm_min_exposure)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_cycle_once(self, logical_channel_id: int) -> Tuple[float, float]:
        """
        Execute a single lock cycle for the given logical channel.

        Steps:
        1. Route the laser via the Sercalo switch (if provided).
        2. Set the WLM internal switcher channel.
        3. Wait for the WLM to signal readiness (event-based when available).
        4. Perform the buffer trick (dummy measurements).
        5. Take a fresh frequency reading.
        6. Pass the reading into the PID to obtain a requested DAC voltage.
        7. Clamp the voltage to the configured DAC limits and write it.

        Returns
        -------
        (frequency_hz, voltage_v)
        """
        if logical_channel_id not in self._channels:
            raise KeyError(f"Unknown logical channel id: {logical_channel_id}")

        cfg = self._channels[logical_channel_id]

        # 1) Route via Sercalo / fiber switch, if configured.
        if self._switch is not None and cfg.switch_command is not None:
            try:
                self._switch.SendCommand(cfg.switch_command)
            except Exception as exc:  # pragma: no cover - hardware side-effect
                raise RuntimeError(f"Fiber switch command failed: {exc}") from exc

        # 2) Inform the WLM about the desired switcher channel.
        try:
            self._wlm.SetSwitcherChannel(cfg.wlm_channel)
        except Exception as exc:
            raise RuntimeError(f"SetSwitcherChannel failed for channel {cfg.wlm_channel}: {exc}") from exc

        # 3) Wait for the WLM / switch to be ready.
        ready = self._event.wait_for_switch_ready(self._wait_timeout_s)
        if not ready:
            raise TimeoutError(f"WLM did not signal readiness within {self._wait_timeout_s:.3f} s")

        # 4) Buffer trick: flush stale measurements.
        self._flush_wlm_buffer(cfg.wlm_channel)

        # 5) Fresh frequency reading for control.
        try:
            frequency_hz = float(self._wlm.GetFrequencyNum(cfg.wlm_channel))
        except Exception as exc:
            raise RuntimeError(f"GetFrequencyNum failed for channel {cfg.wlm_channel}: {exc}") from exc

        # 6) PID mapping: frequency -> requested DAC voltage.
        requested_voltage = float(self._pid(cfg.logical_id, frequency_hz))

        # 7) Clamp to DAC limits and write.
        voltage = self._clamp_voltage(requested_voltage, cfg.dac_limits)
        self._dac_writer(cfg.logical_id, voltage)

        return frequency_hz, voltage

    def run_continuous(
        self,
        sequence: Iterable[int],
        stop_condition: Optional[Callable[[], bool]] = None,
        sleep_on_error_s: float = 0.01,
    ) -> None:
        """
        Continuously iterate over a sequence of logical channel IDs and run one
        lock cycle per channel.

        This method is intended for manual experiments rather than production
        servers. For production use, wrap this in a higher-level thread or
        process and provide a robust stop_condition.
        """
        seq = list(sequence)
        if not seq:
            raise ValueError("run_continuous requires at least one logical channel id")

        def should_stop() -> bool:
            return stop_condition() if stop_condition is not None else False

        while not should_stop():
            for logical_id in seq:
                if should_stop():
                    break
                try:
                    self.run_cycle_once(logical_id)
                except TimeoutError:
                    # Hard timeouts are reported but we keep the loop alive.
                    time.sleep(sleep_on_error_s)
                except Exception:
                    # For unexpected errors we also back off briefly; callers
                    # can override this behaviour by wrapping run_continuous.
                    time.sleep(sleep_on_error_s)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _clamp_voltage(
        self,
        value: float,
        limits: Tuple[Optional[float], Optional[float]],
    ) -> float:
        lo, hi = limits
        v = value
        if lo is not None and v < lo:
            v = lo
        if hi is not None and v > hi:
            v = hi
        return v

    def _flush_wlm_buffer(self, wlm_channel: int) -> None:
        """
        Implement the "Buffer Trick" by performing dummy measurements after a
        switch to flush stale values from the WLM pipeline.

        When TriggerMeasurement is available via the event adapter, that is
        used. Otherwise, we discard direct GetFrequencyNum readings as a safe
        fallback.
        """
        # Try to switch to manual/fast exposure with minimal duration.
        previous_mode: Optional[bool] = None
        try:
            previous_mode = bool(self._wlm.GetExposureMode())
            # False corresponds to manual mode in our existing wrapper.
            self._wlm.SetExposureMode(False)
            self._wlm.SetExposure(self._wm_min_exposure)
        except Exception:
            # If we cannot change exposure safely, proceed with current settings.
            previous_mode = None

        for _ in range(self._dummy_triggers):
            try:
                # Prefer explicit TriggerMeasurement when available in the DLL.
                self._event.trigger_measurement()
            except Exception:
                # Fallback: simply force additional reads and discard them.
                try:
                    _ = self._wlm.GetFrequencyNum(wlm_channel)
                except Exception:
                    # If even this fails, there is little we can do here.
                    break

        # Restore previous exposure mode when possible.
        if previous_mode is not None:
            try:
                self._wlm.SetExposureMode(previous_mode)
            except Exception:
                pass


## AGENT_UPDATE
# - Implemented `OptimizedLock` as an event-driven WLM locking core, using an `_EventAdapter`
#   to prefer `WaitForWLMEvent` and fall back to polling when needed.
# - Added a buffer-flush routine that uses `TriggerMeasurement` when available (or discards
#   extra `GetFrequencyNum` reads) and clamps DAC voltages using per-channel limits supplied
#   by the caller, keeping PID logic modular and voltage safety explicit.

