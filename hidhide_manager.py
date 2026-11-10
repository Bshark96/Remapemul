import os
import sys
import ctypes
from ctypes import wintypes
import subprocess
import glob
from typing import List, Tuple, Optional

# Standard HidHide CLI and Device Paths
HIDHIDE_DEVICE_PATH = r"\\.\HidHide"
HIDHIDE_CLI_DEFAULT_PATH = r"C:\Program Files\Nefarius Software Solutions\HidHide\x64\HidHideCLI.exe"

# Known Legion Go Gamepad Device Instance Substrings to Blacklist
LEGION_HARDWARE_PATTERNS = [
    "VID_17EF&PID_6182",
    "VID_17EF&PID_6183",
    "VID_17EF&PID_6184",
    "VID_17EF&PID_6185",
    "VID_17EF&PID_61EB",
    "VID_17EF&PID_61EC",
    "VID_17EF&PID_61ED",
    "VID_17EF&PID_61EE",
]

# IOCTL codes for \\.\HidHide
IOCTL_GET_WHITELIST = 0x80016004
IOCTL_SET_WHITELIST = 0x80016008
IOCTL_GET_BLACKLIST = 0x8001600A
IOCTL_SET_BLACKLIST = 0x8001600C
IOCTL_GET_ACTIVE = 0x80016010
IOCTL_SET_ACTIVE = 0x80016014


class HidHideManager:
    """
    Manages HidHide driver and CLI to hide physical Lenovo Legion Go controllers
    from Windows and games, eliminating the 'double input' issue when emulating
    Steam Deck or Xbox controllers.
    """
    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = cli_path or self._find_cli()
        self.driver_available = self._check_driver()

    def _find_cli(self) -> Optional[str]:
        candidates = [
            HIDHIDE_CLI_DEFAULT_PATH,
            r"C:\Program Files\Nefarius Software Solutions\HidHide\HidHideCLI.exe",
            r"C:\Program Files\Nefarius Software Solutions e.U\HidHide\x64\HidHideCLI.exe",
            r"C:\Program Files\HidHideCLI\HidHideCLI.exe",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def _check_driver(self) -> bool:
        kernel32 = ctypes.windll.kernel32
        h = kernel32.CreateFileW(
            HIDHIDE_DEVICE_PATH,
            0x80000000,  # GENERIC_READ
            0x00000003,  # FILE_SHARE_READ | FILE_SHARE_WRITE
            None,
            3,           # OPEN_EXISTING
            0x00000080,  # FILE_ATTRIBUTE_NORMAL
            None
        )
        if h != -1 and h != 0:
            kernel32.CloseHandle(h)
            return True
        return False

    def is_installed(self) -> bool:
        return self.driver_available or (self.cli_path is not None and os.path.exists(self.cli_path))

    def _run_cli(self, *args, timeout_sec: float = 3.0) -> Tuple[bool, str]:
        if not self.cli_path or not os.path.exists(self.cli_path):
            return False, "HidHideCLI not found"
        try:
            cmd = [self.cli_path] + list(args)
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            return proc.returncode == 0, (proc.stdout or proc.stderr).strip()
        except Exception as exc:
            return False, str(exc)

    def is_cloaked(self) -> bool:
        """Returns True if HidHide cloaking is currently active."""
        if self.cli_path:
            ok, out = self._run_cli("--cloak-state")
            if ok and "active" in out.lower():
                return True
            if ok and "inactive" in out.lower():
                return False

        # Fallback to direct IOCTL query
        kernel32 = ctypes.windll.kernel32
        h = kernel32.CreateFileW(
            HIDHIDE_DEVICE_PATH, 0x80000000, 3, None, 3, 0x80, None
        )
        if h != -1 and h != 0:
            try:
                out_buf = ctypes.create_string_buffer(4)
                returned = wintypes.DWORD(0)
                if kernel32.DeviceIoControl(h, IOCTL_GET_ACTIVE, None, 0, out_buf, 4, ctypes.byref(returned), None):
                    return bool(out_buf.raw[0])
            finally:
                kernel32.CloseHandle(h)
        return False

    def set_cloaking(self, enable: bool) -> bool:
        """Enables or disables global HidHide cloaking."""
        if self.cli_path:
            cmd = "--cloak-on" if enable else "--cloak-off"
            ok, _ = self._run_cli(cmd)
            if ok:
                return True

        # IOCTL fallback
        kernel32 = ctypes.windll.kernel32
        h = kernel32.CreateFileW(
            HIDHIDE_DEVICE_PATH, 0xC0000000, 3, None, 3, 0x80, None
        )
        if h != -1 and h != 0:
            try:
                in_buf = ctypes.c_ubyte(1 if enable else 0)
                returned = wintypes.DWORD(0)
                return bool(kernel32.DeviceIoControl(
                    h, IOCTL_SET_ACTIVE, ctypes.byref(in_buf), 1, None, 0, ctypes.byref(returned), None
                ))
            finally:
                kernel32.CloseHandle(h)
        return False

    def get_whitelist(self) -> List[str]:
        """Returns list of whitelisted application paths."""
        if self.cli_path:
            ok, out = self._run_cli("--app-list")
            if ok:
                return [line.strip() for line in out.splitlines() if line.strip()]
        return []

    def whitelist_application(self, app_path: Optional[str] = None) -> bool:
        """
        Adds the specified executable (or currently executing Python / App)
        to the HidHide whitelist so it retains unblocked access to raw HID hardware.
        """
        target = app_path or sys.executable
        target = os.path.abspath(target)
        if self.cli_path:
            ok, _ = self._run_cli("--app-reg", target)
            return ok
        return False

    def get_blacklist(self) -> List[str]:
        """Returns list of currently hidden device instance paths."""
        if self.cli_path:
            ok, out = self._run_cli("--dev-list")
            if ok:
                return [line.strip() for line in out.splitlines() if line.strip()]
        return []

    def get_gaming_devices(self) -> List[Tuple[str, str]]:
        """
        Returns list of (Device Instance Path, Friendly Name) for all gaming HID devices.
        """
        devices = []
        if self.cli_path:
            ok, out = self._run_cli("--dev-gaming")
            if ok:
                for line in out.splitlines():
                    line = line.strip()
                    if line:
                        devices.append((line, line))
        return devices

    def hide_legion_controllers(self) -> Tuple[int, List[str]]:
        """
        Finds and hides all native physical Lenovo Legion Go gamepad interfaces.
        Preserves non-gamepad devices or handles them according to configuration.
        """
        if not self.cli_path:
            return 0, []

        ok, out = self._run_cli("--dev-gaming")
        if not ok:
            return 0, []

        hidden_count = 0
        hidden_paths = []

        for line in out.splitlines():
            dev_path = line.strip()
            # Match Lenovo Legion Go hardware patterns
            if any(pattern in dev_path.upper() for pattern in LEGION_HARDWARE_PATTERNS):
                # We specifically want to hide the standard Gamepad interface (IG_00 or MI_00)
                # so games don't see the double controller, while keeping raw vendor HID accessible
                hok, _ = self._run_cli("--dev-hide", dev_path)
                if hok:
                    hidden_count += 1
                    hidden_paths.append(dev_path)

        return hidden_count, hidden_paths

    def unhide_legion_controllers(self) -> Tuple[int, List[str]]:
        """Unhides all Lenovo Legion Go devices."""
        if not self.cli_path:
            return 0, []

        hidden = self.get_blacklist()
        unhidden_count = 0
        unhidden_paths = []

        for dev_path in hidden:
            if any(pattern in dev_path.upper() for pattern in LEGION_HARDWARE_PATTERNS):
                ok, _ = self._run_cli("--dev-unhide", dev_path)
                if ok:
                    unhidden_count += 1
                    unhidden_paths.append(dev_path)

        return unhidden_count, unhidden_paths
