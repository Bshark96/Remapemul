/**
 * Obvious, human-readable types for remapping the Lenovo Legion Go (VID 0x17EF)
 * to a Valve Steam Deck Controller (VID 0x28DE, PID 0x1205 "Neptune") on Windows.
 */

export type SteamDeckButtonTarget =
  | 'buttonL4Grip'
  | 'buttonL5Grip'
  | 'buttonR4Grip'
  | 'buttonR5Grip'
  | 'buttonSteam'
  | 'buttonQuickAccess'
  | 'leftTrackpadClick'
  | 'rightTrackpadClick'
  | 'leftTrackpadTouch'
  | 'rightTrackpadTouch'
  | 'leftStickCapacitiveTouch'
  | 'rightStickCapacitiveTouch'
  | 'modeShiftRightPadToLeftPad'
  | 'buttonA'
  | 'buttonB'
  | 'buttonX'
  | 'buttonY'
  | 'buttonL1'
  | 'buttonR1'
  | 'buttonL3Click'
  | 'buttonR3Click'
  | 'buttonView'
  | 'buttonMenu'
  | 'dpadUp'
  | 'dpadDown'
  | 'dpadLeft'
  | 'dpadRight'
  | 'none';

export type ScrollWheelMappingMode =
  | 'leftTrackpadVerticalSwipe'
  | 'leftTrackpadCircularScroll'
  | 'dpadUpDown'
  | 'buttonL4L5Tap';

export interface LegionGoInputState {
  // Lenovo System & Top Buttons
  legionLButton: boolean;
  legionRButton: boolean;
  buttonView: boolean;
  buttonMenu: boolean;

  // Standard Face & D-Pad Buttons
  buttonA: boolean;
  buttonB: boolean;
  buttonX: boolean;
  buttonY: boolean;
  dpadUp: boolean;
  dpadDown: boolean;
  dpadLeft: boolean;
  dpadRight: boolean;

  // Bumpers & Analog Hall Effect Triggers (0 .. 32767)
  buttonLB: boolean;
  buttonRB: boolean; // United RB / M1 (Right Bumper / Top-Edge)
  leftTriggerAnalog: number;
  rightTriggerAnalog: number;

  // Rear & Side Extra TrueStrike Buttons (Unique to Legion Go)
  buttonY1: boolean; // Left Upper Rear Grip
  buttonY2: boolean; // Left Lower Rear Grip
  buttonY3: boolean; // Right Inner Rear Grip
  buttonM2: boolean; // Right Side FPS Button
  buttonM3: boolean; // Right Lower Rear Grip

  // Rear Scroll Wheel & FPS Hardware Switch (VID_17EF Only)
  scrollWheelDelta: number; // -1 (Down), 0 (Idle), +1 (Up)
  scrollWheelUp: boolean;
  scrollWheelDown: boolean;
  scrollWheelClick: boolean;
  fpsModeSwitchOn: boolean;

  // Hall Effect Thumbsticks (-32768 .. +32767)
  leftStickX: number;
  leftStickY: number;
  leftStickClick: boolean;
  rightStickX: number;
  rightStickY: number;
  rightStickClick: boolean;

  // Integrated Right Precision Trackpad (-32768 .. +32767)
  rightTrackpadTouch: boolean;
  rightTrackpadClick: boolean;
  rightTrackpadX: number;
  rightTrackpadY: number;
  rightTrackpadPressure: number; // 0 .. 32767

  // Onboard Bosch BMI323 6-Axis IMU (-32768 .. +32767)
  imuGyroPitch: number;
  imuGyroYaw: number;
  imuGyroRoll: number;
  imuAccelX: number;
  imuAccelY: number;
  imuAccelZ: number;
}

export interface SteamDeckControllerState {
  // Face Buttons & D-Pad
  buttonA: boolean;
  buttonB: boolean;
  buttonX: boolean;
  buttonY: boolean;
  dpadUp: boolean;
  dpadDown: boolean;
  dpadLeft: boolean;
  dpadRight: boolean;

  // Shoulder Bumpers & Triggers
  buttonL1: boolean;
  buttonR1: boolean;
  buttonL2Digital: boolean;
  buttonR2Digital: boolean;
  leftTriggerAnalog: number; // uint16: 0 .. 32767
  rightTriggerAnalog: number; // uint16: 0 .. 32767

  // Thumbsticks + Capacitive Touch Sensors
  leftStickX: number; // int16: -32768 .. 32767
  leftStickY: number;
  buttonL3Click: boolean;
  leftStickCapacitiveTouch: boolean;

  rightStickX: number; // int16: -32768 .. 32767
  rightStickY: number;
  buttonR3Click: boolean;
  rightStickCapacitiveTouch: boolean;

  // Dual Trackpads (Left & Right)
  leftTrackpadTouch: boolean;
  leftTrackpadClick: boolean;
  leftTrackpadX: number; // int16: -32768 .. 32767
  leftTrackpadY: number;
  leftTrackpadPressure: number; // uint16: 0 .. 32767

  rightTrackpadTouch: boolean;
  rightTrackpadClick: boolean;
  rightTrackpadX: number; // int16: -32768 .. 32767
  rightTrackpadY: number;
  rightTrackpadPressure: number; // uint16: 0 .. 32767

  // 4 Back Grip Buttons (L4, R4, L5, R5)
  buttonL4Grip: boolean;
  buttonR4Grip: boolean;
  buttonL5Grip: boolean;
  buttonR5Grip: boolean;

  // System & Chord Buttons
  buttonView: boolean;
  buttonMenu: boolean;
  buttonSteam: boolean;
  buttonQuickAccess: boolean; // "..." QAM button

  // 6-Axis IMU (Accelerometer + Gyroscope)
  accelX: number;
  accelY: number;
  accelZ: number;
  gyroPitch: number;
  gyroYaw: number;
  gyroRoll: number;
}

export interface LegionGoToSteamDeckMappingProfile {
  profileName: string;
  // Direct button assignments for Lenovo specific buttons
  mapLegionLButton: SteamDeckButtonTarget;
  mapLegionRButton: SteamDeckButtonTarget;
  mapButtonY1: SteamDeckButtonTarget;
  mapButtonY2: SteamDeckButtonTarget;
  mapButtonY3: SteamDeckButtonTarget;
  mapButtonRB: SteamDeckButtonTarget;
  mapButtonM2: SteamDeckButtonTarget;
  mapButtonM3: SteamDeckButtonTarget;
  mapScrollWheelUp: SteamDeckButtonTarget;
  mapScrollWheelDown: SteamDeckButtonTarget;
  mapScrollWheelClick: SteamDeckButtonTarget;

  // Scroll wheel & Virtual Left Trackpad behavior
  scrollWheelMode: ScrollWheelMappingMode;
  autoStickCapacitiveTouchOnDeflection: boolean;
  stickCapacitiveDeadzonePercent: number; // e.g. 8%
  gyroSensitivityMultiplier: number; // e.g. 1.0
  suppressWindowsTrackpadMouse: boolean;
  enableHidHideCloak: boolean;
  usbipLoopbackPort: number;
  emulatedDeckSerialNumber: string;
}

export interface HidByteFieldDescriptor {
  byteStart: number;
  byteEnd: number;
  fieldName: string;
  pythonStructFormat: string;
  category: 'header' | 'buttons' | 'trackpads' | 'imu' | 'triggers' | 'sticks';
  description: string;
}
