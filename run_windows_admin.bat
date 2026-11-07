@echo off
REM ============================================================================
REM Standalone PyQt6 Lenovo Legion Go (XInput + Single/Dual DInput) -> Steam Deck
REM Pure Valve Steam Deck 0x28DE:0x1205 Emulation + Multi-IMU Gyro Engine
REM ============================================================================
cd /d "%~dp0"
title LegionDeck Standalone PyQt6 Windows Studio

if exist "C:\Program Files\USBip" set "PATH=%PATH%;C:\Program Files\USBip"
if exist "C:\Program Files\usbip" set "PATH=%PATH%;C:\Program Files\usbip"
if exist "C:\Program Files (x86)\USBip" set "PATH=%PATH%;C:\Program Files (x86)\USBip"
if exist "C:\USBip" set "PATH=%PATH%;C:\USBip"

echo [1/3] Working Directory: %CD%
echo [1/3] Checking PyQt6 and hidapi (Removing any vgamepad PS4 fallback)...
python -m pip uninstall -y vgamepad >nul 2>nul
python -m pip install --upgrade pip PyQt6 hidapi

echo [2/3] Checking usbip-win2 virtual USB bus driver (usbip.exe)...
where usbip.exe >nul 2>nul
if %errorlevel% equ 0 (
    echo [OK] Found usbip.exe in PATH / Program Files.
) else (
    echo [WARN] usbip.exe is NOT installed yet!
    for %%F in ("%USERPROFILE%\Desktop\*USBip*.exe" "%USERPROFILE%\Desktop\*USBip*.msi") do (
        if exist "%%~fF" (
            echo [AUTO-INSTALL] Found installer on Desktop: "%%~fF"
            echo Launching USBip-0.9.8 installer now — please complete the setup wizard...
            start /wait "" "%%~fF"
            if exist "C:\Program Files\USBip" set "PATH=%PATH%;C:\Program Files\USBip"
        )
    )
)

if not exist "%~dp0legion_go_steamdeck_app.py" (
    echo.
    echo [ERROR] legion_go_steamdeck_app.py is not in "%~dp0"!
    echo Please place both legion_go_steamdeck_app.py and run_windows_admin.bat in the SAME folder.
    pause
    exit /b 1
)

echo [3/3] Starting Standalone PyQt6 Desktop Application...
python "%~dp0legion_go_steamdeck_app.py"
pause
