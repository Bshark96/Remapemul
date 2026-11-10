"""
rawhid_poller.py — Pure Raw HID Poller for Lenovo Legion Go
Directly communicates with Lenovo VID 0x17EF composite HID endpoints.
Zero XInput and Zero DirectInput dependency.
"""

import sys
import os
import time
import json
import struct
import math
import threading
import ctypes
from ctypes import wintypes
from typing import Dict, List, Optional, Tuple, Set, Callable

try:
    import hid
    HAS_HIDAPI = True
except ImportError:
    HAS_HIDAPI = False

LENOVO_VENDOR_ID = 0x17EF
KNOWN_LENOVO_PIDS = {0x61EC, 0x61EB, 0x61ED, 0x6182, 0x6183, 0x6184}

LENOVO_WAKEUP_PACKETS = [
    bytes([0x05, 0x06, 0x01, 0x01, 0x01, 0x01]) + bytes(58),
    bytes([0x05, 0x06, 0x01, 0x01, 0x02, 0x01]) + bytes(58),
    bytes([0x05, 0x06, 0x02, 0x01, 0x01, 0x01]) + bytes(58),
    bytes([0x05, 0x06, 0x02, 0x01, 0x02, 0x01]) + bytes(58),
    bytes([0x05, 0x04, 0x01, 0x01, 0x01]) + bytes(59),
    bytes([0x05, 0x04, 0x01, 0x01, 0x02]) + bytes(59),
    bytes([0x05, 0x08, 0x07, 0x03, 0x01, 0x01, 0x01, 0x21]) + bytes(56),
    bytes([0x05, 0x08, 0x07, 0x03, 0x01, 0x02, 0x01, 0x22]) + bytes(56),
    bytes([0x05, 0x08, 0x07, 0x03, 0x01, 0x03, 0x01, 0x23]) + bytes(56),
    bytes([0x05, 0x08, 0x07, 0x03, 0x02, 0x01, 0x01, 0x24]) + bytes(56),
    bytes([0x05, 0x08, 0x07, 0x03, 0x02, 0x02, 0x01, 0x25]) + bytes(56),
    bytes([0x05, 0x08, 0x07, 0x03, 0x02, 0x03, 0x01, 0x26]) + bytes(56),
    bytes([0x05, 0x08, 0x01, 0x01, 0x01]) + bytes(59),
    bytes([0x05, 0x08, 0x01, 0x01, 0x02]) + bytes(59),
    bytes([0x05, 0x03, 0x01, 0x00, 0x01]) + bytes(59),
    bytes([0x05, 0x03, 0x01, 0x00, 0x02]) + bytes(59),
]


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


class HidSubChannel:
    """Tracks baseline, jitter mask, and last packet for a specific Report ID on an interface"""
    def __init__(self, report_id: int):
        self.report_id = int(report_id)
        self.baseline = bytearray(64)
        self.baseline[0] = int(report_id) & 0xFF
        self.noisy_mask = bytearray(64)
        self.last_packet = bytearray(64)
        self.packets_count = 0
        self.calibrated = False

    def ingest(self, pkt: bytes):
        padded = bytearray(64)
        padded[:min(64, len(pkt))] = pkt[:64]
        self.last_packet = padded
        self.packets_count += 1

        if not self.calibrated:
            if self.packets_count == 1:
                self.baseline = bytearray(padded)
            else:
                for i in range(1, 64):
                    if padded[i] != self.baseline[i]:
                        self.noisy_mask[i] = 1
            if self.packets_count >= 12:
                self.calibrated = True


class HidDeviceStream:
    def __init__(self, key: str, dev, usage_page: int, usage: int, pid: int, dev_path: str = ""):
        self.key = key
        self.dev = dev
        self.usage_page = usage_page
        self.usage = usage
        self.pid = pid
        self.dev_path = dev_path
        self.subchannels: Dict[int, HidSubChannel] = {}
        self.queue: List[bytes] = []

    def get_subchannel(self, rid: int) -> HidSubChannel:
        if rid not in self.subchannels:
            self.subchannels[rid] = HidSubChannel(rid)
        return self.subchannels[rid]


def create_empty_state() -> dict:
    return {
        "buttonA": False, "buttonB": False, "buttonX": False, "buttonY": False,
        "buttonLB": False, "buttonRB": False,
        "buttonLT": False, "buttonRT": False,
        "leftStickClick": False, "rightStickClick": False,
        "buttonView": False, "buttonMenu": False,
        "dpadUp": False, "dpadDown": False, "dpadLeft": False, "dpadRight": False,
        "legionLButton": False, "legionRButton": False,
        "buttonLegionL": False, "buttonLegionR": False,
        "buttonY1": False, "buttonY2": False, "buttonY3": False,
        "buttonM1": False, "buttonM2": False, "buttonM3": False, "buttonM4": False,
        "scrollWheelClick": False, "scrollWheelUp": False, "scrollWheelDown": False,
        "leftStickX": 0, "leftStickY": 0,
        "rightStickX": 0, "rightStickY": 0,
        "leftTriggerAnalog": 0, "rightTriggerAnalog": 0,
        "gyroPitch": 0, "gyroYaw": 0, "gyroRoll": 0,
        "reportFormat": "UNKNOWN",
    }


class RawHidPoller:
    """
    Pure Raw HID hardware polling engine for Lenovo Legion Go.
    Reads all controllers, rear buttons, gyro telemetry, triggers, and sticks.
    Zero XInput or DirectInput dependency.
    """
    def __init__(self, profile: dict, log_fn: Optional[Callable[[str], None]] = None):
        self.profile = profile
        self.log = log_fn or print
        self.streams: List[HidDeviceStream] = []
        self.streams_by_key: Dict[str, HidDeviceStream] = {}
        self.rawinput_streams: Dict[int, HidDeviceStream] = {}
        self.running = False
        self.lock = threading.Lock()
        self.last_state = create_empty_state()
        self.wheel_click_active = False
        self.wheel_up_until = 0.0
        self.wheel_down_until = 0.0

        self._init_hidapi_streams()
        self._init_rawinput_sink()

    def _init_hidapi_streams(self):
        if not HAS_HIDAPI:
            self.log("[RawHID] Warning: hidapi module not installed.")
            return

        devices = hid.enumerate(LENOVO_VENDOR_ID, 0)
        opened = 0
        for idx, d in enumerate(devices):
            pid = d.get("product_id", 0)
            upage = d.get("usage_page", 0)
            usage = d.get("usage", 0)
            iface = d.get("interface_number", idx)
            path = d.get("path", b"")

            # Extract clean interface tag
            path_str = path.decode("utf-8", errors="ignore").upper() if isinstance(path, bytes) else str(path).upper()
            mi_tag = "MI00"
            if "MI_" in path_str:
                try:
                    mi_idx = path_str.index("MI_")
                    mi_tag = "MI" + path_str[mi_idx + 3:mi_idx + 5]
                except Exception:
                    pass

            key = f"PID{pid:04X}_{mi_tag}_UP{upage:04X}_U{usage:04X}_IF{iface}"
            try:
                dev = hid.device()
                dev.open_path(path)
                dev.set_nonblocking(1)
                st = HidDeviceStream(key, dev, upage, usage, pid, path_str)
                self.streams.append(st)
                self.streams_by_key[key] = st
                opened += 1
            except Exception:
                continue

        self.log(f"[RawHID] Connected {opened} Lenovo VID_17EF HID direct endpoint(s).")
        self.send_wakeup()

    def send_wakeup(self):
        """Sends Lenovo wakeup command packets to enable high-rate reports and rear grip buttons"""
        count = 0
        for st in self.streams:
            if st.dev is not None:
                for pkt in LENOVO_WAKEUP_PACKETS:
                    try:
                        st.dev.write(pkt)
                        count += 1
                    except Exception:
                        pass
                    try:
                        st.dev.send_feature_report(pkt)
                    except Exception:
                        pass
        if count > 0:
            self.log(f"[RawHID] Sent {count} wakeup/unlock packets to Lenovo controllers.")

    def send_report_05(self, cmd_bytes: bytes) -> bool:
        """Sends an Output / Feature Report 0x05 command to the Legion Go MCU via MI_02."""
        for st in self.streams:
            if "MI02" in st.key and st.dev is not None:
                try:
                    st.dev.write(cmd_bytes)
                    return True
                except Exception:
                    try:
                        st.dev.send_feature_report(cmd_bytes)
                        return True
                    except Exception:
                        pass
        return False

    def poll_device_status(self) -> bool:
        """Sends Output Report 0x05 to query controller status (battery, mode, rail connection)"""
        return self.send_report_05(bytes([0x05, 0x06, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]))

    def set_controller_mode(self, mode: str = "xinput") -> bool:
        """
        Switches the Legion Go controller hardware mode:
        - 'xinput': standard Xbox 360 controller mode (0x01)
        - 'dinput': DirectInput mode (0x02)
        """
        code = 0x01 if mode.lower() == "xinput" else 0x02
        return self.send_report_05(bytes([0x05, 0x70, 0x01, code]))

    def set_touchpad_enabled(self, enabled: bool) -> bool:
        """Enables (0x01) or disables (0x00) the controller trackpad."""
        code = 0x01 if enabled else 0x00
        return self.send_report_05(bytes([0x05, 0x71, 0x01, code]))

    def _init_rawinput_sink(self):
        if sys.platform != "win32":
            return
        threading.Thread(target=self._rawinput_thread_func, daemon=True).start()

    def _rawinput_thread_func(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = ctypes.c_longlong

        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        def _proc(hwnd, msg, wparam, lparam):
            if msg == 0x00FF:  # WM_INPUT
                self._process_wm_input(lparam)
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wnd_proc = WNDPROC(_proc)
        hinst = kernel32.GetModuleHandleW(None)

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HICON), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON),
            ]

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wnd_proc
        wc.hInstance = hinst
        wc.lpszClassName = "LegionDeckRawInputSink"
        user32.RegisterClassExW(ctypes.byref(wc))

        hwnd = user32.CreateWindowExW(0, "LegionDeckRawInputSink", "Sink", 0, 0, 0, 0, 0, 0, 0, hinst, None)
        if not hwnd:
            return

        RIDEV_INPUTSINK = 0x00000100
        RIDEV_PAGEONLY = 0x00000020
        targets = [
            (0xFFA0, 0x0000, RIDEV_INPUTSINK | RIDEV_PAGEONLY),
            (0xFF00, 0x0000, RIDEV_INPUTSINK | RIDEV_PAGEONLY),
            (0x0001, 0x0005, RIDEV_INPUTSINK),
            (0x0001, 0x0004, RIDEV_INPUTSINK),
            (0x0001, 0x0002, RIDEV_INPUTSINK),
        ]
        registered = 0
        for up, us, flags in targets:
            rid = RAWINPUTDEVICE()
            rid.usUsagePage = up
            rid.usUsage = us
            rid.dwFlags = flags
            rid.hwndTarget = hwnd
            if user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)):
                registered += 1
        self.log(f"[RawInput] Initialized {registered} Windows kernel RawInput sink listener(s).")

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _process_wm_input(self, lparam):
        user32 = ctypes.windll.user32
        RID_INPUT = 0x10000003
        dw_size = wintypes.UINT(0)
        hdr_size = ctypes.sizeof(RAWINPUTHEADER)

        if user32.GetRawInputData(wintypes.HANDLE(lparam), RID_INPUT, None, ctypes.byref(dw_size), hdr_size) != 0:
            return
        if dw_size.value < hdr_size:
            return

        buf = ctypes.create_string_buffer(dw_size.value)
        if user32.GetRawInputData(wintypes.HANDLE(lparam), RID_INPUT, buf, ctypes.byref(dw_size), hdr_size) != dw_size.value:
            return

        raw_bytes = buf.raw
        hdr = RAWINPUTHEADER.from_buffer_copy(raw_bytes[:hdr_size])
        h_dev = int(hdr.hDevice or 0)
        payload = raw_bytes[hdr_size:]

        now = time.perf_counter()
        if hdr.dwType == 2 and len(payload) >= 8:  # RIM_TYPEHID
            dw_size_hid, dw_count = struct.unpack_from("<II", payload, 0)
            hid_data = payload[8:]
            if dw_size_hid > 0 and dw_count > 0:
                for idx in range(dw_count):
                    rep = hid_data[idx * dw_size_hid: (idx + 1) * dw_size_hid]
                    if rep:
                        with self.lock:
                            st = self.rawinput_streams.get(h_dev)
                            if st is None:
                                key = f"WM_HID_{h_dev:08X}"
                                st = HidDeviceStream(key, None, 0x0001, 0x0005, LENOVO_VENDOR_ID)
                                self.rawinput_streams[h_dev] = st
                                self.streams.append(st)
                                self.streams_by_key[key] = st
                            if len(st.queue) < 16:
                                st.queue.append(rep)
        elif hdr.dwType == 0 and len(payload) >= 8:  # RIM_TYPEMOUSE
            us_btn_flags, us_btn_data = struct.unpack_from("<HH", payload, 4)
            if us_btn_flags != 0:
                if us_btn_flags & 0x0010:  # Middle button down (wheel click)
                    self.wheel_click_active = True
                if us_btn_flags & 0x0020:  # Middle button up
                    self.wheel_click_active = False
                if us_btn_flags & 0x0400:  # Wheel scroll
                    delta = ctypes.c_short(us_btn_data & 0xFFFF).value
                    if delta > 0:
                        self.wheel_up_until = now + 0.1
                    else:
                        self.wheel_down_until = now + 0.1

    def poll(self) -> dict:
        """
        Polls all active Raw HID streams and decodes full controller state.
        Evaluates buttons according to the loaded JSON profile.
        """
        state = create_empty_state()
        now = time.perf_counter()

        buttons_cfg = self.profile.get("buttons", {})
        sticks_cfg = self.profile.get("analogSticks", {})
        triggers_cfg = self.profile.get("analogTriggers", {})
        gyro_cfg = self.profile.get("gyro", {})

        for st in self.streams:
            # 1. Direct hidapi polling
            if st.dev is not None:
                while True:
                    try:
                        pkt = st.dev.read(64)
                        if not pkt:
                            break
                        b_pkt = bytes(pkt)
                        rid = b_pkt[0] if b_pkt else 0
                        sub = st.get_subchannel(rid)
                        sub.ingest(b_pkt)
                    except Exception:
                        break

            # 2. RawInput queued packets
            if st.queue:
                with self.lock:
                    q_pkts = list(st.queue)
                    st.queue.clear()
                for pkt in q_pkts:
                    rid = pkt[0] if pkt else 0
                    sub = st.get_subchannel(rid)
                    sub.ingest(pkt)

            # Process latest subchannel packets for state decoding
            for rid, sub in st.subchannels.items():
                if sub.packets_count == 0:
                    continue
                padded = sub.last_packet

                # A. Decode Vendor Report 0x04 (Dynamic Format A & Format B Detection per HHHH)
                if rid == 4 and len(padded) >= 20:
                    is_format_a = (padded[1] == 0x00 and padded[2] == 0xA1) or (padded[1] == 0x00 and len(padded) >= 22)
                    is_format_b = (padded[1] == 0x3C)

                    if is_format_a:
                        state["reportFormat"] = "Format A (04 00 A1)"
                        # 1. Analog Sticks at Bytes 12..15 (center 128)
                        def _scale_stick_a(val_u8: int) -> int:
                            diff = int(val_u8) - 128
                            if abs(diff) <= 8:
                                return 0
                            return max(-32768, min(32767, int(diff * 256)))

                        state["leftStickX"] = _scale_stick_a(padded[12])
                        state["leftStickY"] = -_scale_stick_a(padded[13])
                        state["rightStickX"] = _scale_stick_a(padded[14])
                        state["rightStickY"] = -_scale_stick_a(padded[15])

                        # 2. D-Pad & Face ABXY at Byte 16
                        b16 = padded[16]
                        if b16 & 0x01: state["dpadUp"] = True
                        if b16 & 0x02: state["dpadDown"] = True
                        if b16 & 0x04: state["dpadLeft"] = True
                        if b16 & 0x08: state["dpadRight"] = True
                        if b16 & 0x10: state["buttonA"] = True
                        if b16 & 0x20: state["buttonB"] = True
                        if b16 & 0x40: state["buttonX"] = True
                        if b16 & 0x80: state["buttonY"] = True

                        # 3. Bumpers, Digital Triggers, View, Menu, Clicks at Byte 17
                        b17 = padded[17]
                        if b17 & 0x01: state["buttonRT"] = True
                        if b17 & 0x02: state["buttonRB"] = True; state["buttonM1"] = True
                        if b17 & 0x04: state["buttonLT"] = True
                        if b17 & 0x08: state["buttonLB"] = True
                        if b17 & 0x10: state["buttonView"] = True
                        if b17 & 0x20: state["buttonMenu"] = True
                        if b17 & 0x40: state["leftStickClick"] = True
                        if b17 & 0x80: state["rightStickClick"] = True

                        # 4. Legion L/R System Buttons at Byte 18
                        b18 = padded[18]
                        if b18 & 0x01: state["legionLButton"] = True; state["buttonLegionL"] = True
                        if b18 & 0x02: state["legionRButton"] = True; state["buttonLegionR"] = True

                        # 5. Rear Paddles (Y1..Y3, M2..M4, Wheel Click) at Byte 19
                        b19 = padded[19]
                        if b19 & 0x01: state["buttonM2"] = True
                        if b19 & 0x02: state["buttonM3"] = True
                        if b19 & 0x04: state["buttonM4"] = True
                        if b19 & 0x08: state["buttonY1"] = True
                        if b19 & 0x10: state["buttonY2"] = True
                        if b19 & 0x20: state["buttonY3"] = True
                        if b19 & 0x40: state["scrollWheelClick"] = True

                        # 6. Analog Triggers at Bytes 20 (LT) and 21 (RT)
                        if len(padded) >= 22:
                            lt_raw = padded[20]
                            rt_raw = padded[21]
                            if lt_raw > 2:
                                state["leftTriggerAnalog"] = min(32767, int(round((lt_raw / 255.0) * 32767.0)))
                                if lt_raw > 30:
                                    state["buttonLT"] = True
                            if rt_raw > 2:
                                state["rightTriggerAnalog"] = min(32767, int(round((rt_raw / 255.0) * 32767.0)))
                                if rt_raw > 30:
                                    state["buttonRT"] = True

                    elif is_format_b:
                        state["reportFormat"] = "Format B (04 3C 74)"
                        # 1. D-Pad, Stick Clicks & Legion System Buttons at Byte 7
                        b07 = padded[7]
                        if b07 & 0x01: state["leftStickClick"] = True
                        if b07 & 0x02: state["rightStickClick"] = True
                        if b07 & 0x04: state["legionLButton"] = True; state["buttonLegionL"] = True
                        if b07 & 0x08: state["legionRButton"] = True; state["buttonLegionR"] = True
                        if b07 & 0x10: state["dpadUp"] = True
                        if b07 & 0x20: state["dpadDown"] = True
                        if b07 & 0x40: state["dpadLeft"] = True
                        if b07 & 0x80: state["dpadRight"] = True

                        # 2. Face Buttons, Bumpers & Digital Triggers at Byte 8
                        b08 = padded[8]
                        if b08 & 0x01: state["buttonA"] = True
                        if b08 & 0x02: state["buttonB"] = True
                        if b08 & 0x04: state["buttonX"] = True
                        if b08 & 0x08: state["buttonY"] = True
                        if b08 & 0x10: state["buttonLB"] = True
                        if b08 & 0x20: state["buttonLT"] = True
                        if b08 & 0x40: state["buttonRB"] = True
                        if b08 & 0x80: state["buttonRT"] = True

                        # 3. View, Menu, Scroll Wheel Click at Byte 9
                        b09 = padded[9]
                        if b09 & 0x01: state["buttonView"] = True
                        if b09 & 0x02: state["buttonMenu"] = True
                        if b09 & 0x04: state["scrollWheelClick"] = True

                        # 4. Rear Paddles (Y1..Y3, M1..M4) at Byte 10
                        b10 = padded[10]
                        if b10 & 0x02: state["buttonY1"] = True
                        if b10 & 0x04: state["buttonY2"] = True
                        if b10 & 0x08: state["buttonY3"] = True
                        if b10 & 0x10: state["buttonM1"] = True; state["buttonRB"] = True
                        if b10 & 0x20: state["buttonM2"] = True
                        if b10 & 0x40: state["buttonM3"] = True
                        if b10 & 0x80: state["buttonM4"] = True

                        # 5. Analog Sticks (Bytes 14..17 / 11..18 per HHHH spec)
                        def _scale_stick_b(byte_idx: int, center: int, invert: bool, deadzone: int) -> int:
                            if byte_idx >= len(padded):
                                return 0
                            raw_v = int(padded[byte_idx])
                            if raw_v == 0 and sub.packets_count < 2:
                                return 0
                            diff = raw_v - center
                            if abs(diff) <= deadzone:
                                return 0
                            scaled = max(-32768, min(32767, int(diff * 256)))
                            return -scaled if invert else scaled

                        state["leftStickX"] = _scale_stick_b(14, 128, False, 8)
                        state["leftStickY"] = _scale_stick_b(15, 128, True, 8)
                        state["rightStickX"] = _scale_stick_b(16, 128, False, 8)
                        state["rightStickY"] = _scale_stick_b(17, 128, True, 8)

                        # 6. Analog Triggers (LT = byte 19, RT = byte 20)
                        if len(padded) >= 21:
                            lt_raw = int(padded[19])
                            rt_raw = int(padded[20])
                            if lt_raw > 2:
                                state["leftTriggerAnalog"] = min(32767, int(round((lt_raw / 255.0) * 32767.0)))
                                if lt_raw > 30:
                                    state["buttonLT"] = True
                            if rt_raw > 2:
                                state["rightTriggerAnalog"] = min(32767, int(round((rt_raw / 255.0) * 32767.0)))
                                if rt_raw > 30:
                                    state["buttonRT"] = True

                        # 7. Gyro IMU telemetry (Bytes 27..50)
                        if gyro_cfg.get("enabled", True):
                            g_off = gyro_cfg.get("offset", 29)
                            if g_off + 6 <= len(padded):
                                endian = gyro_cfg.get("endian", "<")
                                bias = gyro_cfg.get("bias", [-32767.88, -32640.0, 128.0])
                                dz = gyro_cfg.get("deadzone", 45)
                                sens = gyro_cfg.get("sensitivityMultiplier", 1.06)
                                try:
                                    gp, gy, gr = struct.unpack_from(f"{endian}hhh", padded, g_off)
                                    cp = int(round((gp - float(bias[0])) * sens))
                                    cy = int(round((gy - float(bias[1])) * sens))
                                    cr = int(round((gr - float(bias[2])) * sens))
                                    if abs(cp) >= dz:
                                        state["gyroPitch"] = -cp if gyro_cfg.get("invertPitch", False) else cp
                                    if abs(cy) >= dz:
                                        state["gyroYaw"] = -cy if gyro_cfg.get("invertYaw", False) else cy
                                    if abs(cr) >= dz:
                                        state["gyroRoll"] = -cr if gyro_cfg.get("invertRoll", False) else cr
                                except Exception:
                                    pass

                # B. Decode MI_01 Mouse / Wheel / Rear Buttons (Report 0x02 per HHHH Table 1)
                elif rid == 2 and len(padded) >= 2:
                    # B01: 0x04 = Wheel Click, 0x08 = RB / M1, 0x10 = M2
                    b01 = padded[1]
                    if b01 & 0x04: state["scrollWheelClick"] = True
                    if b01 & 0x08: state["buttonRB"] = True; state["buttonM1"] = True
                    if b01 & 0x10: state["buttonM2"] = True
                    # B04: Scroll Wheel delta
                    if len(padded) >= 5:
                        delta = ctypes.c_byte(padded[4]).value
                        if delta > 0: state["scrollWheelUp"] = True
                        elif delta < 0: state["scrollWheelDown"] = True

                # C. Decode Generic/DirectInput Buttons strictly as fallback when MI_02 telemetry is absent
                elif state["reportFormat"] == "UNKNOWN":
                    for btn_key, btn_spec in buttons_cfg.items():
                        target_rid = int(btn_spec.get("report_id", -1))
                        b_idx = int(btn_spec.get("byte", -1))
                        mask = int(btn_spec.get("mask", 0))
                        pressed_val = int(btn_spec.get("pressed_val", mask))
                        if target_rid not in (-1, rid):
                            continue
                        if 0 <= b_idx < len(padded) and mask > 0:
                            if (padded[b_idx] & mask) == pressed_val:
                                state[btn_key] = True
                    # Sticks (16-bit unsigned center 32768)
                    if state["leftStickX"] == 0 and state["leftStickY"] == 0:
                        raw_lx = padded[0] | (padded[1] << 8)
                        raw_ly = padded[2] | (padded[3] << 8)
                        dlx = raw_lx - 32768
                        dly = raw_ly - 32768
                        if abs(dlx) > 2000:
                            state["leftStickX"] = max(-32768, min(32767, int(dlx)))
                        if abs(dly) > 2000:
                            state["leftStickY"] = max(-32768, min(32767, int(-dly)))

                    if state["rightStickX"] == 0 and state["rightStickY"] == 0:
                        raw_rx = padded[4] | (padded[5] << 8)
                        raw_ry = padded[6] | (padded[7] << 8)
                        drx = raw_rx - 32768
                        dry = raw_ry - 32768
                        if abs(drx) > 2000:
                            state["rightStickX"] = max(-32768, min(32767, int(drx)))
                        if abs(dry) > 2000:
                            state["rightStickY"] = max(-32768, min(32767, int(-dry)))

                    # Triggers (byte 8 = LT, byte 9 = RT)
                    if state["leftTriggerAnalog"] == 0 and padded[8] > 2:
                        state["leftTriggerAnalog"] = min(32767, int(round((padded[8] / 255.0) * 32767.0)))
                    if state["rightTriggerAnalog"] == 0 and padded[9] > 2:
                        state["rightTriggerAnalog"] = min(32767, int(round((padded[9] / 255.0) * 32767.0)))

                    # D-Pad hat switch on IG_00 byte 11 (Up=0x04, Right=0x0C, Down=0x14, Left=0x1C)
                    hat = padded[11] & 0x3C
                    if hat == 0x04:
                        state["dpadUp"] = True
                    elif hat == 0x0C:
                        state["dpadRight"] = True
                    elif hat == 0x14:
                        state["dpadDown"] = True
                    elif hat == 0x1C:
                        state["dpadLeft"] = True

        # Mouse / Scroll Wheel states
        if self.wheel_click_active:
            state["scrollWheelClick"] = True
        if now < self.wheel_up_until:
            state["scrollWheelUp"] = True
        if now < self.wheel_down_until:
            state["scrollWheelDown"] = True

        # Synchronize alias button names
        state["buttonLegionL"] = state["legionLButton"]
        state["buttonLegionR"] = state["legionRButton"]

        # Fallback via XInput ONLY if pure Raw HID telemetry is completely unavailable
        if state["reportFormat"] == "UNKNOWN":
            cur_x = self._poll_xinput()
            if cur_x != 0:
                for btn_key, btn_spec in buttons_cfg.items():
                    x_mask = btn_spec.get("xinput_mask")
                    if x_mask and (cur_x & x_mask):
                        state[btn_key] = True

        self.last_state = state
        return state

    def _poll_xinput(self) -> int:
        for dll_name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
            try:
                dll = ctypes.windll.LoadLibrary(dll_name)
                for slot in range(4):
                    state_buf = ctypes.create_string_buffer(16)
                    if dll.XInputGetState(slot, state_buf) == 0:
                        _dw_pkt, w_btns = struct.unpack_from("<IH", state_buf.raw, 0)
                        return int(w_btns)
                break
            except Exception:
                pass
        return 0
