"""
Hardware-facing diagnostic to test Sercalo fiber switching and WLM readiness.

This script performs a single channel switch and logs:

- BEFORE sending the switch command:
  - Old WLM active channel and port (`GetActiveChannel`)
  - Old WLM switcher channel (`GetSwitcherChannel`)
  - Old exposure mode and exposure ticks
  - Old frequency for the current switcher channel
- AFTER sending the switch command and waiting for readiness:
  - Result of the event-based wait (`wait_for_switch_ready`)
  - New WLM active channel and port
  - New WLM switcher channel
  - New exposure mode and exposure ticks
  - New frequency for the target WLM channel
  - Wall-clock time until the WLM reported readiness after the switch

Usage (standalone, without the web lock running):

    python hw_switch_diagnostic.py --target 2

You can also import `run_hardware_switch_test` from an interactive session
and pass in existing hardware handles (e.g. `wvm`, `FiberSwitch`, `_EventAdapter`)
as well as your controller and mutex:

    from hw_switch_diagnostic import run_hardware_switch_test
    run_hardware_switch_test(
        wlm=wvm,
        switch=FiberSwitch,
        event_adapter=event_adapter,
        target_channel=2,
        lock_controller=lck.cntrl,
        wm_mutex=mutex,
    )

In that case the helper will pause the controller and use the provided mutex
to keep WLM access serialized during the diagnostic.
"""

from __future__ import annotations

import argparse
import time
from typing import Optional

from modules.wavelengthmeter import WavelengthMeter
from modules.FiberSwitchCommunication import FiberSwitch

from fast_wlm_core import _EventAdapter


def _channel_to_switch_command(channel: int) -> str:
    """
    Map a numeric WLM channel (1–4) to a Sercalo switch command ("A"–"D").

    This follows the convention used in the existing BaLi code, where
    WMCH1..WMCH4 are mapped to A..D on the fiber switch.
    """
    mapping = {1: "A", 2: "B", 3: "C", 4: "D"}
    if channel not in mapping:
        raise ValueError(f"Unsupported target channel {channel!r}; expected 1–4.")
    return mapping[channel]


def _read_state(wlm: WavelengthMeter, channel_for_freq: Optional[int]) -> dict:
    """Read a snapshot of the current WLM state for logging."""
    try:
        active_channel, active_port = wlm.GetActiveChannel()
    except Exception as exc:
        active_channel, active_port = -1, -1
        print(f"[WARN] GetActiveChannel failed: {exc}")

    try:
        switcher_channel = int(wlm.GetSwitcherChannel())
    except Exception as exc:
        switcher_channel = -1
        print(f"[WARN] GetSwitcherChannel failed: {exc}")

    try:
        exposure_mode = bool(wlm.GetExposureMode())
    except Exception as exc:
        exposure_mode = False
        print(f"[WARN] GetExposureMode failed: {exc}")

    try:
        exposure_ticks = int(wlm.GetExposure())
    except Exception as exc:
        exposure_ticks = -1
        print(f"[WARN] GetExposure failed: {exc}")

    freq_value: float
    if channel_for_freq is None or channel_for_freq <= 0:
        # Fall back to the default front-channel frequency.
        try:
            freq_value = float(wlm.GetFrequency())
        except Exception as exc:
            freq_value = float("nan")
            print(f"[WARN] GetFrequency failed: {exc}")
    else:
        try:
            freq_value = float(wlm.GetFrequencyNum(channel_for_freq))
        except Exception as exc:
            freq_value = float("nan")
            print(f"[WARN] GetFrequencyNum({channel_for_freq}) failed: {exc}")

    return {
        "active_channel": active_channel,
        "active_port": active_port,
        "switcher_channel": switcher_channel,
        "exposure_mode": exposure_mode,
        "exposure_ticks": exposure_ticks,
        "frequency_hz": freq_value,
    }


def _print_state(label: str, state: dict) -> None:
    """Pretty-print a state snapshot with a label prefix."""
    freq_thz = state["frequency_hz"] / 1e12 if state["frequency_hz"] == state["frequency_hz"] else float("nan")
    print(
        f"[{label}] "
        f"active=({state['active_channel']}, port {state['active_port']}), "
        f"switcher={state['switcher_channel']}, "
        f"exposure_mode={'auto' if state['exposure_mode'] else 'manual'}, "
        f"exposure_ticks={state['exposure_ticks']}, "
        f"freq={freq_thz:.9f} THz"
    )


def run_hardware_switch_test(
    wlm: WavelengthMeter,
    switch: FiberSwitch,
    event_adapter: _EventAdapter,
    target_channel: int,
    timeout_s: float = 0.1,
    *,
    lock_controller: Optional[object] = None,
    wm_mutex: Optional[object] = None,
) -> None:
    """
    Perform a single hardware switch to `target_channel` and log before/after state.

    Parameters
    ----------
    wlm:
        Existing `WavelengthMeter` instance (started by caller).
    switch:
        `FiberSwitch` instance used to route the beam.
    event_adapter:
        `_EventAdapter` instance that provides `wait_for_switch_ready`.
    target_channel:
        Target WLM channel index (int). Also used to derive the Sercalo command.
    timeout_s:
        Maximum time to wait for the WLM to signal readiness after the switch.
    lock_controller:
        Optional controller object exposing `pause()` / `resume()` (e.g. `lck.cntrl`).
        If provided, the diagnostic will pause before accessing the WLM and resume
        afterwards.
    wm_mutex:
        Optional mutex object (e.g. `threading.Lock`) protecting WLM access in the
        main lock code. If provided, it is acquired around the diagnostic section.
    """
    switch_cmd = _channel_to_switch_command(target_channel)

    def _enter_critical():
        if lock_controller is not None:
            try:
                print("[INFO] Pausing lock controller for diagnostic.")
                lock_controller.pause()
            except Exception as exc:
                print(f"[WARN] Failed to pause controller: {exc}")

    def _exit_critical():
        if lock_controller is not None:
            try:
                print("[INFO] Resuming lock controller after diagnostic.")
                lock_controller.resume()
            except Exception as exc:
                print(f"[WARN] Failed to resume controller: {exc}")

    _enter_critical()
    ctx = wm_mutex if wm_mutex is not None else None

    try:
        if ctx is not None:
            with ctx:  # type: ignore[abstract]
                _run_single_switch(
                    wlm=wlm,
                    switch=switch,
                    event_adapter=event_adapter,
                    target_channel=target_channel,
                    switch_cmd=switch_cmd,
                    timeout_s=timeout_s,
                )
        else:
            _run_single_switch(
                wlm=wlm,
                switch=switch,
                event_adapter=event_adapter,
                target_channel=target_channel,
                switch_cmd=switch_cmd,
                timeout_s=timeout_s,
            )
    finally:
        _exit_critical()


def _run_single_switch(
    wlm: WavelengthMeter,
    switch: FiberSwitch,
    event_adapter: _EventAdapter,
    target_channel: int,
    switch_cmd: str,
    timeout_s: float,
) -> None:
    """
    Core logic for a single switch, assuming any higher-level pause/mutex logic
    has already been applied.
    """
    print("=== Hardware WLM Switch Diagnostic ===")
    print(f"Target WLM channel: {target_channel}")
    print(f"Sercalo command:    {switch_cmd}")
    print(f"Wait timeout:       {timeout_s * 1e3:.1f} ms")
    print()

    # BEFORE: read current state.
    # Use the current switcher channel (if > 0) as the reference for frequency.
    try:
        current_switcher = int(wlm.GetSwitcherChannel())
    except Exception:
        current_switcher = -1
    before_state = _read_state(wlm, channel_for_freq=current_switcher if current_switcher > 0 else None)
    _print_state("BEFORE", before_state)

    # Send switch command and set WLM switcher channel.
    print("\n[INFO] Sending fiber switch command and updating WLM switcher channel...")
    t0 = time.perf_counter()
    try:
        switch.SendCommand(switch_cmd)
    except Exception as exc:
        print(f"[ERROR] Fiber switch command '{switch_cmd}' failed: {exc}")
        return

    try:
        wlm.SetSwitcherChannel(target_channel)
    except Exception as exc:
        print(f"[ERROR] SetSwitcherChannel({target_channel}) failed: {exc}")
        return

    # Wait for readiness using the event adapter.
    ready = event_adapter.wait_for_switch_ready(timeout_s=timeout_s)
    dt = time.perf_counter() - t0
    print(f"[POLL] ready={ready}, elapsed={dt * 1e3:.3f} ms")
    if not ready:
        print("[WARN] WLM did not report readiness within the timeout window.")

    # AFTER: state for the target channel, with no additional buffer flushing.
    after_state = _read_state(wlm, channel_for_freq=target_channel)
    _print_state("AFTER", after_state)
    print(f"[TIMING] t_ready_after_switch = {dt * 1e3:.3f} ms")


def _build_default_handles(port: Optional[str], baudrate: int) -> tuple[WavelengthMeter, FiberSwitch, _EventAdapter]:
    """
    Build default WLM, FiberSwitch, and event adapter instances for standalone use.

    The WLM is started in measurement mode; the caller is responsible for calling
    `stop()` when done.
    """
    wlm = WavelengthMeter()
    wlm.start()

    # The FiberSwitch class currently overrides the port internally, but we keep
    # the parameter for future compatibility and clarity.
    fs = FiberSwitch(port=port, baudrate=baudrate)

    event_adapter = _EventAdapter()
    return wlm, fs, event_adapter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnostic: switch Sercalo channel and wait for WLM readiness using WaitForWLMEvent / polling.",
    )
    parser.add_argument(
        "--target",
        type=int,
        required=True,
        help="Target WLM channel index (1–4). Also mapped to Sercalo A–D.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.1,
        help="Maximum wait time in seconds for WLM readiness (default: 0.1).",
    )
    parser.add_argument(
        "--port",
        type=str,
        default=None,
        help="Optional serial port for the fiber switch (may be overridden by driver).",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=115200,
        help="Baud rate for the fiber switch (default: 115200).",
    )

    args = parser.parse_args()

    wlm, fs, event_adapter = _build_default_handles(port=args.port, baudrate=args.baudrate)
    try:
        run_hardware_switch_test(
            wlm=wlm,
            switch=fs,
            event_adapter=event_adapter,
            target_channel=args.target,
            timeout_s=args.timeout,
        )
    finally:
        try:
            wlm.stop()
        except Exception:
            pass
        try:
            fs.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()


## AGENT_UPDATE
# - Added `hw_switch_diagnostic.py`, a standalone hardware diagnostic that switches a target
#   WLM channel via the Sercalo fiber switch, waits for WLM readiness using the `_EventAdapter`
#   (preferring `WaitForWLMEvent` and falling back to polling), and logs detailed before/after
#   channel, exposure, frequency, and timing information, with optional hooks to pause an
#   existing lock controller and share the WLM mutex when used inside the main experiment.

