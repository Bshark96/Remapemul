#!/usr/bin/env python3
"""
================================================================================
LegionDeck Studio — Lenovo Legion Go to Valve Steam Deck (0x28DE:0x1205)
Modern Standalone PyQt6 Windows Studio powered by Pure Raw HID.
Zero XInput and Zero DirectInput dependency.
================================================================================
"""

import sys
import os
import json
import time
import subprocess
import threading
from typing import Dict, Any, Optional

from PyQt6.QtCore import Qt, QTimer, QSize, QPointF
from PyQt6.QtGui import QIcon, QFont, QColor, QPainter, QBrush, QPen, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QSlider, QSpinBox,
    QLineEdit, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QGroupBox, QProgressBar, QSystemTrayIcon,
    QMenu, QMessageBox, QFrame
)

from rawhid_poller import RawHidPoller, create_empty_state
from steamdeck_usbip import SteamDeckUsbipServer
from hidhide_manager import HidHideManager

PROFILE_PATH = "legion_deck_rawhid.json"

TARGET_OPTIONS = [
    ("buttonA", "Button A"),
    ("buttonB", "Button B"),
    ("buttonX", "Button X"),
    ("buttonY", "Button Y"),
    ("buttonL1", "Bumper L1 (LB)"),
    ("buttonR1", "Bumper R1 (RB)"),
    ("buttonL2Digital", "Trigger L2 Full Pull"),
    ("buttonR2Digital", "Trigger R2 Full Pull"),
    ("buttonL3Click", "Left Stick Click (L3)"),
    ("buttonR3Click", "Right Stick Click (R3)"),
    ("buttonView", "View Button (-)"),
    ("buttonMenu", "Menu Button (+)"),
    ("dpadUp", "D-Pad Up"),
    ("dpadDown", "D-Pad Down"),
    ("dpadLeft", "D-Pad Left"),
    ("dpadRight", "D-Pad Right"),
    ("buttonSteam", "Steam Button (STEAM)"),
    ("buttonQuickAccess", "Quick Access Menu (...)"),
    ("buttonL4Grip", "Steam Deck L4 Rear Grip"),
    ("buttonL5Grip", "Steam Deck L5 Rear Grip"),
    ("buttonR4Grip", "Steam Deck R4 Rear Grip"),
    ("buttonR5Grip", "Steam Deck R5 Rear Grip"),
    ("leftTrackpadTouch", "Left Trackpad Touch"),
    ("rightTrackpadTouch", "Right Trackpad Touch"),
    ("leftTrackpadClick", "Left Trackpad Click"),
    ("rightTrackpadClick", "Right Trackpad Click"),
    ("none", "Unassigned (Disabled)"),
]

PHYSICAL_BUTTON_LABELS = {
    "buttonA": "Face A (Bottom)",
    "buttonB": "Face B (Right)",
    "buttonX": "Face X (Left)",
    "buttonY": "Face Y (Top)",
    "buttonLB": "Left Bumper (LB)",
    "buttonRB": "Right Bumper (RB / M1)",
    "buttonLT": "Left Trigger Digital (LT)",
    "buttonRT": "Right Trigger Digital (RT)",
    "leftStickClick": "Left Stick Click (L3)",
    "rightStickClick": "Right Stick Click (R3)",
    "buttonView": "View (-)",
    "buttonMenu": "Menu (+)",
    "dpadUp": "D-Pad Up",
    "dpadDown": "D-Pad Down",
    "dpadLeft": "D-Pad Left",
    "dpadRight": "D-Pad Right",
    "legionLButton": "Legion L (Space / Top Left)",
    "legionRButton": "Legion R (Quick Settings / Top Right)",
    "buttonY1": "Y1 (Left Rear Upper)",
    "buttonY2": "Y2 (Left Rear Lower)",
    "buttonY3": "Y3 (Right Rear Inner)",
    "buttonM1": "M1 (Right Top Edge)",
    "buttonM2": "M2 (Right Side Lower)",
    "buttonM3": "M3 (Right Rear Outer)",
    "buttonM4": "M4 (Right Auxiliary)",
    "scrollWheelClick": "Scroll Wheel Click",
    "scrollWheelUp": "Scroll Wheel Up",
    "scrollWheelDown": "Scroll Wheel Down",
}

VISUALIZER_BUTTON_NAMES = {
    "buttonA": "A",
    "buttonB": "B",
    "buttonX": "X",
    "buttonY": "Y",
    "buttonLB": "LB",
    "buttonRB": "RB",
    "buttonLT": "LT",
    "buttonRT": "RT",
    "dpadUp": "Up",
    "dpadDown": "Down",
    "dpadLeft": "Left",
    "dpadRight": "Right",
    "leftStickClick": "L3",
    "rightStickClick": "R3",
    "buttonView": "View (-)",
    "buttonMenu": "Menu (+)",
    "legionLButton": "Legion L",
    "legionRButton": "Legion R",
    "buttonY1": "Y1",
    "buttonY2": "Y2",
    "buttonY3": "Y3",
    "buttonM1": "M1",
    "buttonM2": "M2",
    "buttonM3": "M3",
    "buttonM4": "M4",
    "scrollWheelClick": "Wheel",
}


DARK_STYLE_SHEET = """
QMainWindow, QWidget {
    background-color: #0F172A;
    color: #F8FAFC;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: bold;
    color: #38BDF8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QPushButton {
    background-color: #1E293B;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 14px;
    color: #F8FAFC;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #0284C7;
}
QPushButton:pressed {
    background-color: #0284C7;
}
QPushButton#PrimaryActionBtn {
    background-color: #0284C7;
    border: 1px solid #38BDF8;
}
QPushButton#PrimaryActionBtn:hover {
    background-color: #0369A1;
}
QPushButton#StopActionBtn {
    background-color: #DC2626;
    border: 1px solid #EF4444;
}
QPushButton#StopActionBtn:hover {
    background-color: #B91C1C;
}
QProgressBar {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 4px;
    text-align: center;
    color: #F8FAFC;
    font-size: 11px;
}
QProgressBar::chunk {
    background-color: #0284C7;
    border-radius: 3px;
}
QPlainTextEdit {
    background-color: #020617;
    border: 1px solid #1E293B;
    border-radius: 6px;
    color: #38BDF8;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
}
QTableWidget {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 6px;
    gridline-color: #334155;
}
QHeaderView::section {
    background-color: #0F172A;
    border: 1px solid #334155;
    padding: 4px 8px;
    color: #94A3B8;
    font-weight: bold;
}
QComboBox, QSpinBox, QLineEdit {
    background-color: #1E293B;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 4px 8px;
    color: #F8FAFC;
}
QComboBox QAbstractItemView {
    background-color: #1E293B;
    border: 1px solid #475569;
    selection-background-color: #0284C7;
}
"""


class StickCanvas(QWidget):
    """Visualizes analog stick 2D deflection (X/Y) with crosshair and boundary circle"""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.stick_x = 0
        self.stick_y = 0
        self.setFixedSize(110, 110)

    def set_position(self, x: int, y: int):
        self.stick_x = max(-32768, min(32767, x))
        self.stick_y = max(-32768, min(32767, y))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 8

        # Background circle
        painter.setBrush(QBrush(QColor("#1E293B")))
        painter.setPen(QPen(QColor("#475569"), 1.5))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Crosshairs
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))
        painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))

        # Normalized stick thumb position
        nx = (self.stick_x / 32768.0) * (radius - 10)
        ny = -(self.stick_y / 32768.0) * (radius - 10)

        # Deflected thumb indicator
        painter.setBrush(QBrush(QColor("#0284C7")))
        painter.setPen(QPen(QColor("#38BDF8"), 2))
        painter.drawEllipse(QPointF(cx + nx, cy + ny), 9, 9)

        # Title
        painter.setPen(QColor("#94A3B8"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(0, h - 3, w, 14, Qt.AlignmentFlag.AlignCenter, self.title)


class LegionDeckApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LegionDeck Studio — Pure Raw HID Steam Deck Emulation")
        self.resize(1020, 780)
        self.setStyleSheet(DARK_STYLE_SHEET)

        self._pending_logs = []
        self.btn_indicators: Dict[str, QLabel] = {}
        self.profile = self._load_profile()
        self._init_ui()

        self.poller = RawHidPoller(self.profile, log_fn=self.log)
        self.usbip_server = SteamDeckUsbipServer(
            get_legion_state_fn=lambda: self.poller.last_state,
            get_profile_fn=lambda: self.profile,
            log_fn=self.log
        )
        self.hidhide = HidHideManager()
        self._populate_remap_table()
        self._init_tray()
        self._update_hidhide_ui()

        # Main Polling Timer (60Hz for UI, Server handles 250Hz internally)
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._on_tick)
        self.poll_timer.start(16)

        # Flush any pending logs to log_box
        for msg in self._pending_logs:
            self.log_box.appendPlainText(msg)
        self._pending_logs.clear()

        # Auto-start emulation if configured
        if self.profile.get("usbipSettings", {}).get("autoStart", False):
            self._start_emulation()

    def _load_profile(self) -> dict:
        if os.path.exists(PROFILE_PATH):
            try:
                with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                self.log(f"[Profile] Error loading {PROFILE_PATH}: {exc}")
        return {}

    def _save_profile(self):
        try:
            with open(PROFILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.profile, f, indent=2)
            self.log(f"[Profile] Saved configuration to '{PROFILE_PATH}'.")
            QMessageBox.information(self, "Profile Saved", f"Configuration successfully saved to '{PROFILE_PATH}'.")
        except Exception as exc:
            self.log(f"[Profile] Save error: {exc}")
            QMessageBox.warning(self, "Save Error", str(exc))

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # ======================================================================
        # TOP HEADER BANNER
        # ======================================================================
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #1E293B; border-radius: 8px; padding: 6px;")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(10, 4, 10, 4)

        title_lbl = QLabel("LEGION DECK STUDIO")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #38BDF8; letter-spacing: 1px;")
        h_layout.addWidget(title_lbl)

        badge_lbl = QLabel("PURE RAW HID (NO XINPUT / NO DINPUT)")
        badge_lbl.setStyleSheet("background-color: #0369A1; color: #FFFFFF; font-size: 10px; font-weight: bold; border-radius: 4px; padding: 3px 8px;")
        h_layout.addWidget(badge_lbl)

        h_layout.addStretch()

        self.server_badge = QLabel("USB/IP: STOPPED")
        self.server_badge.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 12px;")
        h_layout.addWidget(self.server_badge)

        main_layout.addWidget(header_frame)

        # ======================================================================
        # DASHBOARD CONTENT
        # ======================================================================
        dash_layout = QHBoxLayout()
        dash_layout.setSpacing(10)

        # LEFT COLUMN: USB/IP Server Controls & Live Hardware Visualizer
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        # 1. Server Control Box
        srv_grp = QGroupBox("Valve Steam Deck (0x28DE:0x1205) Emulation")
        srv_layout = QVBoxLayout(srv_grp)

        btn_row = QHBoxLayout()
        self.toggle_srv_btn = QPushButton("START STEAM DECK EMULATION")
        self.toggle_srv_btn.setObjectName("PrimaryActionBtn")
        self.toggle_srv_btn.setFixedHeight(38)
        self.toggle_srv_btn.clicked.connect(self._toggle_emulation)
        btn_row.addWidget(self.toggle_srv_btn)

        wake_btn = QPushButton("Send Wakeup / Unlock")
        wake_btn.setFixedHeight(38)
        wake_btn.clicked.connect(self._on_wake_clicked)
        btn_row.addWidget(wake_btn)
        srv_layout.addLayout(btn_row)

        # HidHide Anti-Double-Input & MCU Hardware Controls
        hh_row = QHBoxLayout()
        self.hidhide_btn = QPushButton("CLOAK PHYSICAL CONTROLLER (HIDHIDE)")
        self.hidhide_btn.setFixedHeight(30)
        self.hidhide_btn.clicked.connect(self._toggle_hidhide)
        hh_row.addWidget(self.hidhide_btn)

        self.hidhide_status_lbl = QLabel("HidHide: Checking...")
        self.hidhide_status_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        hh_row.addWidget(self.hidhide_status_lbl)
        srv_layout.addLayout(hh_row)

        mcu_row = QHBoxLayout()
        mcu_row.addWidget(QLabel("MCU Mode (Rep 05):"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["XInput (0x01)", "DirectInput (0x02)"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mcu_row.addWidget(self.mode_combo)

        poll_status_btn = QPushButton("Poll Status")
        poll_status_btn.setFixedHeight(26)
        poll_status_btn.clicked.connect(self._on_poll_status)
        mcu_row.addWidget(poll_status_btn)
        srv_layout.addLayout(mcu_row)

        info_row = QHBoxLayout()
        port = self.profile.get("usbipSettings", {}).get("port", 3240)
        info_row.addWidget(QLabel(f"Port: {port} (usbip-win2)"))
        self.client_lbl = QLabel("Client: Disconnected")
        self.client_lbl.setStyleSheet("color: #94A3B8;")
        info_row.addWidget(self.client_lbl)
        self.urb_lbl = QLabel("URBs: 0")
        self.urb_lbl.setStyleSheet("color: #94A3B8;")
        info_row.addWidget(self.urb_lbl)
        srv_layout.addLayout(info_row)
        left_col.addWidget(srv_grp)

        # 2. Live Hardware Visualizer Box
        vis_grp = QGroupBox("Live Raw HID Hardware Monitor")
        vis_layout = QVBoxLayout(vis_grp)

        # Sticks & Triggers Row
        stk_row = QHBoxLayout()
        self.left_stick_canvas = StickCanvas("Left Stick (LS)")
        stk_row.addWidget(self.left_stick_canvas)

        self.right_stick_canvas = StickCanvas("Right Stick (RS)")
        stk_row.addWidget(self.right_stick_canvas)

        # Triggers
        trig_box = QVBoxLayout()
        trig_box.addWidget(QLabel("LT Trigger (0-100%)"))
        self.lt_bar = QProgressBar()
        self.lt_bar.setRange(0, 32767)
        self.lt_bar.setFixedHeight(18)
        trig_box.addWidget(self.lt_bar)

        trig_box.addWidget(QLabel("RT Trigger (0-100%)"))
        self.rt_bar = QProgressBar()
        self.rt_bar.setRange(0, 32767)
        self.rt_bar.setFixedHeight(18)
        trig_box.addWidget(self.rt_bar)
        stk_row.addLayout(trig_box)
        vis_layout.addLayout(stk_row)

        # Button Indicator Grid
        btn_grid_lbl = QLabel("Physical Button Bits (Raw HID):")
        btn_grid_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; margin-top: 6px;")
        vis_layout.addWidget(btn_grid_lbl)

        btn_grid_widget = QWidget()
        btn_grid_layout = QHBoxLayout(btn_grid_widget)
        btn_grid_layout.setContentsMargins(0, 0, 0, 0)
        btn_grid_layout.setSpacing(4)

        # Partition buttons into logical hardware groups per HHHH spec
        groups = [
            ("Face", ["buttonA", "buttonB", "buttonX", "buttonY"]),
            ("Bumpers & Triggers", ["buttonLB", "buttonRB", "buttonLT", "buttonRT"]),
            ("D-Pad", ["dpadUp", "dpadDown", "dpadLeft", "dpadRight"]),
            ("Sticks", ["leftStickClick", "rightStickClick"]),
            ("System", ["buttonView", "buttonMenu", "legionLButton", "legionRButton"]),
            ("Rear Grips", ["buttonY1", "buttonY2", "buttonY3", "buttonM1", "buttonM2", "buttonM3", "buttonM4", "scrollWheelClick"]),
        ]

        for grp_name, btns in groups:
            col = QVBoxLayout()
            col.setSpacing(3)
            col_lbl = QLabel(grp_name)
            col_lbl.setStyleSheet("font-size: 10px; color: #64748B; font-weight: bold;")
            col.addWidget(col_lbl)
            for b in btns:
                txt = VISUALIZER_BUTTON_NAMES.get(b, b)
                lbl = QLabel(txt)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setMinimumWidth(32)
                lbl.setStyleSheet("background-color: #1E293B; border: 1px solid #334155; border-radius: 4px; padding: 2px 4px; font-size: 10px; color: #94A3B8;")
                col.addWidget(lbl)
                self.btn_indicators[b] = lbl
            btn_grid_layout.addLayout(col)

        vis_layout.addWidget(btn_grid_widget)

        # Gyro IMU Telemetry
        self.gyro_lbl = QLabel("Gyro IMU: Pitch=0, Yaw=0, Roll=0")
        self.gyro_lbl.setStyleSheet("color: #38BDF8; font-size: 11px; margin-top: 6px;")
        vis_layout.addWidget(self.gyro_lbl)

        left_col.addWidget(vis_grp)
        dash_layout.addLayout(left_col, 5)

        # RIGHT COLUMN: Button Remapping Table & Calibration Launcher
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        remap_grp = QGroupBox("Steam Deck Button Remapping & Calibration")
        remap_layout = QVBoxLayout(remap_grp)

        # Remap Table
        self.remap_table = QTableWidget()
        self.remap_table.setColumnCount(3)
        self.remap_table.setHorizontalHeaderLabels(["Physical Control", "Bit Specification", "Steam Deck Output"])
        self.remap_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.remap_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.remap_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._populate_remap_table()
        remap_layout.addWidget(self.remap_table)

        # Action Buttons Row
        act_row = QHBoxLayout()
        save_btn = QPushButton("Save Profile")
        save_btn.setObjectName("PrimaryActionBtn")
        save_btn.clicked.connect(self._save_profile)
        act_row.addWidget(save_btn)

        reload_btn = QPushButton("Reload Profile")
        reload_btn.clicked.connect(self._reload_profile)
        act_row.addWidget(reload_btn)
        remap_layout.addLayout(act_row)

        right_col.addWidget(remap_grp)
        dash_layout.addLayout(right_col, 6)

        main_layout.addLayout(dash_layout, 7)

        # ======================================================================
        # BOTTOM EVENT LOG
        # ======================================================================
        log_grp = QGroupBox("System & Controller Event Log")
        log_layout = QVBoxLayout(log_grp)
        log_layout.setContentsMargins(8, 8, 8, 8)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(140)
        log_layout.addWidget(self.log_box)

        main_layout.addWidget(log_grp, 3)

    def _populate_remap_table(self):
        buttons_spec = self.profile.get("buttons", {})
        remap_cfg = self.profile.get("steamDeckRemap", {})

        all_keys = sorted(set(PHYSICAL_BUTTON_LABELS.keys()) | set(buttons_spec.keys()))
        self.remap_table.setRowCount(len(all_keys))

        for row, btn_key in enumerate(all_keys):
            # 1. Physical label
            label_text = PHYSICAL_BUTTON_LABELS.get(btn_key, btn_key)
            item_lbl = QTableWidgetItem(label_text)
            item_lbl.setFlags(item_lbl.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.remap_table.setItem(row, 0, item_lbl)

            # 2. Bit specification
            spec = buttons_spec.get(btn_key, {})
            if spec:
                bit_desc = f"R{spec.get('report_id', 4):02X} : B{spec.get('byte', 0)} : Mask 0x{spec.get('mask', 0):02X}"
            else:
                bit_desc = "(Unmapped)"
            item_bit = QTableWidgetItem(bit_desc)
            item_bit.setFlags(item_bit.flags() ^ Qt.ItemFlag.ItemIsEditable)
            item_bit.setForeground(QColor("#94A3B8"))
            self.remap_table.setItem(row, 1, item_bit)

            # 3. Target Dropdown
            combo = QComboBox()
            current_target = remap_cfg.get(btn_key, btn_key)
            selected_idx = 0
            for idx, (target_val, target_name) in enumerate(TARGET_OPTIONS):
                combo.addItem(target_name, target_val)
                if target_val == current_target:
                    selected_idx = idx
            combo.setCurrentIndex(selected_idx)
            combo.currentIndexChanged.connect(lambda i, bk=btn_key, cb=combo: self._on_remap_changed(bk, cb.itemData(i)))
            self.remap_table.setCellWidget(row, 2, combo)

    def _on_wake_clicked(self):
        if hasattr(self, "poller") and self.poller is not None:
            self.poller.send_wakeup()

    def _on_remap_changed(self, phys_btn: str, target_val: str):
        remap = self.profile.setdefault("steamDeckRemap", {})
        remap[phys_btn] = target_val
        self.log(f"[Remap] Bound '{phys_btn}' -> '{target_val}'")

    def _reload_profile(self):
        self.profile = self._load_profile()
        self.poller.profile = self.profile
        self._populate_remap_table()
        self.log("[Profile] Reloaded profile.")

    def _toggle_emulation(self):
        if self.usbip_server.running:
            self._stop_emulation()
        else:
            self._start_emulation()

    def _start_emulation(self):
        port = self.profile.get("usbipSettings", {}).get("port", 3240)
        self.usbip_server.start(port=port)
        self.toggle_srv_btn.setText("STOP STEAM DECK EMULATION")
        self.toggle_srv_btn.setObjectName("StopActionBtn")
        self.toggle_srv_btn.setStyle(self.toggle_srv_btn.style())
        self.server_badge.setText("USB/IP: RUNNING (PORT 3240)")
        self.server_badge.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
        self.log(f"[USB/IP] Server started on port {port}. Ready for usbip-win2 attachment.")

    def _stop_emulation(self):
        self.usbip_server.stop()
        self.toggle_srv_btn.setText("START STEAM DECK EMULATION")
        self.toggle_srv_btn.setObjectName("PrimaryActionBtn")
        self.toggle_srv_btn.setStyle(self.toggle_srv_btn.style())
        self.server_badge.setText("USB/IP: STOPPED")
        self.server_badge.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 12px;")
        self.log("[USB/IP] Server stopped.")

    def _update_hidhide_ui(self):
        if not hasattr(self, "hidhide_status_lbl"):
            return
        if not self.hidhide.is_installed():
            self.hidhide_status_lbl.setText("HidHide: Driver Not Installed")
            self.hidhide_status_lbl.setStyleSheet("color: #EF4444; font-size: 11px;")
            self.hidhide_btn.setEnabled(False)
            return

        is_cloaked = self.hidhide.is_cloaked()
        if is_cloaked:
            self.hidhide_btn.setText("UNCLOAK PHYSICAL CONTROLLER")
            self.hidhide_btn.setStyleSheet("background-color: #059669; color: white; font-weight: bold; border-radius: 4px; padding: 4px;")
            self.hidhide_status_lbl.setText("HidHide: Cloaked (Physical Controller Hidden)")
            self.hidhide_status_lbl.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
        else:
            self.hidhide_btn.setText("CLOAK PHYSICAL CONTROLLER (HIDHIDE)")
            self.hidhide_btn.setStyleSheet("")
            self.hidhide_status_lbl.setText("HidHide: Ready (Uncloaked)")
            self.hidhide_status_lbl.setStyleSheet("color: #F59E0B; font-size: 11px;")

    def _toggle_hidhide(self):
        if not self.hidhide.is_installed():
            QMessageBox.warning(self, "HidHide Not Installed", "HidHide driver or CLI was not found on this system.")
            return

        currently_cloaked = self.hidhide.is_cloaked()
        if not currently_cloaked:
            self.log("[HidHide] Whitelisting current application executable...")
            self.hidhide.whitelist_application()
            self.log("[HidHide] Blacklisting physical Lenovo Legion Go gamepad devices...")
            count, paths = self.hidhide.hide_legion_controllers()
            self.log(f"[HidHide] Hidden {count} Legion controller interface(s).")
            self.hidhide.set_cloaking(True)
            self.log("[HidHide] Cloaking activated. Physical controller is now hidden from games.")
        else:
            self.hidhide.set_cloaking(False)
            self.log("[HidHide] Cloaking deactivated. Physical controller is visible.")

        self._update_hidhide_ui()

    def _on_mode_changed(self, index: int):
        mode = "xinput" if index == 0 else "dinput"
        ok = self.poller.set_controller_mode(mode)
        if ok:
            self.log(f"[MCU] Switched Legion Go hardware to {mode.upper()} mode via Output Report 0x05.")
        else:
            self.log(f"[MCU] Sent Output Report 0x05 mode switch command.")

    def _on_poll_status(self):
        ok = self.poller.poll_device_status()
        if ok:
            self.log("[MCU] Sent Report 0x05 status query (05 06 01 00 00 ...).")
        else:
            self.log("[MCU] Sent Report 0x05 status query.")

    def _on_tick(self):
        # 1. Hardware Poll
        state = self.poller.poll()

        # 2. Update Stick Canvases
        self.left_stick_canvas.set_position(state.get("leftStickX", 0), state.get("leftStickY", 0))
        self.right_stick_canvas.set_position(state.get("rightStickX", 0), state.get("rightStickY", 0))

        # 3. Update Triggers
        self.lt_bar.setValue(state.get("leftTriggerAnalog", 0))
        self.rt_bar.setValue(state.get("rightTriggerAnalog", 0))

        # 4. Update Button Indicators
        for btn_key, lbl in self.btn_indicators.items():
            is_down = state.get(btn_key, False)
            if is_down:
                lbl.setStyleSheet("background-color: #0284C7; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 2px 4px; font-size: 10px;")
            else:
                lbl.setStyleSheet("background-color: #1E293B; border: 1px solid #334155; border-radius: 4px; padding: 2px 4px; font-size: 10px; color: #94A3B8;")

        # 5. Update Gyro & Protocol Format
        p, y, r = state.get("gyroPitch", 0), state.get("gyroYaw", 0), state.get("gyroRoll", 0)
        fmt = state.get("reportFormat", "UNKNOWN")
        fmt_desc = fmt if fmt != "UNKNOWN" else "Polling MI_02 Telemetry..."
        self.gyro_lbl.setText(f"Protocol: {fmt_desc} | Gyro IMU: Pitch={p:+06d}, Yaw={y:+06d}, Roll={r:+06d}")

        # 6. Update Server Status
        if self.usbip_server.running:
            if self.usbip_server.client_attached:
                self.client_lbl.setText("Client: Valve Steam Deck Mounted")
                self.client_lbl.setStyleSheet("color: #10B981; font-weight: bold;")
            else:
                self.client_lbl.setText("Client: Waiting for usbip.exe...")
                self.client_lbl.setStyleSheet("color: #F59E0B;")
            self.urb_lbl.setText(f"URBs: {self.usbip_server.total_urbs_answered}")

    def log(self, message: str):
        t_str = time.strftime("%H:%M:%S")
        entry = f"[{t_str}] {message}"
        if hasattr(self, "log_box") and self.log_box is not None:
            self.log_box.appendPlainText(entry)
        elif hasattr(self, "_pending_logs"):
            self._pending_logs.append(entry)
        print(message)

    def _init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.windowIcon())
        tray_menu = QMenu()
        show_action = QAction("Open LegionDeck Studio", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self._clean_exit)
        tray_menu.addAction(exit_action)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event):
        if self.profile.get("minimizeToTrayOnClose", True):
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "LegionDeck Running",
                "LegionDeck Studio is minimized to the system tray.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        else:
            self._clean_exit()

    def _clean_exit(self):
        self.usbip_server.stop()
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    window = LegionDeckApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
