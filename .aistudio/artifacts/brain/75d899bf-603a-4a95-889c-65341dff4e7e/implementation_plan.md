# Fix LT/RT Trigger Calibration Target & Eliminate RT → Left Stick Y Cross-Talk (`PID 0x61EB`)

This update fixes the bug where clicking **Detect LT Analog / Stage** calibrated `RT` instead of `LT`, and stops the Right Trigger (`RT`) from pulling `Left Stick Y` to `-32768` (and triggering `LStick_CapTouch`) in DirectInput mode (`PID 0x61EB`).

---

## User Review & Critical Decisions

> [!IMPORTANT]
> **Root Cause Analysis from Your `21:30:08` Hardware Log & Screenshot:**
> 1. **Why Both Trigger Calibrations Calibrated as `RT`**:
>    - The **Detect LT Analog / Stage** button passed `"left"` to `_open_trigger_stage_wizard("left")`, whereas `TriggerStageCalibrationDialog` and `start_trigger_stage_detection` checked `if str(target_side).upper() == "LT" else "RT"`. Because `"LEFT" != "LT"`, both buttons evaluated to `"RT"`.
> 2. **Why `RT` Pulled `Left Stick Y` to `-32768` on `PID 0x61EB`**:
>    - Your log shows that in `PID 0x61EB` (`PID61EB_MI02_C00_UPFFA0_U0001_IF2_1:R04`), the physical thumbsticks remain completely still at center (`B12..15 = [80 80 80 80]`), while `RT` sweeps `B21` from `0x00` to `0xFF` (`0 -> 255`) and sets `B17 = 0x01`.
>    - At the same time, Windows `winmm.joyGetPosEx` on `PID 0x61EB` maps that trigger sweep onto a DirectInput `dwYpos` axis that rests at `32768` (`0x8000`) and sweeps to `65535` (`0xFFFF`) at full pull (`32767 - 65535 = -32768` on `L-Stick Y`).
>    - Because `finalize_trigger_stage_detection` selected `HID R04 Byte 21` as the winning trigger source (scoring `72,930` vs `49,150` for DirectInput), it did not add the co-moving DirectInput `(joy_id, "Y")` axis to the excluded stick axes list.

---

## 1. Overview & Core Concept

- **Fix `LT` vs `RT` Wizard Target Selection**: Accept `"LT"`, `"LEFT"`, `"L"`, or `"L2"` as `LT` (and pass `"LT"` / `"RT"` explicitly from the UI buttons) so **Detect LT Analog / Stage** always calibrates and saves `ltSource` (Left Trigger) and **Detect RT Analog / Stage** calibrates and saves `rtSource` (Right Trigger).
- **Eliminate `RT -> Left Stick Y` Cross-Talk in DirectInput Mode (`PID 0x61EB`)**:
  1. **Automatic Co-Moving DirectInput Axis Exclusion**: Whenever you calibrate `LT` or `RT` in `TriggerStageCalibrationDialog`, **every** DirectInput `(joy_id, axis_name)` that moves significantly (`span >= 4000`) during that trigger pull is automatically recorded in `excludedDinputStickAxes` for that trigger—even when a Raw HID byte (`R04 B20` / `B21`) is chosen as the primary analog source.
  2. **Native `PID 0x61EB` Report `0x04` Stick & Trigger Authority**: When `PID 0x61EB` Report `0x04` is active (`B12..15` = 4 centered stick axes resting at `0x80`, `B20` = LT analog `0x00..0xFF`, `B21` = RT analog `0x00..0xFF`), decode `LT` (`B20`) and `RT` (`B21`) directly and gate DirectInput `leftStickX/Y` and `rightStickX/Y` against Report `0x04` `B12..15` so a trigger pull while `B12..15 == [0x80, 0x80, 0x80, 0x80]` can never deflect `Left Stick Y` or trigger `LStick_CapTouch`.

---

## 2. User Experience & Visual Design

- **Independent `LT` and `RT` Calibration Wizards**:
  - Clicking **Detect LT Analog / Stage** opens the dialog titled `Detect & Calibrate LT Analog Trigger + Press Stages`, monitors `leftTriggerAnalog` / `leftTriggerStage`, and locks `ltSource` + `ltExcludedDinputAxes`.
  - Clicking **Detect RT Analog / Stage** opens `Detect & Calibrate RT Analog Trigger + Press Stages`, monitors `rightTriggerAnalog` / `rightTriggerStage`, and locks `rtSource` + `rtExcludedDinputAxes`.
- **Clean Stick & Trigger Separation in Tab 1**:
  - Pulling `RT` from `0%` to `100%` smoothly drives `R2 Trigger: 0 -> 32767` through `[REST] -> [PULL] -> [HALF-PRESS] -> [FULL-PRESS]` while `L-Stick Y` remains at `0` and `LStick_CapTouch` stays `OFF`.

---

## 3. Key Product Decisions & Trade-Offs

- **Decision 1: Exclude All Co-Moving DirectInput Axes During Trigger Calibration**
  - *Chosen Approach*: Store `ltExcludedDinputAxes` and `rtExcludedDinputAxes` in `triggerCalibration` whenever `finalize_trigger_stage_detection` completes, capturing every DirectInput `(joy_id, axis)` that swept `>= 4000` during Step 2.
  - *Why*: On composite controllers like `PID 0x61EB`, a single physical trigger pull simultaneously updates a Raw HID byte (`R04 B21`) and a DirectInput axis (`dwYpos`). Blocking all co-moving DirectInput axes from stick evaluation guarantees zero stick cross-talk regardless of which source wins the highest analog resolution score.
- **Decision 2: Use `PID 0x61EB` Report `0x04` (`B12..15` & `B20..21`) as Ground Truth When Present**
  - *Chosen Approach*: When `UPFFA0` Report `0x04` is streaming (as seen in your log `B00..23=[04 00 A1 64 04 64 04 01 01 01 02 02 80 80 80 80 00 01 00 00 00 FF 01 80]`), use `B12..15` (`0x80` center) to verify whether the physical thumbsticks are actually deflected and decode `B20` (LT) / `B21` (RT) out-of-the-box.
  - *Why*: Eliminates `RT -> Left Stick Y` cross-talk immediately even before running manual trigger calibration.

---

## 4. Technical Architecture & Data Strategy

```
┌────────────────────────────────────────────────────────────────────────────┐
│               LT / RT Trigger & Stick Isolation Pipeline                   │
├────────────────────────────────────────────────────────────────────────────┤
│  1. UI Buttons (Tab 2 -> Section C)                                        │
│     • "Detect LT Analog / Stage" -> _open_trigger_stage_wizard("LT")       │
│     • "Detect RT Analog / Stage" -> _open_trigger_stage_wizard("RT")       │
│     • Normalizes ("LT", "LEFT", "L", "L2") -> "LT"                         │
├────────────────────────────────────────────────────────────────────────────┤
│  2. finalize_trigger_stage_detection(profile)                              │
│     • Locks best analog source into ltSource (for LT) or rtSource (for RT) │
│     • Records ALL DirectInput (joy_id, axis) with span >= 4000 during      │
│       Step 2 into ltExcludedDinputAxes / rtExcludedDinputAxes              │
├────────────────────────────────────────────────────────────────────────────┤
│  3. PID 0x61EB Report 0x04 & DirectInput Stick Guard                       │
│     • Reads R04 B20 (LT 0..255) & B21 (RT 0..255) -> 0..32767 analog       │
│     • Checks R04 B12..15 (LX, LY, RX, RY centered at 0x80):                │
│       When R04 B12..15 are at center (0x78..0x88), DirectInput axes        │
│       cannot deflect leftStickX/Y or rightStickX/Y                         │
└────────────────────────────────────────────────────────────────────────────┘
```
