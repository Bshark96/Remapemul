"""
steamdeck_usbip.py — Pure Python USB/IP Server for Valve Steam Deck Emulation
Emulates a Valve Steam Deck (VID 0x28DE, PID 0x1205) Neptune controller to Windows.
Transmits native 64-byte Neptune reports at up to 250Hz.
"""

import socket
import struct
import threading
import time
from typing import Dict, Any, Callable, Optional

VALVE_VENDOR_ID = 0x28DE
STEAM_DECK_PRODUCT_ID = 0x1205

# ==============================================================================
# USB & HID REPORT DESCRIPTORS
# ==============================================================================
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


def build_usb_string_descriptor(text: str) -> bytes:
    raw = text.encode("utf-16le")
    b_len = min(254, len(raw) + 2)
    return struct.pack("<BB", b_len, 0x03) + raw[: b_len - 2]


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


def encode_neptune_64byte_report(deck: dict, frame_counter: int) -> bytes:
    """Encodes a native Valve Steam Deck Neptune 64-byte input report"""
    b8 = (
        (0x01 if deck.get("buttonR2Digital") else 0)
        | (0x02 if deck.get("buttonL2Digital") else 0)
        | (0x04 if deck.get("buttonR1") else 0)
        | (0x08 if deck.get("buttonL1") else 0)
        | (0x10 if deck.get("buttonY") else 0)
        | (0x20 if deck.get("buttonB") else 0)
        | (0x40 if deck.get("buttonX") else 0)
        | (0x80 if deck.get("buttonA") else 0)
    )
    b9 = (
        (0x01 if deck.get("dpadUp") else 0)
        | (0x02 if deck.get("dpadRight") else 0)
        | (0x04 if deck.get("dpadLeft") else 0)
        | (0x08 if deck.get("dpadDown") else 0)
        | (0x10 if deck.get("buttonView") else 0)
        | (0x20 if deck.get("buttonSteam") else 0)
        | (0x40 if deck.get("buttonMenu") else 0)
        | (0x80 if deck.get("buttonL5Grip") else 0)
    )
    b10 = (
        (0x01 if deck.get("buttonR5Grip") else 0)
        | (0x02 if deck.get("leftTrackpadClick") else 0)
        | (0x04 if deck.get("rightTrackpadClick") else 0)
        | (0x08 if deck.get("leftTrackpadTouch") else 0)
        | (0x10 if deck.get("rightTrackpadTouch") else 0)
        | (0x40 if deck.get("buttonL3Click") else 0)
        | (0x80 if deck.get("buttonR3Click") else 0)
    )
    b12 = (
        (0x02 if deck.get("buttonL4Grip") else 0)
        | (0x04 if deck.get("buttonR4Grip") else 0)
        | (0x40 if deck.get("leftStickCapacitiveTouch") else 0)
        | (0x80 if deck.get("rightStickCapacitiveTouch") else 0)
    )
    b13 = 0x04 if deck.get("buttonQuickAccess") else 0x00

    return struct.pack(
        "<BBBB I BBBBBBBB hhhh hhhhhh hhhh HH hhhh HH I",
        0x01, 0x00, 0x09, 0x3C,
        frame_counter & 0xFFFFFFFF,
        b8, b9, b10, 0x00, b12, b13, 0x00, 0x00,
        deck.get("leftTrackpadX", 0), deck.get("leftTrackpadY", 0),
        deck.get("rightTrackpadX", 0), deck.get("rightTrackpadY", 0),
        deck.get("accelX", 0), deck.get("accelY", 0), deck.get("accelZ", 0),
        deck.get("gyroPitch", 0), deck.get("gyroYaw", 0), deck.get("gyroRoll", 0),
        16384, 0, 0, 0,
        deck.get("leftTriggerAnalog", 0), deck.get("rightTriggerAnalog", 0),
        deck.get("leftStickX", 0), deck.get("leftStickY", 0),
        deck.get("rightStickX", 0), deck.get("rightStickY", 0),
        deck.get("leftTrackpadPressure", 0), deck.get("rightTrackpadPressure", 0),
        (frame_counter * 4000) & 0xFFFFFFFF,
    )


class SteamDeckUsbipServer:
    """
    Pure-Python USB/IP server emulating Valve Steam Deck Neptune controller.
    """
    def __init__(self, get_legion_state_fn: Callable[[], dict], get_profile_fn: Callable[[], dict], log_fn: Optional[Callable[[str], None]] = None):
        self.get_legion_state = get_legion_state_fn
        self.get_profile = get_profile_fn
        self.log = log_fn or print
        self.running = False
        self.client_attached = False
        self.server_socket: Optional[socket.socket] = None
        self.send_lock = threading.Lock()
        self.last_feature_cmd = 0x83
        self.last_feature_arg = 0x01
        self.urb_frame_counter = 1
        self.total_urbs_answered = 0
        self.parked_urbs: Dict[int, Any] = {}

    def start(self, port: int = 3240):
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
            self.log(f"[USB/IP] Server active on 127.0.0.1:{port} (Emulating Valve Steam Deck 28DE:1205)")

            while self.running:
                conn, addr = self.server_socket.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.log(f"[USB/IP] Client connected from {addr[0]}:{addr[1]}")
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
        except Exception as exc:
            if self.running:
                self.log(f"[USB/IP] Server notice: {exc}")

    @staticmethod
    def _recv_exact(conn: socket.socket, length: int) -> bytes:
        buf = bytearray()
        while len(buf) < length:
            chunk = conn.recv(length - len(buf))
            if not chunk:
                return b""
            buf.extend(chunk)
        return bytes(buf)

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

    def build_feature_report_response(self) -> bytes:
        buf = bytearray(64)
        cmd = self.last_feature_cmd
        buf[0] = cmd
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
            serial = self.get_profile().get("usbipSettings", {}).get("serialNumber", "SD-LEGION-GO-28DE").encode("ascii")[:32]
            buf[1] = len(serial) + 2
            buf[2] = self.last_feature_arg
            buf[3:3 + len(serial)] = serial
        return bytes(buf)

    def _map_legion_to_deck(self, legion: dict) -> dict:
        """Applies remapping dictionary to convert Raw HID state to Steam Deck state"""
        deck = {
            "buttonA": False, "buttonB": False, "buttonX": False, "buttonY": False,
            "buttonL1": False, "buttonR1": False,
            "buttonL2Digital": False, "buttonR2Digital": False,
            "buttonL3Click": False, "buttonR3Click": False,
            "buttonView": False, "buttonMenu": False,
            "dpadUp": False, "dpadDown": False, "dpadLeft": False, "dpadRight": False,
            "buttonSteam": False, "buttonQuickAccess": False,
            "buttonL4Grip": False, "buttonL5Grip": False,
            "buttonR4Grip": False, "buttonR5Grip": False,
            "leftTrackpadTouch": False, "rightTrackpadTouch": False,
            "leftTrackpadClick": False, "rightTrackpadClick": False,
            "leftStickCapacitiveTouch": False, "rightStickCapacitiveTouch": False,
            "leftTrackpadX": 0, "leftTrackpadY": 0,
            "rightTrackpadX": 0, "rightTrackpadY": 0,
            "accelX": 0, "accelY": 0, "accelZ": 0,
            "gyroPitch": legion.get("gyroPitch", 0),
            "gyroYaw": legion.get("gyroYaw", 0),
            "gyroRoll": legion.get("gyroRoll", 0),
            "leftTriggerAnalog": legion.get("leftTriggerAnalog", 0),
            "rightTriggerAnalog": legion.get("rightTriggerAnalog", 0),
            "leftStickX": legion.get("leftStickX", 0),
            "leftStickY": legion.get("leftStickY", 0),
            "rightStickX": legion.get("rightStickX", 0),
            "rightStickY": legion.get("rightStickY", 0),
            "leftTrackpadPressure": 0, "rightTrackpadPressure": 0,
        }

        # Triggers digital threshold
        if deck["leftTriggerAnalog"] >= 24000:
            deck["buttonL2Digital"] = True
        if deck["rightTriggerAnalog"] >= 24000:
            deck["buttonR2Digital"] = True

        TARGET_ALIASES = {
            "leftStickClick": "buttonL3Click",
            "rightStickClick": "buttonR3Click",
            "buttonLB": "buttonL1",
            "buttonRB": "buttonR1",
            "buttonLT": "buttonL2Digital",
            "buttonRT": "buttonR2Digital",
            "buttonL4": "buttonL4Grip",
            "buttonL5": "buttonL5Grip",
            "buttonR4": "buttonR4Grip",
            "buttonR5": "buttonR5Grip",
            "buttonQAM": "buttonQuickAccess",
            "scrollWheelClick": "buttonQuickAccess",
            "touchpadClick": "leftTrackpadClick",
        }

        remap = self.get_profile().get("steamDeckRemap", {})
        for phys_btn, target_btn in remap.items():
            if legion.get(phys_btn):
                canonical_target = TARGET_ALIASES.get(target_btn, target_btn)
                if canonical_target in deck:
                    deck[canonical_target] = True

        return deck

    def _handle_client(self, conn: socket.socket):
        try:
            hdr = self._recv_exact(conn, 8)
            if len(hdr) < 8:
                return
            version, op_code, _status = struct.unpack(">HHI", hdr)
            if op_code == 0x8005:  # OP_REQ_DEVLIST
                dev_summary = self._build_usbip_dev_summary()
                ifaces = (
                    struct.pack("BBBB", 0x03, 0x01, 0x02, 0x00) +
                    struct.pack("BBBB", 0x03, 0x01, 0x01, 0x00) +
                    struct.pack("BBBB", 0x03, 0x00, 0x00, 0x00)
                )
                reply = struct.pack(">HHII", version, 0x0005, 0, 1) + dev_summary + ifaces
                conn.sendall(reply)
                self.log("[USB/IP] Answered OP_REQ_DEVLIST (Bus 1-1: Valve Steam Deck 28DE:1205)")
            elif op_code == 0x8003:  # OP_REQ_IMPORT
                busid_raw = self._recv_exact(conn, 32)
                busid = busid_raw.decode("ascii", errors="ignore").strip("\x00")
                self.log(f"[USB/IP] Attached Bus {busid}! Windows mounting Steam Deck...")
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

    def _urb_loop(self, conn: socket.socket):
        """Processes USB/IP URB submissions and sends Steam Deck Neptune controller reports"""
        while self.running and self.client_attached:
            req_hdr = self._recv_exact(conn, 48)
            if len(req_hdr) < 48:
                break
            cmd, seqnum, devid, direction, ep, transfer_flags, transfer_buffer_length, _sf, _nop, _intv = struct.unpack(
                ">IIIIIIiiII", req_hdr[:40]
            )
            setup = req_hdr[40:48]

            if cmd == 0x00000001:  # USBIP_CMD_SUBMIT
                out_data = b""
                if direction == 0 and transfer_buffer_length > 0:
                    out_data = self._recv_exact(conn, transfer_buffer_length)

                if ep == 0:  # Control endpoint
                    resp_payload = self._handle_control_transfer(setup, out_data)
                    self._send_ret_submit(conn, seqnum, direction == 1, resp_payload, transfer_buffer_length)
                elif ep == 3 and direction == 1:  # Steam Deck IN endpoint
                    legion = self.get_legion_state()
                    deck = self._map_legion_to_deck(legion)
                    self.urb_frame_counter = (self.urb_frame_counter + 1) & 0xFFFFFFFF
                    rep = encode_neptune_64byte_report(deck, self.urb_frame_counter)
                    self.total_urbs_answered += 1
                    self._send_ret_submit(conn, seqnum, True, rep[:transfer_buffer_length], transfer_buffer_length)
                elif ep in (1, 2) and direction == 1:  # Mouse / Keyboard IN endpoint
                    empty_rep = b"\x00" * min(8, transfer_buffer_length)
                    self._send_ret_submit(conn, seqnum, True, empty_rep, transfer_buffer_length)
                else:
                    self._send_ret_submit(conn, seqnum, direction == 1, b"", transfer_buffer_length)

            elif cmd == 0x00000002:  # USBIP_CMD_UNLINK
                unlink_seqnum = struct.unpack(">I", req_hdr[4:8])[0]
                ret_unlink = struct.pack(">IIIIIIII", 0x00000004, seqnum, 0, 0, 0, 0, 0, 0) + b"\x00" * 16
                with self.send_lock:
                    conn.sendall(ret_unlink)

    def _handle_control_transfer(self, setup: bytes, out_data: bytes) -> bytes:
        bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack("<BBHHH", setup)
        req_type = bmRequestType & 0x60

        if req_type == 0x00:  # Standard
            if bRequest == 0x06:  # GET_DESCRIPTOR
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
                        serial_str = self.get_profile().get("usbipSettings", {}).get("serialNumber", "SD-LEGION-GO-28DE")
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
            elif bRequest == 0x00:
                return b"\x00\x00"[:wLength]
            elif bRequest == 0x08:
                return b"\x01"[:wLength]
            elif bRequest == 0x0A:
                return b"\x00"[:wLength]
            elif bRequest in (0x01, 0x03, 0x05, 0x09, 0x0B):
                return b""

        elif req_type == 0x20:  # Class (HID)
            if bRequest == 0x09:  # SET_REPORT
                if out_data:
                    offset = 1 if (len(out_data) > 1 and out_data[0] == 0x00) else 0
                    cmd = out_data[offset]
                    self.last_feature_cmd = cmd
                    if len(out_data) > offset + 2:
                        self.last_feature_arg = out_data[offset + 2]
                return b""
            elif bRequest == 0x01:  # GET_REPORT
                report_type = (wValue >> 8) & 0xFF
                if report_type == 0x03:  # Feature
                    return self.build_feature_report_response()[:wLength]
                else:
                    legion = self.get_legion_state()
                    deck = self._map_legion_to_deck(legion)
                    self.urb_frame_counter = (self.urb_frame_counter + 1) & 0xFFFFFFFF
                    return encode_neptune_64byte_report(deck, self.urb_frame_counter)[:wLength]

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
