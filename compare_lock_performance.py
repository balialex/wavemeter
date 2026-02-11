"""
Benchmark legacy (sleep-based) vs optimized (event-driven) wavemeter lock cycles.

This script provides:
- A **simulation mode** (default) that runs without hardware using a simple
  WLM and event-model to compare:
    - Legacy method: fixed `time.sleep(0.23)` after each channel switch.
    - Optimized method: `OptimizedLock` with event-based waiting and
      buffer flushing.
- Optional hooks for future **hardware mode** wiring using the existing
  `modules.wavelengthmeter`, `modules.usb_dao`, and `FiberSwitchCommunication`.

Usage examples
--------------
- As a timing script:
    python compare_lock_performance.py --mode sim --cycles 100

- As a pytest module (simulation only, no hardware required):
    pytest -q compare_lock_performance.py
"""

from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple
import random

from fast_wlm_core import (
    ChannelConfig,
    OptimizedLock,
    PIDInterface,
    build_hardware_optimized_lock,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, limits: Tuple[float | None, float | None]) -> float:
    lo, hi = limits
    v = value
    if lo is not None and v < lo:
        v = lo
    if hi is not None and v > hi:
        v = hi
    return v


class SimpleGainPID(PIDInterface):
    """
    Very lightweight PID-like controller used for benchmarking.

    It implements a pure proportional control law:
        V = offset + k * (f - f_set)
    where:
        - V is the requested DAC voltage.
        - f is the current frequency reading.
        - f_set is the target frequency for the channel.
    """

    def __init__(
        self,
        setpoints_hz: Dict[int, float],
        gain_per_hz: float,
        offset_v: float = 0.0,
    ) -> None:
        self._setpoints = dict(setpoints_hz)
        self._gain = float(gain_per_hz)
        self._offset = float(offset_v)

    def __call__(self, channel_id: int, frequency_hz: float) -> float:
        f_set = self._setpoints.get(channel_id, 0.0)
        error = frequency_hz - f_set
        return self._offset + self._gain * error


# ---------------------------------------------------------------------------
# Simulation-only WLM + event adapter
# ---------------------------------------------------------------------------


@dataclass
class _SimChannelState:
    base_frequency_hz: float


class SimulatedWLM:
    """
    Minimal wavemeter simulator that supports:
    - `SetSwitcherChannel`
    - `GetFrequencyNum`
    - `GetExposureMode`, `SetExposureMode`, `SetExposure`

    It models:
    - A finite response time after each channel switch.
    - Simple Gaussian noise around a per-channel base frequency.
    """

    def __init__(
        self,
        base_frequencies_hz: Dict[int, float],
        response_time_s: float = 0.005,
        noise_std_hz: float = 1e6,
    ) -> None:
        self._channels: Dict[int, _SimChannelState] = {
            ch: _SimChannelState(freq) for ch, freq in base_frequencies_hz.items()
        }
        self._response_time_s = float(response_time_s)
        self._noise_std_hz = float(noise_std_hz)
        self._current_channel: int = next(iter(self._channels))
        self._last_switch_time: float = time.perf_counter()
        self._exposure_mode: bool = False  # False ~ manual, True ~ auto
        self._exposure_ticks: int = 1

    def SetSwitcherChannel(self, channel: int) -> None:
        if channel not in self._channels:
            raise KeyError(f"Unknown simulated WLM channel {channel}")
        self._current_channel = channel
        self._last_switch_time = time.perf_counter()

    def _ready(self) -> bool:
        return (time.perf_counter() - self._last_switch_time) >= self._response_time_s

    def GetFrequencyNum(self, channel: int) -> float:
        if channel not in self._channels:
            raise KeyError(f"Unknown simulated WLM channel {channel}")

        # If the simulated integration is not finished yet, return a slightly
        # stale value (previous channel) plus noise.
        if not self._ready():
            base = self._channels[self._current_channel].base_frequency_hz
        else:
            base = self._channels[channel].base_frequency_hz

        noise = random.gauss(0.0, self._noise_std_hz)
        return base + noise

    # Exposure API used by OptimizedLock._flush_wlm_buffer
    def GetExposureMode(self) -> bool:
        return self._exposure_mode

    def SetExposureMode(self, mode: bool) -> None:
        self._exposure_mode = bool(mode)

    def SetExposure(self, ticks: int, num: int = 1, ccd_arr: int = 1) -> None:  # signature compatible shim
        self._exposure_ticks = int(ticks)


class SimEventAdapter:
    """
    Event-style adapter for the simulated WLM.

    It simply waits until the simulated response time has passed after a switch.
    """

    def __init__(self, sim_wlm: SimulatedWLM) -> None:
        self._wlm = sim_wlm

    def wait_for_switch_ready(self, timeout_s: float) -> bool:
        start = time.perf_counter()
        while time.perf_counter() - start <= timeout_s:
            if self._wlm._ready():
                return True
            time.sleep(0.0005)
        return False

    def trigger_measurement(self) -> None:
        # In the simulation we do not need explicit trigger behaviour; the
        # additional calls into GetFrequencyNum during the buffer flush are
        # sufficient to emulate pipeline flushing.
        return


# ---------------------------------------------------------------------------
# Benchmark runners
# ---------------------------------------------------------------------------


def run_legacy_benchmark(
    n_cycles: int,
    channels: Iterable[ChannelConfig],
    wlm,
    pid: PIDInterface,
    fixed_sleep_s: float = 0.23,
) -> Tuple[List[float], List[float]]:
    """
    Legacy method: fixed sleep after each switch, then read WLM and apply PID.

    This approximates the current BaLi implementation where a hard-coded
    `time.sleep(0.23)` dominates the cycle time.
    """
    times: List[float] = []
    freqs: List[float] = []
    channels_list = list(channels)

    for _ in range(n_cycles):
        for cfg in channels_list:
            t0 = time.perf_counter()
            wlm.SetSwitcherChannel(cfg.wlm_channel)
            time.sleep(fixed_sleep_s)
            f = float(wlm.GetFrequencyNum(cfg.wlm_channel))
            _ = pid(cfg.logical_id, f)  # PID output not used directly in the benchmark
            t1 = time.perf_counter()
            times.append(t1 - t0)
            freqs.append(f)

    return times, freqs


def run_optimized_benchmark(
    n_cycles: int,
    opt_lock: OptimizedLock,
    logical_ids: Iterable[int],
) -> Tuple[List[float], List[float]]:
    """Optimized method: use `OptimizedLock.run_cycle_once` for each channel."""
    times: List[float] = []
    freqs: List[float] = []
    ids = list(logical_ids)

    for _ in range(n_cycles):
        for logical_id in ids:
            t0 = time.perf_counter()
            f, _ = opt_lock.run_cycle_once(logical_id)
            t1 = time.perf_counter()
            times.append(t1 - t0)
            freqs.append(f)

    return times, freqs


def summarize_metrics(
    cycle_times_s: List[float],
    freqs_hz: List[float],
) -> Dict[str, float]:
    """Compute mean / std for cycle time and frequency."""
    return {
        "cycle_time_mean_s": statistics.mean(cycle_times_s),
        "cycle_time_std_s": statistics.pstdev(cycle_times_s)
        if len(cycle_times_s) > 1
        else 0.0,
        "freq_mean_hz": statistics.mean(freqs_hz),
        "freq_std_hz": statistics.pstdev(freqs_hz) if len(freqs_hz) > 1 else 0.0,
    }


def compare_simulated(n_cycles: int = 100) -> Dict[str, Dict[str, float]]:
    """
    Run a full simulated comparison of legacy vs optimized locking.

    Returns a nested dict:
    {
        "legacy": {...metrics...},
        "optimized": {...metrics...},
    }
    """
    # Two example channels with arbitrary but distinct base frequencies.
    base_freqs = {1: 384.23e12, 2: 461.31e12}

    channels = [
        ChannelConfig(logical_id=1, wlm_channel=1, dac_limits=(0.0, 10.0)),
        ChannelConfig(logical_id=2, wlm_channel=2, dac_limits=(0.0, 10.0)),
    ]

    setpoints = base_freqs  # ideal setpoint equals the nominal base frequency
    pid = SimpleGainPID(setpoints_hz=setpoints, gain_per_hz=-1e-9, offset_v=5.0)

    sim_wlm = SimulatedWLM(base_freqs)
    sim_event = SimEventAdapter(sim_wlm)

    def dummy_dac_writer(_channel_id: int, _voltage: float) -> None:
        # In simulation we do not need to drive real hardware.
        return

    opt_lock = OptimizedLock(
        wlm=sim_wlm,
        channels=channels,
        pid=pid,
        dac_writer=dummy_dac_writer,
        switch=None,
        event_adapter=sim_event,
        dummy_triggers=2,
        wait_timeout_s=0.05,
    )

    legacy_times, legacy_freqs = run_legacy_benchmark(
        n_cycles=n_cycles,
        channels=channels,
        wlm=sim_wlm,
        pid=pid,
        fixed_sleep_s=0.23,
    )
    opt_times, opt_freqs = run_optimized_benchmark(
        n_cycles=n_cycles,
        opt_lock=opt_lock,
        logical_ids=[1, 2],
    )

    return {
        "legacy": summarize_metrics(legacy_times, legacy_freqs),
        "optimized": summarize_metrics(opt_times, opt_freqs),
    }


# ---------------------------------------------------------------------------
# Hardware benchmarking
# ---------------------------------------------------------------------------


def _parse_dac_limits_from_context(
    path: str = "docs/CONTEXT.md",
) -> Dict[int, Tuple[float | None, float | None]]:
    """
    Parse DAC limit definitions from CONTEXT.md.

    Expected format per channel (one per line), for example:
        - DAC_LIMIT_1: [0.0, 10.0]
        - DAC_LIMIT_2: [0.0, 10.0]

    Returns a mapping from logical channel id to (min, max) tuple.
    """
    import os
    import re

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"CONTEXT file '{path}' not found. Hardware mode requires explicit DAC limits."
        )

    limits: Dict[int, Tuple[float | None, float | None]] = {}
    pattern = re.compile(r"DAC_LIMIT_(\d+)\s*:\s*\[([^\]]+)\]")

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if not match:
                continue
            ch_id = int(match.group(1))
            parts = [p.strip() for p in match.group(2).split(",")]
            if len(parts) != 2:
                continue
            try:
                lo = float(parts[0]) if parts[0].lower() != "none" else None
                hi = float(parts[1]) if parts[1].lower() != "none" else None
            except ValueError:
                continue
            limits[ch_id] = (lo, hi)

    if not limits:
        raise RuntimeError(
            "No DAC_LIMIT_* entries were found in docs/CONTEXT.md.\n"
            "Please add entries like '- DAC_LIMIT_1: [0.0, 10.0]' before using --mode hardware."
        )

    return limits


def _build_hardware_channels_from_context() -> List[ChannelConfig]:
    """
    Build `ChannelConfig` objects using DAC limits parsed from CONTEXT.md.

    The default mapping assumes:
    - WLM channels match logical channel ids.
    - DAC channels are `logical_id - 1`.
    - Sercalo commands follow A/B/C/D for channels 1–4.
    """
    dac_limits = _parse_dac_limits_from_context()

    cmd_map = {1: "A", 2: "B", 3: "C", 4: "D"}
    channels: List[ChannelConfig] = []
    for logical_id, limits in sorted(dac_limits.items()):
        switch_cmd = cmd_map.get(logical_id)
        channels.append(
            ChannelConfig(
                logical_id=logical_id,
                wlm_channel=logical_id,
                dac_limits=limits,
                switch_command=switch_cmd,
                dac_channel=logical_id - 1,
            )
        )
    return channels


def run_hardware_benchmark(
    n_cycles: int,
    context_path: str = "docs/CONTEXT.md",
) -> Dict[str, Dict[str, float]]:
    """
    Run a hardware benchmark comparing legacy vs optimized locking.

    Safety interlocks:
    - DAC limits must be declared in CONTEXT.md via DAC_LIMIT_* entries.
    - A dry-run phase is executed first, which:
        - Switches Sercalo channels.
        - Waits for WLM readiness and reads frequencies.
        - Does NOT write any DAC voltages.
    """
    from modules.wavelengthmeter import WavelengthMeter
    from modules.FiberSwitchCommunication import FiberSwitch
    from modules.usb_dao import USB_DAO

    # Verify DAC limits from CONTEXT.md.
    _ = _parse_dac_limits_from_context(path=context_path)
    channels = _build_hardware_channels_from_context()

    # Shared hardware handles.
    wlm = WavelengthMeter()
    daq = USB_DAO()
    switch = FiberSwitch(port=None, baudrate=115200)

    # Simple PID used for benchmarking; gains are intentionally conservative.
    setpoints = {cfg.logical_id: 0.0 for cfg in channels}
    pid = SimpleGainPID(setpoints_hz=setpoints, gain_per_hz=0.0, offset_v=0.0)

    # -----------------------------
    # Dry-run: no DAC output
    # -----------------------------
    print("=== Hardware Dry-Run: Sercalo switching & WLM readout (no DAC output) ===")

    def _dry_dac_writer(_channel_id: int, _voltage: float) -> None:
        # Explicitly drop DAC writes during the dry-run phase.
        return

    dry_lock = OptimizedLock(
        wlm=wlm,
        channels=channels,
        pid=pid,
        dac_writer=_dry_dac_writer,
        switch=switch,
        event_adapter=None,  # real DLL-based adapter (WaitForWLMEvent / polling)
    )

    dry_cycles = max(5, min(20, n_cycles))
    dry_freqs: List[float] = []
    for i in range(dry_cycles):
        for cfg in channels:
            f, _ = dry_lock.run_cycle_once(cfg.logical_id)
            dry_freqs.append(f)
            if f <= 0:
                raise RuntimeError(
                    f"Dry-run aborted: invalid WLM frequency {f} on logical channel {cfg.logical_id}"
                )
            print(f"Dry-run cycle {i+1}, channel {cfg.logical_id}: f = {f/1e12:.6f} THz")

    # -----------------------------
    # Legacy vs optimized benchmark
    # -----------------------------
    print("\n=== Hardware Benchmark: Legacy vs Optimized ===")

    # Legacy: sleep-based loop using the same WLM instance.
    legacy_times, legacy_freqs = run_legacy_benchmark(
        n_cycles=n_cycles,
        channels=channels,
        wlm=wlm,
        pid=pid,
        fixed_sleep_s=0.23,
    )

    # Optimized: event-driven lock; uses shared WLM + DAQ + Sercalo switch.
    pid_gains = (0.0, 0.0, 0.0)
    opt_lock = build_hardware_optimized_lock(
        channels=channels,
        setpoints_hz=setpoints,
        pid_gains=pid_gains,
        switch=switch,
        event_adapter=None,
        wlm=wlm,
        daq=daq,
    )

    opt_times: List[float] = []
    opt_freqs: List[float] = []
    baseline_ms = 230.0
    cycle_index = 0

    print("\nCycle | Method     | t_cycle_ms | baseline_ms")
    print("------+-----------+-----------+------------")

    for _ in range(n_cycles):
        for cfg in channels:
            cycle_index += 1
            t0 = time.perf_counter()
            f, _ = opt_lock.run_cycle_once(cfg.logical_id)
            t1 = time.perf_counter()
            dt = t1 - t0
            opt_times.append(dt)
            opt_freqs.append(f)
            print(
                f"{cycle_index:5d} | optimized | {dt*1e3:9.2f} | {baseline_ms:10.2f}"
            )

    return {
        "legacy": summarize_metrics(legacy_times, legacy_freqs),
        "optimized": summarize_metrics(opt_times, opt_freqs),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare legacy (sleep-based) vs optimized (event-based) wavemeter lock performance.",
    )
    parser.add_argument(
        "--mode",
        choices=["sim", "hardware"],
        default="sim",
        help="Benchmark mode: 'sim' (no hardware) or 'hardware' (real devices).",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=100,
        help="Number of full channel cycles to run for each method.",
    )
    args = parser.parse_args()

    if args.mode == "sim":
        results = compare_simulated(n_cycles=args.cycles)
    elif args.mode == "hardware":  # pragma: no cover - requires lab hardware
        results = run_hardware_benchmark(n_cycles=args.cycles)
    else:  # pragma: no cover - defensive
        raise NotImplementedError(f"Unknown mode '{args.mode}'")

    legacy = results["legacy"]
    optimized = results["optimized"]

    print("=== Legacy vs Optimized Lock Performance (Simulation) ===")
    print(f"Cycles per method: {args.cycles}")
    print()
    print("Legacy:")
    print(f"  Cycle time mean: {legacy['cycle_time_mean_s'] * 1e3:.2f} ms")
    print(f"  Cycle time std:  {legacy['cycle_time_std_s'] * 1e3:.2f} ms")
    print(f"  Freq std:        {legacy['freq_std_hz'] / 1e6:.3f} MHz")
    print()
    print("Optimized:")
    print(f"  Cycle time mean: {optimized['cycle_time_mean_s'] * 1e3:.2f} ms")
    print(f"  Cycle time std:  {optimized['cycle_time_std_s'] * 1e3:.2f} ms")
    print(f"  Freq std:        {optimized['freq_std_hz'] / 1e6:.3f} MHz")


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()


# ---------------------------------------------------------------------------
# Pytest-style checks (simulation only)
# ---------------------------------------------------------------------------


def test_optimized_not_slower_sim():
    """Optimized cycle time should be significantly faster than legacy in simulation."""
    results = compare_simulated(n_cycles=30)
    legacy = results["legacy"]
    optimized = results["optimized"]
    assert optimized["cycle_time_mean_s"] < 0.5 * legacy["cycle_time_mean_s"]


def test_optimized_stability_reasonable_sim():
    """
    Optimized frequency noise should remain comparable to legacy.

    We allow some tolerance because the buffer trick and different timing
    may slightly change the effective integration statistics.
    """
    results = compare_simulated(n_cycles=50)
    legacy = results["legacy"]
    optimized = results["optimized"]
    assert optimized["freq_std_hz"] <= 2.0 * legacy["freq_std_hz"]


## AGENT_UPDATE
# - Extended `compare_lock_performance.py` with a hardware benchmarking path that
#   verifies per-channel DAC limits from `docs/CONTEXT.md`, performs a dry-run
#   (Sercalo switching and WLM readout without DAC output), and then compares
#   legacy (fixed 230 ms sleep) vs event-driven `OptimizedLock` with live
#   cycle-time telemetry against the 230 ms baseline.
# - Kept a simulation-only path and pytest checks so performance comparisons and
#   stability/accuracy metrics can still be evaluated without lab hardware.

