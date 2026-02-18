"""
Hardware-facing diagnostic to exercise the wavemeter buffer-flush behaviour
("buffer trick") on a single WLM channel, without touching DACs or the fiber
switch.

This script:

- Takes a series of raw `GetFrequencyNum` samples on a selected WLM channel.
- Applies the same buffer-flush sequence used in `OptimizedLock._flush_wlm_buffer`:
  - Switches to manual/fast exposure with minimal ticks.
  - Issues a configurable number of dummy triggers via `_EventAdapter`.
  - Falls back to extra `GetFrequencyNum` calls when triggers are unavailable.
  - Restores the previous exposure mode.
- Takes another series of raw samples and prints simple statistics for
  comparison.

Usage (standalone, without the web lock running):

    python hw_buffer_diagnostic.py --channel 2 --dummy-triggers 3 --samples 5

You can also import `run_buffer_trick_test` from an interactive session and
reuse an existing `WavelengthMeter` and `_EventAdapter`:

    from hw_buffer_diagnostic import run_buffer_trick_test
    from fast_wlm_core import _EventAdapter

    event_adapter = _EventAdapter()
    run_buffer_trick_test(
        wlm=wvm,
        event_adapter=event_adapter,
        channel=2,
        dummy_triggers=3,
        wm_min_exposure=1,
        samples=5,
    )

If you call this from inside the main lock process, pause the controller and
use the shared WLM mutex:

    lck.cntrl.pause()
    with mutex:
        run_buffer_trick_test(...)
    lck.cntrl.resume()
"""

from __future__ import annotations

import argparse
import statistics
from typing import List

from modules.wavelengthmeter import WavelengthMeter

from fast_wlm_core import _EventAdapter


def _freq_to_thz(value_hz: float) -> float:
    return value_hz / 1e12


def run_buffer_trick_test(
    wlm: WavelengthMeter,
    event_adapter: _EventAdapter,
    channel: int,
    dummy_triggers: int = 2,
    wm_min_exposure: int = 1,
    samples: int = 5,
) -> None:
    """
    Collect pre-flush samples, apply the buffer trick, and collect post-flush samples.

    Parameters
    ----------
    wlm:
        Existing `WavelengthMeter` instance (started by the caller).
    event_adapter:
        `_EventAdapter` instance used to access `trigger_measurement`.
    channel:
        WLM channel index to probe with `GetFrequencyNum`.
    dummy_triggers:
        Number of dummy triggers to issue during the buffer flush.
    wm_min_exposure:
        Minimal exposure ticks to set while flushing the buffer.
    samples:
        Number of raw samples to record before and after the flush.
    """
    print("=== Hardware WLM Buffer-Trick Diagnostic ===")
    print(f"Channel:         {channel}")
    print(f"Dummy triggers:  {dummy_triggers}")
    print(f"Min exposure:    {wm_min_exposure}")
    print(f"Sample count:    {samples}")
    print()

    # Record initial exposure mode and ticks for information.
    try:
        initial_mode = bool(wlm.GetExposureMode())
    except Exception as exc:
        initial_mode = False
        print(f"[WARN] GetExposureMode failed: {exc}")

    try:
        initial_exposure = int(wlm.GetExposure())
    except Exception as exc:
        initial_exposure = -1
        print(f"[WARN] GetExposure failed: {exc}")

    print(
        f"[STATE] initial_exposure_mode="
        f"{'auto' if initial_mode else 'manual'}, "
        f"initial_exposure_ticks={initial_exposure}"
    )
    print()

    # Pre-flush raw samples.
    before_values: List[float] = []
    print("[RAW BEFORE]")
    for i in range(samples):
        try:
            f = float(wlm.GetFrequencyNum(channel))
        except Exception as exc:
            f = float("nan")
            print(f"  sample {i + 1}: ERROR ({exc})")
        else:
            before_values.append(f)
            print(f"  sample {i + 1}: { _freq_to_thz(f):.9f} THz")

    print()

    # Apply buffer trick: same structure as OptimizedLock._flush_wlm_buffer.
    previous_mode = None
    try:
        previous_mode = bool(wlm.GetExposureMode())
        wlm.SetExposureMode(False)
        wlm.SetExposure(wm_min_exposure)
    except Exception:
        previous_mode = None

    for _ in range(max(0, int(dummy_triggers))):
        try:
            event_adapter.trigger_measurement()
        except Exception:
            try:
                _ = wlm.GetFrequencyNum(channel)
            except Exception:
                break

    if previous_mode is not None:
        try:
            wlm.SetExposureMode(previous_mode)
        except Exception:
            pass

    # Post-flush raw samples.
    after_values: List[float] = []
    print("[RAW AFTER]")
    for i in range(samples):
        try:
            f = float(wlm.GetFrequencyNum(channel))
        except Exception as exc:
            f = float("nan")
            print(f"  sample {i + 1}: ERROR ({exc})")
        else:
            after_values.append(f)
            print(f"  sample {i + 1}: { _freq_to_thz(f):.9f} THz")

    print()

    # Simple stats for visual comparison.
    def _stats(label: str, values: List[float]) -> None:
        cleaned = [v for v in values if v == v]
        if not cleaned:
            print(f"[STATS {label}] no valid samples")
            return
        mean_hz = statistics.mean(cleaned)
        std_hz = statistics.pstdev(cleaned) if len(cleaned) > 1 else 0.0
        print(
            f"[STATS {label}] mean={_freq_to_thz(mean_hz):.9f} THz, "
            f"std={std_hz / 1e6:.3f} MHz"
        )

    _stats("BEFORE", before_values)
    _stats("AFTER", after_values)


def _build_default_handles() -> tuple[WavelengthMeter, _EventAdapter]:
    """
    Build default WLM and event adapter instances for standalone use.

    The WLM is started in measurement mode; the caller is responsible for
    calling `stop()` when done.
    """
    wlm = WavelengthMeter()
    wlm.start()
    event_adapter = _EventAdapter()
    return wlm, event_adapter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnostic: exercise the WLM buffer trick on a single channel.",
    )
    parser.add_argument(
        "--channel",
        type=int,
        required=True,
        help="WLM channel index to probe with GetFrequencyNum.",
    )
    parser.add_argument(
        "--dummy-triggers",
        type=int,
        default=2,
        help="Number of dummy triggers used during the buffer flush (default: 2).",
    )
    parser.add_argument(
        "--wm-min-exposure",
        type=int,
        default=1,
        help="Minimal exposure ticks to set while flushing the buffer (default: 1).",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of raw samples to record before and after the flush (default: 5).",
    )

    args = parser.parse_args()

    wlm, event_adapter = _build_default_handles()
    try:
        run_buffer_trick_test(
            wlm=wlm,
            event_adapter=event_adapter,
            channel=args.channel,
            dummy_triggers=args.dummy_triggers,
            wm_min_exposure=args.wm_min_exposure,
            samples=args.samples,
        )
    finally:
        try:
            wlm.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()


## AGENT_UPDATE
# - Added `hw_buffer_diagnostic.py`, a standalone hardware diagnostic that reuses
#   the same buffer-flush sequence as `OptimizedLock._flush_wlm_buffer` to compare
#   pre- and post-flush WLM frequency samples on a single channel, with a small
#   CLI for configuring channel, dummy triggers, exposure ticks, and sample count,
#   and guidance for pausing the main lock and using the shared mutex when invoked
#   from inside the existing locking process.

