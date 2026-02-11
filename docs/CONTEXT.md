# Project Context: BaLi Laser Locking & Optimization

## 1. Objective
Stabilize multiple lasers (e.g., 493nm, 650nm) for a Ba+/Li quantum simulation experiment using a single HighFinesse Wavemeter (WLM) and a Fiber Switch. Goal: Scan magnetic fields to detect Feshbach resonances via ion loss rates (survival probability).

## 2. Hardware Stack
- **Wavemeter:** HighFinesse WS-series (interfaced via `wlmData.dll` / `ctypes`).
- **Switch:** Sercalo SN-1x4-3N-FA (MEMS-based, non-latching).
    - **Physical Switching Time:** < 1 ms (typical 0.5 ms).
    - **Current Control:** Ethernet-based (`modules.FiberSwitchCommunication`), likely via an intermediate TTL/Serial controller.
- **Lasers:** Toptica DLCpro (controlled via `toptica-lasersdk`).
- **DAQs:** USB-DAQ for analog voltage output (Piezo control).

## 3. Current Implementation (`wavemeterbali.py`)
- **Method:** Sequential switching between channels.
- **Bottleneck:** Hardcoded `time.sleep(0.23)` after switching. 
    - *Insight:* Given the Sercalo switch's 1ms response time, this 230ms delay is entirely software-overhead or safety margin for the WLM buffer, not a hardware limitation of the switch.
- **PID:** Classic feedback loop mapping WLM frequency error to DAC voltage.

## 4. Planned Improvements (Oxford Logic)
- **Improvement A (Event Polling):** Replace fixed sleep with `WaitForWLMEvent` (specifically `cmiSwitcherChannel`) or polling `GetOperationState` to detect when the WLM is ready for the next reading.
- **Improvement B (Buffer Trick):** Flush the WLM internal pipeline after switching by performing 2-3 "zero-exposure" measurements (manual trigger) before reading the control value.
- **Goal:** Reduce cycle time from ~300ms to < 50ms per laser, significantly increasing feedback bandwidth.

## 5. Physical Constraints & Targets
- **Target Stability:** 1 MHz to 5 MHz (based on Kilian Berger's Thesis).
- **System:** 138Barium+ ions in 6Lithium gas.
- **Experiment:** Magnetic field ramps across Feshbach resonances; requires high stability to maintain resonance during the scan.

## 6. Library Specifics (Reference for Agents)
- **WLM DLL:** `wlmData.dll` (Windows).
- **Key Functions:**
    - `SetSwitcherChannel(channel)`: Triggers the WLM internal channel logic.
    - `GetFrequency(channel)`: Reads the frequency (can return stale data if not flushed).
    - `SetExposureMode(bool)`: Used to toggle between auto and manual (fast) exposure.
    - `TriggerMeasurement(action)`: Force a measurement (e.g., `etSingleShot`).
    - `WaitForWLMEvent(...)`: Preferred method for synchronization.
- **External Refs:** Refer to `pylablib.devices.HighFinesse.wlm` for robust DLL wrapping.