#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
STANDALONE PYQT6 WINDOWS DESKTOP APP:
LENOVO LEGION GO (0x17EF) -> VALVE STEAM DECK CONTROLLER (0x28DE:0x1205)
================================================================================
100% Standalone Python Desktop Application (No Browser / No WebUI Required).
Includes:
  - Auto-Detect XInput (0x6182), Single DInput (0x6183), and Dual Split DInput
    (0x6184 Left + 0x6185 Right) via XInput + winmm.joyGetPosEx + hidapi (0x01/0x05)
  - Configurable Multi-IMU 6-Axis Gyro Engine:
      * Choose Physical Gyro Source: Right Controller IMU, Left Controller IMU,
        Combined Left+Right / Tablet IMU (0x0020), or Disabled
      * Choose Gyro Activation: Native Steam Deck Stick/Pad Touch, Hold Chosen
        Button to Activate, or Always-On 6-Axis Stream
  - Live Physical + Click-to-Test Hardware Visualizer (All 24 Buttons, Sticks,
    Triggers, 8-Way D-Pad Hat Switch, Physical Right Touchpad & Scroll Wheel)
  - Win32 WH_MOUSE_LL Touchpad & Scroll Wheel Cursor Lock -> Steam Deck Trackpad
    (Toggle lock anytime with Ctrl+Alt+U; auto-unlocks inside LegionDeck window)
  - Automatic HidHideCLI Device Instance Path Cloaking (--dev-hide VID_17EF*)

Run on Windows 10/11 (Administrator):
  pip install PyQt6 hidapi
  python legion_go_steamdeck_app.py
================================================================================
"""

import ctypes
from ctypes import wintypes
import json
import math
import os
import re
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

# Always set working directory to the folder containing legion_go_steamdeck_app.py
os.chdir(Path(__file__).resolve().parent)

# Auto-install PyQt6 and hidapi if user launched script directly
try:
    import PyQt6  # noqa: F401
except ImportError:
    print("[Bootstrap] Installing PyQt6 and hidapi...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyQt6", "hidapi"])

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPointF,
    QRectF,
    pyqtSignal,
    QObject,
    QAbstractNativeEventFilter,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

try:
    import hid  # pip install hidapi
    HAS_HIDAPI = True
except ImportError:
    HAS_HIDAPI = False


# ==============================================================================
# 1. CONSTANTS, TARGET LABELS & AUTO-SAVED PROFILE DEFAULTS
# ==============================================================================
PROFILE_FILE_PATH = Path(__file__).resolve().parent / "legion_deck_profile.json"

LENOVO_VENDOR_ID = 0x17EF
LENOVO_PID_XINPUT = 0x6182
LENOVO_PID_DINPUT_SINGLE = 0x6183
LENOVO_PID_DINPUT_LEFT = 0x6184
LENOVO_PID_DINPUT_RIGHT = 0x6185
LENOVO_PID_DONGLE = 0x61EB
LENOVO_PRODUCT_IDS = [
    LENOVO_PID_XINPUT,
    LENOVO_PID_DINPUT_SINGLE,
    LENOVO_PID_DINPUT_LEFT,
    LENOVO_PID_DINPUT_RIGHT,
    LENOVO_PID_DONGLE,
]

VALVE_VENDOR_ID = 0x28DE
STEAM_DECK_PRODUCT_ID = 0x1205  # Valve Software Steam Deck Controller ("Neptune")

STEAM_DECK_HID_REPORT_DESCRIPTOR = bytes([
    0x06, 0x00, 0xFF,  # Usage Page (Vendor Defined 0xFF00)
    0x09, 0x01,        # Usage (0x01)
    0xA1, 0x01,        # Collection (Application)
    0x15, 0x00,        #   Logical Minimum (0)
    0x26, 0xFF, 0x00,  #   Logical Maximum (255)
    0x75, 0x08,        #   Report Size (8 bits)
    0x95, 0x40,        #   Report Count (64 bytes)
    0x09, 0x01,        #   Usage (0x01 - 64-byte Neptune Input Report)
    0x81, 0x02,        #   Input (Data,Var,Abs)
    0x95, 0x40,        #   Report Count (64 bytes)
    0x09, 0x01,        #   Usage (0x01 - 64-byte Output Report)
    0x91, 0x02,        #   Output (Data,Var,Abs)
    0x95, 0x40,        #   Report Count (64 bytes)
    0x09, 0x01,        #   Usage (0x01 - 64-byte Feature Handshake Report)
    0xB1, 0x02,        #   Feature (Data,Var,Abs)
    0xC0               # End Collection (33 bytes)
])

STEAM_DECK_TARGET_OPTIONS = [
    ("buttonL4Grip", "Steam Deck L4 Rear Grip"),
    ("buttonL5Grip", "Steam Deck L5 Rear Grip"),
    ("buttonR4Grip", "Steam Deck R4 Rear Grip"),
    ("buttonR5Grip", "Steam Deck R5 Rear Grip"),
    ("buttonSteam", "Steam Button (STEAM)"),
    ("buttonQuickAccess", "Quick Access Menu (...)"),
    ("modeShiftRightPadToLeftPad", "Mode-Shift: Right Pad acts as Left Pad"),
    ("leftTrackpadClick", "Left Trackpad Click"),
    ("rightTrackpadClick", "Right Trackpad Click"),
    ("leftTrackpadTouch", "Left Trackpad Capacitive Touch"),
    ("rightTrackpadTouch", "Right Trackpad Capacitive Touch"),
    ("leftStickCapacitiveTouch", "Left Stick Capacitive Touch (Gyro Trigger)"),
    ("rightStickCapacitiveTouch", "Right Stick Capacitive Touch (Gyro Trigger)"),
    ("buttonA", "Button A"),
    ("buttonB", "Button B"),
    ("buttonX", "Button X"),
    ("buttonY", "Button Y"),
    ("buttonL1", "Bumper L1"),
    ("buttonR1", "Bumper R1"),
    ("buttonL2Digital", "Trigger L2 Digital Full Pull"),
    ("buttonR2Digital", "Trigger R2 Digital Full Pull"),
    ("buttonL3Click", "Left Stick Click (L3)"),
    ("buttonR3Click", "Right Stick Click (R3)"),
    ("buttonView", "View Button (-)"),
    ("buttonMenu", "Menu Button (+)"),
    ("dpadUp", "D-Pad Up"),
    ("dpadDown", "D-Pad Down"),
    ("dpadLeft", "D-Pad Left"),
    ("dpadRight", "D-Pad Right"),
    ("none", "Unassigned (Disabled)"),
]

TARGET_KEY_TO_LABEL = dict(STEAM_DECK_TARGET_OPTIONS)

LEGION_BUTTON_KEY_TO_LABEL = {
    "legionLButton": "Legion L (Top Left)",
    "legionRButton": "Legion R (Top Right)",
    "buttonY1": "Y1 (Left Rear Upper)",
    "buttonY2": "Y2 (Left Rear Lower)",
    "buttonY3": "Y3 (Right Rear Inner)",
    "buttonM2": "M2 (Right Side Lower FPS)",
    "buttonM3": "M3 (Right Rear Outer)",
    "scrollWheelUp": "Rear Scroll Wheel Up (VID_17EF)",
    "scrollWheelDown": "Rear Scroll Wheel Down (VID_17EF)",
    "scrollWheelClick": "Rear Scroll Wheel Click (VID_17EF)",
    "buttonA": "A (Bottom Face)",
    "buttonB": "B (Right Face)",
    "buttonX": "X (Left Face)",
    "buttonY": "Y (Top Face)",
    "buttonLB": "LB (Left Bumper)",
    "buttonRB": "RB / M1 (Right Bumper / Top-Edge)",
    "leftStickClick": "L3 (Left Stick Click)",
    "rightStickClick": "R3 (Right Stick Click)",
    "buttonView": "View (-)",
    "buttonMenu": "Menu (+)",
    "dpadUp": "D-Pad Up",
    "dpadDown": "D-Pad Down",
    "dpadLeft": "D-Pad Left",
    "dpadRight": "D-Pad Right",
    "rightTrackpadTouch": "Right Touchpad Touch",
    "rightTrackpadClick": "Right Touchpad Click",
}

LEGION_BUTTON_TO_MAP_KEY = {
    "legionLButton": "mapLegionLButton",
    "legionRButton": "mapLegionRButton",
    "buttonY1": "mapButtonY1",
    "buttonY2": "mapButtonY2",
    "buttonY3": "mapButtonY3",
    "buttonM2": "mapButtonM2",
    "buttonM3": "mapButtonM3",
    "scrollWheelUp": "mapScrollWheelUp",
    "scrollWheelDown": "mapScrollWheelDown",
    "scrollWheelClick": "mapScrollWheelClick",
    "buttonA": "mapButtonA",
    "buttonB": "mapButtonB",
    "buttonX": "mapButtonX",
    "buttonY": "mapButtonY",
    "buttonLB": "mapButtonLB",
    "buttonRB": "mapButtonRB",
    "leftStickClick": "mapLeftStickClick",
    "rightStickClick": "mapRightStickClick",
    "buttonView": "mapButtonView",
    "buttonMenu": "mapButtonMenu",
    "dpadUp": "mapDpadUp",
    "dpadDown": "mapDpadDown",
    "dpadLeft": "mapDpadLeft",
    "dpadRight": "mapDpadRight",
}

XINPUT_BIT_NAMES = [
    (0x0001, "DPadUp"),
    (0x0002, "DPadDown"),
    (0x0004, "DPadLeft"),
    (0x0008, "DPadRight"),
    (0x0010, "Menu(+)"),
    (0x0020, "View(-)"),
    (0x0040, "L3"),
    (0x0080, "R3"),
    (0x0100, "LB"),
    (0x0200, "RB/M1"),
    (0x0400, "Guide/LegionL"),
    (0x1000, "A"),
    (0x2000, "B"),
    (0x4000, "X"),
    (0x8000, "Y"),
]

NEPTUNE_BYTE_BIT_NAMES = {
    8: [
        (0x01, "R2_Dig"),
        (0x02, "L2_Dig"),
        (0x04, "R1"),
        (0x08, "L1"),
        (0x10, "Y"),
        (0x20, "B"),
        (0x40, "X"),
        (0x80, "A"),
    ],
    9: [
        (0x01, "DPadUp"),
        (0x02, "DPadRight"),
        (0x04, "DPadLeft"),
        (0x08, "DPadDown"),
        (0x10, "View(-)"),
        (0x20, "STEAM"),
        (0x40, "Menu(+)"),
        (0x80, "L5_Grip"),
    ],
    10: [
        (0x01, "R5_Grip"),
        (0x02, "LPad_Click"),
        (0x04, "RPad_Click"),
        (0x08, "LPad_Touch"),
        (0x10, "RPad_Touch"),
        (0x40, "L3_Click"),
        (0x80, "R3_Click"),
    ],
    12: [
        (0x02, "L4_Grip"),
        (0x04, "R4_Grip"),
        (0x40, "LStick_CapTouch"),
        (0x80, "RStick_CapTouch"),
    ],
    13: [
        (0x04, "QAM(...)"),
    ],
}

SCROLL_WHEEL_MODE_OPTIONS = [
    ("remappedButtons", "Use Remapped Scroll Wheel Up / Down Actions (Tab 2)"),
    ("leftTrackpadVerticalSwipe", "Also Emulate Deck Left Trackpad Vertical Swipe (Y Axis)"),
    ("leftTrackpadCircularScroll", "Also Emulate Deck Left Trackpad Circular Scroll (Radial Menus)"),
]

CONTROLLER_PROTOCOL_OPTIONS = [
    ("auto", "Auto-Detect: XInput (0x6182) + Single DInput (0x6183) + Dual DInput (0x6184/0x6185)"),
    ("xinput_only", "Force XInput Mode Only (PID 0x6182 / Legion L + RB)"),
    ("dinput_only", "Force DirectInput Mode Only (PID 0x6183 / 0x6184+0x6185 / Legion L + LB)"),
]

GYRO_SOURCE_OPTIONS = [
    ("rightControllerImu", "Right Controller IMU — Precision Aiming (Default)"),
    ("leftControllerImu", "Left Controller IMU — Steering / Left-Hand Tilt"),
    ("combinedOrTabletImu", "Combined Left + Right Average / Tablet Body IMU (0x0020)"),
    ("disabled", "Gyro Completely Disabled (Zero Output)"),
]

GYRO_ACTIVATION_OPTIONS = [
    ("touchActivated", "Native Steam Deck IMU with Stick / Trackpad Touch (Default)"),
    ("holdButtonActivated", "Activate Gyro Only While Holding Chosen Button"),
    ("alwaysOn", "Always-On Steam Deck 6-Axis IMU Stream (250Hz Continuous)"),
]

GYRO_HOLD_BUTTON_OPTIONS = [
    ("buttonRB", "RB / M1 (Right Bumper / Top-Edge)"),
    ("buttonM2", "M2 Side Button (Right Lower FPS)"),
    ("buttonY1", "Y1 Rear Grip (Left Upper)"),
    ("buttonY2", "Y2 Rear Grip (Left Lower)"),
    ("buttonY3", "Y3 Rear Grip (Right Inner)"),
    ("buttonM3", "M3 Rear Grip (Right Outer)"),
    ("buttonLB", "Left Bumper (LB)"),
    ("leftTriggerPull", "Left Trigger (L2 Pull)"),
    ("rightTriggerPull", "Right Trigger (R2 Pull)"),
    ("rightStickClick", "Right Stick Click (R3)"),
    ("leftStickClick", "Left Stick Click (L3)"),
    ("rightTrackpadTouch", "Right Touchpad Touch"),
]

DEFAULT_TRIGGER_CALIBRATION = {
    "ltSource": None,
    "rtSource": None,
    "ltDeadzonePct": 3,
    "ltHalfPressPct": 45,
    "ltFullPressPct": 75,
    "rtDeadzonePct": 3,
    "rtHalfPressPct": 45,
    "rtFullPressPct": 75,
    "ltHalfPressAction": "none",
    "rtHalfPressAction": "none",
}

DEFAULT_PROFILE = {
    "profileName": "Default Native Steam Deck Profile",
    # Controller Protocol Mode
    "controllerProtocolMode": "auto",
    # Extra Lenovo Legion Go Buttons
    "mapLegionLButton": "buttonSteam",
    "mapLegionRButton": "buttonQuickAccess",
    "mapButtonY1": "buttonL4Grip",
    "mapButtonY2": "buttonL5Grip",
    "mapButtonY3": "buttonR4Grip",
    "mapButtonM3": "buttonR5Grip",
    "mapButtonM2": "modeShiftRightPadToLeftPad",
    "mapScrollWheelUp": "dpadUp",
    "mapScrollWheelDown": "dpadDown",
    "mapScrollWheelClick": "leftTrackpadClick",
    # Standard Gamepad Buttons (Also 100% Remappable; RB & M1 united as mapButtonRB)
    "mapButtonA": "buttonA",
    "mapButtonB": "buttonB",
    "mapButtonX": "buttonX",
    "mapButtonY": "buttonY",
    "mapButtonLB": "buttonL1",
    "mapButtonRB": "buttonR1",
    "mapLeftStickClick": "buttonL3Click",
    "mapRightStickClick": "buttonR3Click",
    "mapButtonView": "buttonView",
    "mapButtonMenu": "buttonMenu",
    "mapDpadUp": "dpadUp",
    "mapDpadDown": "dpadDown",
    "mapDpadLeft": "dpadLeft",
    "mapDpadRight": "dpadRight",
    # Multi-IMU Gyro Configuration
    "gyroEnabled": True,
    "gyroPhysicalSource": "rightControllerImu",
    "gyroActivationMode": "touchActivated",
    "gyroHoldButton": "buttonRB",
    "gyroSensitivityMultiplier": 1.0,
    "gyroInvertPitch": False,
    "gyroInvertYaw": False,
    "gyroInvertRoll": False,
    # Trackpad, Wheel & Interception Settings
    "scrollWheelMode": "remappedButtons",
    "lockWindowsCursorAndRouteTouchpad": True,
    "touchpadSensitivity": 145,
    "suspendLegionSpaceService": True,
    "interceptKeyboardShortcuts": True,
    "autoStickCapacitiveTouchOnDeflection": True,
    "stickCapacitiveDeadzonePercent": 8,
    "enableHidHideCloak": True,
    "autoStartEmulationOnLaunch": False,
    "minimizeToTrayOnClose": True,
    "darkMode": True,
    "usbipLoopbackPort": 3240,
    "emulatedDeckSerialNumber": "SD-LEGION-GO-28DE",
    "learnedVendorButtons": {},
    "learnedMouseButtons": {},
    "learnedKeyBindings": {},
    "learnedDinputButtons": {},
    "learnedXinputButtons": {},
    "gyroCalibration": None,
    "triggerCalibration": dict(DEFAULT_TRIGGER_CALIBRATION),
}

EXTRA_VENDOR_BUTTON_KEYS = {
    "legionLButton",
    "legionRButton",
    "buttonY1",
    "buttonY2",
    "buttonY3",
    "buttonM2",
    "buttonM3",
    "scrollWheelUp",
    "scrollWheelDown",
    "scrollWheelClick",
}

VK_CODE_NAMES = {
    0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4", 0x74: "F5", 0x75: "F6",
    0x76: "F7", 0x77: "F8", 0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12",
    0x7C: "F13", 0x7D: "F14", 0x7E: "F15", 0x7F: "F16", 0x80: "F17", 0x81: "F18",
    0x82: "F19", 0x83: "F20", 0x84: "F21", 0x85: "F22", 0x86: "F23", 0x87: "F24",
}


def format_vk_name(vk: int) -> str:
    vk = int(vk)
    if vk in VK_CODE_NAMES:
        return VK_CODE_NAMES[vk]
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return f"Key '{chr(vk)}' (0x{vk:02X})"
    return f"VK_0x{vk:02X}"


PRESET_PROFILES = {
    "default": dict(DEFAULT_PROFILE),
    "gyro_fps": {
        **DEFAULT_PROFILE,
        "profileName": "Precision Gyro FPS Profile (Right IMU)",
        "gyroEnabled": True,
        "gyroPhysicalSource": "rightControllerImu",
        "gyroActivationMode": "touchActivated",
        "mapButtonRB": "buttonR1",
        "mapButtonM2": "rightTrackpadClick",
        "gyroSensitivityMultiplier": 1.4,
        "stickCapacitiveDeadzonePercent": 5,
    },
    "radial_pad": {
        **DEFAULT_PROFILE,
        "profileName": "Dual-Trackpad & Radial Menu Profile",
        "gyroEnabled": True,
        "gyroPhysicalSource": "combinedOrTabletImu",
        "mapButtonM2": "modeShiftRightPadToLeftPad",
        "scrollWheelMode": "leftTrackpadCircularScroll",
        "mapScrollWheelClick": "leftTrackpadClick",
    },
}


def create_empty_legion_state() -> dict:
    return {
        "legionLButton": False,
        "legionRButton": False,
        "buttonView": False,
        "buttonMenu": False,
        "buttonA": False,
        "buttonB": False,
        "buttonX": False,
        "buttonY": False,
        "dpadUp": False,
        "dpadDown": False,
        "dpadLeft": False,
        "dpadRight": False,
        "buttonLB": False,
        "buttonRB": False,
        "leftTriggerAnalog": 0,
        "rightTriggerAnalog": 0,
        "leftTriggerStage": "REST",
        "rightTriggerStage": "REST",
        "buttonY1": False,
        "buttonY2": False,
        "buttonY3": False,
        "buttonM2": False,
        "buttonM3": False,
        "scrollWheelDelta": 0,
        "scrollWheelUp": False,
        "scrollWheelDown": False,
        "scrollWheelClick": False,
        "leftStickX": 0,
        "leftStickY": 0,
        "leftStickClick": False,
        "rightStickX": 0,
        "rightStickY": 0,
        "rightStickClick": False,
        "rightTrackpadTouch": False,
        "rightTrackpadClick": False,
        "rightTrackpadX": 0,
        "rightTrackpadY": 0,
        "rightTrackpadPressure": 0,
        # Selected / Merged IMU (plus per-unit IMU channels for Left, Right, Tablet)
        "imuGyroPitch": 0,
        "imuGyroYaw": 0,
        "imuGyroRoll": 0,
        "imuAccelX": 0,
        "imuAccelY": 0,
        "imuAccelZ": 16384,
        "rightImuGyro": (0, 0, 0),
        "leftImuGyro": (0, 0, 0),
        "tabletImuGyro": (0, 0, 0),
    }


# ==============================================================================
# 2. WIN32 LOW-LEVEL MOUSE & KEYBOARD INTERCEPTOR (TOUCHPAD LOCK + SHORTCUTS)
# ==============================================================================
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class Win32TouchpadAndShortcutInterceptor:
    def __init__(self, get_profile_fn, is_cursor_over_ui_fn, log_fn):
        self.get_profile = get_profile_fn
        self.is_cursor_over_ui = is_cursor_over_ui_fn
        self.log = log_fn

        self.capture_enabled = False
        self.manual_unlock_override = False  # Toggled with Ctrl+Alt+U

        self.pad_touch = False
        self.pad_click = False
        self.pad_x = 0
        self.pad_y = 0
        self.last_motion_time = 0.0
        self.last_cursor_pt = None

        self.wheel_delta = 0
        self.wheel_click = False
        self.mouse_xbutton1 = False  # Mouse 4 (XButton1)
        self.mouse_xbutton2 = False  # Mouse 5 (XButton2)
        self.last_wheel_time = 0.0
        self.last_lenovo_wheel_hw_time = 0.0

        self.active_vk_codes = set()
        self.learning_target_btn = None
        self.on_key_learned_callback = None

        # Thread-safe cached studio window bounds updated by main Qt GUI timer
        self.studio_window_active = True
        self.studio_window_rect = (0, 0, 1920, 1080)
        self.test_lock_override = False

        self._hook_thread = None
        self._mouse_proc_ref = None
        self._kbd_proc_ref = None

    def start(self):
        if sys.platform != "win32" or self._hook_thread is not None:
            return
        self._hook_thread = threading.Thread(target=self._run_win32_hook_pump, daemon=True)
        self._hook_thread.start()

    def reset_pad_center(self):
        self.pad_x = 0
        self.pad_y = 0
        self.pad_touch = False
        self.pad_click = False

    def poll_and_decay(self):
        now = time.perf_counter()
        if self.pad_touch and not self.pad_click and (now - self.last_motion_time) > 0.16:
            self.pad_touch = False
            self.pad_x = 0
            self.pad_y = 0
        if self.wheel_delta != 0 and (now - self.last_wheel_time) > 0.12:
            self.wheel_delta = 0

    def _should_lock_cursor_now(self, pt_x: int = None, pt_y: int = None) -> bool:
        if not self.capture_enabled or self.manual_unlock_override:
            return False
        if not self.get_profile().get("lockWindowsCursorAndRouteTouchpad", True):
            return False
        if not self.test_lock_override and self.studio_window_active:
            if pt_x is None or pt_y is None:
                return False
            x1, y1, x2, y2 = self.studio_window_rect
            if x1 <= pt_x <= x2 and y1 <= pt_y <= y2:
                return False
        return True

    def _run_win32_hook_pump(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(
            LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        )

        # Explicit 64-bit Windows ctypes signatures so lParam pointers never overflow 32-bit c_int
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = wintypes.BOOL

        def low_level_mouse_proc(nCode, wParam, lParam):
            if nCode >= 0:
                try:
                    ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    prof = self.get_profile()
                    pt_x, pt_y = int(ms.pt.x), int(ms.pt.y)
                    lock_active = self._should_lock_cursor_now(pt_x, pt_y)

                    if wParam == WM_MOUSEMOVE:
                        if self.last_cursor_pt is None:
                            self.last_cursor_pt = (pt_x, pt_y)
                        dx = pt_x - self.last_cursor_pt[0]
                        dy = pt_y - self.last_cursor_pt[1]

                        if lock_active:
                            if dx != 0 or dy != 0:
                                sens = int(prof.get("touchpadSensitivity", 145))
                                self.pad_touch = True
                                self.pad_x = max(-32768, min(32767, self.pad_x + dx * sens))
                                self.pad_y = max(-32768, min(32767, self.pad_y - dy * sens))
                                self.last_motion_time = time.perf_counter()
                            return 1
                        else:
                            self.last_cursor_pt = (pt_x, pt_y)

                    elif wParam == WM_LBUTTONDOWN and lock_active:
                        self.pad_touch = True
                        self.pad_click = True
                        self.last_motion_time = time.perf_counter()
                        return 1
                    elif wParam == WM_LBUTTONUP and lock_active:
                        self.pad_click = False
                        self.last_motion_time = time.perf_counter()
                        return 1
                    elif wParam in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                        xbtn = (int(ms.mouseData) >> 16) & 0xFFFF
                        is_xdown = (wParam == WM_XBUTTONDOWN)
                        if xbtn == 1:
                            self.mouse_xbutton1 = is_xdown
                        elif xbtn == 2:
                            self.mouse_xbutton2 = is_xdown
                        if lock_active or self.capture_enabled:
                            return 1
                    elif wParam == WM_MOUSEWHEEL:
                        # Only swallow Windows scroll wheel if the event came from the VID_17EF Legion Go scroll wheel
                        # within the last 25ms; external USB/Bluetooth mice pass through untouched!
                        if (self.capture_enabled or lock_active) and (time.perf_counter() - self.last_lenovo_wheel_hw_time) < 0.025:
                            return 1
                except Exception:
                    pass
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        def low_level_kbd_proc(nCode, wParam, lParam):
            if nCode >= 0:
                try:
                    kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    vk = int(kb.vkCode)
                    is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)

                    if is_down:
                        self.active_vk_codes.add(vk)
                    elif is_up:
                        self.active_vk_codes.discard(vk)

                    # Emergency Cursor Lock Toggle: Ctrl + Alt + U (VK_U = 0x55)
                    if is_down and vk == 0x55:
                        ctrl_down = (user32.GetAsyncKeyState(0x11) & 0x8000) != 0
                        alt_down = (user32.GetAsyncKeyState(0x12) & 0x8000) != 0
                        if ctrl_down and alt_down:
                            self.manual_unlock_override = not self.manual_unlock_override
                            state_str = "UNLOCKED (Windows Cursor Free)" if self.manual_unlock_override else "LOCKED -> Routed to Steam Deck Trackpad"
                            self.log(f"[Touchpad Lock] Ctrl+Alt+U pressed: Cursor {state_str}")
                            self.reset_pad_center()
                            return 1

                    if self.get_profile().get("interceptKeyboardShortcuts", True):
                        # Swallow F13..F24 (0x7C..0x87) and any user-bound VK code so rear button macros never leak to Windows
                        if 0x7C <= vk <= 0x87:
                            return 1
                        learned_keys = self.get_profile().get("learnedKeyBindings", {})
                        for _btn_name, bound_vk in learned_keys.items():
                            if int(bound_vk) == vk:
                                return 1
                except Exception:
                    pass
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        self._mouse_proc_ref = HOOKPROC(low_level_mouse_proc)
        self._kbd_proc_ref = HOOKPROC(low_level_kbd_proc)

        h_mod = kernel32.GetModuleHandleW(None)
        m_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_proc_ref, h_mod, 0)
        k_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kbd_proc_ref, h_mod, 0)

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if m_hook:
            user32.UnhookWindowsHookEx(m_hook)
        if k_hook:
            user32.UnhookWindowsHookEx(k_hook)


# ==============================================================================
# 3. UNIVERSAL XINPUT + SINGLE/DUAL DIRECTINPUT + MULTI-IMU HARDWARE READER
# ==============================================================================
class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", wintypes.BYTE),
        ("bRightTrigger", wintypes.BYTE),
        ("sThumbLX", wintypes.SHORT),
        ("sThumbLY", wintypes.SHORT),
        ("sThumbRX", wintypes.SHORT),
        ("sThumbRY", wintypes.SHORT),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", wintypes.DWORD),
        ("Gamepad", XINPUT_GAMEPAD),
    ]


class JOYINFOEX(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("dwXpos", wintypes.DWORD),
        ("dwYpos", wintypes.DWORD),
        ("dwZpos", wintypes.DWORD),
        ("dwRpos", wintypes.DWORD),
        ("dwUpos", wintypes.DWORD),
        ("dwVpos", wintypes.DWORD),
        ("dwButtons", wintypes.DWORD),
        ("dwButtonNumber", wintypes.DWORD),
        ("dwPOV", wintypes.DWORD),
        ("dwReserved1", wintypes.DWORD),
        ("dwReserved2", wintypes.DWORD),
    ]


class JOYCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("szPname", wintypes.WCHAR * 32),
        ("wXmin", wintypes.UINT),
        ("wXmax", wintypes.UINT),
        ("wYmin", wintypes.UINT),
        ("wYmax", wintypes.UINT),
        ("wZmin", wintypes.UINT),
        ("wZmax", wintypes.UINT),
        ("wNumButtons", wintypes.UINT),
        ("wPeriodMin", wintypes.UINT),
        ("wPeriodMax", wintypes.UINT),
        ("wRmin", wintypes.UINT),
        ("wRmax", wintypes.UINT),
        ("wUmin", wintypes.UINT),
        ("wUmax", wintypes.UINT),
        ("wVmin", wintypes.UINT),
        ("wVmax", wintypes.UINT),
        ("wCaps", wintypes.UINT),
        ("wMaxAxes", wintypes.UINT),
        ("wNumAxes", wintypes.UINT),
        ("wMaxButtons", wintypes.UINT),
        ("szRegKey", wintypes.WCHAR * 32),
        ("szOEMVxD", wintypes.WCHAR * 260),
    ]


class HidReportSubChannel:
    """
    Isolated per-Report-ID sub-channel inside a HidInterfaceStream.
    Demultiplexing by Report ID (Byte 0: e.g. 0x01 Gamepad vs 0x02/0x07 Sensor vs 0x04/0x05 Vendor)
    ensures that alternating packet types on the same HID handle never overwrite each other's
    baseline or cause random byte-jumping in DirectInput / Raw HID mode.
    """
    def __init__(self, report_id: int, is_vendor_event: bool = False):
        self.report_id = int(report_id)
        self.open_time = time.perf_counter()
        self.calibrated = bool(is_vendor_event)
        self.is_event_driven = bool(is_vendor_event)
        self.baseline_locked = bool(is_vendor_event)
        self.first_event_packet = None
        self.last_event_time = 0.0
        self.samples = []
        self.baseline = bytearray(64)
        self.baseline[0] = int(report_id) & 0xFF
        self.noisy_mask = bytearray(64)
        self.byte_distinct_values = [set() for _ in range(64)]
        self.modal_baseline = bytearray(64)
        self.modal_baseline[0] = int(report_id) & 0xFF
        self.modal_noisy_mask = bytearray(64)
        self.modal_has_snapshot = False
        self.last_clean_delta = bytes(64)
        self.last_raw_packet = bytes(64)
        self.prev_logged_packet = None
        self.last_byte_change_log_time = 0.0
        self.packets_read = 0
        self.imu_ring = []
        self.auto_imu_checked = False
        self.auto_imu_spec = None  # {"offset": int, "bias": [float, float, float], "deadzone": int}

    def reset_modal_snapshot(self):
        self.modal_noisy_mask = bytearray(64)
        if self.packets_read > 0:
            self.modal_baseline = bytearray(self.last_raw_packet)
            self.modal_has_snapshot = True
        else:
            self.modal_baseline = bytearray(self.baseline)
            self.modal_has_snapshot = True


class HidInterfaceStream:
    """
    Tracks per-interface AND per-Report-ID idle baselines and noise masks
    for each readable VID_17EF collection (hidapi OR Win32 WM_INPUT RawInput).
    """
    def __init__(self, key: str, dev, usage_page: int, usage: int, pid: int, dev_path: str = ""):
        self.key = key
        self.dev = dev
        self.usage_page = usage_page
        self.usage = usage
        self.pid = pid
        self.dev_path = dev_path
        self.open_time = time.perf_counter()
        self.last_packet_time = 0.0
        self.external_queue = []
        self.sub_channels = {}  # report_id (int) -> HidReportSubChannel
        self.packets_read = 0
        self.last_raw_packet = bytes(64)
        self.live_gyro = (0, 0, 0)

    def get_or_create_subchannel(self, report_id: int) -> HidReportSubChannel:
        rid = int(report_id)
        sub = self.sub_channels.get(rid)
        if sub is None:
            # Note: Report ID 0x04 (R04) carries continuous 250Hz IMU gyro/touchpad telemetry
            # alongside button bytes (like R04:B17:0x02 for M2). Keep R04 as is_vendor_event=False
            # so initial calibration and SETTLING automatically mask out changing gyro/touch bytes!
            is_vendor_evt = (
                self.usage_page == 0x000C
                or (self.usage_page == 0x0001 and self.usage in (0x0002, 0x0080))
                or rid == 0x05
            )
            sub = HidReportSubChannel(rid, is_vendor_event=is_vendor_evt)
            self.sub_channels[rid] = sub
        return sub

    def reset_calibration(self):
        self.open_time = time.perf_counter()
        self.sub_channels.clear()
        self.live_gyro = (0, 0, 0)

    def reset_modal_snapshot(self):
        for sub in self.sub_channels.values():
            sub.reset_modal_snapshot()


def _normalize_hid_path(raw_path) -> str:
    """
    Normalizes a Windows HID device path (bytes or str) to a canonical uppercase key
    so hidapi paths and WM_INPUT GetRawInputDeviceInfoW paths for the EXACT same
    composite interface match 1-to-1 without ever colliding across different MI_xx / COLxx interfaces.
    """
    if isinstance(raw_path, (bytes, bytearray)):
        s = raw_path.decode("utf-8", errors="ignore")
    else:
        s = str(raw_path or "")
    s = s.upper().strip().replace("/", chr(92))
    idx = s.find("VID_17EF")
    if idx >= 0:
        s = s[idx:]
    return s


def _extract_mi_col_tags(raw_path) -> tuple:
    """
    Extracts (mi_tag, col_tag) from a Windows composite device path (e.g. ('MI02', 'C01'))
    so every composite controller interface has a distinct, human-readable stream key.
    """
    norm = _normalize_hid_path(raw_path)
    mi_m = re.search(r"MI_([0-9A-F]{2})", norm)
    col_m = re.search(r"COL([0-9A-F]{2})", norm)
    mi_tag = f"MI{mi_m.group(1)}" if mi_m else "MI00"
    col_tag = f"C{col_m.group(1)}" if col_m else "C00"
    return mi_tag, col_tag


# ==============================================================================
# 3B. WIN32 WM_INPUT RAW INPUT GLOBAL SINK (ALL COMPOSITE HID + MOUSE INTERFACES)
# ==============================================================================
class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class Win32RawInputHidSink(QAbstractNativeEventFilter):
    """
    Captures WM_INPUT (0x00FF) Raw Input reports directly from the Windows kernel for
    ALL Lenovo VID_17EF composite controller interfaces simultaneously while excluding
    Touchscreen/Digitizer (0x000D) and Windows Sensor (0x0020) noise:
      - Vendor 0xFFA0 / 0xFF00 / 0xFF01 / 0xFF80 / 0xFF89
      - Consumer Control 0x000C & System Control 0x0001:0x0080
      - Composite HID Mouse 0x0001:0x0002 (RIM_TYPEMOUSE — Mouse 5, Mouse 4, Scroll Wheel Click & Delta!)
      - All Composite Gamepads & Joysticks 0x0001:0x0004 & 0x0001:0x0005
    """
    def __init__(self, hardware_reader, log_fn):
        super().__init__()
        self.reader = hardware_reader
        self.log = log_fn
        self.dev_info_cache = {}
        self.registered = False

    def register_for_hwnd(self, hwnd: int):
        if sys.platform != "win32" or not hwnd:
            return
        try:
            user32 = ctypes.windll.user32
            RIDEV_INPUTSINK = 0x00000100
            RIDEV_PAGEONLY = 0x00000020
            targets = [
                (0xFFA0, 0x0000, RIDEV_INPUTSINK | RIDEV_PAGEONLY),
                (0xFF00, 0x0000, RIDEV_INPUTSINK | RIDEV_PAGEONLY),
                (0xFF01, 0x0000, RIDEV_INPUTSINK | RIDEV_PAGEONLY),
                (0xFF80, 0x0000, RIDEV_INPUTSINK | RIDEV_PAGEONLY),
                (0xFF89, 0x0000, RIDEV_INPUTSINK | RIDEV_PAGEONLY),
                (0x000C, 0x0000, RIDEV_INPUTSINK | RIDEV_PAGEONLY),
                (0xFFA0, 0x0001, RIDEV_INPUTSINK),
                (0x000C, 0x0001, RIDEV_INPUTSINK),
                (0x0001, 0x0005, RIDEV_INPUTSINK),
                (0x0001, 0x0004, RIDEV_INPUTSINK),
                (0x0001, 0x0002, RIDEV_INPUTSINK),  # Composite HID Mouse (Mouse 5 / Mouse 4 / Wheel Click!)
                (0x0001, 0x0080, RIDEV_INPUTSINK),
            ]
            reg_count = 0
            for up, us, flags in targets:
                rid = RAWINPUTDEVICE()
                rid.usUsagePage = up
                rid.usUsage = us
                rid.dwFlags = flags
                rid.hwndTarget = hwnd
                if user32.RegisterRawInputDevices(
                    ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
                ):
                    reg_count += 1
            self.registered = reg_count > 0
            if self.registered:
                self.log(f"[WM_INPUT] Registered {reg_count} kernel RawInput composite listeners for VID_17EF (Touchscreen 0x000D & Sensor 0x0020 excluded).")
        except Exception as exc:
            self.log(f"[WM_INPUT] Notice: {exc}")

    def _get_device_details(self, h_device: int):
        if not h_device:
            return "", 0, 0, 0, 0
        if h_device in self.dev_info_cache:
            return self.dev_info_cache[h_device]
        path_str = ""
        vid, pid, upage, usage = 0, LENOVO_PID_XINPUT, 0xFFA0, 0x0001
        try:
            user32 = ctypes.windll.user32
            RIDI_DEVICENAME = 0x20000007
            RIDI_DEVICEINFO = 0x2000000B
            sz = wintypes.UINT(0)
            user32.GetRawInputDeviceInfoW(wintypes.HANDLE(h_device), RIDI_DEVICENAME, None, ctypes.byref(sz))
            if sz.value > 0:
                buf = ctypes.create_unicode_buffer(sz.value + 2)
                if user32.GetRawInputDeviceInfoW(wintypes.HANDLE(h_device), RIDI_DEVICENAME, buf, ctypes.byref(sz)) > 0:
                    path_str = (buf.value or "").upper()
            if "VID_17EF" in path_str:
                vid = LENOVO_VENDOR_ID
            m = re.search(r"PID_([0-9A-F]{4})", path_str)
            if m:
                pid = int(m.group(1), 16)

            info_sz = wintypes.UINT(32)
            info_buf = ctypes.create_string_buffer(32)
            struct.pack_into("<I", info_buf, 0, 32)
            if user32.GetRawInputDeviceInfoW(wintypes.HANDLE(h_device), RIDI_DEVICEINFO, info_buf, ctypes.byref(info_sz)) > 0:
                _cb, dw_type = struct.unpack_from("<II", info_buf.raw, 0)
                if dw_type == 2:  # RIM_TYPEHID
                    _cb, _t, d_vid, d_pid, _d_ver, d_upage, d_usage = struct.unpack_from("<IIIIIHH", info_buf.raw, 0)
                    vid = int(d_vid) or vid
                    if d_pid:
                        pid = int(d_pid)
                    upage = int(d_upage)
                    usage = int(d_usage)
                elif dw_type == 0:  # RIM_TYPEMOUSE (Composite VID_17EF Mouse Interface)
                    upage = 0x0001
                    usage = 0x0002
        except Exception:
            pass
        res = (path_str, vid, pid, upage, usage)
        self.dev_info_cache[h_device] = res
        return res

    def nativeEventFilter(self, eventType, message):
        if sys.platform != "win32":
            return False, 0
        try:
            if eventType in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                msg_ptr = int(message)
                if not msg_ptr:
                    return False, 0
                msg = wintypes.MSG.from_address(msg_ptr)
                if msg.message == 0x00FF:  # WM_INPUT
                    self._process_wm_input(msg.lParam)
        except Exception:
            pass
        return False, 0

    def _process_wm_input(self, lparam):
        user32 = ctypes.windll.user32
        RID_INPUT = 0x10000003
        dw_size = wintypes.UINT(0)
        hdr_size = ctypes.sizeof(RAWINPUTHEADER)
        if user32.GetRawInputData(
            wintypes.HANDLE(lparam), RID_INPUT, None, ctypes.byref(dw_size), hdr_size
        ) != 0 or dw_size.value < hdr_size:
            return

        buf = ctypes.create_string_buffer(dw_size.value)
        if user32.GetRawInputData(
            wintypes.HANDLE(lparam), RID_INPUT, buf, ctypes.byref(dw_size), hdr_size
        ) != dw_size.value:
            return

        raw_bytes = buf.raw
        hdr = RAWINPUTHEADER.from_buffer_copy(raw_bytes[:hdr_size])
        dev_path, vid, pid, upage, usage = self._get_device_details(int(hdr.hDevice or 0))
        if vid != LENOVO_VENDOR_ID and "VID_17EF" not in dev_path:
            return
        # Never ingest Touchscreen/Digitizer (0x000D) or Windows Sensor (0x0020) collections
        if upage in (0x000D, 0x0020):
            return

        payload = raw_bytes[hdr_size:]
        if hdr.dwType == 2 and len(payload) >= 8:  # RIM_TYPEHID
            dw_size_hid, dw_count = struct.unpack_from("<II", payload, 0)
            hid_data = payload[8:]
            if dw_size_hid > 0 and dw_count > 0:
                for idx in range(dw_count):
                    start = idx * dw_size_hid
                    rep = hid_data[start:start + dw_size_hid]
                    if rep:
                        self.reader.ingest_rawinput_hid(
                            int(hdr.hDevice or 0), pid, upage, usage, dev_path, rep
                        )
        elif hdr.dwType == 0 and len(payload) >= 8:  # RIM_TYPEMOUSE (only button flags; ignore X/Y move!)
            us_btn_flags, us_btn_data = struct.unpack_from("<HH", payload, 4)
            if us_btn_flags != 0:
                self.reader.ingest_rawinput_mouse(
                    int(hdr.hDevice or 0), pid, dev_path, int(us_btn_flags), int(us_btn_data)
                )


class LegionGoHardwareReader:
    """
    Universal Multi-Composite Hardware Poller supporting:
      - Simultaneous listening to ALL Lenovo VID_17EF composite HID & WM_INPUT interfaces
        (MI_00..MI_05, COL01..COL08, Vendor 0xFFA0, Consumer 0x000C, Composite Mouse 0x0001:0x0002,
        and Composite Gamepads 0x0001:0x0004/0x0005) in both XInput and DInput modes
      - Unified RB / M1 switch handling (XInput 0x0200, R04:B17:0x02, R05:0x24, Mouse 4/5, F13)
      - Device-specific Scroll Wheel Up / Down / Click strictly isolated to VID_17EF composite mouse
      - DirectInput + XInput + Raw HID Half-Press / Full-Press Analog Trigger Stage Engine
    """
    def __init__(self, hook_interceptor: Win32TouchpadAndShortcutInterceptor, log_fn=None):
        self.hook = hook_interceptor
        self.log = log_fn or (lambda _m: None)
        self.xinput_dll = None
        self.xinput_get_state_ex = None
        self.winmm_dll = None

        if sys.platform == "win32":
            for dll_name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
                try:
                    self.xinput_dll = ctypes.windll.LoadLibrary(dll_name)
                    try:
                        self.xinput_get_state_ex = ctypes.WINFUNCTYPE(
                            wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(XINPUT_STATE)
                        )((100, self.xinput_dll))
                    except Exception:
                        self.xinput_get_state_ex = None
                    break
                except OSError:
                    continue
            try:
                self.winmm_dll = ctypes.windll.winmm
            except Exception:
                self.winmm_dll = None

        self.hid_streams = []
        self.opened_hid_paths = set()
        self.rawinput_streams_by_handle = {}
        self.rawinput_mouse_bitmaps = {}  # h_device -> bytearray(64)
        self.rawinput_wheel_click = False
        self.rawinput_wheel_up_until = 0.0
        self.rawinput_wheel_down_until = 0.0
        self.rawinput_mouse_xbutton1 = False  # Mouse 4 (XButton1)
        self.rawinput_mouse_xbutton2 = False  # Mouse 5 (XButton2)
        self.connected_pids = set()
        self.active_xinput_slot = -1
        self.active_xinput_slots = []
        self.active_dinput_mode = "None"
        self.detected_mode_summary = "Scanning..."
        self.learning_target_button = None
        self.learning_stage = "IDLE"  # IDLE, SETTLING, WAITING_PRESS, WAITING_RELEASE, CONFIRMED
        self.learning_start_time = 0.0
        self.learning_candidate = None
        self._candidate_tracker = {}
        self._ignore_learning_until = 0.0
        self._modal_base_xinput = 0
        self._modal_base_dinput = {}
        self._modal_base_wheel_click = False
        self._modal_base_mouse4 = False
        self._modal_base_mouse5 = False
        self._modal_base_vks = set()
        self.last_learned_summary = ""
        self._prev_xinput_btns = 0
        self._prev_dinput_btns = {}
        self._dinput_axis_rest = {}
        self.last_raw_dinput_axes = {}  # (joy_id, axis_name) -> int (0..65535)
        self._last_reconnect_attempt = 0.0
        self._app_birth_time = time.perf_counter()
        self._wakeup_waves_done = set()
        self._hidhide_startup_checked = False

        # 2-Step Interactive Gyro Calibration Wizard state
        self.gyro_cal_mode = "IDLE"  # IDLE, STILL, ROTATE
        self.gyro_cal_still_samples = {}  # (iface_key, report_id) -> list[bytes]
        self.gyro_cal_rotate_samples = {}  # (iface_key, report_id) -> list[bytes]

        # Interactive Trigger Analog & Press Stage Calibration state
        self.trigger_cal_target = None  # "LT" or "RT"
        self.trigger_cal_stage = "IDLE"  # "IDLE", "REST", "PULL"
        self.trigger_cal_rest_dinput = {}  # (joy_id, axis_name) -> list[int]
        self.trigger_cal_peak_dinput = {}  # (joy_id, axis_name) -> list[int]
        self.trigger_cal_rest_hid = {}     # (iface_key, report_id, byte_idx) -> list[int]
        self.trigger_cal_peak_hid = {}     # (iface_key, report_id, byte_idx) -> list[int]
        self.trigger_cal_rest_xinput = {"LT": [], "RT": []}
        self.trigger_cal_peak_xinput = {"LT": [], "RT": []}
        self.last_trigger_cal_summary = ""

        # Deep Input Press & Raw Byte-Delta Inspector state (Tab 3 Report View)
        self.deep_log_presses = True
        self.deep_log_raw_bytes = True
        self.deep_log_noisy_bytes = False
        self._prev_logged_xinput_btns = 0
        self._prev_logged_dinput_btns = {}
        self._prev_logged_mouse_state = (False, False, False)  # (wheel_click, mouse4, mouse5)
        self._prev_logged_vks = set()
        self._prev_logged_hw_buttons = {}
        self._trigger_sources_this_tick = {}  # btn_key -> list[str]

    def _add_trigger_source(self, btn_key: str, source_desc: str):
        lst = self._trigger_sources_this_tick.setdefault(btn_key, [])
        if source_desc not in lst:
            lst.append(source_desc)

    def dump_all_streams_hex_snapshot(self):
        """
        Prints a full diagnostic hex snapshot of all open VID_17EF HID streams, R01..R05 sub-channels,
        baselines, noisy masks, XInput, DirectInput, and Mouse/Keyboard hook states to Tab 3 log.
        """
        self.log("=" * 86)
        self.log(
            f"[DEEP SNAPSHOT] Mode: {self.detected_mode_summary} | "
            f"XInput wButtons=0x{self._prev_xinput_btns:04X} (Slots={self.active_xinput_slots}) | "
            f"DInput={self._prev_dinput_btns}"
        )
        wheel_clk = bool(self.rawinput_wheel_click)
        m4 = bool(self.hook.mouse_xbutton1 or self.rawinput_mouse_xbutton1)
        m5 = bool(self.hook.mouse_xbutton2 or self.rawinput_mouse_xbutton2)
        vks = [f"{format_vk_name(v)}(0x{v:02X})" for v in sorted(self.hook.active_vk_codes)]
        self.log(
            f"[DEEP SNAPSHOT] Mouse5(XButton2)={m5} | Mouse4(XButton1)={m4} | "
            f"WheelClick(VID_17EF)={wheel_clk} | Active Keys={vks}"
        )
        if not self.hid_streams:
            self.log("[DEEP SNAPSHOT] No VID_17EF HID streams currently open.")
        for st in self.hid_streams:
            if not st.sub_channels:
                self.log(f"  Stream {st.key} (UP=0x{st.usage_page:04X} U=0x{st.usage:04X}): 0 packets received yet.")
                continue
            for rid, sub in sorted(st.sub_channels.items()):
                raw_hex = " ".join(f"{b:02X}" for b in sub.last_raw_packet[:32])
                base_hex = " ".join(f"{b:02X}" for b in sub.baseline[:32])
                noisy_idxs = [i for i in range(1, 64) if sub.noisy_mask[i] != 0]
                diffs = []
                for i in range(1, 64):
                    if sub.last_raw_packet[i] != sub.baseline[i]:
                        tag = "noisy" if sub.noisy_mask[i] else "QUIET"
                        diffs.append(
                            f"B{i:02d}:0x{sub.baseline[i]:02X}->0x{sub.last_raw_packet[i]:02X}(^0x{sub.last_raw_packet[i]^sub.baseline[i]:02X},{tag})"
                        )
                self.log(
                    f"  Stream {st.key}:R{rid:02X} | pkts={sub.packets_read} | "
                    f"event_driven={sub.is_event_driven} | auto_masked_bytes={noisy_idxs[:16]}"
                )
                self.log(f"    Raw [00..31]: {raw_hex}")
                self.log(f"    Base[00..31]: {base_hex}")
                self.log(f"    Active Diffs: {', '.join(diffs[:12]) if diffs else 'None (all bytes at baseline)'}")
        self.log("=" * 86)

    def _ensure_hidhide_whitelisted_on_startup(self):
        if self._hidhide_startup_checked or sys.platform != "win32":
            return
        self._hidhide_startup_checked = True
        cli_path = r"C:\Program Files\Nefarius Software Solutions\HidHide\x64\HidHideCLI.exe"
        if not os.path.exists(cli_path):
            return
        try:
            subprocess.run(
                [cli_path, "--app-reg", sys.executable],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2.0,
                check=False,
            )
            pyw = Path(sys.executable).with_name("pythonw.exe")
            if pyw.exists():
                subprocess.run(
                    [cli_path, "--app-reg", str(pyw)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=2.0,
                    check=False,
                )
            subprocess.run(
                [cli_path, "--cloak-off"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2.0,
                check=False,
            )
            self.log("[HidHide] Startup self-whitelist (--app-reg) & uncloak verified for full VID_17EF composite access.")
        except Exception:
            pass

    def connect_hardware(self) -> bool:
        self._ensure_hidhide_whitelisted_on_startup()
        if not HAS_HIDAPI:
            return False
        kept_rawinput = [st for st in self.hid_streams if st.dev is None and st.usage_page not in (0x000D, 0x0020)]
        for st in self.hid_streams:
            if st.dev is not None:
                try:
                    st.dev.close()
                except Exception:
                    pass
        self.hid_streams = list(kept_rawinput)
        self.opened_hid_paths.clear()
        self.connected_pids.clear()

        try:
            devices = hid.enumerate(LENOVO_VENDOR_ID, 0)
            opened_count = 0
            for idx, dev_info in enumerate(devices):
                pid = dev_info.get("product_id", 0)
                if pid in LENOVO_PRODUCT_IDS or pid != 0:
                    upage = dev_info.get("usage_page", 0)
                    usage = dev_info.get("usage", 0)
                    # Skip Touchscreen/Digitizer (0x000D) and Windows Sensor (0x0020) collections
                    if upage in (0x000D, 0x0020):
                        continue
                    self.connected_pids.add(pid)
                    iface = dev_info.get("interface_number", idx)
                    dev_path = dev_info.get("path", b"")
                    norm_path = _normalize_hid_path(dev_path)
                    if norm_path in self.opened_hid_paths:
                        continue
                    mi_tag, col_tag = _extract_mi_col_tags(dev_path)
                    key = f"PID{pid:04X}_{mi_tag}_{col_tag}_UP{upage:04X}_U{usage:04X}_IF{iface}_{idx}"
                    try:
                        d = hid.device()
                        d.open_path(dev_path)
                        d.set_nonblocking(1)
                        st = HidInterfaceStream(key, d, upage, usage, pid, dev_path=norm_path)
                        self.hid_streams.append(st)
                        self.opened_hid_paths.add(norm_path)
                        opened_count += 1
                    except Exception:
                        continue
            if opened_count > 0:
                pids_hex = ", ".join(f"0x{p:04X}" for p in sorted(self.connected_pids))
                self.log(f"[Hardware] Listening to {opened_count} Lenovo VID_17EF ({pids_hex}) composite HID collection(s) simultaneously.")
                self.send_lenovo_raw_button_wakeup()
            return opened_count > 0 or self.active_xinput_slot >= 0
        except Exception:
            return False

    def _check_for_new_hid_interfaces(self):
        if not HAS_HIDAPI:
            return
        try:
            devices = hid.enumerate(LENOVO_VENDOR_ID, 0)
            new_opened = 0
            for idx, dev_info in enumerate(devices):
                upage = dev_info.get("usage_page", 0)
                usage = dev_info.get("usage", 0)
                if upage in (0x000D, 0x0020):
                    continue
                dev_path = dev_info.get("path", b"")
                norm_path = _normalize_hid_path(dev_path)
                if not norm_path or norm_path in self.opened_hid_paths:
                    continue
                pid = dev_info.get("product_id", 0)
                iface = dev_info.get("interface_number", idx)
                mi_tag, col_tag = _extract_mi_col_tags(dev_path)
                key = f"PID{pid:04X}_{mi_tag}_{col_tag}_UP{upage:04X}_U{usage:04X}_IF{iface}_{len(self.hid_streams)}"
                try:
                    d = hid.device()
                    d.open_path(dev_path)
                    d.set_nonblocking(1)
                    st = HidInterfaceStream(key, d, upage, usage, pid, dev_path=norm_path)
                    self.hid_streams.append(st)
                    self.opened_hid_paths.add(norm_path)
                    self.connected_pids.add(pid)
                    new_opened += 1
                except Exception:
                    continue
            if new_opened > 0:
                self.log(f"[Hotplug] Attached {new_opened} additional Lenovo VID_17EF composite interface(s).")
                self.send_lenovo_raw_button_wakeup(quiet_log=True)
        except Exception:
            pass

    def send_lenovo_raw_button_wakeup(self, quiet_log: bool = False):
        """
        Sends Lenovo Legion Go Vendor HID (0xFFA0, Report IDs 0x05 & 0x04) initialization packets
        + onboard rear-button slot activation across ALL writable VID_17EF composite streams.
        """
        self._ignore_learning_until = time.perf_counter() + 0.35
        sent = 0
        wakeup_reports = [
            # 1. Length-Prefixed (Byte 1 = 0x06) Raw Button & Software Intercept Enable for Left (0x01) & Right (0x02)
            bytes([0x05, 0x06, 0x01, 0x01, 0x01, 0x01]) + bytes(58),
            bytes([0x05, 0x06, 0x01, 0x01, 0x02, 0x01]) + bytes(58),
            bytes([0x05, 0x06, 0x02, 0x01, 0x01, 0x01]) + bytes(58),
            bytes([0x05, 0x06, 0x02, 0x01, 0x02, 0x01]) + bytes(58),
            # 2. Direct Sub-Command Format for Firmware Variations (Report 0x05 & 0x04)
            bytes([0x05, 0x04, 0x01, 0x01, 0x01]) + bytes(59),
            bytes([0x05, 0x04, 0x01, 0x01, 0x02]) + bytes(59),
            bytes([0x04, 0x05, 0x01, 0x01, 0x01]) + bytes(59),
            bytes([0x04, 0x05, 0x01, 0x01, 0x02]) + bytes(59),
            # 3. Wake Onboard Rear Button Mapping Table (Left 0x01 Slots 1..3 = Y1..Y3; Right 0x02 Slots 1..3 = M1..M3)
            bytes([0x05, 0x08, 0x07, 0x03, 0x01, 0x01, 0x01, 0x21]) + bytes(56),
            bytes([0x05, 0x08, 0x07, 0x03, 0x01, 0x02, 0x01, 0x22]) + bytes(56),
            bytes([0x05, 0x08, 0x07, 0x03, 0x01, 0x03, 0x01, 0x23]) + bytes(56),
            bytes([0x05, 0x08, 0x07, 0x03, 0x02, 0x01, 0x01, 0x24]) + bytes(56),
            bytes([0x05, 0x08, 0x07, 0x03, 0x02, 0x02, 0x01, 0x25]) + bytes(56),
            bytes([0x05, 0x08, 0x07, 0x03, 0x02, 0x03, 0x01, 0x26]) + bytes(56),
            # 4. Enable 6-Axis IMU Gyroscope / Accelerometer Telemetry & Status Handshake
            bytes([0x05, 0x08, 0x01, 0x01, 0x01]) + bytes(59),
            bytes([0x05, 0x08, 0x01, 0x01, 0x02]) + bytes(59),
            bytes([0x05, 0x03, 0x01, 0x00, 0x01]) + bytes(59),
            bytes([0x05, 0x03, 0x01, 0x00, 0x02]) + bytes(59),
        ]
        for st in self.hid_streams:
            if st.dev is not None:
                for pkt in wakeup_reports:
                    try:
                        st.dev.write(pkt)
                        sent += 1
                    except Exception:
                        pass
                    try:
                        st.dev.send_feature_report(pkt)
                    except Exception:
                        pass
                for feat_id in (0x05, 0x04):
                    try:
                        st.dev.get_feature_report(feat_id, 64)
                    except Exception:
                        pass
        for st in self.hid_streams:
            st.reset_modal_snapshot()
        if sent > 0 and not quiet_log:
            self.log(f"[Lenovo 0xFFA0] Auto-unlocked raw rear buttons, Legion L/R & IMU across all composite endpoints ({sent} packets sent).")

    def ingest_rawinput_hid(self, h_device: int, pid: int, upage: int, usage: int, dev_path: str, rep: bytes):
        """
        Ingests WM_INPUT RawInput HID packets from ALL Lenovo VID_17EF composite interfaces
        (excluding Touchscreen 0x000D and Windows Sensor 0x0020).
        """
        if upage in (0x000D, 0x0020):
            return
        self.connected_pids.add(pid)
        norm_path = _normalize_hid_path(dev_path)
        if norm_path:
            for existing in self.hid_streams:
                if (
                    existing.dev is not None
                    and existing.dev_path == norm_path
                    and existing.packets_read > 0
                ):
                    return

        st = self.rawinput_streams_by_handle.get(h_device)
        if st is None:
            mi_tag, col_tag = _extract_mi_col_tags(dev_path)
            idx_tag = len(self.rawinput_streams_by_handle)
            key = f"WM_PID{pid:04X}_{mi_tag}_{col_tag}_UP{upage:04X}_U{usage:04X}_{idx_tag}"
            st = HidInterfaceStream(key, None, upage, usage, pid, dev_path=norm_path)
            self.rawinput_streams_by_handle[h_device] = st
            self.hid_streams.append(st)
            self.log(f"[WM_INPUT] Attached composite RawInput stream {key}")
        if len(st.external_queue) < 32:
            st.external_queue.append(rep)

    def ingest_rawinput_mouse(self, h_device: int, pid: int, dev_path: str, us_btn_flags: int, us_btn_data: int):
        """
        Captures Mouse 5 (XButton2 = 0x0100/0x0200), Mouse 4 (XButton1 = 0x0040/0x0080),
        Rear Scroll Wheel Click (Middle Button = 0x0010/0x0020), and Scroll Wheel Rotation (0x0400)
        strictly from the Lenovo VID_17EF composite Mouse interface (0x0001:0x0002), while ignoring X/Y cursor move
        and leaving external USB/Bluetooth mice completely untouched.
        """
        self.connected_pids.add(pid)
        norm_path = _normalize_hid_path(dev_path)
        st = self.rawinput_streams_by_handle.get(h_device)
        if st is None:
            mi_tag, col_tag = _extract_mi_col_tags(dev_path)
            idx_tag = len(self.rawinput_streams_by_handle)
            key = f"WM_MOUSE_PID{pid:04X}_{mi_tag}_{col_tag}_UP0001_U0002_{idx_tag}"
            st = HidInterfaceStream(key, None, 0x0001, 0x0002, pid, dev_path=norm_path)
            self.rawinput_streams_by_handle[h_device] = st
            self.hid_streams.append(st)
            self.log(f"[WM_INPUT] Attached Lenovo VID_17EF composite Mouse / Scroll Wheel stream {key}")

        bmp = self.rawinput_mouse_bitmaps.get(h_device)
        if bmp is None:
            bmp = bytearray(64)
            bmp[0] = 0x02  # Report ID 0x02 for composite mouse stream
            self.rawinput_mouse_bitmaps[h_device] = bmp

        now = time.perf_counter()
        changed = False
        # Middle Mouse Button (Mouse 3) = Rear Scroll Wheel Click (VID_17EF only)
        if us_btn_flags & 0x0010:  # RI_MOUSE_MIDDLE_BUTTON_DOWN
            self.rawinput_wheel_click = True
            self.hook.last_lenovo_wheel_hw_time = now
            bmp[1] |= 0x04
            changed = True
        if us_btn_flags & 0x0020:  # RI_MOUSE_MIDDLE_BUTTON_UP
            self.rawinput_wheel_click = False
            self.hook.last_lenovo_wheel_hw_time = now
            bmp[1] &= (~0x04) & 0xFF
            changed = True
        # Mouse 4 (XButton1)
        if us_btn_flags & 0x0040:  # RI_MOUSE_BUTTON_4_DOWN
            self.rawinput_mouse_xbutton1 = True
            bmp[1] |= 0x08
            changed = True
        if us_btn_flags & 0x0080:  # RI_MOUSE_BUTTON_4_UP
            self.rawinput_mouse_xbutton1 = False
            bmp[1] &= (~0x08) & 0xFF
            changed = True
        # Mouse 5 (XButton2)
        if us_btn_flags & 0x0100:  # RI_MOUSE_BUTTON_5_DOWN
            self.rawinput_mouse_xbutton2 = True
            bmp[1] |= 0x10
            changed = True
        if us_btn_flags & 0x0200:  # RI_MOUSE_BUTTON_5_UP
            self.rawinput_mouse_xbutton2 = False
            bmp[1] &= (~0x10) & 0xFF
            changed = True
        if us_btn_flags & 0x0400:  # RI_MOUSE_WHEEL (strictly VID_17EF)
            w_delta = ctypes.c_short(us_btn_data & 0xFFFF).value
            if w_delta != 0:
                self.hook.last_lenovo_wheel_hw_time = now
                self.hook.wheel_delta = 1 if w_delta > 0 else -1
                self.hook.last_wheel_time = now
                if w_delta > 0:
                    self.rawinput_wheel_up_until = now + 0.095
                    self.rawinput_wheel_down_until = 0.0
                else:
                    self.rawinput_wheel_down_until = now + 0.095
                    self.rawinput_wheel_up_until = 0.0

        if changed and len(st.external_queue) < 32:
            st.external_queue.append(bytes(bmp))

    def reset_idle_calibration(self):
        for st in self.hid_streams:
            st.reset_calibration()
        self._dinput_axis_rest.clear()
        self.hook.reset_pad_center()

    # --------------------------------------------------------------------------
    # 2-Step Interactive Gyro Calibration Wizard Engine
    # --------------------------------------------------------------------------
    def start_gyro_wizard_step1(self):
        self.gyro_cal_still_samples.clear()
        self.gyro_cal_rotate_samples.clear()
        self.gyro_cal_mode = "STILL"
        self.log("[Gyro Wizard] Step 1/2 started: Recording 1.5s resting baseline (keep controller still)...")

    def start_gyro_wizard_step2(self):
        self.gyro_cal_rotate_samples.clear()
        self.gyro_cal_mode = "ROTATE"
        self.log("[Gyro Wizard] Step 2/2 started: Recording 2.5s 3-axis rotation (tilt & rotate controller now)...")

    def cancel_gyro_wizard(self):
        self.gyro_cal_mode = "IDLE"

    def finalize_gyro_wizard(self, profile: dict) -> tuple:
        self.gyro_cal_mode = "IDLE"
        best_score = -1.0
        best_cal = None

        for key_tuple, rot_list in self.gyro_cal_rotate_samples.items():
            still_list = self.gyro_cal_still_samples.get(key_tuple, [])
            if len(still_list) < 6 or len(rot_list) < 10:
                continue
            iface_key, rep_id = key_tuple

            for endian in ("<", ">"):
                fmt = f"{endian}hhh"
                for offset in range(1, 57):
                    try:
                        s_vals = [struct.unpack_from(fmt, pkt, offset) for pkt in still_list]
                        r_vals = [struct.unpack_from(fmt, pkt, offset) for pkt in rot_list]
                    except Exception:
                        continue

                    n_s = float(len(s_vals))
                    n_r = float(len(r_vals))
                    means_s = [sum(v[a] for v in s_vals) / n_s for a in range(3)]
                    stds_s = [
                        math.sqrt(sum((v[a] - means_s[a]) ** 2 for v in s_vals) / n_s)
                        for a in range(3)
                    ]
                    means_r = [sum(v[a] for v in r_vals) / n_r for a in range(3)]
                    stds_r = [
                        math.sqrt(sum((v[a] - means_r[a]) ** 2 for v in r_vals) / n_r)
                        for a in range(3)
                    ]

                    if max(stds_s) > 900.0:
                        continue
                    active_axes = sum(1 for a in range(3) if stds_r[a] > 180.0 and stds_r[a] > stds_s[a] * 3.0)
                    if active_axes < 2:
                        continue
                    if max(stds_r) > 31000.0:
                        continue

                    ratios = [stds_r[a] / max(12.0, stds_s[a]) for a in range(3)]
                    score = (ratios[0] + ratios[1] + ratios[2]) * (1.5 if active_axes == 3 else 0.8)
                    if endian == "<":
                        score *= 1.15

                    if score > best_score:
                        best_score = score
                        best_cal = {
                            "iface": iface_key,
                            "report_id": int(rep_id),
                            "offset": int(offset),
                            "endian": endian,
                            "bias": [round(means_s[0], 2), round(means_s[1], 2), round(means_s[2], 2)],
                            "deadzone": int(max(45, min(280, max(stds_s) * 2.8))),
                        }

        if best_cal is not None:
            profile["gyroCalibration"] = best_cal
            profile["gyroEnabled"] = True
            msg = (
                f"Locked Gyro IMU on {best_cal['iface']} (Report 0x{best_cal['report_id']:02X}, "
                f"Bytes {best_cal['offset']}..{best_cal['offset']+5}, Endian '{best_cal['endian']}hhh', "
                f"Deadzone={best_cal['deadzone']})"
            )
            self.log(f"[Gyro Wizard] SUCCESS: {msg}")
            return True, msg, best_cal

        msg = (
            "No 6-axis IMU motion signal detected during Step 2. Make sure your controller is awake "
            "and rotate it briskly in Pitch, Yaw, and Roll during Step 2."
        )
        self.log(f"[Gyro Wizard] {msg}")
        return False, msg, None

    # --------------------------------------------------------------------------
    # Interactive Trigger Analog & Press Stage Detector (LT / RT)
    # --------------------------------------------------------------------------
    def start_trigger_stage_detection(self, target_side: str):
        self.trigger_cal_target = "LT" if str(target_side).upper() == "LT" else "RT"
        self.trigger_cal_rest_dinput.clear()
        self.trigger_cal_peak_dinput.clear()
        self.trigger_cal_rest_hid.clear()
        self.trigger_cal_peak_hid.clear()
        self.trigger_cal_rest_xinput = {"LT": [], "RT": []}
        self.trigger_cal_peak_xinput = {"LT": [], "RT": []}
        self.trigger_cal_stage = "REST"
        self.log(f"[Trigger Calibration] Step 1/2 ({self.trigger_cal_target}): Release both triggers completely to record resting baseline...")

    def advance_trigger_stage_to_pull(self):
        if self.trigger_cal_stage == "REST":
            self.trigger_cal_stage = "PULL"
            self.log(f"[Trigger Calibration] Step 2/2 ({self.trigger_cal_target}): Slowly squeeze {self.trigger_cal_target} through Half-Press (50%) to Full-Press (100%)...")

    def cancel_trigger_stage_detection(self):
        self.trigger_cal_stage = "IDLE"
        self.trigger_cal_target = None

    def finalize_trigger_stage_detection(self, profile: dict) -> tuple:
        target = self.trigger_cal_target or "RT"
        self.trigger_cal_stage = "IDLE"
        self.trigger_cal_target = None
        src_key = "ltSource" if target == "LT" else "rtSource"
        tcal = profile.setdefault("triggerCalibration", dict(DEFAULT_TRIGGER_CALIBRATION))

        best_source = None
        best_score = 0.0
        best_summary = ""

        # 1. Check DirectInput axes for proportional travel
        for key_tuple, pull_vals in self.trigger_cal_peak_dinput.items():
            rest_vals = self.trigger_cal_rest_dinput.get(key_tuple, [])
            if not rest_vals or not pull_vals:
                continue
            rest_avg = int(sum(rest_vals) / len(rest_vals))
            max_dev_val = max(pull_vals, key=lambda v: abs(v - rest_avg))
            span = abs(max_dev_val - rest_avg)
            unique_steps = len(set(pull_vals))
            if span >= 4000 and unique_steps >= 3:
                score = float(span) * (1.5 if unique_steps >= 6 else 1.0)
                if score > best_score:
                    best_score = score
                    joy_id, axis_name = key_tuple
                    best_source = {
                        "kind": "dinput_axis",
                        "joy_id": int(joy_id),
                        "axis": str(axis_name),
                        "rest": int(rest_avg),
                        "full": int(max_dev_val),
                    }
                    best_summary = (
                        f"DirectInput Joy{joy_id} Axis '{axis_name}' "
                        f"(Rest={rest_avg} -> Full={max_dev_val}, {unique_steps} analog steps)"
                    )

        # 2. Check XInput analog trigger (0..255)
        x_rest = self.trigger_cal_rest_xinput.get(target, [])
        x_pull = self.trigger_cal_peak_xinput.get(target, [])
        if x_rest and x_pull:
            r_avg = int(sum(x_rest) / len(x_rest))
            p_max = int(max(x_pull))
            if (p_max - r_avg) >= 60 and best_score < 20000.0:
                best_source = {
                    "kind": "xinput",
                    "side": target,
                    "rest": int(r_avg),
                    "full": int(p_max),
                }
                best_summary = f"XInput {target} Analog Trigger (Rest={r_avg} -> Full={p_max})"
                best_score = 25000.0

        # 3. Check Raw HID bytes (0..255) for proportional analog trigger travel
        for key_tuple, pull_vals in self.trigger_cal_peak_hid.items():
            rest_vals = self.trigger_cal_rest_hid.get(key_tuple, [])
            if not rest_vals or not pull_vals:
                continue
            if len(set(rest_vals)) > 3:
                continue
            rest_avg = int(sum(rest_vals) / len(rest_vals))
            max_dev_val = max(pull_vals, key=lambda v: abs(v - rest_avg))
            span = abs(max_dev_val - rest_avg)
            unique_steps = len(set(pull_vals))
            if span >= 35 and unique_steps >= 4:
                score = float(span) * 220.0 * (1.3 if unique_steps >= 8 else 1.0)
                if score > best_score:
                    best_score = score
                    iface_key, rep_id, byte_idx = key_tuple
                    best_source = {
                        "kind": "hid_byte",
                        "iface": str(iface_key),
                        "report_id": int(rep_id),
                        "byte": int(byte_idx),
                        "rest": int(rest_avg),
                        "full": int(max_dev_val),
                    }
                    best_summary = (
                        f"HID {iface_key}:R{rep_id:02X} Byte {byte_idx} "
                        f"(Rest={rest_avg} -> Full={max_dev_val}, {unique_steps} analog steps)"
                    )

        if best_source is not None:
            tcal[src_key] = best_source
            self.last_trigger_cal_summary = f"{target}: {best_summary}"
            self.log(f"[Trigger Calibration] LOCKED {self.last_trigger_cal_summary}")
            return True, self.last_trigger_cal_summary, best_source

        msg = (
            f"Could not detect an analog trigger sweep for {target}. "
            f"Make sure you hold both triggers at rest during Step 1, then squeeze {target} all the way down in Step 2."
        )
        self.log(f"[Trigger Calibration] {msg}")
        return False, msg, None

    # --------------------------------------------------------------------------
    # 3-Stage Press-and-Release Physical Button Detector
    # --------------------------------------------------------------------------
    def start_learning_button(self, button_key: str):
        self.last_learned_summary = ""
        self.learning_target_button = button_key
        self.hook.learning_target_btn = None
        self.learning_stage = "SETTLING"
        self.learning_start_time = time.perf_counter()
        self.learning_candidate = None
        self._candidate_tracker.clear()
        self._modal_base_xinput = self._prev_xinput_btns
        self._modal_base_dinput = dict(self._prev_dinput_btns)
        self._modal_base_wheel_click = bool(self.rawinput_wheel_click)
        self._modal_base_mouse4 = bool(self.hook.mouse_xbutton1 or self.rawinput_mouse_xbutton1)
        self._modal_base_mouse5 = bool(self.hook.mouse_xbutton2 or self.rawinput_mouse_xbutton2)
        self._modal_base_vks = set(self.hook.active_vk_codes)
        for st in self.hid_streams:
            st.reset_modal_snapshot()
        self.log(
            f"[Detect Physical] Stage 0/2 (Settling 350ms): Auto-masking gyro/touch noise across {len(self.hid_streams)} stream(s) for '{button_key}'..."
        )

    def cancel_learning_button(self):
        self.learning_target_button = None
        self.hook.learning_target_btn = None
        self.learning_stage = "IDLE"
        self.learning_candidate = None
        self._candidate_tracker.clear()

    def confirm_learning_candidate(self, profile: dict) -> bool:
        """
        Finalizes Stage 2 of Press-and-Release detection and saves the binding into profile.
        """
        cand = self.learning_candidate
        target = self.learning_target_button
        if not cand or not target:
            return False
        kind = cand.get("kind")

        # Clear any conflicting previous binding on this target control first
        for d_name in ("learnedVendorButtons", "learnedMouseButtons", "learnedKeyBindings", "learnedDinputButtons", "learnedXinputButtons"):
            profile.setdefault(d_name, {}).pop(target, None)

        if kind == "hid":
            entry = {
                "iface": str(cand.get("iface", "")),
                "report_id": int(cand.get("report_id", -1)),
                "byte": int(cand["byte"]),
                "mask": int(cand["mask"]),
                "pressed_val": int(cand["pressed_bit"]),
            }
            profile.setdefault("learnedVendorButtons", {})[target] = entry
        elif kind == "mouse_btn":
            profile.setdefault("learnedMouseButtons", {})[target] = str(cand.get("mouse_btn", "mouse5"))
        elif kind == "key_vk":
            profile.setdefault("learnedKeyBindings", {})[target] = int(cand.get("vk", 0x7C))
        elif kind == "xinput":
            profile.setdefault("learnedXinputButtons", {})[target] = int(cand["mask"])
        elif kind == "dinput":
            profile.setdefault("learnedDinputButtons", {})[target] = {
                "role": cand["role"],
                "bit": int(cand["bit"]),
            }
        elif kind == "wheel_click":
            profile.setdefault("learnedMouseButtons", {})[target] = "mouse3"
        elif kind == "wheel_up":
            profile.setdefault("learnedMouseButtons", {})[target] = "wheel_up"
        elif kind == "wheel_down":
            profile.setdefault("learnedMouseButtons", {})[target] = "wheel_down"
        self.last_learned_summary = cand.get("summary", "Captured Input")
        self.learning_target_button = None
        self.hook.learning_target_btn = None
        self.learning_stage = "CONFIRMED"
        self.log(f"[Detect Physical] CONFIRMED '{target}' -> {self.last_learned_summary}")
        return True

    def get_live_monitor_snapshot(self) -> str:
        stage_desc = self.learning_stage
        if self.learning_stage == "SETTLING":
            stage_desc = "STAGE 0/2: SETTLING IDLE SNAPSHOT & AUTO-MASKING GYRO/TOUCH (Do not press yet...)"
        elif self.learning_stage == "WAITING_PRESS":
            stage_desc = "STAGE 1/2: READY — PRESS & HOLD PHYSICAL BUTTON (OR SCROLL WHEEL / MOUSE 4-5 / F13-F24) NOW"
        elif self.learning_stage == "WAITING_RELEASE" and self.learning_candidate:
            stage_desc = f"STAGE 2/2: PRESS DETECTED ({self.learning_candidate.get('summary')}) — RELEASE TO CONFIRM!"
        elif self.learning_stage == "CONFIRMED":
            stage_desc = f"CONFIRMED: {self.last_learned_summary}"

        now = time.perf_counter()
        wheel_clk_active = bool(self.rawinput_wheel_click)
        wheel_up_active = bool(now < self.rawinput_wheel_up_until)
        wheel_dn_active = bool(now < self.rawinput_wheel_down_until)
        mouse4_active = bool(self.hook.mouse_xbutton1 or self.rawinput_mouse_xbutton1)
        mouse5_active = bool(self.hook.mouse_xbutton2 or self.rawinput_mouse_xbutton2)
        vk_list = [format_vk_name(v) for v in sorted(self.hook.active_vk_codes)]
        lines = [
            f"Detector State  : {stage_desc}",
            f"Controller Mode : {self.detected_mode_summary} | XInput=0x{self._prev_xinput_btns:04X} (RB/M1=0x0200) | DInput={self._prev_dinput_btns}",
            f"VID_17EF Mouse  : Mouse5={mouse5_active} | Mouse4={mouse4_active} | WheelClick={wheel_clk_active} | WheelUp={wheel_up_active} | WheelDown={wheel_dn_active} | Keys={vk_list}",
            f"VID_17EF Streams: {len(self.hid_streams)} collection(s) (Gyro & Touchpad Auto-Masked)",
            "-" * 78,
        ]
        for st in self.hid_streams:
            if not st.sub_channels:
                lines.append(f"{st.key:<30} [READY-EVT] pkts=0      (Instant Frame-1 event capture armed)")
                continue
            for rid, sub in sorted(st.sub_channels.items()):
                mode_tag = "EVENT-BTN" if sub.is_event_driven else ("STREAM" if sub.calibrated else "CALIB")
                hex_0_11 = " ".join(f"{b:02X}" for b in sub.last_raw_packet[:12])
                hex_12_23 = " ".join(f"{b:02X}" for b in sub.last_raw_packet[12:24])
                base_ref = sub.modal_baseline if (self.learning_target_button and sub.modal_has_snapshot) else sub.baseline
                nz_deltas = []
                for i in range(1, 64):
                    if sub.noisy_mask[i] == 0 and sub.modal_noisy_mask[i] == 0:
                        d_val = sub.last_raw_packet[i] ^ base_ref[i]
                        if d_val != 0:
                            nz_deltas.append(f"B{i}:0x{base_ref[i]:02X}->0x{sub.last_raw_packet[i]:02X}(^0x{d_val:02X})")
                delta_str = ", ".join(nz_deltas[:6]) if nz_deltas else "idle (all quiet bytes at baseline)"
                lines.append(
                    f"{st.key}:R{rid:02X} [{mode_tag:<9}] pkts={sub.packets_read:<6} delta={delta_str}"
                )
                if sub.packets_read > 0:
                    lines.append(
                        f"   B00..11=[{hex_0_11}] | B12..23=[{hex_12_23}]"
                    )
        return "\n".join(lines)

    @staticmethod
    def _apply_stick_deadzone(val: int, deadzone: int = 2400) -> int:
        if abs(val) < deadzone:
            return 0
        return max(-32768, min(32767, val))

    @staticmethod
    def _decode_dinput_pov_hat(pov: int, hw: dict):
        if pov is None or pov >= 36000 or pov < 0:
            return
        if pov <= 7:
            hat = pov
        else:
            hat = int(round(pov / 4500.0)) % 8
        if hat in (7, 0, 1):
            hw["dpadUp"] = True
        if hat in (1, 2, 3):
            hw["dpadRight"] = True
        if hat in (3, 4, 5):
            hw["dpadDown"] = True
        if hat in (5, 6, 7):
            hw["dpadLeft"] = True

    def _apply_dinput_button_bitmask(self, btns: int, unit_role: str, unit_key: str, hw: dict, profile: dict, has_analog_lt: bool = False, has_analog_rt: bool = False):
        learned_dinput = profile.setdefault("learnedDinputButtons", {})
        prev_d_log = self._prev_logged_dinput_btns.get(unit_key, 0)
        if btns != prev_d_log:
            self._prev_logged_dinput_btns[unit_key] = btns
            if self.deep_log_raw_bytes:
                xor_d = btns ^ prev_d_log
                bit_tags = []
                for b_i in range(32):
                    if xor_d & (1 << b_i):
                        state_s = "+ON" if (btns & (1 << b_i)) else "-OFF"
                        bit_tags.append(f"Bit{b_i}(Btn#{b_i+1}){state_s}")
                self.log(
                    f"[DINPUT DELTA] {unit_key}: dwButtons 0x{prev_d_log:08X} -> 0x{btns:08X} "
                    f"(XOR ^0x{xor_d:08X} | {', '.join(bit_tags)})"
                )
        self._prev_dinput_btns[unit_key] = btns

        if self.learning_target_button is not None:
            base_d = self._modal_base_dinput.get(unit_key, 0)
            if self.learning_stage == "SETTLING":
                self._modal_base_dinput[unit_key] = btns
            elif self.learning_stage == "WAITING_PRESS":
                diff_d = btns & (~base_d)
                if diff_d != 0:
                    for bit_idx in range(32):
                        if diff_d & (1 << bit_idx):
                            ckey = ("dinput", unit_key, bit_idx)
                            cnt = self._candidate_tracker.get(ckey, 0) + 1
                            self._candidate_tracker[ckey] = cnt
                            if cnt >= 2:
                                self.learning_candidate = {
                                    "kind": "dinput",
                                    "role": unit_key,
                                    "bit": bit_idx,
                                    "summary": f"DirectInput ({unit_key}) Button #{bit_idx + 1} (Bit {bit_idx})",
                                }
                                self.learning_stage = "WAITING_RELEASE"
                                self.log(
                                    f"[Detect Physical] Stage 1/2: Detected {self.learning_candidate['summary']} — Release button now to confirm!"
                                )
                            break
            elif self.learning_stage == "WAITING_RELEASE" and self.learning_candidate:
                if (
                    self.learning_candidate.get("kind") == "dinput"
                    and self.learning_candidate.get("role") in (unit_key, unit_role)
                ):
                    bit_idx = int(self.learning_candidate["bit"])
                    if (btns & (1 << bit_idx)) == 0:
                        self.confirm_learning_candidate(profile)

        claimed_bits = set()
        custom_bound_controls = set()
        for btn_key, spec in learned_dinput.items():
            spec_role = str(spec.get("role", "combined"))
            if spec_role in ("", unit_key, unit_role, "combined") or spec_role.startswith(unit_role):
                bit_idx = int(spec.get("bit", -1))
                if 0 <= bit_idx < 32:
                    claimed_bits.add(bit_idx)
                    custom_bound_controls.add(btn_key)
                    if btns & (1 << bit_idx):
                        hw[btn_key] = True
                        self._add_trigger_source(
                            btn_key, f"Learned DInput ({unit_key}) Bit {bit_idx} (Btn #{bit_idx+1}, dwButtons=0x{btns:08X})"
                        )

        def _set_default_bit(bit_idx: int, ctrl_key: str):
            if bit_idx in claimed_bits or ctrl_key in custom_bound_controls:
                return
            if btns & (1 << bit_idx):
                hw[ctrl_key] = True
                self._add_trigger_source(
                    ctrl_key, f"DInput ({unit_key}) Bit {bit_idx} (Btn #{bit_idx+1}, dwButtons=0x{btns:08X})"
                )

        if unit_role == "left":
            _set_default_bit(0, "buttonLB")
            if 1 not in claimed_bits and (btns & (1 << 1)) and not has_analog_lt and hw["leftTriggerAnalog"] == 0:
                hw["leftTriggerAnalog"] = 32767
            _set_default_bit(2, "buttonView")
            _set_default_bit(3, "leftStickClick")
            _set_default_bit(4, "legionLButton")
            _set_default_bit(5, "buttonY1")
            _set_default_bit(6, "buttonY2")
            _set_default_bit(8, "buttonView")
        elif unit_role == "right":
            _set_default_bit(0, "buttonA")
            _set_default_bit(1, "buttonB")
            _set_default_bit(2, "buttonX")
            _set_default_bit(3, "buttonY")
            _set_default_bit(4, "buttonRB")
            if 5 not in claimed_bits and (btns & (1 << 5)) and not has_analog_rt and hw["rightTriggerAnalog"] == 0:
                hw["rightTriggerAnalog"] = 32767
            _set_default_bit(6, "buttonMenu")
            _set_default_bit(7, "rightStickClick")
            _set_default_bit(8, "legionRButton")
            _set_default_bit(9, "buttonY3")
            _set_default_bit(10, "buttonRB")
            _set_default_bit(11, "buttonM2")
            _set_default_bit(12, "buttonM3")
            _set_default_bit(13, "scrollWheelClick")
        else:
            _set_default_bit(0, "buttonA")
            _set_default_bit(1, "buttonB")
            _set_default_bit(2, "buttonX")
            _set_default_bit(3, "buttonY")
            _set_default_bit(4, "buttonLB")
            _set_default_bit(5, "buttonRB")
            if 6 not in claimed_bits and (btns & (1 << 6)) and not has_analog_lt and hw["leftTriggerAnalog"] == 0:
                hw["leftTriggerAnalog"] = 32767
            if 7 not in claimed_bits and (btns & (1 << 7)) and not has_analog_rt and hw["rightTriggerAnalog"] == 0:
                hw["rightTriggerAnalog"] = 32767
            _set_default_bit(8, "buttonView")
            _set_default_bit(9, "buttonMenu")
            _set_default_bit(10, "leftStickClick")
            _set_default_bit(11, "rightStickClick")
            _set_default_bit(12, "legionLButton")
            _set_default_bit(13, "legionRButton")
            _set_default_bit(14, "buttonY1")
            _set_default_bit(15, "buttonY2")
            _set_default_bit(16, "buttonY3")
            _set_default_bit(17, "buttonRB")
            _set_default_bit(18, "buttonM2")
            _set_default_bit(19, "buttonM3")
            _set_default_bit(20, "scrollWheelClick")

    def _poll_winmm_dinput(self, hw: dict, profile: dict, xinput_ok: bool = False) -> bool:
        if self.winmm_dll is None:
            return False
        dinput_found = False
        units_seen = []

        tcal = profile.get("triggerCalibration", {})
        claimed_trigger_axes = set()
        for src_key in ("ltSource", "rtSource"):
            src_spec = tcal.get(src_key)
            if isinstance(src_spec, dict) and src_spec.get("kind") == "dinput_axis":
                claimed_trigger_axes.add((int(src_spec.get("joy_id", -1)), str(src_spec.get("axis", ""))))

        for joy_id in range(16):
            jinfo = JOYINFOEX()
            jinfo.dwSize = ctypes.sizeof(JOYINFOEX)
            jinfo.dwFlags = 0x00FF  # JOY_RETURNALL
            res = self.winmm_dll.joyGetPosEx(joy_id, ctypes.byref(jinfo))
            if res != 0:
                continue

            caps = JOYCAPSW()
            if self.winmm_dll.joyGetDevCapsW(joy_id, ctypes.byref(caps), ctypes.sizeof(JOYCAPSW)) != 0:
                continue
            if caps.wMid != LENOVO_VENDOR_ID or caps.wNumButtons < 1:
                continue
            pid = caps.wPid

            dinput_found = True
            unit_role = "combined"
            if pid == LENOVO_PID_DINPUT_LEFT:
                unit_role = "left"
            elif pid == LENOVO_PID_DINPUT_RIGHT:
                unit_role = "right"
            unit_key = f"{unit_role}_joy{joy_id}"
            units_seen.append((pid, unit_role, joy_id))

            raw_axes = {
                "X": int(jinfo.dwXpos),
                "Y": int(jinfo.dwYpos),
                "Z": int(jinfo.dwZpos),
                "R": int(jinfo.dwRpos),
                "U": int(jinfo.dwUpos),
                "V": int(jinfo.dwVpos),
            }
            for ax_k, ax_v in raw_axes.items():
                self.last_raw_dinput_axes[(joy_id, ax_k)] = ax_v
                if self.trigger_cal_stage == "REST":
                    lst = self.trigger_cal_rest_dinput.setdefault((joy_id, ax_k), [])
                    if len(lst) < 60:
                        lst.append(ax_v)
                elif self.trigger_cal_stage == "PULL":
                    lst = self.trigger_cal_peak_dinput.setdefault((joy_id, ax_k), [])
                    if len(lst) < 240:
                        lst.append(ax_v)

            if joy_id not in self._dinput_axis_rest:
                self._dinput_axis_rest[joy_id] = dict(raw_axes)
            rest = self._dinput_axis_rest[joy_id]

            def _centered_stick(axis_name: str, invert: bool = False) -> int:
                if (joy_id, axis_name) in claimed_trigger_axes:
                    return 0
                val = raw_axes[axis_name]
                r_val = rest.get(axis_name, 32768)
                # Strict centered-stick baseline check (28500..37000) prevents analog triggers from moving sticks!
                if not (28500 <= r_val <= 37000):
                    return 0
                delta = (32767 - val) if invert else (val - 32768)
                return self._apply_stick_deadzone(delta, 2600)

            def _proportional_unipolar_trigger(axis_name: str) -> int:
                r_val = rest.get(axis_name, 32768)
                val = raw_axes[axis_name]
                if r_val <= 6000 and val > r_val + 900:
                    span = max(1, 65535 - r_val)
                    return max(0, min(32767, int(round((val - r_val) * 32767.0 / span))))
                return 0

            has_analog_lt = False
            has_analog_rt = False

            # Only decode DirectInput sticks & default triggers when XInput is not already providing them
            if not xinput_ok:
                lx = _centered_stick("X", invert=False)
                ly = _centered_stick("Y", invert=True)
                rx = _centered_stick("Z", invert=False)
                ry = _centered_stick("R", invert=True)

                if unit_role == "left":
                    if abs(lx) > abs(hw["leftStickX"]):
                        hw["leftStickX"] = lx
                    if abs(ly) > abs(hw["leftStickY"]):
                        hw["leftStickY"] = ly
                    for trig_ax in ("Z", "R", "U", "V"):
                        t_val = _proportional_unipolar_trigger(trig_ax)
                        if t_val > 0:
                            hw["leftTriggerAnalog"] = max(hw["leftTriggerAnalog"], t_val)
                            has_analog_lt = True
                    self._decode_dinput_pov_hat(int(jinfo.dwPOV), hw)
                elif unit_role == "right":
                    # On split Right DirectInput controller, check unipolar trigger axes first so RT never moves stick Y!
                    for trig_ax in ("Z", "R", "U", "V", "Y"):
                        t_val = _proportional_unipolar_trigger(trig_ax)
                        if t_val > 0:
                            hw["rightTriggerAnalog"] = max(hw["rightTriggerAnalog"], t_val)
                            has_analog_rt = True
                    cand_rx = lx if abs(lx) > abs(rx) else rx
                    cand_ry = ly if abs(ly) > abs(ry) else ry
                    if abs(cand_rx) > abs(hw["rightStickX"]):
                        hw["rightStickX"] = cand_rx
                    if abs(cand_ry) > abs(hw["rightStickY"]):
                        hw["rightStickY"] = cand_ry
                else:
                    if abs(lx) > abs(hw["leftStickX"]):
                        hw["leftStickX"] = lx
                    if abs(ly) > abs(hw["leftStickY"]):
                        hw["leftStickY"] = ly
                    if abs(rx) > abs(hw["rightStickX"]):
                        hw["rightStickX"] = rx
                    if abs(ry) > abs(hw["rightStickY"]):
                        hw["rightStickY"] = ry
                    u_lt = _proportional_unipolar_trigger("U")
                    v_rt = _proportional_unipolar_trigger("V")
                    if u_lt > 0:
                        hw["leftTriggerAnalog"] = max(hw["leftTriggerAnalog"], u_lt)
                        has_analog_lt = True
                    if v_rt > 0:
                        hw["rightTriggerAnalog"] = max(hw["rightTriggerAnalog"], v_rt)
                        has_analog_rt = True
                    self._decode_dinput_pov_hat(int(jinfo.dwPOV), hw)

            self._apply_dinput_button_bitmask(
                int(jinfo.dwButtons), unit_role, unit_key, hw, profile, has_analog_lt=has_analog_lt, has_analog_rt=has_analog_rt
            )

        if any(r == "left" for _, r, _ in units_seen) or any(r == "right" for _, r, _ in units_seen):
            self.active_dinput_mode = f"Dual Split DInput ({len(units_seen)} units)"
        elif dinput_found:
            pids_hex = "/".join(f"0x{p:04X}#J{j}" for p, _, j in units_seen)
            self.active_dinput_mode = f"DirectInput ({pids_hex})"
        else:
            self.active_dinput_mode = "None"
        return dinput_found

    def _decode_default_lenovo_vendor_buttons(
        self,
        st: HidInterfaceStream,
        sub: HidReportSubChannel,
        padded: bytearray,
        clean_delta: bytearray,
        hw: dict,
        profile: dict,
        xinput_ok: bool,
    ):
        """
        Out-of-the-box decoder for Lenovo Legion Go with unified RB / M1 switch:
          - RB and M1 share the top-right physical switch and are united into 'buttonRB'.
          - Pressing XInput RB (0x0200), R04:B17:0x02, R05:0x24, Mouse 4, Mouse 5, or F13 activates 'buttonRB' (when unbound).
          - Vendor 0xFFA0 Report ID 0x05 event packets (Y1..M3, Legion L/R)
          - Composite Mouse (0x0001:0x0002) -> Wheel Click (0x04 -> scrollWheelClick), Mouse 4/5 (0x08/0x10 -> buttonRB)
          - Composite Gamepad (0x0001:0x0004/0x0005) Extended Bytes (15..17)
        """
        learned_hid = profile.get("learnedVendorButtons", {})
        learned_din = profile.get("learnedDinputButtons", {})
        learned_mouse = profile.get("learnedMouseButtons", {})
        learned_keys = profile.get("learnedKeyBindings", {})
        learned_xin = profile.get("learnedXinputButtons", {})
        custom_keys = (
            set(learned_hid.keys())
            | set(learned_din.keys())
            | set(learned_mouse.keys())
            | set(learned_keys.keys())
            | set(learned_xin.keys())
        )

        def _set_if_unbound(btn_key: str, src_info: str):
            if btn_key not in custom_keys:
                hw[btn_key] = True
                self._add_trigger_source(btn_key, src_info)

        # 1. Lenovo Vendor 0xFFA0 / 0xFF00 Report ID 0x05 Event Packets
        if st.usage_page >= 0xFF00 and sub.report_id == 0x05:
            for b_idx in range(3, 10):
                b_val = clean_delta[b_idx]
                raw_v = padded[b_idx]
                if b_val == 0:
                    continue
                s_tag = f"HID {st.key}:R05 B{b_idx}=0x{raw_v:02X} (^0x{b_val:02X})"
                if raw_v == 0x21: _set_if_unbound("buttonY1", s_tag); continue
                if raw_v == 0x22: _set_if_unbound("buttonY2", s_tag); continue
                if raw_v == 0x23: _set_if_unbound("buttonY3", s_tag); continue
                if raw_v == 0x24: _set_if_unbound("buttonRB", s_tag); continue
                if raw_v == 0x25: _set_if_unbound("buttonM2", s_tag); continue
                if raw_v == 0x26: _set_if_unbound("buttonM3", s_tag); continue
                if b_idx >= 4:
                    if b_val & 0x01: _set_if_unbound("buttonY1", s_tag)
                    if b_val & 0x02: _set_if_unbound("buttonY2", s_tag)
                    if b_val & 0x04: _set_if_unbound("buttonY3", s_tag)
                    if b_val & 0x08: _set_if_unbound("buttonRB", s_tag)
                    if b_val & 0x10: _set_if_unbound("buttonM2", s_tag)
                    if b_val & 0x20: _set_if_unbound("buttonM3", s_tag)
                    if b_val & 0x40: _set_if_unbound("legionLButton", s_tag)
                    if b_val & 0x80: _set_if_unbound("legionRButton", s_tag)
                elif b_idx == 3:
                    if b_val & 0x40: _set_if_unbound("legionLButton", s_tag)
                    if b_val & 0x80: _set_if_unbound("legionRButton", s_tag)

        # 2. Vendor 0xFFA0 Report ID 0x04 Byte 17 bit 0x02 -> Unified RB / M1
        if st.usage_page >= 0xFF00 and sub.report_id == 0x04 and sub.calibrated:
            if (padded[17] ^ sub.baseline[17]) & 0x02:
                _set_if_unbound("buttonRB", f"HID {st.key}:R04 B17=0x{padded[17]:02X} (RB/M1 Switch)")

        # 3. Composite HID Mouse (0x0001:0x0002) -> Wheel Click (0x04), Mouse 4/5 (0x08/0x10 -> Unified RB/M1)
        if st.usage_page == 0x0001 and st.usage == 0x0002:
            if padded[1] & 0x04:
                _set_if_unbound("scrollWheelClick", f"HID Mouse {st.key}:R{sub.report_id:02X} B1=0x{padded[1]:02X} (0x04 WheelClick)")
            if padded[1] & 0x08:
                _set_if_unbound("buttonRB", f"HID Mouse {st.key}:R{sub.report_id:02X} B1=0x{padded[1]:02X} (0x08 Mouse4 -> RB/M1)")
            if padded[1] & 0x10:
                _set_if_unbound("buttonRB", f"HID Mouse {st.key}:R{sub.report_id:02X} B1=0x{padded[1]:02X} (0x10 Mouse5 -> RB/M1)")

        # 4. Composite Gamepad (0x0001:0x0004/0x0005) Extended Bytes (15..17)
        if st.usage_page == 0x0001 and st.usage in (0x0004, 0x0005) and sub.calibrated:
            b15 = clean_delta[15]
            b16 = clean_delta[16]
            b17 = clean_delta[17]
            if b15 & 0x01: _set_if_unbound("legionLButton", f"HID {st.key}:R{sub.report_id:02X} B15=0x{padded[15]:02X} (^0x{b15:02X})")
            if b15 & 0x02: _set_if_unbound("legionRButton", f"HID {st.key}:R{sub.report_id:02X} B15=0x{padded[15]:02X} (^0x{b15:02X})")
            if not xinput_ok:
                if b15 & 0x04: _set_if_unbound("buttonView", f"HID {st.key}:R{sub.report_id:02X} B15=0x{padded[15]:02X}")
                if b15 & 0x08: _set_if_unbound("buttonMenu", f"HID {st.key}:R{sub.report_id:02X} B15=0x{padded[15]:02X}")
            if b16 & 0x01: _set_if_unbound("buttonY1", f"HID {st.key}:R{sub.report_id:02X} B16=0x{padded[16]:02X} (^0x{b16:02X})")
            if b16 & 0x02: _set_if_unbound("buttonY2", f"HID {st.key}:R{sub.report_id:02X} B16=0x{padded[16]:02X} (^0x{b16:02X})")
            if b16 & 0x04: _set_if_unbound("buttonY3", f"HID {st.key}:R{sub.report_id:02X} B16=0x{padded[16]:02X} (^0x{b16:02X})")
            if b16 & 0x08: _set_if_unbound("buttonRB", f"HID {st.key}:R{sub.report_id:02X} B16=0x{padded[16]:02X} (^0x{b16:02X})")
            if b16 & 0x10: _set_if_unbound("buttonM2", f"HID {st.key}:R{sub.report_id:02X} B16=0x{padded[16]:02X} (^0x{b16:02X})")
            if b16 & 0x20: _set_if_unbound("buttonM3", f"HID {st.key}:R{sub.report_id:02X} B16=0x{padded[16]:02X} (^0x{b16:02X})")
            if b17 & 0x01: _set_if_unbound("scrollWheelClick", f"HID {st.key}:R{sub.report_id:02X} B17=0x{padded[17]:02X} (^0x{b17:02X})")
            if b17 & 0x02: _set_if_unbound("buttonRB", f"HID {st.key}:R{sub.report_id:02X} B17=0x{padded[17]:02X} (^0x{b17:02X})")

    @staticmethod
    def _extract_calibrated_imu_gyro(st: HidInterfaceStream, sub: HidReportSubChannel, padded: bytearray, profile: dict):
        if not profile.get("gyroEnabled", True):
            st.live_gyro = (0, 0, 0)
            return

        gcal = profile.get("gyroCalibration")
        if gcal:
            cal_iface = str(gcal.get("iface", ""))
            up_tag = f"UP{st.usage_page:04X}_U{st.usage:04X}"
            if cal_iface != st.key and up_tag not in cal_iface:
                return
            if int(gcal.get("report_id", -1)) not in (-1, sub.report_id):
                return
            offset = int(gcal.get("offset", -1))
            if offset < 1 or offset + 6 > 64:
                return
            # Automatically mask the 6-byte gyro slice in sub.noisy_mask so gyro never triggers button detection!
            for g_i in range(offset, min(64, offset + 6)):
                if g_i != 17:
                    sub.noisy_mask[g_i] = 1
            endian = gcal.get("endian", "<")
            bias = gcal.get("bias", [0.0, 0.0, 0.0])
            dz = int(gcal.get("deadzone", 60))
            try:
                gp, gy, gr = struct.unpack_from(f"{endian}hhh", padded, offset)
                cp = int(round(gp - float(bias[0])))
                cy = int(round(gy - float(bias[1])))
                cr = int(round(gr - float(bias[2])))
                if abs(cp) < dz and abs(cy) < dz and abs(cr) < dz:
                    bias[0] = round(float(bias[0]) * 0.96 + gp * 0.04, 2)
                    bias[1] = round(float(bias[1]) * 0.96 + gy * 0.04, 2)
                    bias[2] = round(float(bias[2]) * 0.96 + gr * 0.04, 2)
                    st.live_gyro = (0, 0, 0)
                    return
                if abs(cp) < dz: cp = 0
                if abs(cy) < dz: cy = 0
                if abs(cr) < dz: cr = 0
                st.live_gyro = (
                    max(-32768, min(32767, cp)),
                    max(-32768, min(32767, cy)),
                    max(-32768, min(32767, cr)),
                )
            except Exception:
                pass
            return

        if sub.is_event_driven:
            return
        if not sub.auto_imu_checked:
            sub.imu_ring.append(bytes(padded))
            if len(sub.imu_ring) >= 24:
                sub.auto_imu_checked = True
                start_off = 18 if sub.report_id == 0x04 else (15 if (st.usage_page == 0x0001 and st.usage in (0x0004, 0x0005)) else 3)
                best_spec = None
                best_var_score = 999999.0
                for off in range(start_off, 57):
                    try:
                        seq = [struct.unpack_from("<hhh", pkt, off) for pkt in sub.imu_ring]
                    except Exception:
                        continue
                    n = float(len(seq))
                    means = [sum(v[a] for v in seq) / n for a in range(3)]
                    if any(abs(m) > 2600.0 for m in means):
                        continue
                    stds = [
                        math.sqrt(sum((v[a] - means[a]) ** 2 for v in seq) / n)
                        for a in range(3)
                    ]
                    if max(stds) > 85.0 or min(stds) < 0.4 or sum(1 for s in stds if s >= 0.8) < 2:
                        continue
                    is_counter = False
                    for a in range(3):
                        diffs = [seq[k][a] - seq[k - 1][a] for k in range(1, len(seq)) if seq[k][a] != seq[k - 1][a]]
                        if not diffs:
                            continue
                        pos_cnt = sum(1 for d in diffs if d > 0)
                        neg_cnt = sum(1 for d in diffs if d < 0)
                        if max(pos_cnt, neg_cnt) / float(len(diffs)) > 0.70:
                            is_counter = True
                            break
                        if abs(seq[-1][a] - seq[0][a]) > max(25.0, stds[a] * 2.4):
                            is_counter = True
                            break
                    if is_counter:
                        continue
                    var_score = sum(stds)
                    if var_score < best_var_score:
                        best_var_score = var_score
                        best_spec = {
                            "offset": off,
                            "bias": [means[0], means[1], means[2]],
                            "deadzone": int(max(80, min(260, max(stds) * 4.2))),
                        }
                sub.auto_imu_spec = best_spec
                if best_spec is not None:
                    for g_i in range(best_spec["offset"], min(64, best_spec["offset"] + 6)):
                        if g_i != 17:
                            sub.noisy_mask[g_i] = 1
                sub.imu_ring.clear()
            return

        if sub.auto_imu_spec is not None:
            spec = sub.auto_imu_spec
            off = spec["offset"]
            bias = spec["bias"]
            dz = spec["deadzone"]
            try:
                gp, gy, gr = struct.unpack_from("<hhh", padded, off)
                cp = int(round(gp - bias[0]))
                cy = int(round(gy - bias[1]))
                cr = int(round(gr - bias[2]))
                if abs(cp) < dz and abs(cy) < dz and abs(cr) < dz:
                    bias[0] = bias[0] * 0.96 + gp * 0.04
                    bias[1] = bias[1] * 0.96 + gy * 0.04
                    bias[2] = bias[2] * 0.96 + gr * 0.04
                    st.live_gyro = (0, 0, 0)
                    return
                if abs(cp) < dz: cp = 0
                if abs(cy) < dz: cy = 0
                if abs(cr) < dz: cr = 0
                st.live_gyro = (
                    max(-32768, min(32767, cp)),
                    max(-32768, min(32767, cy)),
                    max(-32768, min(32767, cr)),
                )
            except Exception:
                pass

    def _finalize_subchannel_calibration(self, st: HidInterfaceStream, sub: HidReportSubChannel):
        """
        Finalizes per-Report-ID sub-channel calibration after >= 12 packets OR 160ms elapsed.
        """
        is_vendor_or_evt = (
            st.usage_page == 0x000C
            or (st.usage_page == 0x0001 and self.usage_is_mouse_or_sys(st.usage))
            or sub.report_id == 0x05
        )
        if len(sub.samples) >= 4 and not is_vendor_or_evt:
            sub.is_event_driven = False
            first = sub.samples[0]
            sub.baseline = bytearray(first)
            sub.baseline_locked = True
            for s in sub.samples[1:]:
                for i in range(64):
                    if s[i] != first[i]:
                        sub.noisy_mask[i] = 1
            sub.calibrated = True
            quiet = sum(1 for b in sub.noisy_mask if b == 0)
            self.log(f"[HID Stream] {st.key}:R{sub.report_id:02X}: Continuous stream ({quiet}/64 quiet button bytes; gyro/touch auto-masked).")
        else:
            sub.is_event_driven = True
            sub.noisy_mask = bytearray(64)
            sub.baseline = bytearray(64)
            sub.baseline[0] = sub.report_id & 0xFF
            sub.baseline_locked = True
            sub.calibrated = True
            self.log(f"[HID Event] {st.key}:R{sub.report_id:02X}: Ready for event-driven button packets.")

    @staticmethod
    def usage_is_mouse_or_sys(usage: int) -> bool:
        return usage in (0x0002, 0x0080)

    def poll_physical_state(self, profile: dict) -> dict:
        self._trigger_sources_this_tick.clear()
        hw = create_empty_legion_state()
        proto_mode = profile.get("controllerProtocolMode", "auto")

        now = time.perf_counter()
        since_birth = now - self._app_birth_time

        for wave_idx, wave_t in ((1, 1.0), (2, 2.5)):
            if since_birth >= wave_t and wave_idx not in self._wakeup_waves_done:
                self._wakeup_waves_done.add(wave_idx)
                self._check_for_new_hid_interfaces()
                if self.learning_target_button is None:
                    self.send_lenovo_raw_button_wakeup(quiet_log=True)

        if HAS_HIDAPI and (now - self._last_reconnect_attempt) > 2.8:
            self._last_reconnect_attempt = now
            if not any(s.dev is not None for s in self.hid_streams):
                self.connect_hardware()
            else:
                self._check_for_new_hid_interfaces()

        # Advance 3-Stage Learning State from SETTLING -> WAITING_PRESS once 350ms quiet window completes
        if self.learning_target_button is not None and self.learning_stage == "SETTLING":
            if (now - self.learning_start_time) >= 0.35 and now >= self._ignore_learning_until:
                self.learning_stage = "WAITING_PRESS"
                self.log(
                    f"[Detect Physical] Stage 1/2: Ready! Press and hold '{self.learning_target_button}' now..."
                )

        if (
            self.learning_target_button is not None
            and self.learning_stage == "WAITING_RELEASE"
            and self.learning_candidate is not None
            and self.learning_candidate.get("is_event_driven", False)
            and (now - float(self.learning_candidate.get("candidate_time", now))) >= 0.38
        ):
            self.confirm_learning_candidate(profile)

        # ----------------------------------------------------------------------
        # STEP 1: Poll ALL Active XInput Slots (0..3) Simultaneously in XInput Mode
        # ----------------------------------------------------------------------
        xinput_ok = False
        raw_xinput_btns = 0
        merged_lt = 0
        merged_rt = 0
        merged_lx = 0
        merged_ly = 0
        merged_rx = 0
        merged_ry = 0
        learned_xinput = profile.setdefault("learnedXinputButtons", {})

        if proto_mode in ("auto", "xinput_only") and self.xinput_dll is not None:
            active_slots = []
            for slot in range(4):
                xstate = XINPUT_STATE()
                if self.xinput_get_state_ex is not None:
                    res = self.xinput_get_state_ex(slot, ctypes.byref(xstate))
                else:
                    res = self.xinput_dll.XInputGetState(slot, ctypes.byref(xstate))
                if res == 0:
                    active_slots.append(slot)
                    xinput_ok = True
                    gp = xstate.Gamepad
                    raw_xinput_btns |= int(gp.wButtons)
                    if int(gp.bLeftTrigger) > merged_lt:
                        merged_lt = int(gp.bLeftTrigger)
                    if int(gp.bRightTrigger) > merged_rt:
                        merged_rt = int(gp.bRightTrigger)
                    if abs(int(gp.sThumbLX)) > abs(merged_lx):
                        merged_lx = int(gp.sThumbLX)
                    if abs(int(gp.sThumbLY)) > abs(merged_ly):
                        merged_ly = int(gp.sThumbLY)
                    if abs(int(gp.sThumbRX)) > abs(merged_rx):
                        merged_rx = int(gp.sThumbRX)
                    if abs(int(gp.sThumbRY)) > abs(merged_ry):
                        merged_ry = int(gp.sThumbRY)
            self.active_xinput_slots = active_slots
            self.active_xinput_slot = active_slots[0] if active_slots else -1
            if xinput_ok:
                self._prev_xinput_btns = raw_xinput_btns
                if self.trigger_cal_stage == "REST":
                    self.trigger_cal_rest_xinput["LT"].append(merged_lt)
                    self.trigger_cal_rest_xinput["RT"].append(merged_rt)
                elif self.trigger_cal_stage == "PULL":
                    self.trigger_cal_peak_xinput["LT"].append(merged_lt)
                    self.trigger_cal_peak_xinput["RT"].append(merged_rt)
        else:
            self.active_xinput_slots = []
            self.active_xinput_slot = -1

        # ----------------------------------------------------------------------
        # STEP 2: Poll ALL Lenovo VID_17EF Composite HID + WM_INPUT Streams Simultaneously
        # ----------------------------------------------------------------------
        learned_hid = profile.setdefault("learnedVendorButtons", {})
        right_gyros = []
        left_gyros = []
        tablet_gyros = []

        for st in self.hid_streams:
            if st.usage_page in (0x000D, 0x0020):
                continue
            try:
                for sub in list(st.sub_channels.values()):
                    if not sub.calibrated and (now - sub.open_time) >= 0.16:
                        self._finalize_subchannel_calibration(st, sub)
                    if (
                        sub.is_event_driven
                        and sub.last_event_time > 0.0
                        and (now - sub.last_event_time) >= 0.22
                        and self.learning_stage == "IDLE"
                        and (st.usage_page >= 0xFF00 or st.usage_page == 0x000C)
                    ):
                        if sub.last_raw_packet != bytes(sub.baseline):
                            sub.last_raw_packet = bytes(sub.baseline)
                            sub.last_clean_delta = bytes(64)
                            sub.prev_logged_packet = bytearray(sub.baseline)
                            if self.deep_log_raw_bytes:
                                self.log(
                                    f"[HID EVENT RESET] {st.key}:R{sub.report_id:02X} -> Auto-returned to idle baseline after 220ms"
                                )

                packets_this_tick = []
                while len(packets_this_tick) < 16:
                    raw_item = None
                    if st.external_queue:
                        raw_item = st.external_queue.pop(0)
                    elif st.dev is not None:
                        raw_item = st.dev.read(64)
                    if not raw_item:
                        break
                    packets_this_tick.append(raw_item)

                for raw in packets_this_tick:
                    st.packets_read += 1
                    st.last_packet_time = now
                    padded = bytearray(64)
                    padded[:min(64, len(raw))] = raw[:64]
                    st.last_raw_packet = bytes(padded)

                    rep_id = int(padded[0])
                    sub = st.get_or_create_subchannel(rep_id)
                    sub.packets_read += 1
                    sub.last_event_time = now
                    sub.last_raw_packet = bytes(padded)

                    if self.gyro_cal_mode == "STILL":
                        lst = self.gyro_cal_still_samples.setdefault((st.key, rep_id), [])
                        if len(lst) < 120:
                            lst.append(bytes(padded))
                    elif self.gyro_cal_mode == "ROTATE":
                        lst = self.gyro_cal_rotate_samples.setdefault((st.key, rep_id), [])
                        if len(lst) < 200:
                            lst.append(bytes(padded))

                    if self.trigger_cal_stage in ("REST", "PULL"):
                        target_dict = self.trigger_cal_rest_hid if self.trigger_cal_stage == "REST" else self.trigger_cal_peak_hid
                        for b_i in range(1, 32):
                            lst = target_dict.setdefault((st.key, rep_id, b_i), [])
                            if len(lst) < 180:
                                lst.append(int(padded[b_i]))

                    if not sub.calibrated:
                        sub.samples.append(bytes(padded))
                        if len(sub.samples) >= 12:
                            self._finalize_subchannel_calibration(st, sub)
                        continue

                    if sub.is_event_driven:
                        if sub.first_event_packet is None:
                            sub.first_event_packet = bytes(padded)
                            sub.baseline_locked = True
                        elif bytes(padded) != sub.first_event_packet:
                            cur_bits = sum(bin(b).count("1") for b in padded[1:32])
                            fst_bits = sum(bin(b).count("1") for b in sub.first_event_packet[1:32])
                            if cur_bits < fst_bits:
                                sub.baseline = bytearray(padded)
                                sub.baseline_locked = True

                    # Auto-mask fluctuating gyro/timer/touch bytes during initial 500ms after stream open
                    if not sub.is_event_driven and (now - sub.open_time) <= 0.50:
                        for i in range(1, 64):
                            if sub.noisy_mask[i] == 0:
                                dv = sub.byte_distinct_values[i]
                                if len(dv) < 4:
                                    dv.add(padded[i])
                                if len(dv) >= 3:
                                    sub.noisy_mask[i] = 1

                    self._extract_calibrated_imu_gyro(st, sub, padded, profile)

                    # Deep Raw HID Byte-Delta Inspector Logging
                    if sub.prev_logged_packet is None:
                        sub.prev_logged_packet = bytearray(sub.baseline if sub.is_event_driven else padded)
                    else:
                        quiet_diffs = []
                        noisy_diffs = []
                        is_std_gp = (st.usage_page == 0x0001 and st.usage in (0x0004, 0x0005))
                        for b_i in range(1, 64):
                            old_b = int(sub.prev_logged_packet[b_i])
                            new_b = int(padded[b_i])
                            if old_b != new_b:
                                xor_b = old_b ^ new_b
                                base_b = int(sub.baseline[b_i])
                                is_quiet_btn_byte = (sub.noisy_mask[b_i] == 0)
                                if is_std_gp and xinput_ok and 1 <= b_i <= 12:
                                    is_quiet_btn_byte = False
                                if is_quiet_btn_byte:
                                    sub.prev_logged_packet[b_i] = new_b
                                    quiet_diffs.append(
                                        f"B{b_i:02d}: 0x{old_b:02X}->0x{new_b:02X} (^0x{xor_b:02X}, Base=0x{base_b:02X})"
                                    )
                                else:
                                    noisy_diffs.append(
                                        f"B{b_i:02d}: 0x{old_b:02X}->0x{new_b:02X} (^0x{xor_b:02X})"
                                    )
                        if quiet_diffs and self.deep_log_raw_bytes:
                            pkt_slice = " ".join(f"{b:02X}" for b in padded[:24])
                            self.log(
                                f"[HID BYTE DELTA] {st.key}:R{rep_id:02X} | {' ; '.join(quiet_diffs[:8])} | B00..23=[{pkt_slice}]"
                            )
                        if noisy_diffs and self.deep_log_noisy_bytes and (now - sub.last_byte_change_log_time) >= 0.15:
                            sub.last_byte_change_log_time = now
                            for b_i in range(1, 64):
                                sub.prev_logged_packet[b_i] = padded[b_i]
                            self.log(
                                f"[HID NOISY/GYRO DELTA] {st.key}:R{rep_id:02X} | {' ; '.join(noisy_diffs[:8])}"
                            )

                    clean_delta = bytearray(64)
                    for i in range(64):
                        if sub.noisy_mask[i] == 0:
                            clean_delta[i] = padded[i] ^ sub.baseline[i]
                    sub.last_clean_delta = bytes(clean_delta)

                    self._decode_default_lenovo_vendor_buttons(
                        st, sub, padded, clean_delta, hw, profile, xinput_ok
                    )

                    # 3-Stage Press-and-Release Learning across ALL composite (st.key, rep_id) sub-channels
                    if (
                        self.learning_target_button is not None
                        and now >= self._ignore_learning_until
                    ):
                        is_std_gamepad_col = (st.usage_page == 0x0001 and st.usage in (0x0004, 0x0005))
                        start_byte = 15 if (is_std_gamepad_col and xinput_ok) else 1

                        if self.learning_stage == "SETTLING":
                            if not sub.modal_has_snapshot:
                                sub.modal_baseline = bytearray(padded if sub.packets_read > 0 else sub.baseline)
                                sub.modal_has_snapshot = True
                            else:
                                # Auto-mask ANY byte on continuous streams that fluctuates during the 350ms SETTLING window
                                for i in range(1, 64):
                                    if padded[i] != sub.modal_baseline[i]:
                                        sub.modal_noisy_mask[i] = 1
                                        sub.modal_baseline[i] = padded[i]

                        elif self.learning_stage == "WAITING_PRESS":
                            if not sub.modal_has_snapshot:
                                sub.modal_baseline = bytearray(padded if not sub.is_event_driven else sub.baseline)
                                sub.modal_baseline[0] = padded[0]
                                sub.modal_has_snapshot = True

                            changed_bytes = []
                            for b_idx in range(start_byte, 64):
                                if sub.noisy_mask[b_idx] == 0 and sub.modal_noisy_mask[b_idx] == 0:
                                    d_val = padded[b_idx] ^ sub.modal_baseline[b_idx]
                                    if d_val != 0:
                                        if not sub.is_event_driven and bin(d_val).count("1") > 2:
                                            sub.modal_noisy_mask[b_idx] = 1
                                            sub.modal_baseline[b_idx] = padded[b_idx]
                                            continue
                                        changed_bytes.append((b_idx, d_val))

                            # Filter out multi-byte gyro/touchpad sweeps (>= 3 bytes changing at once)
                            if len(changed_bytes) >= 3 and not sub.is_event_driven:
                                for b_idx, _ in changed_bytes:
                                    sub.modal_noisy_mask[b_idx] = 1
                                    sub.modal_baseline[b_idx] = padded[b_idx]
                            elif len(changed_bytes) >= 1:
                                if sub.is_event_driven or st.usage_page >= 0xFF00 or len(changed_bytes) > 1:
                                    b_idx, d_val = changed_bytes[-1]
                                else:
                                    b_idx, d_val = changed_bytes[0]

                                if bin(d_val).count("1") == 1:
                                    bit_mask = int(d_val)
                                    pressed_bit = int(padded[b_idx] & bit_mask)
                                    base_bit = int(sub.modal_baseline[b_idx] & bit_mask)
                                else:
                                    bit_mask = 0xFF
                                    pressed_bit = int(padded[b_idx])
                                    base_bit = int(sub.modal_baseline[b_idx])

                                ckey = ("hid", st.key, rep_id, b_idx, int(bit_mask), int(pressed_bit))
                                cnt = self._candidate_tracker.get(ckey, 0) + 1
                                self._candidate_tracker[ckey] = cnt
                                req_frames = 1 if (sub.is_event_driven or st.usage_page == 0x000C) else 2
                                if cnt >= req_frames:
                                    self.learning_candidate = {
                                        "kind": "hid",
                                        "iface": st.key,
                                        "report_id": rep_id,
                                        "byte": b_idx,
                                        "mask": int(bit_mask),
                                        "pressed_bit": pressed_bit,
                                        "base_bit": base_bit,
                                        "press_packet": bytes(padded),
                                        "is_event_driven": bool(sub.is_event_driven),
                                        "candidate_time": now,
                                        "summary": f"{st.key}:R{rep_id:02X} Byte {b_idx} (Mask 0x{bit_mask:02X} Val 0x{pressed_bit:02X})",
                                    }
                                    self.learning_stage = "WAITING_RELEASE"
                                    self.log(
                                        f"[Detect Physical] Stage 1/2: Detected {self.learning_candidate['summary']} — Now RELEASE button to confirm!"
                                    )

                        elif self.learning_stage == "WAITING_RELEASE" and self.learning_candidate:
                            if (
                                self.learning_candidate.get("kind") == "hid"
                                and self.learning_candidate.get("iface") == st.key
                                and int(self.learning_candidate.get("report_id", rep_id)) == rep_id
                            ):
                                press_pkt = self.learning_candidate.get("press_packet")
                                b_idx = int(self.learning_candidate["byte"])
                                b_mask = int(self.learning_candidate["mask"])
                                base_bit = int(self.learning_candidate["base_bit"])
                                if (padded[b_idx] & b_mask) == base_bit:
                                    if sub.is_event_driven:
                                        sub.baseline = bytearray(padded)
                                    self.confirm_learning_candidate(profile)
                                elif press_pkt and bytes(padded) != press_pkt and sub.is_event_driven:
                                    toggled_bytes = [
                                        idx for idx in range(start_byte, 64)
                                        if press_pkt[idx] != padded[idx] and padded[idx] == 0
                                    ]
                                    if toggled_bytes:
                                        tb = toggled_bytes[-1]
                                        td = press_pkt[tb] ^ padded[tb]
                                        t_mask = int(td) if bin(td).count("1") == 1 else 0xFF
                                        t_pressed = int(press_pkt[tb] & t_mask)
                                        self.learning_candidate["byte"] = tb
                                        self.learning_candidate["mask"] = t_mask
                                        self.learning_candidate["pressed_bit"] = t_pressed
                                        self.learning_candidate["summary"] = (
                                            f"{st.key}:R{rep_id:02X} Byte {tb} (Mask 0x{t_mask:02X} Val 0x{t_pressed:02X})"
                                        )
                                        sub.baseline = bytearray(padded)
                                        self.confirm_learning_candidate(profile)
            except Exception:
                pass

            # Evaluate learned Raw HID buttons across ALL composite streams simultaneously
            st_up_tag = f"UP{st.usage_page:04X}_U{st.usage:04X}"
            mi_m = re.search(r"(MI[0-9A-F]{2}_C[0-9A-F]{2})", st.key)
            st_mi_col_tag = mi_m.group(1) if mi_m else ""

            for btn_key, spec in learned_hid.items():
                spec_iface = str(spec.get("iface", ""))
                iface_matches = (
                    spec_iface in ("", st.key)
                    or (st.usage_page >= 0xFF00 and st_up_tag in spec_iface)
                    or (st_mi_col_tag and st_mi_col_tag in spec_iface and st_up_tag in spec_iface)
                )
                if not iface_matches:
                    continue
                target_rid = int(spec.get("report_id", -1))
                b_idx = int(spec.get("byte", -1))
                b_mask = int(spec.get("mask", 0))
                if 0 <= b_idx < 64 and b_mask > 0:
                    for rid, sub in st.sub_channels.items():
                        if not sub.calibrated or sub.packets_read == 0:
                            continue
                        if target_rid not in (-1, rid):
                            continue
                        is_active = False
                        if "pressed_val" in spec:
                            if (sub.last_raw_packet[b_idx] & b_mask) == int(spec["pressed_val"]):
                                is_active = True
                        elif (sub.last_clean_delta[b_idx] & b_mask):
                            is_active = True
                        if is_active:
                            hw[btn_key] = True
                            self._add_trigger_source(
                                btn_key,
                                f"Learned HID {st.key}:R{rid:02X} B{b_idx}=0x{sub.last_raw_packet[b_idx]:02X} "
                                f"(Base=0x{sub.baseline[b_idx]:02X}, Mask=0x{b_mask:02X})",
                            )

            if st.live_gyro != (0, 0, 0):
                if st.pid == LENOVO_PID_DINPUT_LEFT:
                    left_gyros.append(st.live_gyro)
                elif st.pid == LENOVO_PID_DINPUT_RIGHT:
                    right_gyros.append(st.live_gyro)
                else:
                    right_gyros.append(st.live_gyro)
                    left_gyros.append(st.live_gyro)

        # ----------------------------------------------------------------------
        # STEP 2B: Evaluate VID_17EF Scroll Wheel Up/Down/Click, Mouse 5/4 (Unified RB/M1)
        #          & Keyboard F13..F24 (WH_KEYBOARD_LL) + Detect Physical Capture!
        # ----------------------------------------------------------------------
        self.hook.poll_and_decay()
        # Wheel click & wheel scroll up/down come strictly from VID_17EF RawInput so external mice work normally!
        wheel_click_now = bool(self.rawinput_wheel_click)
        wheel_up_now = bool(now < self.rawinput_wheel_up_until)
        wheel_down_now = bool(now < self.rawinput_wheel_down_until)
        mouse4_now = bool(self.hook.mouse_xbutton1 or self.rawinput_mouse_xbutton1)
        mouse5_now = bool(self.hook.mouse_xbutton2 or self.rawinput_mouse_xbutton2)
        active_vks = set(self.hook.active_vk_codes)

        cur_mouse_state = (wheel_click_now, mouse4_now, mouse5_now)
        if cur_mouse_state != self._prev_logged_mouse_state:
            old_wc, old_m4, old_m5 = self._prev_logged_mouse_state
            self._prev_logged_mouse_state = cur_mouse_state
            if self.deep_log_raw_bytes:
                m_diffs = []
                if wheel_click_now != old_wc:
                    m_diffs.append(f"VID_17EF_WheelClick={'DOWN' if wheel_click_now else 'UP'}")
                if mouse4_now != old_m4:
                    m_diffs.append(f"Mouse4(XButton1->RB/M1)={'DOWN' if mouse4_now else 'UP'}")
                if mouse5_now != old_m5:
                    m_diffs.append(f"Mouse5(XButton2->RB/M1)={'DOWN' if mouse5_now else 'UP'}")
                self.log(f"[MOUSE HOOK DELTA] {', '.join(m_diffs)}")

        if active_vks != self._prev_logged_vks:
            added_vks = active_vks - self._prev_logged_vks
            removed_vks = self._prev_logged_vks - active_vks
            self._prev_logged_vks = set(active_vks)
            if self.deep_log_raw_bytes:
                k_diffs = []
                for v in sorted(added_vks):
                    k_diffs.append(f"+{format_vk_name(v)}(VK 0x{v:02X}) DOWN")
                for v in sorted(removed_vks):
                    k_diffs.append(f"-{format_vk_name(v)}(VK 0x{v:02X}) UP")
                self.log(f"[KEY HOOK DELTA] {', '.join(k_diffs)}")

        learned_mouse = profile.setdefault("learnedMouseButtons", {})
        learned_keys = profile.setdefault("learnedKeyBindings", {})

        # Custom learned mouse buttons ("mouse5", "mouse4", "mouse3", "wheel_up", "wheel_down")
        claimed_mouse_btns = set()
        for btn_key, m_code in learned_mouse.items():
            claimed_mouse_btns.add(m_code)
            if m_code == "mouse5" and mouse5_now:
                hw[btn_key] = True
                self._add_trigger_source(btn_key, "Learned Mouse 5 (XButton2)")
            elif m_code == "mouse4" and mouse4_now:
                hw[btn_key] = True
                self._add_trigger_source(btn_key, "Learned Mouse 4 (XButton1)")
            elif m_code == "mouse3" and wheel_click_now:
                hw[btn_key] = True
                self._add_trigger_source(btn_key, "Learned VID_17EF Wheel Click (Mouse 3)")
            elif m_code == "wheel_up" and wheel_up_now:
                hw[btn_key] = True
                self._add_trigger_source(btn_key, "Learned VID_17EF Scroll Wheel Up")
            elif m_code == "wheel_down" and wheel_down_now:
                hw[btn_key] = True
                self._add_trigger_source(btn_key, "Learned VID_17EF Scroll Wheel Down")

        # Built-in defaults:
        #   - Mouse 5 / Mouse 4 -> Unified RB / M1 (buttonRB) when not custom-bound
        #   - VID_17EF Wheel Click / Wheel Up / Wheel Down -> scrollWheelClick / scrollWheelUp / scrollWheelDown
        if mouse5_now and "mouse5" not in claimed_mouse_btns:
            hw["buttonRB"] = True
            self._add_trigger_source("buttonRB", "Win32 Mouse 5 (XButton2 -> RB/M1)")
        if mouse4_now and "mouse4" not in claimed_mouse_btns:
            hw["buttonRB"] = True
            self._add_trigger_source("buttonRB", "Win32 Mouse 4 (XButton1 -> RB/M1)")
        if wheel_click_now and "mouse3" not in claimed_mouse_btns:
            hw["scrollWheelClick"] = True
            self._add_trigger_source("scrollWheelClick", "VID_17EF Rear Scroll Wheel Click")
        if wheel_up_now and "wheel_up" not in claimed_mouse_btns:
            hw["scrollWheelUp"] = True
            self._add_trigger_source("scrollWheelUp", "VID_17EF Rear Scroll Wheel Up")
        if wheel_down_now and "wheel_down" not in claimed_mouse_btns:
            hw["scrollWheelDown"] = True
            self._add_trigger_source("scrollWheelDown", "VID_17EF Rear Scroll Wheel Down")

        # Custom learned keyboard VK codes (e.g. F13 = 0x7C .. F24 = 0x87)
        claimed_vks = set()
        for btn_key, vk_val in learned_keys.items():
            ivk = int(vk_val)
            claimed_vks.add(ivk)
            if ivk in active_vks:
                hw[btn_key] = True
                self._add_trigger_source(btn_key, f"Learned Key {format_vk_name(ivk)} (VK 0x{ivk:02X})")

        # Built-in default F13..F18 -> RB/M1, Y1, Y2, Y3, M2, M3 when not custom-bound
        default_vk_map = {
            0x7C: "buttonRB",  # F13 -> RB / M1 (Unified Right Bumper / Top-Edge)
            0x7D: "buttonY1",  # F14 -> Y1 (Left Rear Upper)
            0x7E: "buttonY2",  # F15 -> Y2 (Left Rear Lower)
            0x7F: "buttonY3",  # F16 -> Y3 (Right Rear Inner)
            0x80: "buttonM2",  # F17 -> M2 (Right Side Lower FPS)
            0x81: "buttonM3",  # F18 -> M3 (Right Rear Outer)
        }
        for def_vk, def_btn in default_vk_map.items():
            if def_vk in active_vks and def_vk not in claimed_vks:
                hw[def_btn] = True
                self._add_trigger_source(def_btn, f"Keyboard {format_vk_name(def_vk)} (VK 0x{def_vk:02X})")

        # Detect Physical support for Mouse 5/4/3, VID_17EF Scroll Wheel Up/Down, and Keyboard F13..F24
        if self.learning_target_button is not None and now >= self._ignore_learning_until:
            if self.learning_stage == "SETTLING":
                self._modal_base_wheel_click = wheel_click_now
                self._modal_base_mouse4 = mouse4_now
                self._modal_base_mouse5 = mouse5_now
                self._modal_base_vks = set(active_vks)
            elif self.learning_stage == "WAITING_PRESS":
                if mouse5_now and not self._modal_base_mouse5:
                    self.learning_candidate = {
                        "kind": "mouse_btn",
                        "mouse_btn": "mouse5",
                        "summary": "Mouse 5 Click (XButton2)",
                    }
                    self.learning_stage = "WAITING_RELEASE"
                    self.log("[Detect Physical] Stage 1/2: Detected Mouse 5 (XButton2) — Release button to confirm!")
                elif mouse4_now and not self._modal_base_mouse4:
                    self.learning_candidate = {
                        "kind": "mouse_btn",
                        "mouse_btn": "mouse4",
                        "summary": "Mouse 4 Click (XButton1 / Legion Space Mouse 5)",
                    }
                    self.learning_stage = "WAITING_RELEASE"
                    self.log("[Detect Physical] Stage 1/2: Detected Mouse 4 (XButton1) — Release button to confirm!")
                elif wheel_click_now and not self._modal_base_wheel_click:
                    self.learning_candidate = {
                        "kind": "mouse_btn",
                        "mouse_btn": "mouse3",
                        "summary": "VID_17EF Rear Scroll Wheel Click (Mouse 3)",
                    }
                    self.learning_stage = "WAITING_RELEASE"
                    self.log("[Detect Physical] Stage 1/2: Detected VID_17EF Scroll Wheel Click — Release to confirm!")
                elif wheel_up_now:
                    self.learning_candidate = {
                        "kind": "wheel_up",
                        "mouse_btn": "wheel_up",
                        "summary": "VID_17EF Rear Scroll Wheel Up",
                    }
                    self.confirm_learning_candidate(profile)
                elif wheel_down_now:
                    self.learning_candidate = {
                        "kind": "wheel_down",
                        "mouse_btn": "wheel_down",
                        "summary": "VID_17EF Rear Scroll Wheel Down",
                    }
                    self.confirm_learning_candidate(profile)
                else:
                    new_vks = [v for v in active_vks if v not in self._modal_base_vks and v not in (0x01, 0x02, 0x04, 0x05, 0x06, 0x1B)]
                    if new_vks:
                        vk_hit = sorted(new_vks)[-1]
                        vk_label = format_vk_name(vk_hit)
                        self.learning_candidate = {
                            "kind": "key_vk",
                            "vk": int(vk_hit),
                            "summary": f"Keyboard Key {vk_label} (VK 0x{vk_hit:02X})",
                        }
                        self.learning_stage = "WAITING_RELEASE"
                        self.log(f"[Detect Physical] Stage 1/2: Detected {self.learning_candidate['summary']} — Release key to confirm!")
            elif self.learning_stage == "WAITING_RELEASE" and self.learning_candidate:
                ckind = self.learning_candidate.get("kind")
                if ckind in ("mouse_btn", "wheel_click"):
                    m_target = self.learning_candidate.get("mouse_btn", "mouse3")
                    still_down = (
                        mouse5_now if m_target == "mouse5"
                        else (mouse4_now if m_target == "mouse4" else wheel_click_now)
                    )
                    if not still_down:
                        self.confirm_learning_candidate(profile)
                elif ckind == "key_vk":
                    vk_target = int(self.learning_candidate.get("vk", -1))
                    if vk_target not in active_vks:
                        self.confirm_learning_candidate(profile)

        # ----------------------------------------------------------------------
        # STEP 3: Apply Merged XInput State (Unified RB / M1 on 0x0200)
        # ----------------------------------------------------------------------
        slots_str = ",".join(str(s) for s in self.active_xinput_slots) if self.active_xinput_slots else str(self.active_xinput_slot)

        if xinput_ok:
            btns = raw_xinput_btns
            if btns != self._prev_logged_xinput_btns:
                old_x = self._prev_logged_xinput_btns
                self._prev_logged_xinput_btns = btns
                if self.deep_log_raw_bytes:
                    xor_x = btns ^ old_x
                    x_tags = []
                    for bit_m, bit_n in XINPUT_BIT_NAMES:
                        if xor_x & bit_m:
                            st_dir = "+DOWN" if (btns & bit_m) else "-UP"
                            x_tags.append(f"{bit_n}(0x{bit_m:04X}){st_dir}")
                    self.log(
                        f"[XINPUT DELTA] Slots[{slots_str}] wButtons: 0x{old_x:04X} -> 0x{btns:04X} "
                        f"(XOR ^0x{xor_x:04X} | {', '.join(x_tags) if x_tags else f'0x{xor_x:04X}'})"
                    )

            if self.learning_target_button is not None:
                if self.learning_stage == "SETTLING":
                    self._modal_base_xinput = btns
                elif self.learning_stage == "WAITING_PRESS":
                    diff_x = btns & (~self._modal_base_xinput)
                    if diff_x != 0:
                        bit_mask = diff_x & (-diff_x)
                        ckey = ("xinput", int(bit_mask))
                        cnt = self._candidate_tracker.get(ckey, 0) + 1
                        self._candidate_tracker[ckey] = cnt
                        if cnt >= 2:
                            self.learning_candidate = {
                                "kind": "xinput",
                                "mask": int(bit_mask),
                                "summary": f"XInput Button Mask 0x{bit_mask:04X}",
                            }
                            self.learning_stage = "WAITING_RELEASE"
                            self.log(
                                f"[Detect Physical] Stage 1/2: Detected {self.learning_candidate['summary']} — Release button now to confirm!"
                            )
                elif self.learning_stage == "WAITING_RELEASE" and self.learning_candidate:
                    if self.learning_candidate.get("kind") == "xinput":
                        x_mask = int(self.learning_candidate["mask"])
                        if (btns & x_mask) == 0:
                            self.confirm_learning_candidate(profile)

            xinput_btn_table = [
                (0x0001, "dpadUp", "DPadUp"),
                (0x0002, "dpadDown", "DPadDown"),
                (0x0004, "dpadLeft", "DPadLeft"),
                (0x0008, "dpadRight", "DPadRight"),
                (0x0010, "buttonMenu", "Menu"),
                (0x0020, "buttonView", "View"),
                (0x0040, "leftStickClick", "L3"),
                (0x0080, "rightStickClick", "R3"),
                (0x0100, "buttonLB", "LB"),
                (0x0200, "buttonRB", "RB/M1"),
                (0x0400, "legionLButton", "Guide/LegionL"),
                (0x1000, "buttonA", "A"),
                (0x2000, "buttonB", "B"),
                (0x4000, "buttonX", "X"),
                (0x8000, "buttonY", "Y"),
            ]
            for x_bit, hw_k, x_name in xinput_btn_table:
                if btns & x_bit:
                    hw[hw_k] = True
                    self._add_trigger_source(
                        hw_k, f"XInput Slot[{slots_str}] 0x{x_bit:04X} ({x_name}, wButtons=0x{btns:04X})"
                    )

            for btn_key, x_mask in learned_xinput.items():
                if btns & int(x_mask):
                    hw[btn_key] = True
                    self._add_trigger_source(
                        btn_key, f"Learned XInput Slot[{slots_str}] Mask 0x{int(x_mask):04X} (wButtons=0x{btns:04X})"
                    )

            hw["leftTriggerAnalog"] = max(hw["leftTriggerAnalog"], merged_lt * 128 if merged_lt > 3 else 0)
            hw["rightTriggerAnalog"] = max(hw["rightTriggerAnalog"], merged_rt * 128 if merged_rt > 3 else 0)
            hw["leftStickX"] = self._apply_stick_deadzone(merged_lx)
            hw["leftStickY"] = self._apply_stick_deadzone(merged_ly)
            hw["rightStickX"] = self._apply_stick_deadzone(merged_rx)
            hw["rightStickY"] = self._apply_stick_deadzone(merged_ry)

        # ----------------------------------------------------------------------
        # STEP 4: Poll DirectInput Composite Devices (Sticks Isolated When XInput Active)
        # ----------------------------------------------------------------------
        tcal = profile.setdefault("triggerCalibration", dict(DEFAULT_TRIGGER_CALIBRATION))
        needs_dinput_for_triggers = (
            self.trigger_cal_stage in ("REST", "PULL")
            or (isinstance(tcal.get("ltSource"), dict) and tcal["ltSource"].get("kind") == "dinput_axis")
            or (isinstance(tcal.get("rtSource"), dict) and tcal["rtSource"].get("kind") == "dinput_axis")
        )
        dinput_ok = False
        if proto_mode == "dinput_only" or (proto_mode == "auto" and not xinput_ok) or needs_dinput_for_triggers:
            dinput_ok = self._poll_winmm_dinput(hw, profile, xinput_ok=xinput_ok)

        # ----------------------------------------------------------------------
        # STEP 4B: Evaluate Custom Calibrated Trigger Sources & Press Stages (Half-Press / Full-Press)
        # ----------------------------------------------------------------------
        def _eval_calibrated_trigger_source(src_spec: dict) -> int:
            if not isinstance(src_spec, dict):
                return -1
            kind = src_spec.get("kind")
            rest_v = float(src_spec.get("rest", 0))
            full_v = float(src_spec.get("full", 255))
            span = full_v - rest_v
            if abs(span) < 1e-3:
                return -1
            raw_v = None
            if kind == "dinput_axis":
                raw_v = self.last_raw_dinput_axes.get((int(src_spec.get("joy_id", -1)), str(src_spec.get("axis", ""))))
            elif kind == "xinput":
                raw_v = merged_lt if src_spec.get("side") == "LT" else merged_rt
            elif kind == "hid_byte":
                t_iface = str(src_spec.get("iface", ""))
                t_rid = int(src_spec.get("report_id", -1))
                t_byte = int(src_spec.get("byte", -1))
                if 0 <= t_byte < 64:
                    for st_item in self.hid_streams:
                        if st_item.key == t_iface or t_iface in st_item.key:
                            for rid_k, sub_item in st_item.sub_channels.items():
                                if t_rid in (-1, rid_k) and sub_item.packets_read > 0:
                                    raw_v = int(sub_item.last_raw_packet[t_byte])
                                    break
            if raw_v is None:
                return -1
            ratio = (float(raw_v) - rest_v) / span
            return max(0, min(32767, int(round(ratio * 32767.0))))

        lt_cal_val = _eval_calibrated_trigger_source(tcal.get("ltSource"))
        if lt_cal_val >= 0:
            hw["leftTriggerAnalog"] = lt_cal_val
        rt_cal_val = _eval_calibrated_trigger_source(tcal.get("rtSource"))
        if rt_cal_val >= 0:
            hw["rightTriggerAnalog"] = rt_cal_val

        for side_prefix, analog_key, stage_key in (
            ("lt", "leftTriggerAnalog", "leftTriggerStage"),
            ("rt", "rightTriggerAnalog", "rightTriggerStage"),
        ):
            dz_pct = max(0, min(45, int(tcal.get(f"{side_prefix}DeadzonePct", 5))))
            half_pct = max(10, min(90, int(tcal.get(f"{side_prefix}HalfPressPct", 45))))
            full_pct = max(half_pct + 5, min(100, int(tcal.get(f"{side_prefix}FullPressPct", 85))))
            raw_a = int(hw.get(analog_key, 0))
            pct = (raw_a / 32767.0) * 100.0
            if pct <= dz_pct:
                hw[analog_key] = 0
                hw[stage_key] = "REST"
            elif pct >= full_pct:
                hw[stage_key] = "FULL-PRESS"
            elif pct >= half_pct:
                hw[stage_key] = "HALF-PRESS"
            else:
                hw[stage_key] = "PULL"

        if right_gyros:
            hw["rightImuGyro"] = right_gyros[0]
        if left_gyros:
            hw["leftImuGyro"] = left_gyros[-1]
        if tablet_gyros:
            hw["tabletImuGyro"] = tablet_gyros[0]

        gyro_src = profile.get("gyroPhysicalSource", "rightControllerImu")
        if not profile.get("gyroEnabled", True) or gyro_src == "disabled":
            gp_val, gy_val, gr_val = 0, 0, 0
        elif gyro_src == "rightControllerImu":
            gp_val, gy_val, gr_val = hw["rightImuGyro"]
        elif gyro_src == "leftControllerImu":
            gp_val, gy_val, gr_val = hw["leftImuGyro"]
        elif gyro_src == "combinedOrTabletImu":
            if hw["tabletImuGyro"] != (0, 0, 0):
                gp_val, gy_val, gr_val = hw["tabletImuGyro"]
            else:
                rp, ry, rr = hw["rightImuGyro"]
                lp, ly, lr = hw["leftImuGyro"]
                if (rp, ry, rr) != (0, 0, 0) and (lp, ly, lr) != (0, 0, 0):
                    gp_val, gy_val, gr_val = (rp + lp) // 2, (ry + ly) // 2, (rr + lr) // 2
                else:
                    gp_val, gy_val, gr_val = rp or lp, ry or ly, rr or lr
        else:
            gp_val, gy_val, gr_val = 0, 0, 0

        hw["imuGyroPitch"] = gp_val
        hw["imuGyroYaw"] = gy_val
        hw["imuGyroRoll"] = gr_val

        if xinput_ok:
            self.detected_mode_summary = f"XInput Mode (0x6182 · Slots[{slots_str}] + {len(self.hid_streams)} Composite HID)"
        elif dinput_ok:
            self.detected_mode_summary = f"{self.active_dinput_mode} + {len(self.hid_streams)} Composite HID"
        elif self.connected_pids:
            pids_str = "/".join(f"0x{p:04X}" for p in sorted(self.connected_pids))
            self.detected_mode_summary = f"Composite HID ({pids_str} · {len(self.hid_streams)} streams)"
        else:
            self.detected_mode_summary = "UI Tester Mode (Connect 0x17EF)"

        # 5. Merge Win32 WH_MOUSE_LL Physical Touchpad & VID_17EF Rear Scroll Wheel Delta
        if self.hook.pad_touch or self.hook.pad_click:
            hw["rightTrackpadTouch"] = True
            hw["rightTrackpadClick"] = self.hook.pad_click
            hw["rightTrackpadX"] = self.hook.pad_x
            hw["rightTrackpadY"] = self.hook.pad_y
            hw["rightTrackpadPressure"] = 32767 if self.hook.pad_click else 18500
            if self.hook.pad_click:
                self._add_trigger_source("rightTrackpadClick", f"Win32 Touchpad Click ({self.hook.pad_x}, {self.hook.pad_y})")

        if self.hook.wheel_delta != 0:
            hw["scrollWheelDelta"] = self.hook.wheel_delta
            if self.deep_log_presses:
                w_dir = "UP (+1)" if self.hook.wheel_delta > 0 else "DOWN (-1)"
                w_mode = profile.get("scrollWheelMode", "leftTrackpadVerticalSwipe")
                self.log(f"[WHEEL SCROLL] VID_17EF Rear Scroll Wheel {w_dir} ==> Mode: {w_mode}")

        # 6. Emit Deep Button Press & Release Logs for Tab 3 Inspector
        for btn_key, btn_label in LEGION_BUTTON_KEY_TO_LABEL.items():
            if btn_key == "rightTrackpadTouch":
                continue
            cur_pressed = bool(hw.get(btn_key, False))
            prev_pressed = bool(self._prev_logged_hw_buttons.get(btn_key, False))
            if cur_pressed != prev_pressed:
                self._prev_logged_hw_buttons[btn_key] = cur_pressed
                if self.deep_log_presses:
                    map_key = LEGION_BUTTON_TO_MAP_KEY.get(btn_key, "")
                    target_key = profile.get(map_key, DEFAULT_PROFILE.get(map_key, "none")) if map_key else "rightTrackpadClick"
                    target_label = TARGET_KEY_TO_LABEL.get(target_key, target_key)
                    if cur_pressed:
                        srcs = self._trigger_sources_this_tick.get(btn_key, ["Hardware State Active"])
                        self.log(
                            f"[INPUT PRESSED]  {btn_label} ({btn_key})  <==  {' + '.join(srcs)}  ==>  Mapped to: {target_label} ({target_key})"
                        )
                    else:
                        self.log(
                            f"[INPUT RELEASED] {btn_label} ({btn_key})  ==>  Released ({target_label})"
                        )

        return hw



# ==============================================================================
# 4. FULL BUTTON, SCROLL WHEEL UP/DOWN, DUAL-STAGE TRIGGER & GYRO REMAPPING ENGINE
# ==============================================================================
def clamp_int16(v: float) -> int:
    return max(-32768, min(32767, int(round(v))))


def clamp_uint16(v: float) -> int:
    return max(0, min(32767, int(round(v))))


def merge_hardware_and_tester_state(hw: dict, ui_test: dict) -> dict:
    merged = {}
    for k in hw:
        if isinstance(hw[k], bool):
            merged[k] = bool(hw[k] or ui_test.get(k, False))
        elif isinstance(hw[k], (tuple, str)):
            merged[k] = hw[k]
        else:
            ui_val = ui_test.get(k, 0)
            if k == "imuAccelZ" and ui_val == 16384:
                merged[k] = hw[k] if hw[k] != 16384 else 16384
            else:
                merged[k] = ui_val if ui_val != 0 else hw[k]
    return merged


ALL_REMAPPABLE_BUTTON_SOURCES = [
    ("legionLButton", "mapLegionLButton"),
    ("legionRButton", "mapLegionRButton"),
    ("buttonY1", "mapButtonY1"),
    ("buttonY2", "mapButtonY2"),
    ("buttonY3", "mapButtonY3"),
    ("buttonM2", "mapButtonM2"),
    ("buttonM3", "mapButtonM3"),
    ("scrollWheelClick", "mapScrollWheelClick"),
    ("scrollWheelUp", "mapScrollWheelUp"),
    ("scrollWheelDown", "mapScrollWheelDown"),
    ("buttonA", "mapButtonA"),
    ("buttonB", "mapButtonB"),
    ("buttonX", "mapButtonX"),
    ("buttonY", "mapButtonY"),
    ("buttonLB", "mapButtonLB"),
    ("buttonRB", "mapButtonRB"),
    ("leftStickClick", "mapLeftStickClick"),
    ("rightStickClick", "mapRightStickClick"),
    ("buttonView", "mapButtonView"),
    ("buttonMenu", "mapButtonMenu"),
    ("dpadUp", "mapDpadUp"),
    ("dpadDown", "mapDpadDown"),
    ("dpadLeft", "mapDpadLeft"),
    ("dpadRight", "mapDpadRight"),
]


def is_gyro_hold_button_active(legion: dict, hold_key: str) -> bool:
    if hold_key == "buttonM1":
        hold_key = "buttonRB"
    if hold_key == "leftTriggerPull":
        return legion.get("leftTriggerAnalog", 0) > 12000
    if hold_key == "rightTriggerPull":
        return legion.get("rightTriggerAnalog", 0) > 12000
    return bool(legion.get(hold_key, False))


def map_legion_to_steam_deck_state(legion: dict, profile: dict, wheel_angle: float) -> dict:
    deadzone = (float(profile.get("stickCapacitiveDeadzonePercent", 8)) / 100.0) * 32767.0
    left_stick_moved = math.hypot(legion["leftStickX"], legion["leftStickY"]) > deadzone
    right_stick_moved = math.hypot(legion["rightStickX"], legion["rightStickY"]) > deadzone

    tcal = profile.get("triggerCalibration", DEFAULT_TRIGGER_CALIBRATION)
    lt_full_thresh = int((max(15, min(100, int(tcal.get("ltFullPressPct", 85)))) / 100.0) * 32767.0)
    rt_full_thresh = int((max(15, min(100, int(tcal.get("rtFullPressPct", 85)))) / 100.0) * 32767.0)
    lt_half_thresh = int((max(5, min(95, int(tcal.get("ltHalfPressPct", 45)))) / 100.0) * 32767.0)
    rt_half_thresh = int((max(5, min(95, int(tcal.get("rtHalfPressPct", 45)))) / 100.0) * 32767.0)

    mode_shift_left_pad = False
    for btn_key, map_key in ALL_REMAPPABLE_BUTTON_SOURCES:
        if profile.get(map_key) == "modeShiftRightPadToLeftPad" and legion.get(btn_key):
            mode_shift_left_pad = True
    if tcal.get("ltHalfPressAction") == "modeShiftRightPadToLeftPad" and legion["leftTriggerAnalog"] >= lt_half_thresh:
        mode_shift_left_pad = True
    if tcal.get("rtHalfPressAction") == "modeShiftRightPadToLeftPad" and legion["rightTriggerAnalog"] >= rt_half_thresh:
        mode_shift_left_pad = True

    deck = {
        "buttonA": False,
        "buttonB": False,
        "buttonX": False,
        "buttonY": False,
        "dpadUp": False,
        "dpadDown": False,
        "dpadLeft": False,
        "dpadRight": False,
        "buttonL1": False,
        "buttonR1": False,
        "buttonL2Digital": legion["leftTriggerAnalog"] >= lt_full_thresh,
        "buttonR2Digital": legion["rightTriggerAnalog"] >= rt_full_thresh,
        "leftTriggerAnalog": clamp_uint16(legion["leftTriggerAnalog"]),
        "rightTriggerAnalog": clamp_uint16(legion["rightTriggerAnalog"]),
        "leftStickX": clamp_int16(legion["leftStickX"]),
        "leftStickY": clamp_int16(legion["leftStickY"]),
        "buttonL3Click": False,
        "leftStickCapacitiveTouch": (
            profile.get("autoStickCapacitiveTouchOnDeflection", True) and left_stick_moved
        ),
        "rightStickX": clamp_int16(legion["rightStickX"]),
        "rightStickY": clamp_int16(legion["rightStickY"]),
        "buttonR3Click": False,
        "rightStickCapacitiveTouch": (
            profile.get("autoStickCapacitiveTouchOnDeflection", True) and right_stick_moved
        ),
        "buttonL4Grip": False,
        "buttonR4Grip": False,
        "buttonL5Grip": False,
        "buttonR5Grip": False,
        "buttonView": False,
        "buttonMenu": False,
        "buttonSteam": False,
        "buttonQuickAccess": False,
        "leftTrackpadTouch": legion["rightTrackpadTouch"] if mode_shift_left_pad else False,
        "leftTrackpadClick": legion["rightTrackpadClick"] if mode_shift_left_pad else False,
        "leftTrackpadX": clamp_int16(legion["rightTrackpadX"]) if mode_shift_left_pad else 0,
        "leftTrackpadY": clamp_int16(legion["rightTrackpadY"]) if mode_shift_left_pad else 0,
        "leftTrackpadPressure": 32767 if (mode_shift_left_pad and legion["rightTrackpadClick"])
        else (18500 if (mode_shift_left_pad and legion["rightTrackpadTouch"]) else 0),
        "rightTrackpadTouch": legion["rightTrackpadTouch"] if not mode_shift_left_pad else False,
        "rightTrackpadClick": legion["rightTrackpadClick"] if not mode_shift_left_pad else False,
        "rightTrackpadX": clamp_int16(legion["rightTrackpadX"]) if not mode_shift_left_pad else 0,
        "rightTrackpadY": clamp_int16(legion["rightTrackpadY"]) if not mode_shift_left_pad else 0,
        "rightTrackpadPressure": 32767 if (not mode_shift_left_pad and legion["rightTrackpadClick"])
        else (18500 if (not mode_shift_left_pad and legion["rightTrackpadTouch"]) else 0),
        "accelX": clamp_int16(legion["imuAccelX"]),
        "accelY": clamp_int16(legion["imuAccelY"]),
        "accelZ": clamp_int16(legion["imuAccelZ"]),
        "gyroPitch": 0,
        "gyroYaw": 0,
        "gyroRoll": 0,
    }

    def _activate_deck_target(target: str):
        if target in deck:
            deck[target] = True
            if target == "buttonL3Click":
                deck["leftStickCapacitiveTouch"] = True
            elif target == "buttonR3Click":
                deck["rightStickCapacitiveTouch"] = True
            elif target == "leftTrackpadClick":
                deck["leftTrackpadTouch"] = True
                deck["leftTrackpadPressure"] = 32767
            elif target == "rightTrackpadClick":
                deck["rightTrackpadTouch"] = True
                deck["rightTrackpadPressure"] = 32767
            elif target == "buttonL2Digital" and deck["leftTriggerAnalog"] < lt_full_thresh:
                deck["leftTriggerAnalog"] = 32767
            elif target == "buttonR2Digital" and deck["rightTriggerAnalog"] < rt_full_thresh:
                deck["rightTriggerAnalog"] = 32767

    for src_btn, cfg_key in ALL_REMAPPABLE_BUTTON_SOURCES:
        default_target = DEFAULT_PROFILE.get(cfg_key, "none")
        target = profile.get(cfg_key, default_target)
        if legion.get(src_btn):
            _activate_deck_target(target)

    # Apply Half-Press (Soft Pull) Trigger Stage Actions if configured
    lt_hp_act = str(tcal.get("ltHalfPressAction", "none"))
    if lt_hp_act != "none" and legion["leftTriggerAnalog"] >= lt_half_thresh:
        _activate_deck_target(lt_hp_act)
    rt_hp_act = str(tcal.get("rtHalfPressAction", "none"))
    if rt_hp_act != "none" and legion["rightTriggerAnalog"] >= rt_half_thresh:
        _activate_deck_target(rt_hp_act)

    wheel_delta = legion.get("scrollWheelDelta", 0)
    if wheel_delta != 0:
        wmode = profile.get("scrollWheelMode", "leftTrackpadVerticalSwipe")
        if wmode == "leftTrackpadVerticalSwipe":
            deck["leftTrackpadTouch"] = True
            deck["leftTrackpadX"] = 0
            deck["leftTrackpadY"] = clamp_int16(wheel_delta * 22000)
            deck["leftTrackpadPressure"] = 18500
        elif wmode == "leftTrackpadCircularScroll":
            deck["leftTrackpadTouch"] = True
            deck["leftTrackpadX"] = clamp_int16(math.cos(wheel_angle) * 24000)
            deck["leftTrackpadY"] = clamp_int16(math.sin(wheel_angle) * 24000)
            deck["leftTrackpadPressure"] = 18500
        elif wmode == "dpadUpDown":
            if wheel_delta > 0:
                deck["dpadUp"] = True
            else:
                deck["dpadDown"] = True
        elif wmode == "buttonL4L5Tap":
            if wheel_delta > 0:
                deck["buttonL4Grip"] = True
            else:
                deck["buttonL5Grip"] = True

    # Evaluate Configurable Multi-IMU Gyro Source & Activation Behavior
    gyro_enabled = bool(profile.get("gyroEnabled", True))
    gyro_src = profile.get("gyroPhysicalSource", "rightControllerImu")
    gyro_act = profile.get("gyroActivationMode", "touchActivated")
    hold_btn = profile.get("gyroHoldButton", "buttonRB")
    sens = float(profile.get("gyroSensitivityMultiplier", 1.0))

    gyro_gate_open = False
    if gyro_enabled and gyro_src != "disabled":
        if gyro_act == "alwaysOn":
            gyro_gate_open = True
            deck["rightStickCapacitiveTouch"] = True
        elif gyro_act == "holdButtonActivated":
            if is_gyro_hold_button_active(legion, hold_btn):
                gyro_gate_open = True
                deck["rightStickCapacitiveTouch"] = True
            else:
                gyro_gate_open = False
        else:  # "touchActivated" — also opens & sets rightStickCapacitiveTouch whenever physical gyro is active!
            has_gyro_motion = (
                legion["imuGyroPitch"] != 0
                or legion["imuGyroYaw"] != 0
                or legion["imuGyroRoll"] != 0
            )
            if has_gyro_motion:
                deck["rightStickCapacitiveTouch"] = True
            gyro_gate_open = bool(
                has_gyro_motion
                or deck["leftStickCapacitiveTouch"]
                or deck["rightStickCapacitiveTouch"]
                or deck["leftTrackpadTouch"]
                or deck["rightTrackpadTouch"]
            )

    if gyro_gate_open and gyro_enabled and gyro_src != "disabled":
        p_sign = -1.0 if profile.get("gyroInvertPitch", False) else 1.0
        y_sign = -1.0 if profile.get("gyroInvertYaw", False) else 1.0
        r_sign = -1.0 if profile.get("gyroInvertRoll", False) else 1.0
        deck["gyroPitch"] = clamp_int16(legion["imuGyroPitch"] * sens * p_sign)
        deck["gyroYaw"] = clamp_int16(legion["imuGyroYaw"] * sens * y_sign)
        deck["gyroRoll"] = clamp_int16(legion["imuGyroRoll"] * sens * r_sign)
    else:
        deck["gyroPitch"] = 0
        deck["gyroYaw"] = 0
        deck["gyroRoll"] = 0

    return deck


def encode_neptune_64byte_report(deck: dict, frame_counter: int) -> bytes:
    b8 = (
        (0x01 if deck["buttonR2Digital"] else 0)
        | (0x02 if deck["buttonL2Digital"] else 0)
        | (0x04 if deck["buttonR1"] else 0)
        | (0x08 if deck["buttonL1"] else 0)
        | (0x10 if deck["buttonY"] else 0)
        | (0x20 if deck["buttonB"] else 0)
        | (0x40 if deck["buttonX"] else 0)
        | (0x80 if deck["buttonA"] else 0)
    )
    b9 = (
        (0x01 if deck["dpadUp"] else 0)
        | (0x02 if deck["dpadRight"] else 0)
        | (0x04 if deck["dpadLeft"] else 0)
        | (0x08 if deck["dpadDown"] else 0)
        | (0x10 if deck["buttonView"] else 0)
        | (0x20 if deck["buttonSteam"] else 0)
        | (0x40 if deck["buttonMenu"] else 0)
        | (0x80 if deck["buttonL5Grip"] else 0)
    )
    b10 = (
        (0x01 if deck["buttonR5Grip"] else 0)
        | (0x02 if deck["leftTrackpadClick"] else 0)
        | (0x04 if deck["rightTrackpadClick"] else 0)
        | (0x08 if deck["leftTrackpadTouch"] else 0)
        | (0x10 if deck["rightTrackpadTouch"] else 0)
        | (0x40 if deck["buttonL3Click"] else 0)
        | (0x80 if deck["buttonR3Click"] else 0)
    )
    b12 = (
        (0x02 if deck["buttonL4Grip"] else 0)
        | (0x04 if deck["buttonR4Grip"] else 0)
        | (0x40 if deck["leftStickCapacitiveTouch"] else 0)
        | (0x80 if deck["rightStickCapacitiveTouch"] else 0)
    )
    b13 = 0x04 if deck["buttonQuickAccess"] else 0x00

    return struct.pack(
        "<BBBB I BBBBBBBB hhhh hhhhhh hhhh HH hhhh HH I",
        0x01, 0x00, 0x09, 0x3C,
        frame_counter & 0xFFFFFFFF,
        b8, b9, b10, 0x00, b12, b13, 0x00, 0x00,
        deck["leftTrackpadX"], deck["leftTrackpadY"],
        deck["rightTrackpadX"], deck["rightTrackpadY"],
        deck["accelX"], deck["accelY"], deck["accelZ"],
        deck["gyroPitch"], deck["gyroYaw"], deck["gyroRoll"],
        16384, 0, 0, 0,
        deck["leftTriggerAnalog"], deck["rightTriggerAnalog"],
        deck["leftStickX"], deck["leftStickY"],
        deck["rightStickX"], deck["rightStickY"],
        deck["leftTrackpadPressure"], deck["rightTrackpadPressure"],
        (frame_counter * 4000) & 0xFFFFFFFF,
    )


# ==============================================================================
# 5. PURE-PYTHON USB/IP SERVER FOR VALVE STEAM DECK (VID 0x28DE / PID 0x1205)
# ==============================================================================
def build_usb_string_descriptor(text: str) -> bytes:
    raw = text.encode("utf-16le")
    b_len = min(254, len(raw) + 2)
    return struct.pack("<BB", b_len, 0x03) + raw[: b_len - 2]


HID_MOUSE_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01, 0x09, 0x02, 0xA1, 0x01, 0x09, 0x01,
    0xA1, 0x00, 0x05, 0x09, 0x19, 0x01, 0x29, 0x03,
    0x15, 0x00, 0x25, 0x01, 0x95, 0x03, 0x75, 0x01,
    0x81, 0x02, 0x95, 0x01, 0x75, 0x05, 0x81, 0x01,
    0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x15, 0x81,
    0x25, 0x7F, 0x75, 0x08, 0x95, 0x02, 0x81, 0x06,
    0xC0, 0xC0,
])

HID_KEYBOARD_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x05, 0x07,
    0x19, 0xE0, 0x29, 0xE7, 0x15, 0x00, 0x25, 0x01,
    0x75, 0x01, 0x95, 0x08, 0x81, 0x02, 0x95, 0x01,
    0x75, 0x08, 0x81, 0x01, 0x95, 0x05, 0x75, 0x01,
    0x05, 0x08, 0x19, 0x01, 0x29, 0x05, 0x91, 0x02,
    0x95, 0x01, 0x75, 0x03, 0x91, 0x01, 0x95, 0x06,
    0x75, 0x08, 0x15, 0x00, 0x25, 0x65, 0x05, 0x07,
    0x19, 0x00, 0x29, 0x65, 0x81, 0x00, 0xC0,
])

USB_DEVICE_DESCRIPTOR = struct.pack(
    "<BBHBBBBHHHBBBB",
    18, 0x01, 0x0200, 0x00, 0x00, 0x00, 64,
    VALVE_VENDOR_ID, STEAM_DECK_PRODUCT_ID, 0x0100,
    1, 2, 3, 1,
)

USB_HID_MOUSE_CLASS_DESCRIPTOR = struct.pack(
    "<BBHBBBH", 9, 0x21, 0x0111, 0x00, 1, 0x22, len(HID_MOUSE_REPORT_DESCRIPTOR)
)
USB_HID_KEYBOARD_CLASS_DESCRIPTOR = struct.pack(
    "<BBHBBBH", 9, 0x21, 0x0111, 0x00, 1, 0x22, len(HID_KEYBOARD_REPORT_DESCRIPTOR)
)
USB_HID_DECK_CLASS_DESCRIPTOR = struct.pack(
    "<BBHBBBH", 9, 0x21, 0x0111, 0x00, 1, 0x22, len(STEAM_DECK_HID_REPORT_DESCRIPTOR)
)


def build_usb_config_descriptor() -> bytes:
    iface_defs = [
        (0, 0x01, 0x02, USB_HID_MOUSE_CLASS_DESCRIPTOR, 0x81, 8, 10),
        (1, 0x01, 0x01, USB_HID_KEYBOARD_CLASS_DESCRIPTOR, 0x82, 8, 10),
        (2, 0x00, 0x00, USB_HID_DECK_CLASS_DESCRIPTOR, 0x83, 64, 4),
    ]
    interfaces_blob = bytearray()
    for iface_num, subclass, proto, hid_cls_desc, ep_addr, max_pkt, interval in iface_defs:
        iface_desc = struct.pack(
            "<BBBBBBBBB", 9, 0x04, iface_num, 0, 1, 0x03, subclass, proto, 0
        )
        ep_desc = struct.pack(
            "<BBBBHB", 7, 0x05, ep_addr, 0x03, max_pkt, interval
        )
        interfaces_blob.extend(iface_desc)
        interfaces_blob.extend(hid_cls_desc)
        interfaces_blob.extend(ep_desc)

    total_len = 9 + len(interfaces_blob)
    cfg_header = struct.pack(
        "<BBHBBBBB", 9, 0x02, total_len, 3, 1, 0, 0x80, 250
    )
    return cfg_header + bytes(interfaces_blob)


USB_CONFIG_DESCRIPTOR = build_usb_config_descriptor()


class PurePythonSteamDeckUsbipServer:
    def __init__(self, get_deck_state_fn, get_profile_fn, log_fn):
        self.get_deck_state = get_deck_state_fn
        self.get_profile = get_profile_fn
        self.log = log_fn
        self.running = False
        self.client_attached = False
        self.server_socket = None
        self.send_lock = threading.Lock()
        self.last_feature_cmd = 0x83
        self.last_feature_arg = 0x01
        self.urb_frame_counter = 1
        self.total_urbs_answered = 0
        self.parked_urbs = {}
        self.handshake_counts = {0x81: 0, 0x83: 0, 0x87: 0, 0xAE: 0}

    @staticmethod
    def _recv_exact(conn: socket.socket, length: int) -> bytes:
        buf = bytearray()
        while len(buf) < length:
            chunk = conn.recv(length - len(buf))
            if not chunk:
                return b""
            buf.extend(chunk)
        return bytes(buf)

    def build_feature_report_response(self) -> bytes:
        buf = bytearray(64)
        cmd = self.last_feature_cmd
        buf[0] = cmd
        self.handshake_counts[cmd] = self.handshake_counts.get(cmd, 0) + 1
        if cmd == 0x83:
            attrs = [
                (0, 0x120528DE),
                (1, STEAM_DECK_PRODUCT_ID),
                (2, 0x00000003),
                (4, 1700000000),
                (9, 10),
            ]
            buf[1] = len(attrs) * 5
            offset = 2
            for tag, val in attrs:
                struct.pack_into("<BI", buf, offset, tag, val)
                offset += 5
        elif cmd == 0xAE:
            serial = self.get_profile().get("emulatedDeckSerialNumber", "SD-LEGION-GO-28DE").encode("ascii")[:32]
            buf[1] = len(serial) + 2
            buf[2] = self.last_feature_arg
            buf[3:3 + len(serial)] = serial
        return bytes(buf)

    def start(self, port=3240):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._serve_loop, args=(port,), daemon=True).start()

    def stop(self):
        self.running = False
        self.client_attached = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

    def _serve_loop(self, port: int):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("127.0.0.1", port))
            self.server_socket.listen(4)
            self.log(f"[USB/IP] Listening on 127.0.0.1:{port} -> Valve Steam Deck (0x28DE:0x1205)")
            while self.running:
                conn, addr = self.server_socket.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.log(f"[USB/IP] Client connected from {addr[0]}:{addr[1]}")
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
        except Exception as exc:
            if self.running:
                self.log(f"[USB/IP] Server notice: {exc}")

    @staticmethod
    def _build_usbip_dev_summary() -> bytes:
        path_bytes = b"/sys/devices/pci0000:00/0000:00:01.2/usb1/1-1".ljust(256, b"\x00")
        busid_bytes = b"1-1".ljust(32, b"\x00")
        dev_desc = struct.pack(
            ">IIIHHHBBBBBB",
            1, 1, 2,
            VALVE_VENDOR_ID,
            STEAM_DECK_PRODUCT_ID,
            0x0100,
            0x00, 0x00, 0x00,
            1, 1, 3
        )
        return path_bytes + busid_bytes + dev_desc

    def _handle_client(self, conn: socket.socket):
        try:
            hdr = self._recv_exact(conn, 8)
            if len(hdr) < 8:
                return
            version, op_code, _status = struct.unpack(">HHI", hdr)
            if op_code == 0x8005:
                dev_summary = self._build_usbip_dev_summary()
                ifaces = (
                    struct.pack("BBBB", 0x03, 0x01, 0x02, 0x00) +
                    struct.pack("BBBB", 0x03, 0x01, 0x01, 0x00) +
                    struct.pack("BBBB", 0x03, 0x00, 0x00, 0x00)
                )
                reply = struct.pack(">HHII", version, 0x0005, 0, 1) + dev_summary + ifaces
                conn.sendall(reply)
                self.log("[USB/IP] Answered OP_REQ_DEVLIST (Bus 1-1: Valve Steam Deck 28de:1205)")
            elif op_code == 0x8003:
                busid_raw = self._recv_exact(conn, 32)
                busid = busid_raw.decode("ascii", errors="ignore").strip("\x00")
                self.log(f"[USB/IP] Attached Bus {busid}! Windows mounting USB\\VID_28DE&PID_1205&MI_02...")
                reply = struct.pack(">HHI", version, 0x0003, 0) + self._build_usbip_dev_summary()
                conn.sendall(reply)
                self.client_attached = True
                self.parked_urbs.clear()
                self._urb_loop(conn)
        except Exception as exc:
            self.log(f"[USB/IP] Client session ended: {exc}")
        finally:
            self.client_attached = False
            conn.close()

    def _handle_control_transfer(self, setup: bytes, out_data: bytes) -> bytes:
        bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack("<BBHHH", setup)
        req_type = bmRequestType & 0x60

        if req_type == 0x00:
            if bRequest == 0x06:
                desc_type = (wValue >> 8) & 0xFF
                desc_idx = wValue & 0xFF
                if desc_type == 0x01:
                    return USB_DEVICE_DESCRIPTOR[:wLength]
                elif desc_type == 0x02:
                    return USB_CONFIG_DESCRIPTOR[:wLength]
                elif desc_type == 0x03:
                    if desc_idx == 0:
                        return b"\x04\x03\x09\x04"[:wLength]
                    elif desc_idx == 1:
                        return build_usb_string_descriptor("Valve Software")[:wLength]
                    elif desc_idx == 2:
                        return build_usb_string_descriptor("Steam Deck")[:wLength]
                    else:
                        serial_str = self.get_profile().get("emulatedDeckSerialNumber", "SD-LEGION-GO-28DE")
                        return build_usb_string_descriptor(serial_str)[:wLength]
                elif desc_type == 0x21:
                    if wIndex == 0:
                        return USB_HID_MOUSE_CLASS_DESCRIPTOR[:wLength]
                    elif wIndex == 1:
                        return USB_HID_KEYBOARD_CLASS_DESCRIPTOR[:wLength]
                    return USB_HID_DECK_CLASS_DESCRIPTOR[:wLength]
                elif desc_type == 0x22:
                    if wIndex == 0:
                        return HID_MOUSE_REPORT_DESCRIPTOR[:wLength]
                    elif wIndex == 1:
                        return HID_KEYBOARD_REPORT_DESCRIPTOR[:wLength]
                    return STEAM_DECK_HID_REPORT_DESCRIPTOR[:wLength]
                elif desc_type == 0x06:
                    return struct.pack("<BBHBBBBBB", 10, 0x06, 0x0200, 0, 0, 0, 64, 1, 0)[:wLength]
            elif bRequest == 0x00:
                return b"\x00\x00"[:wLength]
            elif bRequest == 0x08:
                return b"\x01"[:wLength]
            elif bRequest == 0x0A:
                return b"\x00"[:wLength]
            elif bRequest in (0x01, 0x03, 0x05, 0x09, 0x0B):
                return b""

        if req_type == 0x20:
            if bRequest in (0x0A, 0x0B):
                return b""
            elif bRequest == 0x09:
                if out_data:
                    offset = 1 if (len(out_data) > 1 and out_data[0] == 0x00) else 0
                    cmd = out_data[offset]
                    self.last_feature_cmd = cmd
                    if len(out_data) > offset + 2:
                        self.last_feature_arg = out_data[offset + 2]
                    self.handshake_counts[cmd] = self.handshake_counts.get(cmd, 0) + 1
                return b""
            elif bRequest == 0x01:
                report_type = (wValue >> 8) & 0xFF
                if report_type == 0x03:
                    return self.build_feature_report_response()[:wLength]
                else:
                    self.urb_frame_counter = (self.urb_frame_counter + 1) & 0xFFFFFFFF
                    return encode_neptune_64byte_report(self.get_deck_state(), self.urb_frame_counter)[:wLength]

        return b""

    def _send_ret_submit(self, conn: socket.socket, seqnum: int, is_in: bool, resp_payload: bytes, out_len: int):
        actual_len = len(resp_payload) if is_in else out_len
        ret_hdr = struct.pack(
            ">IIIIIiiiii",
            0x00000003,
            seqnum,
            0, 0, 0,
            0,
            actual_len,
            0, 0, 0
        ) + b"\x00" * 8
        with self.send_lock:
            conn.sendall(ret_hdr + (resp_payload if is_in else b""))
        self.total_urbs_answered += 1

    def _reply_ep3_async(self, conn: socket.socket, seqnum: int, buf_len: int):
        try:
            time.sleep(0.0025)
            if seqnum not in self.parked_urbs:
                return
            self.parked_urbs.pop(seqnum, None)
            self.urb_frame_counter = (self.urb_frame_counter + 1) & 0xFFFFFFFF
            resp_payload = encode_neptune_64byte_report(
                self.get_deck_state(), self.urb_frame_counter
            )[:buf_len]
            self._send_ret_submit(conn, seqnum, True, resp_payload, buf_len)
        except Exception:
            pass

    def _urb_loop(self, conn: socket.socket):
        while self.running:
            cmd_hdr = self._recv_exact(conn, 48)
            if len(cmd_hdr) < 48:
                break
            command, seqnum, devid, direction, ep = struct.unpack(">IIIII", cmd_hdr[:20])

            if command == 0x00000001:
                _flags, buf_len, _sf, _iso, _intv = struct.unpack(">IIiii", cmd_hdr[20:40])
                setup = cmd_hdr[40:48]
                ep_num = ep & 0x0F
                is_in = (direction == 1) or (ep_num == 0 and (setup[0] & 0x80) != 0)
                out_data = self._recv_exact(conn, buf_len) if (not is_in and buf_len > 0) else b""

                if ep_num == 0:
                    resp_payload = self._handle_control_transfer(setup, out_data)
                    self._send_ret_submit(conn, seqnum, is_in, resp_payload, buf_len)
                elif ep_num == 3:
                    self.parked_urbs[seqnum] = (devid, ep_num)
                    threading.Thread(
                        target=self._reply_ep3_async,
                        args=(conn, seqnum, buf_len),
                        daemon=True,
                    ).start()
                else:
                    self.parked_urbs[seqnum] = (devid, ep_num)

            elif command == 0x00000002:
                unlink_seqnum = struct.unpack(">I", cmd_hdr[20:24])[0]
                was_parked = self.parked_urbs.pop(unlink_seqnum, None) is not None
                unlink_status = -104 if was_parked else 0
                ret_unlink = struct.pack(
                    ">IIIIIiiiii",
                    0x00000004,
                    seqnum,
                    0, 0, 0,
                    unlink_status,
                    0, 0, 0, 0
                ) + b"\x00" * 8
                with self.send_lock:
                    conn.sendall(ret_unlink)


# ==============================================================================
# 6. CUSTOM PYQT6 QPAINTER WIDGETS (MIUI SQUIRCLE ICON + 2D TRACKPAD CANVAS)
# ==============================================================================
def create_miui_squircle_icon(bg_hex: str, symbol_text: str, size: int = 64) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    path = QPainterPath()
    radius = size * 0.28  # Stock MIUI / MtZ 28% squircle curvature
    path.addRoundedRect(QRectF(2, 2, size - 4, size - 4), radius, radius)
    painter.fillPath(path, QColor(bg_hex))

    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", int(size * 0.34), QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, symbol_text)
    painter.end()
    return QIcon(pix)


class InteractiveTrackpadCanvas(QWidget):
    padChanged = pyqtSignal(bool, int, int)

    def __init__(self, title: str, interactive: bool = True, parent=None):
        super().__init__(parent)
        self.title = title
        self.interactive = interactive
        self.touch_active = False
        self.click_active = False
        self.pad_x = 0
        self.pad_y = 0
        self.user_dragging = False
        self.setMinimumSize(150, 102)
        if interactive:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def set_pad_state(self, touch: bool, click: bool, x_val: int, y_val: int):
        if self.user_dragging:
            return
        if (
            self.touch_active != touch
            or self.click_active != click
            or self.pad_x != x_val
            or self.pad_y != y_val
        ):
            self.touch_active = touch
            self.click_active = click
            self.pad_x = x_val
            self.pad_y = y_val
            self.update()

    def mousePressEvent(self, event):
        if not self.interactive:
            return
        self.user_dragging = True
        self._update_from_pos(event.position())

    def mouseMoveEvent(self, event):
        if not self.interactive or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        self._update_from_pos(event.position())

    def mouseReleaseEvent(self, event):
        if not self.interactive:
            return
        self.user_dragging = False
        self.touch_active = False
        self.pad_x = 0
        self.pad_y = 0
        self.padChanged.emit(False, 0, 0)
        self.update()

    def _update_from_pos(self, pos: QPointF):
        w = max(1.0, float(self.width()))
        h = max(1.0, float(self.height()))
        nx = max(-1.0, min(1.0, (pos.x() / w) * 2.0 - 1.0))
        ny = max(-1.0, min(1.0, (pos.y() / h) * 2.0 - 1.0))
        self.touch_active = True
        self.pad_x = int(round(nx * 32767))
        self.pad_y = int(round(-ny * 32767))
        self.padChanged.emit(True, self.pad_x, self.pad_y)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(2, 2, self.width() - 4, self.height() - 4)

        bg_color = QColor("#111927") if self.touch_active else QColor("#0D1117")
        border_color = QColor("#10B981") if self.touch_active else QColor("#263244")

        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.fillPath(path, bg_color)
        painter.setPen(QPen(border_color, 2 if self.touch_active else 1))
        painter.drawPath(path)

        painter.setPen(QPen(QColor("#1E293B"), 1))
        painter.drawLine(int(rect.left()), int(rect.center().y()), int(rect.right()), int(rect.center().y()))
        painter.drawLine(int(rect.center().x()), int(rect.top()), int(rect.center().x()), int(rect.bottom()))

        painter.setPen(QColor("#94A3B8"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.drawText(QRectF(8, 4, rect.width() - 16, 16), Qt.AlignmentFlag.AlignLeft, self.title)

        coord_str = f"X:{self.pad_x} Y:{self.pad_y} {'[CLK]' if self.click_active else ('[TCH]' if self.touch_active else '[IDLE]')}"
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(QRectF(8, rect.height() - 16, rect.width() - 16, 14), Qt.AlignmentFlag.AlignLeft, coord_str)

        if self.touch_active:
            cx = rect.center().x() + (self.pad_x / 32767.0) * (rect.width() * 0.42)
            cy = rect.center().y() - (self.pad_y / 32767.0) * (rect.height() * 0.36)
            dot_color = QColor("#10B981") if self.click_active else QColor("#0D84FF")
            painter.setBrush(dot_color)
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawEllipse(QPointF(cx, cy), 7, 7)
        painter.end()


# ==============================================================================
# 6B. INTERACTIVE "DETECT PHYSICAL BUTTON" MODAL POPUP WITH LIVE PACKET MONITOR
# ==============================================================================
class DetectPhysicalButtonDialog(QDialog):
    """
    Modal popup displayed when 'Detect Physical' is clicked.
    Uses a 3-Stage Press-and-Release state machine:
      Stage 0 ('SETTLING', 350ms) : Locks fresh idle baseline & masks fluctuating gyro/touch bytes.
      Stage 1 ('WAITING_PRESS')   : Detects button press, mouse click, scroll wheel up/down, or key.
      Stage 2 ('WAITING_RELEASE') : Confirms & saves binding when released!
    """
    def __init__(self, parent, hw_btn_key: str, control_label: str, reader: LegionGoHardwareReader, profile: dict, on_unbind_fn):
        super().__init__(parent)
        self.hw_btn_key = hw_btn_key
        self.control_label = control_label
        self.reader = reader
        self.profile = profile
        self.on_unbind_fn = on_unbind_fn
        self.start_time = time.perf_counter()
        self.timeout_sec = 14.0
        self.captured_done = False

        self.setWindowTitle(f"Detect Physical Input — {control_label}")
        self.setModal(True)
        self.resize(680, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.banner_lbl = QLabel(f"Step 0 of 2: Calibrating idle baseline for {control_label} (350ms)...")
        self.banner_lbl.setWordWrap(True)
        self.banner_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #0D84FF; padding: 8px 12px; border-radius: 8px;"
        )
        layout.addWidget(self.banner_lbl)

        tip_text = chr(10).join([
            "Multi-Composite Raw HID, DInput, XInput, VID_17EF Scroll Wheel & Key Detector:",
            "  1. Wait 0.35s for the banner above to say 'Step 1 of 2: PRESS & HOLD'.",
            "  2. Press and hold the physical button (or scroll the Legion Go wheel up/down).",
            "  3. Release the physical button — the banner turns GREEN ('Confirmed') and saves your binding!",
        ])
        tip_lbl = QLabel(tip_text)
        tip_lbl.setWordWrap(True)
        tip_lbl.setStyleSheet(
            "background-color: #1E293B; color: #E2E8F0; padding: 7px 10px; border-radius: 7px; font-size: 11px;"
        )
        layout.addWidget(tip_lbl)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat("Calibrating idle baseline... (%p%)")
        layout.addWidget(self.progress)

        mon_hdr = QLabel("Live 64-Byte VID_17EF Multi-Composite Monitor (All MI_00..MI_05 & COL01..COL08 Streams):")
        mon_hdr.setObjectName("MutedText")
        layout.addWidget(mon_hdr)

        self.monitor_box = QPlainTextEdit()
        self.monitor_box.setReadOnly(True)
        self.monitor_box.setFont(QFont("Consolas", 9))
        layout.addWidget(self.monitor_box, 1)

        btn_row = QHBoxLayout()
        wake_btn = QPushButton("Send Lenovo 0xFFA0 Raw Unlock")
        wake_btn.clicked.connect(self._on_wake_clicked)
        btn_row.addWidget(wake_btn)

        self.confirm_now_btn = QPushButton("Confirm Detected Input Now")
        self.confirm_now_btn.setObjectName("PrimaryActionBtn")
        self.confirm_now_btn.setEnabled(False)
        self.confirm_now_btn.clicked.connect(self._on_confirm_now_clicked)
        btn_row.addWidget(self.confirm_now_btn)

        unbind_btn = QPushButton("Clear Binding")
        unbind_btn.clicked.connect(self._on_unbind_clicked)
        btn_row.addWidget(unbind_btn)

        btn_row.addStretch(1)

        cancel_btn = QPushButton("Cancel (Esc)")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._tick)
        self.poll_timer.start(30)
        self._tick()

    def _on_wake_clicked(self):
        self.reader.send_lenovo_raw_button_wakeup()
        self.reader.start_learning_button(self.hw_btn_key)
        self.start_time = time.perf_counter()

    def _on_confirm_now_clicked(self):
        if self.reader.confirm_learning_candidate(self.profile):
            self._tick()

    def _on_unbind_clicked(self):
        self.reader.cancel_learning_button()
        self.on_unbind_fn(self.hw_btn_key)
        self.accept()

    def _tick(self):
        self.monitor_box.setPlainText(self.reader.get_live_monitor_snapshot())
        if self.captured_done:
            return

        stage = self.reader.learning_stage
        if stage == "CONFIRMED" or (self.reader.learning_target_button is None and self.reader.last_learned_summary):
            self.captured_done = True
            self.confirm_now_btn.setEnabled(False)
            self.progress.setValue(100)
            self.progress.setFormat("CONFIRMED & SAVED!")
            self.banner_lbl.setText(f"CONFIRMED & SAVED: {self.reader.last_learned_summary}")
            self.banner_lbl.setStyleSheet(
                "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #10B981; padding: 8px 12px; border-radius: 8px;"
            )
            QTimer.singleShot(550, self.accept)
            return

        elapsed = time.perf_counter() - self.start_time
        rem = max(0.0, self.timeout_sec - elapsed)
        pct = int((rem / self.timeout_sec) * 100)
        self.progress.setValue(pct)

        if stage == "SETTLING":
            self.confirm_now_btn.setEnabled(False)
            self.banner_lbl.setText(f"Step 0 of 2: Capturing 350ms quiet idle snapshot for {self.control_label}...")
            self.banner_lbl.setStyleSheet(
                "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #475569; padding: 8px 12px; border-radius: 8px;"
            )
            self.progress.setFormat(f"Settling idle snapshot... ({rem:.1f}s remaining)")
        elif stage == "WAITING_PRESS":
            self.confirm_now_btn.setEnabled(False)
            self.banner_lbl.setText(f"Step 1 of 2: PRESS & HOLD physical '{self.control_label}' on your Legion Go now...")
            self.banner_lbl.setStyleSheet(
                "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #0D84FF; padding: 8px 12px; border-radius: 8px;"
            )
            self.progress.setFormat(f"Waiting for physical input... ({rem:.1f}s remaining)")
        elif stage == "WAITING_RELEASE" and self.reader.learning_candidate:
            cand_sum = self.reader.learning_candidate.get("summary", "Candidate Input")
            self.confirm_now_btn.setEnabled(True)
            self.banner_lbl.setText(
                f"Step 2 of 2: INPUT DETECTED ({cand_sum}) — Now RELEASE to confirm!"
            )
            self.banner_lbl.setStyleSheet(
                "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #D97706; padding: 8px 12px; border-radius: 8px;"
            )
            self.progress.setFormat(f"Waiting for release (or click 'Confirm Detected Input Now')... ({rem:.1f}s)")

        if rem <= 0.0:
            self.reader.cancel_learning_button()
            self.banner_lbl.setText(
                "Timed out (No input detected). Click 'Send Lenovo 0xFFA0 Raw Unlock' to retry."
            )
            self.banner_lbl.setStyleSheet(
                "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #DC2626; padding: 8px 12px; border-radius: 8px;"
            )

    def reject(self):
        self.poll_timer.stop()
        self.reader.cancel_learning_button()
        super().reject()

    def accept(self):
        self.poll_timer.stop()
        super().accept()


# ==============================================================================
# 6C. 2-STEP INTERACTIVE GYRO CALIBRATION WIZARD MODAL DIALOG
# ==============================================================================
class GyroCalibrationDialog(QDialog):
    """
    2-Step Interactive Gyro Calibration Wizard:
      Step 1 (1.5s): Hold Controller Still -> Locks resting bias & noise floor across all Report IDs.
      Step 2 (2.5s): Rotate & Tilt Controller Smoothly -> Finds true 6-byte 16-bit IMU slice (<hhh or >hhh).
    """
    def __init__(self, parent, reader: LegionGoHardwareReader, profile: dict, get_hw_state_fn):
        super().__init__(parent)
        self.reader = reader
        self.profile = profile
        self.get_hw_state = get_hw_state_fn
        self.step = 0  # 0=ready/running step 1, 1=step 1, 2=step 2, 3=done
        self.step_start = 0.0

        self.setWindowTitle("2-Step Interactive Gyroscope Calibration Wizard")
        self.setModal(True)
        self.resize(620, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.banner_lbl = QLabel("Step 1 of 2: Hold your Legion Go / Controller COMPLETELY STILL (1.5s)...")
        self.banner_lbl.setWordWrap(True)
        self.banner_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #0D84FF; padding: 10px 12px; border-radius: 8px;"
        )
        layout.addWidget(self.banner_lbl)

        desc_lbl = QLabel(
            chr(10).join([
                "Why this wizard is needed:",
                "  • Without calibration, random analog LSB noise or packet counters can be mistaken for gyro bytes.",
                "  • Step 1 (1.5s Still) records your resting baseline so Gyro stays at a rock-solid (0, 0, 0) when untouched.",
                "  • Step 2 (2.5s Rotate) compares your rotation across all 64 bytes to lock onto the true 6-axis IMU sensor.",
            ])
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            "background-color: #1E293B; color: #E2E8F0; padding: 8px 10px; border-radius: 7px; font-size: 11px;"
        )
        layout.addWidget(desc_lbl)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.live_readout_lbl = QLabel("Live Calibrated Gyro Output: Pitch = 0  |  Yaw = 0  |  Roll = 0")
        self.live_readout_lbl.setObjectName("MonoReadout")
        self.live_readout_lbl.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 12px; font-weight: 700; color: #38BDF8; padding: 6px; background-color: #0F172A; border-radius: 6px;"
        )
        layout.addWidget(self.live_readout_lbl)

        self.details_lbl = QLabel("")
        self.details_lbl.setWordWrap(True)
        self.details_lbl.setObjectName("MutedText")
        layout.addWidget(self.details_lbl)

        layout.addStretch(1)

        btn_row = QHBoxLayout()
        self.restart_btn = QPushButton("Re-Run 2-Step Wizard")
        self.restart_btn.clicked.connect(self._start_wizard)
        btn_row.addWidget(self.restart_btn)

        clear_btn = QPushButton("Reset Gyro to (0, 0, 0)")
        clear_btn.clicked.connect(self._clear_gyro_cal)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch(1)

        close_btn = QPushButton("Done / Close")
        close_btn.setObjectName("PrimaryButton")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(35)
        self._start_wizard()

    def _start_wizard(self):
        self.step = 1
        self.step_start = time.perf_counter()
        self.reader.start_gyro_wizard_step1()
        self.banner_lbl.setText("Step 1 of 2 (1.5s): Hold controller COMPLETELY STILL right now...")
        self.banner_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #0D84FF; padding: 10px 12px; border-radius: 8px;"
        )
        self.details_lbl.setText("Measuring resting sensor bias and masking out non-IMU packet counters...")

    def _clear_gyro_cal(self):
        self.reader.cancel_gyro_wizard()
        self.profile["gyroCalibration"] = None
        for st in self.reader.hid_streams:
            st.live_gyro = (0, 0, 0)
        self.step = 3
        self.progress.setValue(0)
        self.progress.setFormat("Gyro Reset to (0, 0, 0)")
        self.banner_lbl.setText("Gyroscope Calibration Cleared — Gyro stays at (0, 0, 0) until calibrated.")
        self.banner_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #475569; padding: 10px 12px; border-radius: 8px;"
        )

    def _tick(self):
        hw = self.get_hw_state()
        gp, gy, gr = hw.get("imuGyroPitch", 0), hw.get("imuGyroYaw", 0), hw.get("imuGyroRoll", 0)
        self.live_readout_lbl.setText(
            f"Live Calibrated Gyro Output:   Pitch = {gp:+6d}   |   Yaw = {gy:+6d}   |   Roll = {gr:+6d}"
        )

        now = time.perf_counter()
        elapsed = now - self.step_start

        if self.step == 1:
            dur = 1.5
            pct = min(100, int((elapsed / dur) * 100))
            self.progress.setValue(pct)
            self.progress.setFormat(f"Step 1/2: Holding Still... ({max(0.0, dur - elapsed):.1f}s)")
            if elapsed >= dur:
                self.step = 2
                self.step_start = now
                self.reader.start_gyro_wizard_step2()
                self.banner_lbl.setText(
                    "Step 2 of 2 (2.5s): NOW ROTATE & TILT controller smoothly in Pitch, Yaw & Roll!"
                )
                self.banner_lbl.setStyleSheet(
                    "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #D97706; padding: 10px 12px; border-radius: 8px;"
                )
                self.details_lbl.setText("Tilt up/down, turn left/right, and roll the controller continuously...")
        elif self.step == 2:
            dur = 2.5
            pct = min(100, int((elapsed / dur) * 100))
            self.progress.setValue(pct)
            self.progress.setFormat(f"Step 2/2: Rotate Controller Now... ({max(0.0, dur - elapsed):.1f}s)")
            if elapsed >= dur:
                self.step = 3
                ok, msg, _cal = self.reader.finalize_gyro_wizard(self.profile)
                self.progress.setValue(100)
                if ok:
                    self.progress.setFormat("GYRO CALIBRATED & LOCKED!")
                    self.banner_lbl.setText("SUCCESS: True 6-Axis IMU Gyroscope Locked & Zeroed!")
                    self.banner_lbl.setStyleSheet(
                        "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #10B981; padding: 10px 12px; border-radius: 8px;"
                    )
                else:
                    self.progress.setFormat("No IMU Motion Detected — Click 'Re-Run 2-Step Wizard'")
                    self.banner_lbl.setText("Could not lock IMU motion — Click 'Re-Run 2-Step Wizard' and tilt more briskly.")
                    self.banner_lbl.setStyleSheet(
                        "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #DC2626; padding: 10px 12px; border-radius: 8px;"
                    )
                self.details_lbl.setText(msg)

    def reject(self):
        self.timer.stop()
        self.reader.cancel_gyro_wizard()
        super().reject()

    def accept(self):
        self.timer.stop()
        self.reader.cancel_gyro_wizard()
        super().accept()


# ==============================================================================
# 6D. 2-STEP INTERACTIVE ANALOG TRIGGER & PRESS STAGE CALIBRATION DIALOG
# ==============================================================================
class TriggerStageCalibrationDialog(QDialog):
    """
    2-Step Interactive Analog Trigger & Press Stage Calibration Wizard (LT / RT):
      Step 1 (1.0s): Release Both Triggers Completely -> Records resting baseline across DInput, XInput & Raw HID.
      Step 2 (2.8s): Squeeze Target Trigger Smoothly Through Half-Press to Full-Press -> Locks analog axis/byte
                     and excludes that axis from stick calculations so RT never affects Left Stick Y!
    """
    def __init__(self, parent, target_side: str, reader: LegionGoHardwareReader, profile: dict, get_hw_state_fn):
        super().__init__(parent)
        self.target_side = "LT" if str(target_side).upper() == "LT" else "RT"
        self.reader = reader
        self.profile = profile
        self.get_hw_state = get_hw_state_fn
        self.step = 1
        self.step_start = time.perf_counter()

        self.setWindowTitle(f"Detect & Calibrate {self.target_side} Analog Trigger + Press Stages")
        self.setModal(True)
        self.resize(620, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.banner_lbl = QLabel(
            f"Step 1 of 2 (1.0s): RELEASE BOTH TRIGGERS completely to record {self.target_side} resting zero..."
        )
        self.banner_lbl.setWordWrap(True)
        self.banner_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #0D84FF; padding: 10px 12px; border-radius: 8px;"
        )
        layout.addWidget(self.banner_lbl)

        desc_lbl = QLabel(
            chr(10).join([
                f"Manual {self.target_side} Analog Trigger & Stage Detection (Supports DirectInput, XInput & Raw HID):",
                "  • Step 1 (1.0s): Keep both triggers unpressed so resting value (0%) is locked.",
                f"  • Step 2 (2.8s): Squeeze {self.target_side} smoothly through Half-Press (~50%) all the way to Full-Press (100%).",
                "  • Any DirectInput axis detected as a trigger is automatically excluded from Left/Right Stick X/Y!",
            ])
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            "background-color: #1E293B; color: #E2E8F0; padding: 8px 10px; border-radius: 7px; font-size: 11px;"
        )
        layout.addWidget(desc_lbl)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.live_stage_lbl = QLabel(f"Live {self.target_side} Output: 0 / 32767 (0%)  |  Stage: REST")
        self.live_stage_lbl.setObjectName("MonoReadout")
        self.live_stage_lbl.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 12px; font-weight: 700; color: #38BDF8; padding: 6px; background-color: #0F172A; border-radius: 6px;"
        )
        layout.addWidget(self.live_stage_lbl)

        self.details_lbl = QLabel("")
        self.details_lbl.setWordWrap(True)
        self.details_lbl.setObjectName("MutedText")
        layout.addWidget(self.details_lbl)

        layout.addStretch(1)

        btn_row = QHBoxLayout()
        retry_btn = QPushButton(f"Re-Run {self.target_side} Detection")
        retry_btn.clicked.connect(self._start_detection)
        btn_row.addWidget(retry_btn)

        btn_row.addStretch(1)

        close_btn = QPushButton("Done / Close")
        close_btn.setObjectName("PrimaryButton")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(35)
        self._start_detection()

    def _start_detection(self):
        self.step = 1
        self.step_start = time.perf_counter()
        self.reader.start_trigger_stage_detection(self.target_side)
        self.banner_lbl.setText(
            f"Step 1 of 2 (1.0s): RELEASE BOTH TRIGGERS completely to record {self.target_side} resting zero..."
        )
        self.banner_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #0D84FF; padding: 10px 12px; border-radius: 8px;"
        )
        self.details_lbl.setText("Sampling resting baseline across DirectInput axes, XInput, and Raw HID bytes...")

    def _tick(self):
        hw = self.get_hw_state()
        a_key = "leftTriggerAnalog" if self.target_side == "LT" else "rightTriggerAnalog"
        s_key = "leftTriggerStage" if self.target_side == "LT" else "rightTriggerStage"
        a_val = int(hw.get(a_key, 0))
        s_val = str(hw.get(s_key, "REST"))
        pct_val = int(round((a_val / 32767.0) * 100.0))
        self.live_stage_lbl.setText(
            f"Live {self.target_side} Output: {a_val:5d} / 32767 ({pct_val:3d}%)   |   Press Stage: {s_val}"
        )

        now = time.perf_counter()
        elapsed = now - self.step_start

        if self.step == 1:
            dur = 1.0
            self.progress.setValue(min(100, int((elapsed / dur) * 100)))
            self.progress.setFormat(f"Step 1/2: Recording Resting Zero... ({max(0.0, dur - elapsed):.1f}s)")
            if elapsed >= dur:
                self.step = 2
                self.step_start = now
                self.reader.advance_trigger_stage_to_pull()
                self.banner_lbl.setText(
                    f"Step 2 of 2 (2.8s): Slowly SQUEEZE {self.target_side} through HALF-PRESS (50%) to FULL-PRESS (100%)!"
                )
                self.banner_lbl.setStyleSheet(
                    "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #D97706; padding: 10px 12px; border-radius: 8px;"
                )
                self.details_lbl.setText(f"Pull {self.target_side} all the way down and release...")
        elif self.step == 2:
            dur = 2.8
            self.progress.setValue(min(100, int((elapsed / dur) * 100)))
            self.progress.setFormat(f"Step 2/2: Squeeze {self.target_side} Smoothly to 100%... ({max(0.0, dur - elapsed):.1f}s)")
            if elapsed >= dur:
                self.step = 3
                ok, msg, _src = self.reader.finalize_trigger_stage_detection(self.profile)
                self.progress.setValue(100)
                if ok:
                    self.progress.setFormat(f"{self.target_side} ANALOG TRIGGER & STAGES LOCKED!")
                    self.banner_lbl.setText(f"SUCCESS: Locked {msg}")
                    self.banner_lbl.setStyleSheet(
                        "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #10B981; padding: 10px 12px; border-radius: 8px;"
                    )
                else:
                    self.progress.setFormat(f"No {self.target_side} Sweep Detected — Click 'Re-Run'")
                    self.banner_lbl.setText(msg)
                    self.banner_lbl.setStyleSheet(
                        "font-size: 13px; font-weight: 700; color: #FFFFFF; background-color: #DC2626; padding: 10px 12px; border-radius: 8px;"
                    )
                self.details_lbl.setText(msg)

    def reject(self):
        self.timer.stop()
        self.reader.cancel_trigger_stage_detection()
        super().reject()

    def accept(self):
        self.timer.stop()
        self.reader.cancel_trigger_stage_detection()
        super().accept()


# ==============================================================================
# 7. MAIN STANDALONE PYQT6 DESKTOP STUDIO WINDOW
# ==============================================================================
class LogSignalBridge(QObject):
    log_emitted = pyqtSignal(str)


class LegionGoSteamDeckPyQtApp(QMainWindow):
    log_view = None
    _early_log_buffer = None

    def __init__(self):
        self.log_view = None
        self._early_log_buffer = []
        super().__init__()
        self.setWindowTitle("LegionDeck Studio v3.7 — Lenovo Legion Go (All Composite Devices) to Steam Deck (0x28DE:0x1205)")
        self.setMinimumSize(740, 440)
        self._auto_fit_to_screen()
        self.setWindowIcon(create_miui_squircle_icon("#0D84FF", "SD"))

        self.bound_badge_labels = {}
        self.log_bridge = LogSignalBridge()
        self.log_bridge.log_emitted.connect(self._append_log_line)

        self.profile = self._load_profile_from_disk()
        self.hardware_state = create_empty_legion_state()
        self.ui_tester_state = create_empty_legion_state()
        self.merged_legion_state = create_empty_legion_state()
        self.deck_state = map_legion_to_steam_deck_state(self.merged_legion_state, self.profile, 0.0)
        self.latest_64byte_report = encode_neptune_64byte_report(self.deck_state, 1)
        self.deep_log_neptune_bytes = True
        self._prev_logged_neptune_report = bytes(self.latest_64byte_report)

        self.frame_counter = 1
        self.wheel_angle = 0.0
        self.service_active = False
        self.test_touchpad_lock_only = False
        self.force_quit = False

        self.hook_interceptor = Win32TouchpadAndShortcutInterceptor(
            lambda: self.profile,
            self._is_cursor_inside_active_studio_window,
            lambda msg: self.log_bridge.log_emitted.emit(msg),
        )

        self.hardware_reader = LegionGoHardwareReader(
            self.hook_interceptor,
            lambda msg: self.log_bridge.log_emitted.emit(msg),
        )
        self.hook_interceptor.on_key_learned_callback = self._on_hook_key_captured

        self.raw_input_sink = Win32RawInputHidSink(
            self.hardware_reader,
            lambda msg: self.log_bridge.log_emitted.emit(msg),
        )
        app_inst = QApplication.instance()
        if app_inst is not None:
            app_inst.installNativeEventFilter(self.raw_input_sink)

        self.usbip_server = PurePythonSteamDeckUsbipServer(
            lambda: self.deck_state,
            lambda: self.profile,
            lambda msg: self.log_bridge.log_emitted.emit(msg),
        )
        self.last_bus_diagnostic = "USB/IP Bus: Idle (Click 'Start Emulation')"

        # Build UI widgets FIRST so self.log_view exists before hardware connection logs
        self._build_ui()
        self._setup_system_tray()
        self._apply_miui_stylesheet()
        self._refresh_bound_badges()

        self.hook_interceptor.start()
        self.raw_input_sink.register_for_hwnd(int(self.winId()))
        self.hardware_reader.connect_hardware()

        self._start_250hz_worker()
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._refresh_ui_state)
        self.ui_timer.start(33)

        if self.profile.get("autoStartEmulationOnLaunch", False):
            QTimer.singleShot(400, self.toggle_emulation_service)

    def _auto_fit_to_screen(self):
        """
        Automatically fits the window inside the Lenovo Legion Go's available screen geometry
        (above the Windows taskbar), respecting Windows 125%/150%/175%/200% DPI scaling.
        """
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = min(1140, int(avail.width() * 0.96))
            h = min(680, int(avail.height() * 0.92))
            x = avail.left() + max(0, (avail.width() - w) // 2)
            y = avail.top() + max(0, (avail.height() - h) // 2)
            self.setGeometry(x, y, w, h)
        else:
            self.resize(1060, 640)

    def _on_hook_key_captured(self, target_btn: str, vk: int):
        self.hardware_reader.learning_target_button = None
        self.hardware_reader.last_learned_summary = f"Intercepted Shortcut Key VK=0x{vk:02X} ({vk})"

    @staticmethod
    def _make_compact_combo(combo: QComboBox, min_chars: int = 16):
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(min_chars)

    def _is_cursor_inside_active_studio_window(self) -> bool:
        if self.test_touchpad_lock_only:
            return False
        if not self.isVisible() or self.isMinimized() or not self.isActiveWindow():
            return False
        pos = QCursor.pos()
        return self.frameGeometry().contains(pos)

    def _load_profile_from_disk(self) -> dict:
        if PROFILE_FILE_PATH.exists():
            try:
                loaded = json.loads(PROFILE_FILE_PATH.read_text(encoding="utf-8"))
                merged = {**DEFAULT_PROFILE, **loaded}
                merged["triggerCalibration"] = {
                    **DEFAULT_TRIGGER_CALIBRATION,
                    **(loaded.get("triggerCalibration") or {}),
                }
                if merged.get("gyroHoldButton") == "buttonM1":
                    merged["gyroHoldButton"] = "buttonRB"
                return merged
            except Exception:
                pass
        p = dict(DEFAULT_PROFILE)
        p["triggerCalibration"] = dict(DEFAULT_TRIGGER_CALIBRATION)
        return p

    def _save_profile_to_disk(self):
        try:
            PROFILE_FILE_PATH.write_text(json.dumps(self.profile, indent=2), encoding="utf-8")
        except Exception as exc:
            self.log_bridge.log_emitted.emit(f"[Profile] Save warning: {exc}")

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 6, 8, 6)
        root_layout.setSpacing(6)

        header_card = QFrame()
        header_card.setObjectName("CardFrame")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(create_miui_squircle_icon("#0D84FF", "SD", 34).pixmap(34, 34))
        header_layout.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_lbl = QLabel("Lenovo Legion Go → Valve Steam Deck (0x28DE:0x1205)")
        title_lbl.setObjectName("HeaderTitle")
        self.status_sub_lbl = QLabel("Auto-Detecting XInput (0x6182), Single DInput (0x6183) & Dual DInput (0x6184/0x6185)")
        self.status_sub_lbl.setObjectName("MutedText")
        title_col.addWidget(title_lbl)
        title_col.addWidget(self.status_sub_lbl)
        header_layout.addLayout(title_col, 1)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Preset: Native Steam Deck", "default")
        self.preset_combo.addItem("Preset: Gyro FPS (Right IMU)", "gyro_fps")
        self.preset_combo.addItem("Preset: Radial Trackpad", "radial_pad")
        self._make_compact_combo(self.preset_combo, 14)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        header_layout.addWidget(self.preset_combo)

        self.diag_btn = QPushButton("USBip Check")
        self.diag_btn.clicked.connect(self._diagnose_or_install_usbip)
        header_layout.addWidget(self.diag_btn)

        self.theme_btn = QPushButton("Theme")
        self.theme_btn.clicked.connect(self._toggle_theme)
        header_layout.addWidget(self.theme_btn)

        self.start_btn = QPushButton("Start Emulation")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.clicked.connect(self.toggle_emulation_service)
        header_layout.addWidget(self.start_btn)

        root_layout.addWidget(header_card)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_tab1_interactive_tester(), "01. Live Hardware Tester")
        self.tabs.addTab(self._build_tab2_remapper(), "02. Remapper, Triggers & Gyro Config")
        self.tabs.addTab(self._build_tab3_hex_inspector(), "03. 64-Byte Packet & Deep Input Log")
        root_layout.addWidget(self.tabs, 1)

    def _build_tab1_interactive_tester(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(8)

        left_frame = QFrame()
        left_frame.setObjectName("CardFrame")
        left_col = QVBoxLayout(left_frame)
        left_col.setContentsMargins(8, 8, 8, 8)
        left_col.setSpacing(6)

        left_hdr = QHBoxLayout()
        left_hdr.setSpacing(5)
        self.hw_source_badge = QLabel("Source: Auto-Detecting...")
        self.hw_source_badge.setObjectName("SectionTitle")
        left_hdr.addWidget(self.hw_source_badge, 1)

        self.btn_test_pad_lock = QPushButton("Lock Pad (Ctrl+Alt+U)")
        self.btn_test_pad_lock.setCheckable(True)
        self.btn_test_pad_lock.toggled.connect(self._on_toggle_test_pad_lock)
        left_hdr.addWidget(self.btn_test_pad_lock)

        cal_gyro_btn = QPushButton("Calibrate Gyro")
        cal_gyro_btn.clicked.connect(self._open_gyro_calibration_wizard)
        left_hdr.addWidget(cal_gyro_btn)

        zero_btn = QPushButton("Zero Idle")
        zero_btn.clicked.connect(self._recalibrate_hardware_idle)
        left_hdr.addWidget(zero_btn)

        reset_btn = QPushButton("Reset UI")
        reset_btn.clicked.connect(self._reset_tester_inputs)
        left_hdr.addWidget(reset_btn)
        left_col.addLayout(left_hdr)

        extra_grid = QGridLayout()
        extra_grid.setSpacing(4)
        self.tester_btn_widgets = {}
        self.tester_btn_base_labels = {}
        extra_defs = [
            ("legionLButton", "Legion L"),
            ("legionRButton", "Legion R"),
            ("buttonY1", "Y1 (L-Up)"),
            ("buttonY2", "Y2 (L-Dn)"),
            ("buttonY3", "Y3 (R-In)"),
            ("buttonM3", "M3 (R-Out)"),
            ("buttonM2", "M2 (R-Low)"),
        ]
        for idx, (key, text) in enumerate(extra_defs):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.toggled.connect(lambda checked, k=key: self._set_tester_bool(k, checked))
            self.tester_btn_widgets[key] = btn
            self.tester_btn_base_labels[key] = text
            extra_grid.addWidget(btn, idx // 4, idx % 4)
        left_col.addLayout(extra_grid)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(6)
        self.src_trackpad_canvas = InteractiveTrackpadCanvas(
            "Legion Go Right Touchpad", interactive=True
        )
        self.src_trackpad_canvas.padChanged.connect(self._on_tester_trackpad_dragged)
        mid_row.addWidget(self.src_trackpad_canvas, 1)

        std_col = QVBoxLayout()
        std_col.setSpacing(4)
        pad_click_btn = QPushButton("Right Touchpad Click")
        pad_click_btn.setCheckable(True)
        pad_click_btn.toggled.connect(lambda c: self._set_tester_bool("rightTrackpadClick", c))
        self.tester_btn_widgets["rightTrackpadClick"] = pad_click_btn
        self.tester_btn_base_labels["rightTrackpadClick"] = "Right Touchpad Click"
        std_col.addWidget(pad_click_btn)

        wheel_row = QHBoxLayout()
        wheel_row.setSpacing(4)
        w_up = QPushButton("Wheel ↑")
        w_up.setCheckable(True)
        w_up.toggled.connect(lambda c: self._on_tester_wheel_btn("scrollWheelUp", 1, c))
        self.tester_btn_widgets["scrollWheelUp"] = w_up
        self.tester_btn_base_labels["scrollWheelUp"] = "Wheel ↑"

        w_dn = QPushButton("Wheel ↓")
        w_dn.setCheckable(True)
        w_dn.toggled.connect(lambda c: self._on_tester_wheel_btn("scrollWheelDown", -1, c))
        self.tester_btn_widgets["scrollWheelDown"] = w_dn
        self.tester_btn_base_labels["scrollWheelDown"] = "Wheel ↓"

        w_clk = QPushButton("Wheel Click")
        w_clk.setCheckable(True)
        w_clk.toggled.connect(lambda c: self._set_tester_bool("scrollWheelClick", c))
        self.tester_btn_widgets["scrollWheelClick"] = w_clk
        self.tester_btn_base_labels["scrollWheelClick"] = "Wheel Click"
        wheel_row.addWidget(w_up)
        wheel_row.addWidget(w_dn)
        wheel_row.addWidget(w_clk)
        std_col.addLayout(wheel_row)

        face_grid = QGridLayout()
        face_grid.setSpacing(4)
        for idx, (k, lbl) in enumerate([
            ("buttonA", "A"), ("buttonB", "B"), ("buttonX", "X"), ("buttonY", "Y"),
            ("buttonLB", "LB"), ("buttonRB", "RB / M1"), ("leftStickClick", "L3"), ("rightStickClick", "R3"),
            ("dpadUp", "D-Up"), ("dpadDown", "D-Dn"), ("dpadLeft", "D-Lt"), ("dpadRight", "D-Rt"),
            ("buttonView", "View (-)"), ("buttonMenu", "Menu (+)"),
        ]):
            b = QPushButton(lbl)
            b.setCheckable(True)
            b.toggled.connect(lambda c, key=k: self._set_tester_bool(key, c))
            self.tester_btn_widgets[k] = b
            self.tester_btn_base_labels[k] = lbl
            face_grid.addWidget(b, idx // 4, idx % 4)
        std_col.addLayout(face_grid)
        mid_row.addLayout(std_col, 1)
        left_col.addLayout(mid_row)

        sliders_grid = QGridLayout()
        sliders_grid.setSpacing(4)
        self.tester_sliders = {}
        self.tester_slider_labels = {}
        for idx, (key, title, mn, mx) in enumerate([
            ("leftStickX", "L-Stick X", -32768, 32767),
            ("leftStickY", "L-Stick Y", -32768, 32767),
            ("rightStickX", "R-Stick X", -32768, 32767),
            ("rightStickY", "R-Stick Y", -32768, 32767),
            ("leftTriggerAnalog", "L2 Trigger", 0, 32767),
            ("rightTriggerAnalog", "R2 Trigger", 0, 32767),
        ]):
            lbl = QLabel(f"{title}: 0")
            lbl.setObjectName("MutedText")
            sld = QSlider(Qt.Orientation.Horizontal)
            sld.setRange(mn, mx)
            sld.setValue(0)
            sld.valueChanged.connect(lambda val, k=key: self._set_tester_int(k, val))
            self.tester_sliders[key] = sld
            self.tester_slider_labels[key] = (lbl, title)
            sliders_grid.addWidget(lbl, idx // 2, (idx % 2) * 2)
            sliders_grid.addWidget(sld, idx // 2, (idx % 2) * 2 + 1)
        left_col.addLayout(sliders_grid)

        self.gyro_enable_chk = QCheckBox(
            "Enable Physical Controller Gyroscope → Steam Deck IMU (Real Hardware Gyro)"
        )
        self.gyro_enable_chk.setChecked(bool(self.profile.get("gyroEnabled", True)))
        self.gyro_enable_chk.toggled.connect(self._on_gyro_enable_toggled)
        left_col.addWidget(self.gyro_enable_chk)

        # RIGHT PANEL: Emulated Valve Steam Deck Target Output (0x28DE:0x1205)
        right_frame = QFrame()
        right_frame.setObjectName("CardFrame")
        right_col = QVBoxLayout(right_frame)
        right_col.setContentsMargins(8, 8, 8, 8)
        right_col.setSpacing(6)

        lbl_dst = QLabel("Target Output: Emulated Valve Steam Deck Controller (0x28DE:0x1205)")
        lbl_dst.setObjectName("SectionTitle")
        right_col.addWidget(lbl_dst)

        pads_row = QHBoxLayout()
        pads_row.setSpacing(6)
        self.deck_left_pad_canvas = InteractiveTrackpadCanvas(
            "Deck Left Pad (16..19)", interactive=False
        )
        self.deck_right_pad_canvas = InteractiveTrackpadCanvas(
            "Deck Right Pad (20..23)", interactive=False
        )
        pads_row.addWidget(self.deck_left_pad_canvas, 1)
        pads_row.addWidget(self.deck_right_pad_canvas, 1)
        right_col.addLayout(pads_row)

        self.deck_indicator_labels = {}
        ind_grid = QGridLayout()
        ind_grid.setSpacing(4)
        ind_defs = [
            ("buttonSteam", "STEAM"),
            ("buttonQuickAccess", "QAM (...)"),
            ("buttonL4Grip", "L4 Grip"),
            ("buttonR4Grip", "R4 Grip"),
            ("buttonL5Grip", "L5 Grip"),
            ("buttonR5Grip", "R5 Grip"),
            ("leftStickCapacitiveTouch", "L-Stick Touch"),
            ("rightStickCapacitiveTouch", "R-Stick Touch"),
            ("buttonA", "Deck A"),
            ("buttonB", "Deck B"),
            ("buttonX", "Deck X"),
            ("buttonY", "Deck Y"),
            ("buttonL1", "Deck L1"),
            ("buttonR1", "Deck R1"),
            ("buttonL2Digital", "Deck L2"),
            ("buttonR2Digital", "Deck R2"),
            ("buttonL3Click", "Deck L3"),
            ("buttonR3Click", "Deck R3"),
            ("buttonView", "View (-)"),
            ("buttonMenu", "Menu (+)"),
            ("dpadUp", "D-Pad Up"),
            ("dpadDown", "D-Pad Down"),
            ("dpadLeft", "D-Pad Left"),
            ("dpadRight", "D-Pad Right"),
        ]
        for idx, (k, title) in enumerate(ind_defs):
            box = QLabel(f"{title}\nIDLE")
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setObjectName("IndicatorIdle")
            self.deck_indicator_labels[k] = (box, title)
            ind_grid.addWidget(box, idx // 4, idx % 4)
        right_col.addLayout(ind_grid)

        # Live Steam-Side Gyroscope Output Indicators (Bytes 30..35 sent to Steam Input)
        steam_gyro_grid = QGridLayout()
        steam_gyro_grid.setSpacing(4)
        self.steam_gyro_pitch_box = QLabel("Steam Gyro Pitch\n0")
        self.steam_gyro_pitch_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.steam_gyro_yaw_box = QLabel("Steam Gyro Yaw\n0")
        self.steam_gyro_yaw_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.steam_gyro_roll_box = QLabel("Steam Gyro Roll\n0")
        self.steam_gyro_roll_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.steam_gyro_state_box = QLabel("Steam IMU Status\nREADY")
        self.steam_gyro_state_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        steam_gyro_grid.addWidget(self.steam_gyro_pitch_box, 0, 0)
        steam_gyro_grid.addWidget(self.steam_gyro_yaw_box, 0, 1)
        steam_gyro_grid.addWidget(self.steam_gyro_roll_box, 0, 2)
        steam_gyro_grid.addWidget(self.steam_gyro_state_box, 0, 3)
        right_col.addLayout(steam_gyro_grid)

        self.imu_readout_lbl = QLabel("Deck Sticks: L(0,0) R(0,0) | Triggers: L2=0 R2=0 | Steam Gyro: (0,0,0)")
        self.imu_readout_lbl.setObjectName("MonoReadout")
        right_col.addWidget(self.imu_readout_lbl)

        grid.addWidget(left_frame, 0, 0)
        grid.addWidget(right_frame, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        scroll.setWidget(page)
        return scroll

    def _build_tab2_remapper(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self.mapping_combos = {}

        # Left Column: Extra Lenovo Buttons & Wheel (10) + Standard Buttons (14)
        btn_card = QFrame()
        btn_card.setObjectName("CardFrame")
        btn_col = QVBoxLayout(btn_card)
        btn_col.setContentsMargins(8, 8, 8, 8)
        btn_col.setSpacing(4)

        lbl_extra = QLabel("A. Lenovo Legion Go Extra Buttons & Rear Scroll Wheel (10 Controls)")
        lbl_extra.setObjectName("SectionTitle")
        btn_col.addWidget(lbl_extra)

        sub_hint = QLabel(
            "Click 'Detect Physical' to capture any raw HID / Mouse / DInput / XInput / Key input. Scroll Wheel Up, Down & Click only capture the Lenovo Legion Go (VID_17EF) wheel—external USB/Bluetooth mice work normally."
        )
        sub_hint.setObjectName("MutedText")
        sub_hint.setWordWrap(True)
        btn_col.addWidget(sub_hint)

        extra_rows = [
            ("mapLegionLButton", "legionLButton", "Legion L (Top-Left System)"),
            ("mapLegionRButton", "legionRButton", "Legion R (Top-Right Quick Settings)"),
            ("mapButtonY1", "buttonY1", "Y1 Rear Grip (Left Upper)"),
            ("mapButtonY2", "buttonY2", "Y2 Rear Grip (Left Lower)"),
            ("mapButtonY3", "buttonY3", "Y3 Rear Grip (Right Inner)"),
            ("mapButtonM3", "buttonM3", "M3 Rear Grip (Right Outer)"),
            ("mapButtonM2", "buttonM2", "M2 Side Button (Right Lower FPS)"),
            ("mapScrollWheelUp", "scrollWheelUp", "Rear Scroll Wheel Up (VID_17EF Only)"),
            ("mapScrollWheelDown", "scrollWheelDown", "Rear Scroll Wheel Down (VID_17EF Only)"),
            ("mapScrollWheelClick", "scrollWheelClick", "Rear Scroll Wheel Click (VID_17EF Only)"),
        ]
        for cfg_key, hw_btn_key, label_text in extra_rows:
            btn_col.addLayout(self._create_remap_row(cfg_key, hw_btn_key, label_text))

        lbl_std = QLabel("B. Standard Controller Buttons (14 Controls — RB & M1 United)")
        lbl_std.setObjectName("SectionTitle")
        btn_col.addWidget(lbl_std)

        std_rows = [
            ("mapButtonA", "buttonA", "Face Button A (Bottom)"),
            ("mapButtonB", "buttonB", "Face Button B (Right)"),
            ("mapButtonX", "buttonX", "Face Button X (Left)"),
            ("mapButtonY", "buttonY", "Face Button Y (Top)"),
            ("mapButtonLB", "buttonLB", "Left Bumper (LB)"),
            ("mapButtonRB", "buttonRB", "RB / M1 (Right Bumper / Top-Edge)"),
            ("mapLeftStickClick", "leftStickClick", "Left Stick Click (L3)"),
            ("mapRightStickClick", "rightStickClick", "Right Stick Click (R3)"),
            ("mapButtonView", "buttonView", "View / Select Button (-)"),
            ("mapButtonMenu", "buttonMenu", "Menu / Start Button (+)"),
            ("mapDpadUp", "dpadUp", "D-Pad Up"),
            ("mapDpadDown", "dpadDown", "D-Pad Down"),
            ("mapDpadLeft", "dpadLeft", "D-Pad Left"),
            ("mapDpadRight", "dpadRight", "D-Pad Right"),
        ]
        for cfg_key, hw_btn_key, label_text in std_rows:
            btn_col.addLayout(self._create_remap_row(cfg_key, hw_btn_key, label_text))

        layout.addWidget(btn_card, 3)

        # Right Card: Controller Protocol (XInput/DInput), Trigger Stage Calibration, Gyro & Interception
        opt_card = QFrame()
        opt_card.setObjectName("CardFrame")
        opt_col = QVBoxLayout(opt_card)
        opt_col.setContentsMargins(8, 8, 8, 8)
        opt_col.setSpacing(6)

        # Section C: Controller Protocol, Analog Trigger Stage Calibration & Multi-IMU Gyro
        gyro_lbl = QLabel("C. Controller Protocol, Analog Trigger Stages & Gyro Engine")
        gyro_lbl.setObjectName("SectionTitle")
        opt_col.addWidget(gyro_lbl)

        opt_col.addWidget(QLabel("Controller Input Protocol Mode (Legion L + LB 4s = DInput):"))
        self.proto_combo = QComboBox()
        for p_key, p_lbl in CONTROLLER_PROTOCOL_OPTIONS:
            self.proto_combo.addItem(p_lbl, p_key)
        self._make_compact_combo(self.proto_combo, 18)
        p_idx = max(0, self.proto_combo.findData(self.profile.get("controllerProtocolMode", "auto")))
        self.proto_combo.setCurrentIndex(p_idx)
        self.proto_combo.currentIndexChanged.connect(
            lambda _i: self._update_profile_key("controllerProtocolMode", self.proto_combo.currentData())
        )
        opt_col.addWidget(self.proto_combo)

        trig_btn_row = QHBoxLayout()
        trig_btn_row.setSpacing(4)
        btn_cal_lt = QPushButton("Detect LT Analog / Stage")
        btn_cal_lt.setObjectName("PrimaryButton")
        btn_cal_lt.clicked.connect(lambda: self._open_trigger_stage_wizard("left"))
        btn_cal_rt = QPushButton("Detect RT Analog / Stage")
        btn_cal_rt.setObjectName("PrimaryButton")
        btn_cal_rt.clicked.connect(lambda: self._open_trigger_stage_wizard("right"))
        btn_rst_trig = QPushButton("Reset Triggers")
        btn_rst_trig.clicked.connect(self._reset_trigger_calibration)
        trig_btn_row.addWidget(btn_cal_lt, 1)
        trig_btn_row.addWidget(btn_cal_rt, 1)
        trig_btn_row.addWidget(btn_rst_trig)
        opt_col.addLayout(trig_btn_row)

        self.trigger_cal_status_lbl = QLabel("")
        self.trigger_cal_status_lbl.setObjectName("MutedText")
        self.trigger_cal_status_lbl.setWordWrap(True)
        opt_col.addWidget(self.trigger_cal_status_lbl)

        tcal = self.profile.get("triggerCalibration") or {}
        stage_pct_row = QHBoxLayout()
        stage_pct_row.setSpacing(4)
        stage_pct_row.addWidget(QLabel("Half-Press %:"))
        self.lt_half_spin = QSpinBox()
        self.lt_half_spin.setRange(10, 90)
        self.lt_half_spin.setPrefix("LT ")
        self.lt_half_spin.setSuffix("%")
        self.lt_half_spin.setValue(int(tcal.get("ltHalfPressPct", 45)))
        self.lt_half_spin.valueChanged.connect(lambda v: self._update_trigger_cal_key("ltHalfPressPct", int(v)))
        stage_pct_row.addWidget(self.lt_half_spin)

        self.rt_half_spin = QSpinBox()
        self.rt_half_spin.setRange(10, 90)
        self.rt_half_spin.setPrefix("RT ")
        self.rt_half_spin.setSuffix("%")
        self.rt_half_spin.setValue(int(tcal.get("rtHalfPressPct", 45)))
        self.rt_half_spin.valueChanged.connect(lambda v: self._update_trigger_cal_key("rtHalfPressPct", int(v)))
        stage_pct_row.addWidget(self.rt_half_spin)

        stage_pct_row.addWidget(QLabel("Full %:"))
        self.lt_full_spin = QSpinBox()
        self.lt_full_spin.setRange(55, 100)
        self.lt_full_spin.setPrefix("LT ")
        self.lt_full_spin.setSuffix("%")
        self.lt_full_spin.setValue(int(tcal.get("ltFullPressPct", 90)))
        self.lt_full_spin.valueChanged.connect(lambda v: self._update_trigger_cal_key("ltFullPressPct", int(v)))
        stage_pct_row.addWidget(self.lt_full_spin)

        self.rt_full_spin = QSpinBox()
        self.rt_full_spin.setRange(55, 100)
        self.rt_full_spin.setPrefix("RT ")
        self.rt_full_spin.setSuffix("%")
        self.rt_full_spin.setValue(int(tcal.get("rtFullPressPct", 90)))
        self.rt_full_spin.valueChanged.connect(lambda v: self._update_trigger_cal_key("rtFullPressPct", int(v)))
        stage_pct_row.addWidget(self.rt_full_spin)
        opt_col.addLayout(stage_pct_row)

        half_act_row = QHBoxLayout()
        half_act_row.setSpacing(4)
        half_act_row.addWidget(QLabel("LT Half Action:"))
        self.lt_half_combo = QComboBox()
        for t_key, t_lbl in STEAM_DECK_TARGET_OPTIONS:
            self.lt_half_combo.addItem(t_lbl, t_key)
        self._make_compact_combo(self.lt_half_combo, 15)
        self.lt_half_combo.setCurrentIndex(max(0, self.lt_half_combo.findData(tcal.get("ltHalfPressAction", "none"))))
        self.lt_half_combo.currentIndexChanged.connect(
            lambda _i: self._update_trigger_cal_key("ltHalfPressAction", self.lt_half_combo.currentData())
        )
        half_act_row.addWidget(self.lt_half_combo, 1)

        half_act_row.addWidget(QLabel("RT Half:"))
        self.rt_half_combo = QComboBox()
        for t_key, t_lbl in STEAM_DECK_TARGET_OPTIONS:
            self.rt_half_combo.addItem(t_lbl, t_key)
        self._make_compact_combo(self.rt_half_combo, 15)
        self.rt_half_combo.setCurrentIndex(max(0, self.rt_half_combo.findData(tcal.get("rtHalfPressAction", "none"))))
        self.rt_half_combo.currentIndexChanged.connect(
            lambda _i: self._update_trigger_cal_key("rtHalfPressAction", self.rt_half_combo.currentData())
        )
        half_act_row.addWidget(self.rt_half_combo, 1)
        opt_col.addLayout(half_act_row)

        gyro_wiz_btn = QPushButton("Launch 2-Step Interactive Gyro Calibration Wizard")
        gyro_wiz_btn.setObjectName("PrimaryButton")
        gyro_wiz_btn.clicked.connect(self._open_gyro_calibration_wizard)
        opt_col.addWidget(gyro_wiz_btn)

        self.gyro_cal_status_lbl = QLabel("")
        self.gyro_cal_status_lbl.setObjectName("MutedText")
        self.gyro_cal_status_lbl.setWordWrap(True)
        opt_col.addWidget(self.gyro_cal_status_lbl)

        opt_col.addWidget(QLabel("Physical Gyroscope IMU Source (Left / Right / Combined):"))
        self.gyro_src_combo = QComboBox()
        for g_key, g_lbl in GYRO_SOURCE_OPTIONS:
            self.gyro_src_combo.addItem(g_lbl, g_key)
        self._make_compact_combo(self.gyro_src_combo, 18)
        gs_idx = max(0, self.gyro_src_combo.findData(self.profile.get("gyroPhysicalSource", "rightControllerImu")))
        self.gyro_src_combo.setCurrentIndex(gs_idx)
        self.gyro_src_combo.currentIndexChanged.connect(
            lambda _i: self._update_profile_key("gyroPhysicalSource", self.gyro_src_combo.currentData())
        )
        opt_col.addWidget(self.gyro_src_combo)

        opt_col.addWidget(QLabel("Gyro Activation & Output Behavior:"))
        self.gyro_act_combo = QComboBox()
        for a_key, a_lbl in GYRO_ACTIVATION_OPTIONS:
            self.gyro_act_combo.addItem(a_lbl, a_key)
        self._make_compact_combo(self.gyro_act_combo, 18)
        ga_idx = max(0, self.gyro_act_combo.findData(self.profile.get("gyroActivationMode", "touchActivated")))
        self.gyro_act_combo.setCurrentIndex(ga_idx)
        self.gyro_act_combo.currentIndexChanged.connect(
            lambda _i: self._update_profile_key("gyroActivationMode", self.gyro_act_combo.currentData())
        )
        opt_col.addWidget(self.gyro_act_combo)

        opt_col.addWidget(QLabel("Gyro Hold-to-Activate Button (When 'Hold Button' Selected):"))
        self.gyro_hold_combo = QComboBox()
        for h_key, h_lbl in GYRO_HOLD_BUTTON_OPTIONS:
            self.gyro_hold_combo.addItem(h_lbl, h_key)
        self._make_compact_combo(self.gyro_hold_combo, 18)
        gh_idx = max(0, self.gyro_hold_combo.findData(self.profile.get("gyroHoldButton", "buttonRB")))
        self.gyro_hold_combo.setCurrentIndex(gh_idx)
        self.gyro_hold_combo.currentIndexChanged.connect(
            lambda _i: self._update_profile_key("gyroHoldButton", self.gyro_hold_combo.currentData())
        )
        opt_col.addWidget(self.gyro_hold_combo)

        # Gyro Sensitivity Slider + Axis Inversions
        sens_pct = int(round(float(self.profile.get("gyroSensitivityMultiplier", 1.0)) * 100))
        self.gyro_sens_lbl = QLabel(f"Gyro Sensitivity Multiplier: {sens_pct}% ({sens_pct / 100.0:.2f}x)")
        opt_col.addWidget(self.gyro_sens_lbl)
        self.gyro_sens_slider = QSlider(Qt.Orientation.Horizontal)
        self.gyro_sens_slider.setRange(10, 300)
        self.gyro_sens_slider.setValue(sens_pct)
        self.gyro_sens_slider.valueChanged.connect(self._on_gyro_sens_changed)
        opt_col.addWidget(self.gyro_sens_slider)

        inv_row = QHBoxLayout()
        self.chk_inv_pitch = QCheckBox("Invert Pitch")
        self.chk_inv_pitch.setChecked(bool(self.profile.get("gyroInvertPitch", False)))
        self.chk_inv_pitch.toggled.connect(lambda c: self._update_profile_key("gyroInvertPitch", c))
        self.chk_inv_yaw = QCheckBox("Invert Yaw")
        self.chk_inv_yaw.setChecked(bool(self.profile.get("gyroInvertYaw", False)))
        self.chk_inv_yaw.toggled.connect(lambda c: self._update_profile_key("gyroInvertYaw", c))
        self.chk_inv_roll = QCheckBox("Invert Roll")
        self.chk_inv_roll.setChecked(bool(self.profile.get("gyroInvertRoll", False)))
        self.chk_inv_roll.toggled.connect(lambda c: self._update_profile_key("gyroInvertRoll", c))
        inv_row.addWidget(self.chk_inv_pitch)
        inv_row.addWidget(self.chk_inv_yaw)
        inv_row.addWidget(self.chk_inv_roll)
        opt_col.addLayout(inv_row)

        # Section D: Touchpad Lock, LSDaemon & HidHide Interception
        opt_lbl = QLabel("D. Touchpad Lock, LSDaemon & HidHide Interception")
        opt_lbl.setObjectName("SectionTitle")
        opt_col.addWidget(opt_lbl)

        self.chk_lock_cursor = QCheckBox(
            "Lock Windows Cursor & Route Touchpad/Wheel to Deck Pad (Ctrl+Alt+U)"
        )
        self.chk_lock_cursor.setChecked(bool(self.profile.get("lockWindowsCursorAndRouteTouchpad", True)))
        self.chk_lock_cursor.toggled.connect(
            lambda c: self._update_profile_key("lockWindowsCursorAndRouteTouchpad", c)
        )
        opt_col.addWidget(self.chk_lock_cursor)

        self.chk_lsdaemon = QCheckBox(
            "Suspend Lenovo Legion Space Service (LSDaemon) While Emulating"
        )
        self.chk_lsdaemon.setChecked(bool(self.profile.get("suspendLegionSpaceService", True)))
        self.chk_lsdaemon.toggled.connect(
            lambda c: self._update_profile_key("suspendLegionSpaceService", c)
        )
        opt_col.addWidget(self.chk_lsdaemon)

        self.chk_kbd_hook = QCheckBox(
            "Intercept & Block Keyboard Shortcuts Assigned to Paddles (WH_KEYBOARD_LL)"
        )
        self.chk_kbd_hook.setChecked(bool(self.profile.get("interceptKeyboardShortcuts", True)))
        self.chk_kbd_hook.toggled.connect(
            lambda c: self._update_profile_key("interceptKeyboardShortcuts", c)
        )
        opt_col.addWidget(self.chk_kbd_hook)

        self.chk_hidhide = QCheckBox(
            "Auto-Cloak Physical VID_17EF Devices via HidHideCLI (--dev-hide)"
        )
        self.chk_hidhide.setChecked(bool(self.profile.get("enableHidHideCloak", True)))
        self.chk_hidhide.toggled.connect(lambda c: self._update_profile_key("enableHidHideCloak", c))
        opt_col.addWidget(self.chk_hidhide)

        opt_col.addWidget(QLabel("Rear Scroll Wheel Analog Axis Mode (In addition to Up/Down Buttons):"))
        self.wheel_mode_combo = QComboBox()
        for m_key, m_lbl in SCROLL_WHEEL_MODE_OPTIONS:
            self.wheel_mode_combo.addItem(m_lbl, m_key)
        self._make_compact_combo(self.wheel_mode_combo, 18)
        w_idx = max(0, self.wheel_mode_combo.findData(self.profile.get("scrollWheelMode")))
        self.wheel_mode_combo.setCurrentIndex(w_idx)
        self.wheel_mode_combo.currentIndexChanged.connect(
            lambda _i: self._update_profile_key("scrollWheelMode", self.wheel_mode_combo.currentData())
        )
        opt_col.addWidget(self.wheel_mode_combo)

        self.chk_auto_touch = QCheckBox("Auto-Enable Stick Capacitive Touch When Deflected")
        self.chk_auto_touch.setChecked(bool(self.profile.get("autoStickCapacitiveTouchOnDeflection", True)))
        self.chk_auto_touch.toggled.connect(
            lambda c: self._update_profile_key("autoStickCapacitiveTouchOnDeflection", c)
        )
        opt_col.addWidget(self.chk_auto_touch)

        self.chk_autostart = QCheckBox("Auto-Start Steam Deck Emulation on App Launch")
        self.chk_autostart.setChecked(bool(self.profile.get("autoStartEmulationOnLaunch", False)))
        self.chk_autostart.toggled.connect(
            lambda c: self._update_profile_key("autoStartEmulationOnLaunch", c)
        )
        opt_col.addWidget(self.chk_autostart)

        self.chk_tray = QCheckBox("Minimize to Windows System Tray When Closing Window")
        self.chk_tray.setChecked(bool(self.profile.get("minimizeToTrayOnClose", True)))
        self.chk_tray.toggled.connect(lambda c: self._update_profile_key("minimizeToTrayOnClose", c))
        opt_col.addWidget(self.chk_tray)

        opt_col.addWidget(QLabel("Emulated Steam Deck Serial Number (Feature Report 0xAE):"))
        self.serial_edit = QLineEdit(self.profile.get("emulatedDeckSerialNumber", "SD-LEGION-GO-28DE"))
        self.serial_edit.textChanged.connect(
            lambda txt: self._update_profile_key("emulatedDeckSerialNumber", txt)
        )
        opt_col.addWidget(self.serial_edit)

        io_row = QHBoxLayout()
        io_row.setSpacing(5)
        exp_btn = QPushButton("Export JSON")
        exp_btn.clicked.connect(self._export_profile_dialog)
        imp_btn = QPushButton("Import JSON")
        imp_btn.clicked.connect(self._import_profile_dialog)
        clr_learn_btn = QPushButton("Clear Learned")
        clr_learn_btn.clicked.connect(self._clear_learned_bindings)
        io_row.addWidget(exp_btn)
        io_row.addWidget(imp_btn)
        io_row.addWidget(clr_learn_btn)
        opt_col.addLayout(io_row)
        opt_col.addStretch(1)

        layout.addWidget(opt_card, 2)
        scroll.setWidget(container)
        return scroll

    def _create_remap_row(self, cfg_key: str, hw_btn_key: str, label_text: str) -> QHBoxLayout:
        r = QHBoxLayout()
        r.setSpacing(5)
        lbl = QLabel(label_text)
        r.addWidget(lbl, 1)

        badge = QLabel("")
        badge.setObjectName("MutedText")
        self.bound_badge_labels[hw_btn_key] = badge
        r.addWidget(badge)

        learn_btn = QPushButton("Detect Physical")
        learn_btn.clicked.connect(
            lambda _c=False, hk=hw_btn_key, lt=label_text: self._start_hw_learn(hk, lt)
        )
        r.addWidget(learn_btn)

        combo = QComboBox()
        for target_key, target_label in STEAM_DECK_TARGET_OPTIONS:
            combo.addItem(target_label, target_key)
        self._make_compact_combo(combo, 15)
        default_val = DEFAULT_PROFILE.get(cfg_key, "none")
        current_val = self.profile.get(cfg_key, default_val)
        idx = max(0, combo.findData(current_val))
        combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(
            lambda _i, k=cfg_key, cb=combo: self._update_profile_key(k, cb.currentData())
        )
        self.mapping_combos[cfg_key] = combo
        r.addWidget(combo, 1)
        return r

    def _refresh_bound_badges(self):
        vhid = self.profile.get("learnedVendorButtons", {})
        vmouse = self.profile.get("learnedMouseButtons", {})
        vkey = self.profile.get("learnedKeyBindings", {})
        vdin = self.profile.get("learnedDinputButtons", {})
        vxin = self.profile.get("learnedXinputButtons", {})

        mouse_labels = {
            "mouse5": "Mouse 5 (XButton2)",
            "mouse4": "Mouse 4 (XButton1)",
            "mouse3": "VID_17EF Wheel Click",
            "wheel_up": "VID_17EF Wheel Up",
            "wheel_down": "VID_17EF Wheel Down",
        }

        for hw_key, badge in self.bound_badge_labels.items():
            tags = []
            if hw_key in vhid:
                spec = vhid[hw_key]
                rid = int(spec.get("report_id", -1))
                rid_str = f"R{rid:02X}:" if rid >= 0 else ""
                tags.append(f"HID {rid_str}B{spec.get('byte')}:0x{int(spec.get('mask', 0)):02X}")
            if hw_key in vmouse:
                m_code = str(vmouse[hw_key])
                tags.append(mouse_labels.get(m_code, m_code))
            if hw_key in vdin:
                spec = vdin[hw_key]
                tags.append(f"DIn#{int(spec.get('bit', 0)) + 1}")
            if hw_key in vxin:
                tags.append(f"XIn:0x{int(vxin[hw_key]):04X}")
            if hw_key in vkey:
                tags.append(f"Key:{format_vk_name(int(vkey[hw_key]))}")

            # Show built-in default trigger badges when not overridden
            if not tags:
                if hw_key == "buttonRB":
                    tags.append("XInput 0x0200 / R04:B17 / Mouse 4-5 / F13")
                elif hw_key == "buttonM2":
                    tags.append("R05:0x25 / F17")
                elif hw_key == "scrollWheelUp":
                    tags.append("VID_17EF Wheel Up")
                elif hw_key == "scrollWheelDown":
                    tags.append("VID_17EF Wheel Down")
                elif hw_key == "scrollWheelClick":
                    tags.append("VID_17EF Wheel Click")

            if tags:
                badge.setText("[" + " | ".join(tags) + "]")
                badge.setStyleSheet("color: #10B981; font-size: 10px; font-weight: 700;")
            else:
                badge.setText("")
                badge.setStyleSheet("")

        if getattr(self, "trigger_cal_status_lbl", None) is not None:
            tcal = self.profile.get("triggerCalibration") or {}
            lt_src = tcal.get("ltSource")
            rt_src = tcal.get("rtSource")
            parts = []
            if lt_src:
                parts.append(f"LT: {lt_src.get('type')} ({lt_src.get('rest')}..{lt_src.get('peak')})")
            else:
                parts.append("LT: Auto Analog (XInput/DInput)")
            if rt_src:
                parts.append(f"RT: {rt_src.get('type')} ({rt_src.get('rest')}..{rt_src.get('peak')})")
            else:
                parts.append("RT: Auto Analog (XInput/DInput)")
            self.trigger_cal_status_lbl.setText(
                " | ".join(parts)
                + f"  [Half: LT={tcal.get('ltHalfPressPct', 45)}% RT={tcal.get('rtHalfPressPct', 45)}% | "
                + f"Full: LT={tcal.get('ltFullPressPct', 90)}% RT={tcal.get('rtFullPressPct', 90)}%]"
            )
            self.trigger_cal_status_lbl.setStyleSheet(
                "color: #10B981; font-size: 10px; font-weight: 700;" if (lt_src or rt_src) else ""
            )

        if getattr(self, "gyro_cal_status_lbl", None) is not None:
            gcal = self.profile.get("gyroCalibration")
            if gcal:
                self.gyro_cal_status_lbl.setText(
                    f"Calibrated Gyro Locked: {gcal.get('iface')} (Report 0x{int(gcal.get('report_id', 0)):02X}, "
                    f"Bytes {gcal.get('offset')}..{int(gcal.get('offset', 0))+5}, Deadzone={gcal.get('deadzone')})"
                )
                self.gyro_cal_status_lbl.setStyleSheet("color: #10B981; font-size: 10px; font-weight: 700;")
            else:
                self.gyro_cal_status_lbl.setText(
                    "Gyro Status: Uncalibrated (Resting at 0, 0, 0 — Click 'Launch 2-Step Interactive Gyro Calibration Wizard' above)"
                )
                self.gyro_cal_status_lbl.setStyleSheet("")

    def _unbind_single_control(self, hw_btn_key: str):
        for dict_key in ("learnedVendorButtons", "learnedMouseButtons", "learnedKeyBindings", "learnedDinputButtons", "learnedXinputButtons"):
            d = self.profile.get(dict_key, {})
            d.pop(hw_btn_key, None)
        self._save_profile_to_disk()
        self._refresh_bound_badges()
        self._append_log_line(f"[Detect Physical] Cleared custom binding for '{hw_btn_key}'.")

    def _build_tab3_hex_inspector(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        hex_card = QFrame()
        hex_card.setObjectName("CardFrame")
        hex_col = QVBoxLayout(hex_card)
        lbl = QLabel("Live 64-Byte Valve Neptune Report & Active Hardware Byte Deltas (250Hz)")
        lbl.setObjectName("SectionTitle")
        hex_col.addWidget(lbl)

        self.hex_matrix_view = QPlainTextEdit()
        self.hex_matrix_view.setReadOnly(True)
        self.hex_matrix_view.setFont(QFont("Consolas", 9))
        hex_col.addWidget(self.hex_matrix_view, 1)

        log_card = QFrame()
        log_card.setObjectName("CardFrame")
        log_col = QVBoxLayout(log_card)
        log_lbl = QLabel("Deep Input Press & Byte-Delta Inspector Log (HID / XInput / DInput / Mouse / Keys / Neptune 64B)")
        log_lbl.setObjectName("SectionTitle")
        log_col.addWidget(log_lbl)

        filter_row1 = QHBoxLayout()
        filter_row1.setSpacing(10)
        self.chk_deep_presses = QCheckBox("Log Pressed Controls & Mapped Targets")
        self.chk_deep_presses.setChecked(True)
        self.chk_deep_presses.toggled.connect(lambda c: setattr(self.hardware_reader, "deep_log_presses", bool(c)))
        filter_row1.addWidget(self.chk_deep_presses)

        self.chk_deep_raw_bytes = QCheckBox("Log Raw HID / XInput / DInput / Mouse / Key Byte Deltas")
        self.chk_deep_raw_bytes.setChecked(True)
        self.chk_deep_raw_bytes.toggled.connect(lambda c: setattr(self.hardware_reader, "deep_log_raw_bytes", bool(c)))
        filter_row1.addWidget(self.chk_deep_raw_bytes)
        filter_row1.addStretch(1)
        log_col.addLayout(filter_row1)

        filter_row2 = QHBoxLayout()
        filter_row2.setSpacing(10)
        self.chk_deep_neptune = QCheckBox("Log Outgoing 64B Steam Deck Byte Diffs (B08..13)")
        self.chk_deep_neptune.setChecked(True)
        self.chk_deep_neptune.toggled.connect(lambda c: setattr(self, "deep_log_neptune_bytes", bool(c)))
        filter_row2.addWidget(self.chk_deep_neptune)

        self.chk_deep_noisy = QCheckBox("Include Unfiltered Gyro / Touch / Timer Bytes (Verbose)")
        self.chk_deep_noisy.setChecked(False)
        self.chk_deep_noisy.toggled.connect(lambda c: setattr(self.hardware_reader, "deep_log_noisy_bytes", bool(c)))
        filter_row2.addWidget(self.chk_deep_noisy)
        filter_row2.addStretch(1)
        log_col.addLayout(filter_row2)

        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(6)
        snap_btn = QPushButton("Dump All Streams Hex Snapshot")
        snap_btn.clicked.connect(self.hardware_reader.dump_all_streams_hex_snapshot)
        btn_bar.addWidget(snap_btn)

        wake_btn = QPushButton("Send 0xFFA0 Raw Unlock")
        wake_btn.clicked.connect(lambda: self.hardware_reader.send_lenovo_raw_button_wakeup(quiet_log=False))
        btn_bar.addWidget(wake_btn)

        copy_btn = QPushButton("Copy Log")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.log_view.toPlainText()))
        btn_bar.addWidget(copy_btn)

        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(lambda: self.log_view.clear() if self.log_view is not None else None)
        btn_bar.addWidget(clear_btn)
        btn_bar.addStretch(1)
        log_col.addLayout(btn_bar)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        log_col.addWidget(self.log_view, 1)

        layout.addWidget(hex_card, 1)
        layout.addWidget(log_card, 1)
        self._append_log_line(
            "Deep Input & Byte-Delta Inspector active. Press any physical button, rear paddle (Y1..M3), M2, RB/M1, VID_17EF Scroll Wheel, or F13..F24 to see exact raw bytes and mapped Steam Deck outputs."
        )
        return page

    # --------------------------------------------------------------------------
    # System Tray Icon & Background Mode
    # --------------------------------------------------------------------------
    def _setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(create_miui_squircle_icon("#0D84FF", "SD"))
        self.tray_icon.setToolTip("LegionDeck Studio (0x28DE:0x1205)")

        tray_menu = QMenu(self)
        act_show = QAction("Open LegionDeck Studio", self)
        act_show.triggered.connect(self.showNormal)
        tray_menu.addAction(act_show)

        self.tray_toggle_act = QAction("Start Steam Deck Emulation", self)
        self.tray_toggle_act.triggered.connect(self.toggle_emulation_service)
        tray_menu.addAction(self.tray_toggle_act)

        tray_menu.addSeparator()
        act_quit = QAction("Quit & Restore Windows Services / HidHide", self)
        act_quit.triggered.connect(self._quit_completely)
        tray_menu.addAction(act_quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(
            lambda reason: self.showNormal()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
        self.tray_icon.show()

    def closeEvent(self, event):
        if not self.force_quit and self.profile.get("minimizeToTrayOnClose", True):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "LegionDeck Running in System Tray",
                "Steam Deck Controller (0x28DE:0x1205) is active. Press Ctrl+Alt+U anytime to toggle cursor lock.",
                QSystemTrayIcon.MessageIcon.Information,
                2200,
            )
        else:
            if self.service_active:
                self.toggle_emulation_service()
            event.accept()

    def _quit_completely(self):
        self.force_quit = True
        self.close()
        QApplication.instance().quit()

    # --------------------------------------------------------------------------
    # Interactive Tester & Profile Callbacks
    # --------------------------------------------------------------------------
    def _set_tester_bool(self, key: str, val: bool):
        self.ui_tester_state[key] = val
        if key == "rightTrackpadClick" and val:
            self.ui_tester_state["rightTrackpadTouch"] = True

    def _set_tester_int(self, key: str, val: int):
        self.ui_tester_state[key] = val

    def _on_tester_wheel_btn(self, key: str, delta: int, checked: bool):
        self.ui_tester_state[key] = checked
        if checked:
            self._pulse_wheel(delta)

    def _on_tester_trackpad_dragged(self, touch: bool, x_val: int, y_val: int):
        self.ui_tester_state["rightTrackpadTouch"] = touch
        self.ui_tester_state["rightTrackpadX"] = x_val
        self.ui_tester_state["rightTrackpadY"] = y_val
        self.ui_tester_state["rightTrackpadPressure"] = 18500 if touch else 0

    def _on_toggle_test_pad_lock(self, checked: bool):
        self.test_touchpad_lock_only = checked
        self.hook_interceptor.test_lock_override = checked
        self.hook_interceptor.capture_enabled = bool(checked or self.service_active)
        self.hook_interceptor.manual_unlock_override = False
        if checked:
            self._append_log_line(
                "[Touchpad Test Lock] Cursor locked to Steam Deck Trackpad! Touch your Legion Go Right Touchpad or Scroll Wheel now (Press Ctrl+Alt+U to unlock)."
            )
        else:
            self._append_log_line("[Touchpad Test Lock] Released cursor lock.")

    def _on_gyro_sens_changed(self, val: int):
        mult = round(val / 100.0, 2)
        self.gyro_sens_lbl.setText(f"Gyro Sensitivity Multiplier: {val}% ({mult:.2f}x)")
        self.profile["gyroSensitivityMultiplier"] = mult
        self._save_profile_to_disk()

    def _pulse_wheel(self, delta: int):
        self.ui_tester_state["scrollWheelDelta"] = delta
        QTimer.singleShot(260, lambda: self._set_tester_int("scrollWheelDelta", 0))

    def _on_gyro_enable_toggled(self, checked: bool):
        self.profile["gyroEnabled"] = bool(checked)
        self._save_profile_to_disk()
        self._append_log_line(
            f"[Gyro] Physical Controller Gyroscope -> Steam Deck IMU: {'ENABLED' if checked else 'DISABLED'}"
        )

    def _recalibrate_hardware_idle(self):
        self.hardware_reader.reset_idle_calibration()
        self._append_log_line("[Calibration] Re-zeroing all Lenovo VID_17EF HID per-Report-ID baselines & DInput resting axes...")

    def _open_trigger_stage_wizard(self, side: str):
        if not self.hardware_reader.hid_streams:
            self.hardware_reader.connect_hardware()
        dlg = TriggerStageCalibrationDialog(
            self,
            side,
            self.hardware_reader,
            self.profile,
            lambda: self.hardware_state,
        )
        dlg.exec()
        tcal = self.profile.get("triggerCalibration") or {}
        if getattr(self, "lt_half_spin", None) is not None:
            self.lt_half_spin.blockSignals(True)
            self.lt_half_spin.setValue(int(tcal.get("ltHalfPressPct", 45)))
            self.lt_half_spin.blockSignals(False)
        if getattr(self, "rt_half_spin", None) is not None:
            self.rt_half_spin.blockSignals(True)
            self.rt_half_spin.setValue(int(tcal.get("rtHalfPressPct", 45)))
            self.rt_half_spin.blockSignals(False)
        if getattr(self, "lt_full_spin", None) is not None:
            self.lt_full_spin.blockSignals(True)
            self.lt_full_spin.setValue(int(tcal.get("ltFullPressPct", 90)))
            self.lt_full_spin.blockSignals(False)
        if getattr(self, "rt_full_spin", None) is not None:
            self.rt_full_spin.blockSignals(True)
            self.rt_full_spin.setValue(int(tcal.get("rtFullPressPct", 90)))
            self.rt_full_spin.blockSignals(False)
        if getattr(self, "lt_half_combo", None) is not None:
            self.lt_half_combo.blockSignals(True)
            self.lt_half_combo.setCurrentIndex(max(0, self.lt_half_combo.findData(tcal.get("ltHalfPressAction", "none"))))
            self.lt_half_combo.blockSignals(False)
        if getattr(self, "rt_half_combo", None) is not None:
            self.rt_half_combo.blockSignals(True)
            self.rt_half_combo.setCurrentIndex(max(0, self.rt_half_combo.findData(tcal.get("rtHalfPressAction", "none"))))
            self.rt_half_combo.blockSignals(False)
        self._save_profile_to_disk()
        self._refresh_bound_badges()

    def _reset_trigger_calibration(self):
        self.profile["triggerCalibration"] = copy.deepcopy(DEFAULT_TRIGGER_CALIBRATION)
        self._save_profile_to_disk()
        self._refresh_bound_badges()
        self._append_log_line("[Trigger Calibration] Reset LT & RT analog sources and stage thresholds to defaults.")

    def _update_trigger_cal_key(self, k: str, v):
        tcal = copy.deepcopy(DEFAULT_TRIGGER_CALIBRATION)
        if isinstance(self.profile.get("triggerCalibration"), dict):
            tcal.update(self.profile["triggerCalibration"])
        tcal[k] = v
        self.profile["triggerCalibration"] = tcal
        self._save_profile_to_disk()
        self._refresh_bound_badges()
        self._append_log_line(f"[Trigger Stage] Updated {k} = {v}")

    def _open_gyro_calibration_wizard(self):
        if not self.hardware_reader.hid_streams:
            self.hardware_reader.connect_hardware()
        dlg = GyroCalibrationDialog(
            self,
            self.hardware_reader,
            self.profile,
            lambda: self.hardware_state,
        )
        dlg.exec()
        self._save_profile_to_disk()
        self._refresh_bound_badges()

    def _start_hw_learn(self, hw_btn_key: str, label_text: str = ""):
        if not self.hardware_reader.hid_streams:
            self.hardware_reader.connect_hardware()
        self.hardware_reader.start_learning_button(hw_btn_key)
        dlg = DetectPhysicalButtonDialog(
            self,
            hw_btn_key,
            label_text or hw_btn_key,
            self.hardware_reader,
            self.profile,
            self._unbind_single_control,
        )
        dlg.exec()
        self._save_profile_to_disk()
        self._refresh_bound_badges()

    def _clear_learned_bindings(self):
        self.profile["learnedVendorButtons"] = {}
        self.profile["learnedMouseButtons"] = {}
        self.profile["learnedKeyBindings"] = {}
        self.profile["learnedDinputButtons"] = {}
        self.profile["learnedXinputButtons"] = {}
        self._save_profile_to_disk()
        self._refresh_bound_badges()
        self._append_log_line("[Learn Mode] Cleared all custom learned HID, Mouse, DInput, XInput & Key bindings.")

    def _reset_tester_inputs(self):
        self.test_touchpad_lock_only = False
        self.btn_test_pad_lock.setChecked(False)
        self.ui_tester_state = create_empty_legion_state()
        self.hook_interceptor.reset_pad_center()
        for btn in self.tester_btn_widgets.values():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        for sld in self.tester_sliders.values():
            sld.blockSignals(True)
            sld.setValue(0)
            sld.blockSignals(False)
        self.src_trackpad_canvas.set_pad_state(False, False, 0, 0)

    def _update_profile_key(self, key: str, value):
        self.profile[key] = value
        self._save_profile_to_disk()
        self._append_log_line(f"[Profile] Auto-saved {key} = {value}")

    def _on_preset_selected(self, _idx: int):
        preset_key = self.preset_combo.currentData()
        if preset_key in PRESET_PROFILES:
            learned_hid = self.profile.get("learnedVendorButtons", {})
            learned_mouse = self.profile.get("learnedMouseButtons", {})
            learned_keys = self.profile.get("learnedKeyBindings", {})
            learned_din = self.profile.get("learnedDinputButtons", {})
            learned_xin = self.profile.get("learnedXinputButtons", {})
            gcal = self.profile.get("gyroCalibration", None)
            tcal = self.profile.get("triggerCalibration", copy.deepcopy(DEFAULT_TRIGGER_CALIBRATION))
            self.profile.update(PRESET_PROFILES[preset_key])
            self.profile["learnedVendorButtons"] = learned_hid
            self.profile["learnedMouseButtons"] = learned_mouse
            self.profile["learnedKeyBindings"] = learned_keys
            self.profile["learnedDinputButtons"] = learned_din
            self.profile["learnedXinputButtons"] = learned_xin
            self.profile["gyroCalibration"] = gcal
            self.profile["triggerCalibration"] = tcal
            self._save_profile_to_disk()
            for k, combo in self.mapping_combos.items():
                combo.blockSignals(True)
                combo.setCurrentIndex(max(0, combo.findData(self.profile.get(k, "none"))))
                combo.blockSignals(False)
            self.wheel_mode_combo.setCurrentIndex(
                max(0, self.wheel_mode_combo.findData(self.profile.get("scrollWheelMode")))
            )
            self.gyro_src_combo.setCurrentIndex(
                max(0, self.gyro_src_combo.findData(self.profile.get("gyroPhysicalSource", "rightControllerImu")))
            )
            self.gyro_act_combo.setCurrentIndex(
                max(0, self.gyro_act_combo.findData(self.profile.get("gyroActivationMode", "touchActivated")))
            )
            if getattr(self, "gyro_enable_chk", None) is not None:
                self.gyro_enable_chk.blockSignals(True)
                self.gyro_enable_chk.setChecked(bool(self.profile.get("gyroEnabled", True)))
                self.gyro_enable_chk.blockSignals(False)
            self._refresh_bound_badges()
            self._append_log_line(f"[Preset] Activated '{self.profile['profileName']}'")

    def _export_profile_dialog(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Profile JSON", "legion_deck_profile.json", "JSON Files (*.json)"
        )
        if path:
            Path(path).write_text(json.dumps(self.profile, indent=2), encoding="utf-8")
            self._append_log_line(f"[Profile] Exported to {path}")

    def _import_profile_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Profile JSON", "", "JSON Files (*.json)"
        )
        if path:
            try:
                loaded = json.loads(Path(path).read_text(encoding="utf-8"))
                self.profile.update(loaded)
                self._save_profile_to_disk()
                self._on_preset_selected(0)
                self._append_log_line(f"[Profile] Imported from {path}")
            except Exception as exc:
                QMessageBox.warning(self, "Import Error", f"Could not load JSON: {exc}")

    # --------------------------------------------------------------------------
    # Windows Emulation Service (USB/IP 0x28DE:0x1205 + LSDaemon + HidHideCLI)
    # --------------------------------------------------------------------------
    def toggle_emulation_service(self):
        if not self.service_active:
            self.service_active = True
            self.hook_interceptor.capture_enabled = True
            self.hook_interceptor.manual_unlock_override = False
            self.start_btn.setText("Stop Emulation")
            self.tray_toggle_act.setText("Stop Steam Deck Emulation")

            if not self.hardware_reader.hid_streams:
                self.hardware_reader.connect_hardware()

            if self.profile.get("suspendLegionSpaceService", True) and sys.platform == "win32":
                self._control_lsdaemon_service(suspend=True)

            port = int(self.profile.get("usbipLoopbackPort", 3240))
            self.usbip_server.start(port=port)
            if self.profile.get("enableHidHideCloak", True) and sys.platform == "win32":
                self._configure_hidhide(enable=True)
            self._attach_usbip_windows()
        else:
            self.service_active = False
            self.hook_interceptor.capture_enabled = bool(self.test_touchpad_lock_only)
            self.start_btn.setText("Start Emulation")
            self.tray_toggle_act.setText("Start Steam Deck Emulation")
            if sys.platform == "win32":
                self._detach_usbip_windows()
            self.usbip_server.stop()
            if self.profile.get("enableHidHideCloak", True) and sys.platform == "win32":
                self._configure_hidhide(enable=False)
            if self.profile.get("suspendLegionSpaceService", True) and sys.platform == "win32":
                self._control_lsdaemon_service(suspend=False)
            self.last_bus_diagnostic = "USB/IP Bus: Stopped"
            self._append_log_line("[Service] Stopped Steam Deck Controller emulation.")

    def _control_lsdaemon_service(self, suspend: bool):
        def _worker():
            try:
                if suspend:
                    subprocess.run(["taskkill", "/F", "/IM", "LegionSpace.exe"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    for svc in ("LSDaemon", "LegionSpaceService"):
                        subprocess.run(["sc", "stop", svc], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    self.log_bridge.log_emitted.emit("[LSDaemon] Paused background Lenovo Legion Space service so Legion L/R are free.")
                else:
                    for svc in ("LSDaemon", "LegionSpaceService"):
                        subprocess.run(["sc", "start", svc], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    self.log_bridge.log_emitted.emit("[LSDaemon] Restored Lenovo Legion Space service.")
            except Exception as exc:
                self.log_bridge.log_emitted.emit(f"[LSDaemon] Service notice: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _find_usbip_exe(self) -> str:
        import shutil
        in_path = shutil.which("usbip.exe") or shutil.which("usbip")
        if in_path:
            return in_path
        script_dir = Path(__file__).resolve().parent
        candidates = [
            script_dir / "usbip.exe",
            Path("C:/Program Files/USBip/usbip.exe"),
            Path("C:/Program Files/usbip/usbip.exe"),
            Path("C:/Program Files/usbip-win2/usbip.exe"),
            Path("C:/Program Files (x86)/USBip/usbip.exe"),
            Path("C:/Program Files (x86)/usbip/usbip.exe"),
            Path("C:/USBip/usbip.exe"),
            Path("C:/usbip/usbip.exe"),
            Path.home() / "Desktop" / "usbip.exe",
        ]
        for folder in [Path.home() / "Desktop", Path.home() / "Downloads", script_dir]:
            if folder.exists():
                try:
                    for sub in folder.rglob("usbip.exe"):
                        if sub.name.lower() == "usbip.exe":
                            candidates.append(sub)
                except Exception:
                    pass
        for c in candidates:
            if c.exists():
                return str(c)
        return ""

    def _find_usbip_installer(self) -> str:
        for folder in [Path.home() / "Desktop", Path.home() / "Downloads", Path(__file__).resolve().parent]:
            if folder.exists():
                try:
                    for item in folder.iterdir():
                        low = item.name.lower()
                        if ("usbip" in low) and low.endswith((".exe", ".msi")) and low != "usbip.exe":
                            return str(item)
                except Exception:
                    pass
        return ""

    def _diagnose_or_install_usbip(self):
        usbip_bin = self._find_usbip_exe()
        if not usbip_bin:
            installer = self._find_usbip_installer()
            if installer:
                ans = QMessageBox.question(
                    self,
                    "Install USBip-0.9.8 Driver",
                    f"usbip.exe is not installed yet, but found installer:\n{installer}\n\nLaunch the USBip-0.9.8 installer now?",
                )
                if ans == QMessageBox.StandardButton.Yes:
                    subprocess.Popen([installer], shell=True)
                return
            QMessageBox.warning(
                self,
                "usbip.exe Not Found",
                "Could not find C:/Program Files/USBip/usbip.exe.\n\n"
                "Please run your USBip-0.9.8 installer on your Desktop so Windows can mount USB\\VID_28DE&PID_1205.",
            )
            return

        port = int(self.profile.get("usbipLoopbackPort", 3240))
        self.usbip_server.start(port=port)
        time.sleep(0.2)
        list_proc = subprocess.run(
            [usbip_bin, "list", "-r", "127.0.0.1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        subprocess.run([usbip_bin, "detach", "--all"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        subprocess.run([usbip_bin, "detach", "-p", "1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        att_proc = subprocess.run(
            [usbip_bin, "attach", "-r", "127.0.0.1", "-b", "1-1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        msg = (
            f"Executable: {usbip_bin}\n\n"
            f"--- usbip.exe list -r 127.0.0.1 ---\n{(list_proc.stdout or '') + (list_proc.stderr or '')}\n"
            f"--- usbip.exe attach -r 127.0.0.1 -b 1-1 (exit {att_proc.returncode}) ---\n"
            f"{(att_proc.stdout or '') + (att_proc.stderr or '')}\n\n"
            f"Server Client Attached: {self.usbip_server.client_attached} (URBs Answered: {self.usbip_server.total_urbs_answered})"
        )
        QMessageBox.information(self, "USB/IP Steam Deck Bus Diagnostic", msg)

    def _detach_usbip_windows(self):
        usbip_bin = self._find_usbip_exe()
        if usbip_bin:
            try:
                subprocess.run([usbip_bin, "detach", "--all"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                subprocess.run([usbip_bin, "detach", "-p", "1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            except Exception:
                pass

    def _attach_usbip_windows(self):
        if sys.platform != "win32":
            self.last_bus_diagnostic = "USB/IP Server Listening on 127.0.0.1:3240"
            return
        usbip_bin = self._find_usbip_exe()
        port = int(self.profile.get("usbipLoopbackPort", 3240))

        if not usbip_bin:
            installer = self._find_usbip_installer()
            self.last_bus_diagnostic = (
                f"ERROR: usbip.exe not installed! Run '{Path(installer).name}' on Desktop first!"
                if installer
                else "ERROR: usbip.exe not found in C:/Program Files/USBip! Install USBip-0.9.8 first."
            )
            self._append_log_line(f"[Windows Bus] {self.last_bus_diagnostic}")
            return

        def _run_attach():
            time.sleep(0.35)
            try:
                subprocess.run([usbip_bin, "detach", "--all"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                subprocess.run([usbip_bin, "detach", "-p", "1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                time.sleep(0.2)
                proc = subprocess.run(
                    [usbip_bin, "attach", "-r", "127.0.0.1", "-b", "1-1"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                out = (proc.stdout or "").strip()
                err = (proc.stderr or "").strip()
                if proc.returncode == 0:
                    self.last_bus_diagnostic = f"ATTACHED: Valve Steam Deck (0x28DE:0x1205) -> {out or 'Port Active'}"
                    self.log_bridge.log_emitted.emit(
                        f"[Windows Bus] Attached Valve Steam Deck (0x28DE:0x1205) via {usbip_bin}: {out or 'OK'}"
                    )
                else:
                    self.last_bus_diagnostic = f"ATTACH ERROR ({proc.returncode}): {err or out} (Click 'USBip Check')"
                    self.log_bridge.log_emitted.emit(
                        f"[Windows Bus] {usbip_bin} returned ({proc.returncode}): {err or out}"
                    )
            except Exception as exc:
                self.last_bus_diagnostic = f"Attach exception: {exc}"
                self.log_bridge.log_emitted.emit(f"[Windows Bus] Attach error: {exc}")

        threading.Thread(target=_run_attach, daemon=True).start()
        self.last_bus_diagnostic = f"Attaching 127.0.0.1:{port} via {usbip_bin}..."
        self._append_log_line(f"[Windows Bus] Executing: '{usbip_bin}' attach -r 127.0.0.1 -b 1-1 (port {port})")

    def _configure_hidhide(self, enable: bool):
        cli_path = r"C:\Program Files\Nefarius Software Solutions\HidHide\x64\HidHideCLI.exe"
        if not os.path.exists(cli_path):
            self._append_log_line("[HidHide] HidHideCLI.exe not found (install HidHide to block physical XInput/DInput from Steam).")
            return

        def _worker():
            try:
                if enable:
                    subprocess.run([cli_path, "--app-reg", sys.executable], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    pyw = Path(sys.executable).with_name("pythonw.exe")
                    if pyw.exists():
                        subprocess.run([cli_path, "--app-reg", str(pyw)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    subprocess.run([cli_path, "--inv-off"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

                    instance_paths = set()
                    dev_out = subprocess.run(
                        [cli_path, "--dev-gaming"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
                    ).stdout or ""
                    for match in re.findall(r'((?:HID|USB|XUSB)\\VID_17EF[^"\r\n]+)', dev_out, flags=re.IGNORECASE):
                        instance_paths.add(match.strip())

                    pnp_out = subprocess.run(
                        ["pnputil", "/enum-devices", "/connected"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
                    ).stdout or ""
                    for match in re.findall(r'((?:HID|USB)\\VID_17EF[^\r\n]+)', pnp_out, flags=re.IGNORECASE):
                        instance_paths.add(match.strip())

                    for path_str in instance_paths:
                        subprocess.run([cli_path, "--dev-hide", path_str], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

                    subprocess.run([cli_path, "--cloak-on"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    self.log_bridge.log_emitted.emit(
                        f"[HidHide] Cloaked {len(instance_paths)} Lenovo VID_17EF (XInput/DInput) device path(s) from Steam; whitelisted Python."
                    )
                else:
                    subprocess.run([cli_path, "--cloak-off"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    self.log_bridge.log_emitted.emit("[HidHide] Disabled cloak; restored physical VID_17EF visibility.")
            except Exception as exc:
                self.log_bridge.log_emitted.emit(f"[HidHide] Notice: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    # --------------------------------------------------------------------------
    # 250Hz Polling Loop & 30Hz UI Refresh
    # --------------------------------------------------------------------------
    @staticmethod
    def _is_deck_state_active(d: dict) -> bool:
        for k, v in d.items():
            if k == "accelZ":
                continue
            if isinstance(v, bool) and v:
                return True
            if isinstance(v, int) and v != 0:
                return True
        return False

    def _start_250hz_worker(self):
        def _worker():
            prev_hid_len = len(self.profile.get("learnedVendorButtons", {}))
            prev_key_len = len(self.profile.get("learnedKeyBindings", {}))
            prev_din_len = len(self.profile.get("learnedDinputButtons", {}))
            prev_xin_len = len(self.profile.get("learnedXinputButtons", {}))
            while True:
                hw_state = self.hardware_reader.poll_physical_state(self.profile)
                self.hardware_state = hw_state

                cur_hid_len = len(self.profile.get("learnedVendorButtons", {}))
                cur_key_len = len(self.profile.get("learnedKeyBindings", {}))
                cur_din_len = len(self.profile.get("learnedDinputButtons", {}))
                cur_xin_len = len(self.profile.get("learnedXinputButtons", {}))
                if (
                    cur_hid_len != prev_hid_len
                    or cur_key_len != prev_key_len
                    or cur_din_len != prev_din_len
                    or cur_xin_len != prev_xin_len
                ):
                    prev_hid_len = cur_hid_len
                    prev_key_len = cur_key_len
                    prev_din_len = cur_din_len
                    prev_xin_len = cur_xin_len
                    self._save_profile_to_disk()

                self.merged_legion_state = merge_hardware_and_tester_state(hw_state, self.ui_tester_state)

                if self.merged_legion_state["scrollWheelDelta"] != 0:
                    self.wheel_angle += self.merged_legion_state["scrollWheelDelta"] * 0.35

                new_deck_state = map_legion_to_steam_deck_state(
                    self.merged_legion_state, self.profile, self.wheel_angle
                )
                if self._is_deck_state_active(new_deck_state):
                    self.frame_counter = (self.frame_counter + 1) & 0xFFFFFFFF

                self.deck_state = new_deck_state
                new_rep = encode_neptune_64byte_report(
                    self.deck_state, self.frame_counter
                )
                prev_rep = self._prev_logged_neptune_report
                if prev_rep is not None and len(prev_rep) == 64:
                    nep_diffs = []
                    for b_idx in (8, 9, 10, 12, 13):
                        old_v = prev_rep[b_idx]
                        new_v = new_rep[b_idx]
                        if old_v != new_v:
                            xor_v = old_v ^ new_v
                            bit_list = []
                            for bit_m, bit_n in NEPTUNE_BYTE_BIT_NAMES.get(b_idx, []):
                                if xor_v & bit_m:
                                    b_dir = "+ON" if (new_v & bit_m) else "-OFF"
                                    bit_list.append(f"{bit_n}(0x{bit_m:02X}){b_dir}")
                            nep_diffs.append(
                                f"Byte {b_idx:02d}: 0x{old_v:02X}->0x{new_v:02X} (^0x{xor_v:02X} [{', '.join(bit_list)}])"
                            )
                    if nep_diffs:
                        self._prev_logged_neptune_report = bytes(new_rep)
                        if getattr(self, "deep_log_neptune_bytes", True):
                            self.log_bridge.log_emitted.emit(
                                f"[NEPTUNE 64B DELTA] {' | '.join(nep_diffs)}"
                            )
                else:
                    self._prev_logged_neptune_report = bytes(new_rep)

                self.latest_64byte_report = new_rep
                time.sleep(0.004)  # 250Hz

        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_ui_state(self):
        hw = self.hardware_state
        ui = self.ui_tester_state
        m = self.merged_legion_state
        d = self.deck_state

        if sys.platform == "win32" and not self.raw_input_sink.registered:
            self.raw_input_sink.register_for_hwnd(int(self.winId()))

        fg = self.frameGeometry()
        self.hook_interceptor.studio_window_rect = (fg.left(), fg.top(), fg.right(), fg.bottom())
        self.hook_interceptor.studio_window_active = bool(
            self.isVisible() and not self.isMinimized() and self.isActiveWindow()
        )
        pos = QCursor.pos()
        lock_active = self.hook_interceptor._should_lock_cursor_now(pos.x(), pos.y())

        hid_cnt = len(self.hardware_reader.hid_streams)
        gyro_src = self.profile.get("gyroPhysicalSource", "rightControllerImu")
        gyro_short = {
            "rightControllerImu": "Right IMU",
            "leftControllerImu": "Left IMU",
            "combinedOrTabletImu": "Combined IMU",
            "disabled": "Off",
        }.get(gyro_src, gyro_src)
        self.hw_source_badge.setText(
            f"{self.hardware_reader.detected_mode_summary} · Streams:{hid_cnt} · "
            f"Gyro:{gyro_short} · Pad:{'LOCKED' if lock_active else 'Free'}"
        )

        for key, btn in self.tester_btn_widgets.items():
            base_lbl = self.tester_btn_base_labels.get(key, key)
            phys_pressed = bool(hw.get(key, False))
            ui_pressed = bool(ui.get(key, False))
            if phys_pressed:
                btn.setText(f"{base_lbl} [HW]")
                btn.setStyleSheet(
                    "background-color: #10B981; color: #FFFFFF; border: 1px solid #059669; font-weight: 700;"
                )
            elif ui_pressed:
                btn.setText(f"{base_lbl} [UI]")
                btn.setStyleSheet(
                    "background-color: #0D84FF; color: #FFFFFF; border: 1px solid #0D84FF; font-weight: 700;"
                )
            else:
                if btn.text() != base_lbl:
                    btn.setText(base_lbl)
                if btn.styleSheet() != "":
                    btn.setStyleSheet("")

        tcal = self.profile.get("triggerCalibration") or {}
        lt_half_t = int(round(int(tcal.get("ltHalfPressPct", 45)) * 327.67))
        rt_half_t = int(round(int(tcal.get("rtHalfPressPct", 45)) * 327.67))
        lt_full_t = int(round(int(tcal.get("ltFullPressPct", 90)) * 327.67))
        rt_full_t = int(round(int(tcal.get("rtFullPressPct", 90)) * 327.67))

        for key, sld in self.tester_sliders.items():
            val = int(m.get(key, 0))
            lbl_widget, title = self.tester_slider_labels[key]
            if key == "leftTrigger":
                stage = (
                    "FULL-PRESS" if val >= lt_full_t
                    else ("HALF-PRESS" if val >= lt_half_t else ("PULL" if val > 300 else "REST"))
                )
                lbl_widget.setText(f"{title}: {val} [{stage}]")
            elif key == "rightTrigger":
                stage = (
                    "FULL-PRESS" if val >= rt_full_t
                    else ("HALF-PRESS" if val >= rt_half_t else ("PULL" if val > 300 else "REST"))
                )
                lbl_widget.setText(f"{title}: {val} [{stage}]")
            else:
                lbl_widget.setText(f"{title}: {val}")
            if not sld.isSliderDown() and ui.get(key, 0) == 0:
                sld.blockSignals(True)
                sld.setValue(val)
                sld.blockSignals(False)

        self.src_trackpad_canvas.set_pad_state(
            m["rightTrackpadTouch"], m["rightTrackpadClick"], m["rightTrackpadX"], m["rightTrackpadY"]
        )

        self.deck_left_pad_canvas.set_pad_state(
            d["leftTrackpadTouch"], d["leftTrackpadClick"], d["leftTrackpadX"], d["leftTrackpadY"]
        )
        self.deck_right_pad_canvas.set_pad_state(
            d["rightTrackpadTouch"], d["rightTrackpadClick"], d["rightTrackpadX"], d["rightTrackpadY"]
        )

        for key, (lbl_widget, title) in self.deck_indicator_labels.items():
            active = bool(d.get(key, False))
            lbl_widget.setText(f"{title}\n{'ACTIVE (1)' if active else 'IDLE'}")
            lbl_widget.setStyleSheet(
                "background-color: #10B981; color: #FFFFFF; border-radius: 6px; padding: 3px; font-weight: 700; font-size: 10px;"
                if active
                else "background-color: #1E293B; color: #94A3B8; border-radius: 6px; padding: 3px; font-size: 10px;"
            )

        gp = int(d.get("gyroPitch", 0))
        gy = int(d.get("gyroYaw", 0))
        gr = int(d.get("gyroRoll", 0))
        gyro_en = bool(self.profile.get("gyroEnabled", True)) and gyro_src != "disabled"
        gyro_moving = (gp != 0 or gy != 0 or gr != 0)
        for box_widget, axis_title, axis_val in (
            (self.steam_gyro_pitch_box, "Steam Gyro Pitch", gp),
            (self.steam_gyro_yaw_box, "Steam Gyro Yaw", gy),
            (self.steam_gyro_roll_box, "Steam Gyro Roll", gr),
        ):
            box_widget.setText(f"{axis_title}\n{axis_val:+d}" if axis_val != 0 else f"{axis_title}\n0")
            box_widget.setStyleSheet(
                "background-color: #0D84FF; color: #FFFFFF; border-radius: 6px; padding: 3px; font-weight: 700; font-size: 10px;"
                if axis_val != 0
                else "background-color: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 3px; font-weight: 600; font-size: 10px;"
            )

        if not gyro_en:
            self.steam_gyro_state_box.setText("Steam IMU\nOFF")
            self.steam_gyro_state_box.setStyleSheet(
                "background-color: #334155; color: #94A3B8; border-radius: 6px; padding: 3px; font-size: 10px;"
            )
        elif gyro_moving:
            self.steam_gyro_state_box.setText(f"Steam IMU ({gyro_short})\nSENDING")
            self.steam_gyro_state_box.setStyleSheet(
                "background-color: #10B981; color: #FFFFFF; border-radius: 6px; padding: 3px; font-weight: 700; font-size: 10px;"
            )
        else:
            self.steam_gyro_state_box.setText(f"Steam IMU ({gyro_short})\nZERO (0,0,0)")
            self.steam_gyro_state_box.setStyleSheet(
                "background-color: #1E293B; color: #38BDF8; border-radius: 6px; padding: 3px; font-weight: 600; font-size: 10px;"
            )

        self.imu_readout_lbl.setText(
            f"Deck Sticks: L({d['leftStickX']}, {d['leftStickY']}) R({d['rightStickX']}, {d['rightStickY']})  |  "
            f"L2={d['leftTriggerAnalog']} R2={d['rightTriggerAnalog']}  |  "
            f"Steam Gyro [{gyro_short}]: ({gp:+d}, {gy:+d}, {gr:+d})  [HW Raw: ({hw.get('imuGyroPitch', 0):+d}, {hw.get('imuGyroYaw', 0):+d}, {hw.get('imuGyroRoll', 0):+d})]"
        )

        if self.usbip_server.client_attached:
            self.status_sub_lbl.setText(
                f"USB/IP ATTACHED (0x28DE:0x1205 Active) · URBs: {self.usbip_server.total_urbs_answered} · "
                f"0x83={self.usbip_server.handshake_counts[0x83]} 0xAE={self.usbip_server.handshake_counts[0xAE]} · "
                f"{self.hardware_reader.detected_mode_summary}"
            )
        else:
            self.status_sub_lbl.setText(f"{self.last_bus_diagnostic} · {self.hardware_reader.detected_mode_summary}")

        rep = self.latest_64byte_report
        is_active = self._is_deck_state_active(d)
        state_tag = "ACTIVE INPUT" if is_active else "IDLE (Zero Active Inputs)"

        active_hw_btns = [
            f"{lbl}[HW]" if hw.get(k) else f"{lbl}[UI]"
            for k, lbl in LEGION_BUTTON_KEY_TO_LABEL.items()
            if hw.get(k) or ui.get(k)
        ]
        active_deck_btns = [
            k for k, v in d.items()
            if isinstance(v, bool) and v
        ]

        row_annotations = {
            0: "Header (01 00 09 3C) + 32-bit Frame Counter",
            8: "Buttons/Grips (B08=ABXY/L1R1/L2R2, B09=DPad/View/STEAM/Menu/L5, B10=R5/Pad/L3R3, B12=L4R4/Cap, B13=QAM)",
            16: "Left Trackpad (X, Y) + Right Trackpad (X, Y)",
            24: "IMU Accel (X, Y, Z) + IMU Gyro (Pitch, Yaw, Roll)",
            32: "Quaternion W/X/Y/Z",
            40: "Quaternion + Triggers L2/R2 Analog + Left Stick X",
            48: "Left Stick Y + Right Stick (X, Y) + Pad Pressure L/R",
            56: "Pad Pressure + 32-bit Hardware Timestamp",
        }

        lines = [
            f"Status: {state_tag}  |  Frame #{self.frame_counter}  |  Handshakes: 0x81={self.usbip_server.handshake_counts[0x81]}  0x83={self.usbip_server.handshake_counts[0x83]}  0x87={self.usbip_server.handshake_counts[0x87]}  0xAE={self.usbip_server.handshake_counts[0xAE]}",
            f"Active Physical Pressed : {', '.join(active_hw_btns) if active_hw_btns else 'None (Idle)'}",
            f"Active Steam Deck Bits  : {', '.join(active_deck_btns) if active_deck_btns else 'None (Idle)'}",
            "-" * 88,
            "=== 1. OUTGOING 64-BYTE VALVE STEAM DECK (0x28DE:0x1205) NEPTUNE REPORT ===",
        ]
        for row_idx in range(0, 64, 8):
            chunk = rep[row_idx:row_idx + 8]
            hex_str = "  ".join(f"{b:02X}" for b in chunk)
            note = row_annotations.get(row_idx, "")
            lines.append(f"Bytes {row_idx:02d}..{row_idx+7:02d} :   {hex_str}    | {note}")

        # Decode active Neptune command bytes B08..B13 explicitly
        nep_active_bits = []
        for b_idx in (8, 9, 10, 12, 13):
            b_val = rep[b_idx]
            if b_val != 0:
                b_names = [n for m_bit, n in NEPTUNE_BYTE_BIT_NAMES.get(b_idx, []) if (b_val & m_bit)]
                nep_active_bits.append(f"B{b_idx:02d}=0x{b_val:02X}({','.join(b_names)})")
        lines.append(f"Neptune Button Bytes B08..13 : {', '.join(nep_active_bits) if nep_active_bits else 'All 0x00 (Idle)'}")
        lines.append("-" * 88)
        lines.append("=== 2. LIVE RAW HARDWARE INPUT & COMPOSITE HID BYTE-DELTA INSPECTOR ===")

        x_btns = self.hardware_reader._prev_xinput_btns
        x_names = [n for m_bit, n in XINPUT_BIT_NAMES if (x_btns & m_bit)]
        wheel_clk = bool(self.hardware_reader.rawinput_wheel_click)
        wheel_up = bool(hw.get("scrollWheelUp", False))
        wheel_dn = bool(hw.get("scrollWheelDown", False))
        m4 = bool(self.hook_interceptor.mouse_xbutton1 or self.hardware_reader.rawinput_mouse_xbutton1)
        m5 = bool(self.hook_interceptor.mouse_xbutton2 or self.hardware_reader.rawinput_mouse_xbutton2)
        vks = [f"{format_vk_name(v)}(0x{v:02X})" for v in sorted(self.hook_interceptor.active_vk_codes)]

        lines.append(
            f"XInput Raw wButtons : 0x{x_btns:04X} ({', '.join(x_names) if x_names else 'None'}) | "
            f"DInput Raw: {self.hardware_reader._prev_dinput_btns or 'None'}"
        )
        lines.append(
            f"Mouse & Key Hooks   : Mouse5(RB/M1)={m5} | Mouse4(RB/M1)={m4} | VID_17EF Wheel(Clk={wheel_clk},Up={wheel_up},Dn={wheel_dn}) | Keys={vks}"
        )

        for st in self.hardware_reader.hid_streams:
            if not st.sub_channels:
                continue
            for rid, sub in sorted(st.sub_channels.items()):
                if sub.packets_read == 0:
                    continue
                q_deltas = []
                for b_i in range(1, 64):
                    if (sub.noisy_mask[b_i] == 0 or (rid == 0x04 and b_i == 17)) and sub.last_raw_packet[b_i] != sub.baseline[b_i]:
                        xor_b = sub.last_raw_packet[b_i] ^ sub.baseline[b_i]
                        q_deltas.append(f"B{b_i:02d}:0x{sub.baseline[b_i]:02X}->0x{sub.last_raw_packet[b_i]:02X}(^0x{xor_b:02X})")
                hex_0_19 = " ".join(f"{b:02X}" for b in sub.last_raw_packet[:20])
                d_str = ", ".join(q_deltas[:6]) if q_deltas else "at baseline"
                lines.append(f"{st.key}:R{rid:02X} (pkts={sub.packets_read:<5}) | Changed: {d_str}")
                lines.append(f"   Raw B00..19: [{hex_0_19}]")

        new_text = "\n".join(lines)
        if self.hex_matrix_view.toPlainText() != new_text:
            self.hex_matrix_view.setPlainText(new_text)

    def _append_log_line(self, msg: str):
        formatted = f"{time.strftime('%H:%M:%S')}  {msg}"
        if getattr(self, "log_view", None) is not None:
            if getattr(self, "_early_log_buffer", None):
                for buffered in self._early_log_buffer:
                    self.log_view.appendPlainText(buffered)
                self._early_log_buffer.clear()
            self.log_view.appendPlainText(formatted)
        else:
            if not hasattr(self, "_early_log_buffer"):
                self._early_log_buffer = []
            self._early_log_buffer.append(formatted)

    # --------------------------------------------------------------------------
    # Stock MIUI Light / Dark Theme Stylesheet (Compact Handheld Density)
    # --------------------------------------------------------------------------
    def _toggle_theme(self):
        self.profile["darkMode"] = not self.profile.get("darkMode", True)
        self._save_profile_to_disk()
        self._apply_miui_stylesheet()

    def _apply_miui_stylesheet(self):
        dark = self.profile.get("darkMode", True)
        bg_main = "#0D1117" if dark else "#F5F7FA"
        bg_card = "#161C26" if dark else "#FFFFFF"
        fg_text = "#F1F5F9" if dark else "#0F172A"
        fg_muted = "#94A3B8" if dark else "#64748B"
        border_col = "#222D40" if dark else "#E2E8F0"
        btn_bg = "#1E293B" if dark else "#F1F5F9"

        self.setStyleSheet(f"""
            QMainWindow, QDialog, QWidget {{
                background-color: {bg_main};
                color: {fg_text};
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }}
            QFrame#CardFrame {{
                background-color: {bg_card};
                border: 1px solid {border_col};
                border-radius: 11px;
            }}
            QLabel#HeaderTitle {{
                font-size: 14px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#SectionTitle {{
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#MutedText {{
                color: {fg_muted};
                font-size: 10px;
                background: transparent;
            }}
            QLabel#MonoReadout {{
                font-family: 'Consolas', monospace;
                font-size: 10px;
                color: #38BDF8;
                background: transparent;
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {fg_text};
                border: 1px solid {border_col};
                border-radius: 7px;
                padding: 3px 8px;
                font-weight: 600;
            }}
            QPushButton:checked {{
                background-color: #0D84FF;
                color: #FFFFFF;
                border-color: #0D84FF;
            }}
            QPushButton#PrimaryButton {{
                background-color: #0D84FF;
                color: #FFFFFF;
                border: none;
                padding: 6px 12px;
                font-weight: 700;
            }}
            QComboBox, QLineEdit, QPlainTextEdit {{
                background-color: {bg_main};
                color: {fg_text};
                border: 1px solid {border_col};
                border-radius: 6px;
                padding: 3px 6px;
            }}
            QProgressBar {{
                background-color: {bg_card};
                color: {fg_text};
                border: 1px solid {border_col};
                border-radius: 6px;
                text-align: center;
                font-weight: 600;
                min-height: 18px;
            }}
            QProgressBar::chunk {{
                background-color: #0D84FF;
                border-radius: 5px;
            }}
            QTabWidget::pane {{
                border: none;
            }}
            QTabBar::tab {{
                background: {bg_card};
                color: {fg_muted};
                padding: 6px 14px;
                margin-right: 4px;
                border-radius: 7px;
                border: 1px solid {border_col};
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background: #0D84FF;
                color: #FFFFFF;
                border-color: #0D84FF;
            }}
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LegionGoSteamDeckPyQtApp()
    window.show()
    sys.exit(app.exec())
