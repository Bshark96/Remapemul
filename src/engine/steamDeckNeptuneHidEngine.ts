import {
  HidByteFieldDescriptor,
  LegionGoInputState,
  LegionGoToSteamDeckMappingProfile,
  SteamDeckButtonTarget,
  SteamDeckControllerState,
} from '../types/controllerTypes';

export const DEFAULT_LEGION_GO_INPUT_STATE: LegionGoInputState = {
  legionLButton: false,
  legionRButton: false,
  buttonView: false,
  buttonMenu: false,
  buttonA: false,
  buttonB: false,
  buttonX: false,
  buttonY: false,
  dpadUp: false,
  dpadDown: false,
  dpadLeft: false,
  dpadRight: false,
  buttonLB: false,
  buttonRB: false,
  leftTriggerAnalog: 0,
  rightTriggerAnalog: 0,
  buttonY1: false,
  buttonY2: false,
  buttonY3: false,
  buttonM2: false,
  buttonM3: false,
  scrollWheelDelta: 0,
  scrollWheelUp: false,
  scrollWheelDown: false,
  scrollWheelClick: false,
  fpsModeSwitchOn: false,
  leftStickX: 0,
  leftStickY: 0,
  leftStickClick: false,
  rightStickX: 0,
  rightStickY: 0,
  rightStickClick: false,
  rightTrackpadTouch: false,
  rightTrackpadClick: false,
  rightTrackpadX: 0,
  rightTrackpadY: 0,
  rightTrackpadPressure: 0,
  imuGyroPitch: 0,
  imuGyroYaw: 0,
  imuGyroRoll: 0,
  imuAccelX: 0,
  imuAccelY: 0,
  imuAccelZ: 16384, // 1G gravity baseline on Z axis
};

export const DEFAULT_MAPPING_PROFILE: LegionGoToSteamDeckMappingProfile = {
  profileName: 'Legion Go Full Steam Deck Native Profile',
  mapLegionLButton: 'buttonSteam',
  mapLegionRButton: 'buttonQuickAccess',
  mapButtonY1: 'buttonL4Grip',
  mapButtonY2: 'buttonL5Grip',
  mapButtonY3: 'buttonR4Grip',
  mapButtonM3: 'buttonR5Grip',
  mapButtonM2: 'modeShiftRightPadToLeftPad',
  mapButtonRB: 'buttonR1',
  mapScrollWheelUp: 'dpadUp',
  mapScrollWheelDown: 'dpadDown',
  mapScrollWheelClick: 'leftTrackpadClick',
  scrollWheelMode: 'leftTrackpadVerticalSwipe',
  autoStickCapacitiveTouchOnDeflection: true,
  stickCapacitiveDeadzonePercent: 8,
  gyroSensitivityMultiplier: 1.0,
  suppressWindowsTrackpadMouse: true,
  enableHidHideCloak: true,
  usbipLoopbackPort: 3240,
  emulatedDeckSerialNumber: 'SD-LEGION-GO-28DE',
};

export const STEAM_DECK_TARGET_LABELS: Record<SteamDeckButtonTarget, string> = {
  buttonL4Grip: 'Steam Deck L4 Rear Grip',
  buttonL5Grip: 'Steam Deck L5 Rear Grip',
  buttonR4Grip: 'Steam Deck R4 Rear Grip',
  buttonR5Grip: 'Steam Deck R5 Rear Grip',
  buttonSteam: 'Steam Button (STEAM)',
  buttonQuickAccess: 'Quick Access Menu (...)',
  modeShiftRightPadToLeftPad: 'Mode-Shift: Right Pad acts as Left Pad',
  leftTrackpadClick: 'Left Trackpad Click',
  rightTrackpadClick: 'Right Trackpad Click',
  leftTrackpadTouch: 'Left Trackpad Capacitive Touch',
  rightTrackpadTouch: 'Right Trackpad Capacitive Touch',
  leftStickCapacitiveTouch: 'Left Stick Capacitive Touch (Gyro Trigger)',
  rightStickCapacitiveTouch: 'Right Stick Capacitive Touch (Gyro Trigger)',
  buttonA: 'Button A',
  buttonB: 'Button B',
  buttonX: 'Button X',
  buttonY: 'Button Y',
  buttonL1: 'Bumper L1',
  buttonR1: 'Bumper R1',
  buttonL3Click: 'Left Stick Click (L3)',
  buttonR3Click: 'Right Stick Click (R3)',
  buttonView: 'View Button (-)',
  buttonMenu: 'Menu Button (+)',
  dpadUp: 'D-Pad Up',
  dpadDown: 'D-Pad Down',
  dpadLeft: 'D-Pad Left',
  dpadRight: 'D-Pad Right',
  none: 'Unassigned (Disabled)',
};

function applyTargetAssignment(
  deck: SteamDeckControllerState,
  target: SteamDeckButtonTarget,
  isPressed: boolean
) {
  if (!isPressed || target === 'none' || target === 'modeShiftRightPadToLeftPad') {
    return;
  }
  switch (target) {
    case 'buttonL4Grip':
      deck.buttonL4Grip = true;
      break;
    case 'buttonL5Grip':
      deck.buttonL5Grip = true;
      break;
    case 'buttonR4Grip':
      deck.buttonR4Grip = true;
      break;
    case 'buttonR5Grip':
      deck.buttonR5Grip = true;
      break;
    case 'buttonSteam':
      deck.buttonSteam = true;
      break;
    case 'buttonQuickAccess':
      deck.buttonQuickAccess = true;
      break;
    case 'leftTrackpadClick':
      deck.leftTrackpadClick = true;
      deck.leftTrackpadTouch = true;
      deck.leftTrackpadPressure = Math.max(deck.leftTrackpadPressure, 32767);
      break;
    case 'rightTrackpadClick':
      deck.rightTrackpadClick = true;
      deck.rightTrackpadTouch = true;
      deck.rightTrackpadPressure = Math.max(deck.rightTrackpadPressure, 32767);
      break;
    case 'leftTrackpadTouch':
      deck.leftTrackpadTouch = true;
      deck.leftTrackpadPressure = Math.max(deck.leftTrackpadPressure, 16000);
      break;
    case 'rightTrackpadTouch':
      deck.rightTrackpadTouch = true;
      deck.rightTrackpadPressure = Math.max(deck.rightTrackpadPressure, 16000);
      break;
    case 'leftStickCapacitiveTouch':
      deck.leftStickCapacitiveTouch = true;
      break;
    case 'rightStickCapacitiveTouch':
      deck.rightStickCapacitiveTouch = true;
      break;
    case 'buttonA':
      deck.buttonA = true;
      break;
    case 'buttonB':
      deck.buttonB = true;
      break;
    case 'buttonX':
      deck.buttonX = true;
      break;
    case 'buttonY':
      deck.buttonY = true;
      break;
    case 'buttonL1':
      deck.buttonL1 = true;
      break;
    case 'buttonR1':
      deck.buttonR1 = true;
      break;
    case 'buttonL3Click':
      deck.buttonL3Click = true;
      break;
    case 'buttonR3Click':
      deck.buttonR3Click = true;
      break;
    case 'buttonView':
      deck.buttonView = true;
      break;
    case 'buttonMenu':
      deck.buttonMenu = true;
      break;
    case 'dpadUp':
      deck.dpadUp = true;
      break;
    case 'dpadDown':
      deck.dpadDown = true;
      break;
    case 'dpadLeft':
      deck.dpadLeft = true;
      break;
    case 'dpadRight':
      deck.dpadRight = true;
      break;
  }
}

function clampInt16(val: number): number {
  return Math.max(-32768, Math.min(32767, Math.round(val)));
}

function clampUint16(val: number): number {
  return Math.max(0, Math.min(32767, Math.round(val)));
}

/**
 * Translates Lenovo Legion Go hardware state into Valve Steam Deck Controller state
 * using the active user mapping profile.
 */
export function mapLegionGoToSteamDeckState(
  legion: LegionGoInputState,
  profile: LegionGoToSteamDeckMappingProfile,
  wheelStepAngle = 0
): SteamDeckControllerState {
  const deadzoneThreshold = (profile.stickCapacitiveDeadzonePercent / 100) * 32767;
  const leftStickDeflected =
    Math.hypot(legion.leftStickX, legion.leftStickY) > deadzoneThreshold;
  const rightStickDeflected =
    Math.hypot(legion.rightStickX, legion.rightStickY) > deadzoneThreshold;

  // Check if any held button activates the Right-Pad-to-Left-Pad mode shift
  const isLeftPadModeShiftActive =
    (profile.mapButtonM2 === 'modeShiftRightPadToLeftPad' && legion.buttonM2) ||
    (profile.mapButtonRB === 'modeShiftRightPadToLeftPad' && legion.buttonRB) ||
    (profile.mapButtonY1 === 'modeShiftRightPadToLeftPad' && legion.buttonY1) ||
    (profile.mapButtonY2 === 'modeShiftRightPadToLeftPad' && legion.buttonY2) ||
    (profile.mapButtonY3 === 'modeShiftRightPadToLeftPad' && legion.buttonY3) ||
    (profile.mapButtonM3 === 'modeShiftRightPadToLeftPad' && legion.buttonM3);

  const deck: SteamDeckControllerState = {
    buttonA: legion.buttonA,
    buttonB: legion.buttonB,
    buttonX: legion.buttonX,
    buttonY: legion.buttonY,
    dpadUp: legion.dpadUp,
    dpadDown: legion.dpadDown,
    dpadLeft: legion.dpadLeft,
    dpadRight: legion.dpadRight,

    buttonL1: legion.buttonLB,
    buttonR1: false,
    buttonL2Digital: legion.leftTriggerAnalog > 28000,
    buttonR2Digital: legion.rightTriggerAnalog > 28000,
    leftTriggerAnalog: clampUint16(legion.leftTriggerAnalog),
    rightTriggerAnalog: clampUint16(legion.rightTriggerAnalog),

    leftStickX: clampInt16(legion.leftStickX),
    leftStickY: clampInt16(legion.leftStickY),
    buttonL3Click: legion.leftStickClick,
    leftStickCapacitiveTouch:
      legion.leftStickClick ||
      (profile.autoStickCapacitiveTouchOnDeflection && leftStickDeflected),

    rightStickX: clampInt16(legion.rightStickX),
    rightStickY: clampInt16(legion.rightStickY),
    buttonR3Click: legion.rightStickClick,
    rightStickCapacitiveTouch:
      legion.rightStickClick ||
      (profile.autoStickCapacitiveTouchOnDeflection && rightStickDeflected),

    // Trackpad routing: If Mode-Shift is held, physical Right Trackpad drives Left Trackpad!
    leftTrackpadTouch: isLeftPadModeShiftActive ? legion.rightTrackpadTouch : false,
    leftTrackpadClick: isLeftPadModeShiftActive ? legion.rightTrackpadClick : false,
    leftTrackpadX: isLeftPadModeShiftActive ? clampInt16(legion.rightTrackpadX) : 0,
    leftTrackpadY: isLeftPadModeShiftActive ? clampInt16(legion.rightTrackpadY) : 0,
    leftTrackpadPressure: isLeftPadModeShiftActive
      ? clampUint16(
          legion.rightTrackpadClick
            ? 32767
            : legion.rightTrackpadTouch
            ? Math.max(16384, legion.rightTrackpadPressure)
            : 0
        )
      : 0,

    rightTrackpadTouch: !isLeftPadModeShiftActive ? legion.rightTrackpadTouch : false,
    rightTrackpadClick: !isLeftPadModeShiftActive ? legion.rightTrackpadClick : false,
    rightTrackpadX: !isLeftPadModeShiftActive ? clampInt16(legion.rightTrackpadX) : 0,
    rightTrackpadY: !isLeftPadModeShiftActive ? clampInt16(legion.rightTrackpadY) : 0,
    rightTrackpadPressure: !isLeftPadModeShiftActive
      ? clampUint16(
          legion.rightTrackpadClick
            ? 32767
            : legion.rightTrackpadTouch
            ? Math.max(16384, legion.rightTrackpadPressure)
            : 0
        )
      : 0,

    buttonL4Grip: false,
    buttonR4Grip: false,
    buttonL5Grip: false,
    buttonR5Grip: false,

    buttonView: legion.buttonView,
    buttonMenu: legion.buttonMenu,
    buttonSteam: false,
    buttonQuickAccess: false,

    accelX: clampInt16(legion.imuAccelX),
    accelY: clampInt16(legion.imuAccelY),
    accelZ: clampInt16(legion.imuAccelZ),
    gyroPitch: clampInt16(legion.imuGyroPitch * profile.gyroSensitivityMultiplier),
    gyroYaw: clampInt16(legion.imuGyroYaw * profile.gyroSensitivityMultiplier),
    gyroRoll: clampInt16(legion.imuGyroRoll * profile.gyroSensitivityMultiplier),
  };

  // Apply custom extra-button bindings
  applyTargetAssignment(deck, profile.mapLegionLButton, legion.legionLButton);
  applyTargetAssignment(deck, profile.mapLegionRButton, legion.legionRButton);
  applyTargetAssignment(deck, profile.mapButtonY1, legion.buttonY1);
  applyTargetAssignment(deck, profile.mapButtonY2, legion.buttonY2);
  applyTargetAssignment(deck, profile.mapButtonY3, legion.buttonY3);
  applyTargetAssignment(deck, profile.mapButtonRB, legion.buttonRB);
  applyTargetAssignment(deck, profile.mapButtonM2, legion.buttonM2);
  applyTargetAssignment(deck, profile.mapButtonM3, legion.buttonM3);
  applyTargetAssignment(deck, profile.mapScrollWheelUp, legion.scrollWheelUp);
  applyTargetAssignment(deck, profile.mapScrollWheelDown, legion.scrollWheelDown);
  applyTargetAssignment(deck, profile.mapScrollWheelClick, legion.scrollWheelClick);

  // Apply Rear Scroll Wheel behavior
  if (legion.scrollWheelDelta !== 0) {
    if (profile.scrollWheelMode === 'leftTrackpadVerticalSwipe') {
      deck.leftTrackpadTouch = true;
      deck.leftTrackpadX = 0;
      deck.leftTrackpadY = clampInt16(legion.scrollWheelDelta * 22000);
      deck.leftTrackpadPressure = 18000;
    } else if (profile.scrollWheelMode === 'leftTrackpadCircularScroll') {
      deck.leftTrackpadTouch = true;
      deck.leftTrackpadX = clampInt16(Math.cos(wheelStepAngle) * 24000);
      deck.leftTrackpadY = clampInt16(Math.sin(wheelStepAngle) * 24000);
      deck.leftTrackpadPressure = 18000;
    } else if (profile.scrollWheelMode === 'dpadUpDown') {
      if (legion.scrollWheelDelta > 0) deck.dpadUp = true;
      if (legion.scrollWheelDelta < 0) deck.dpadDown = true;
    } else if (profile.scrollWheelMode === 'buttonL4L5Tap') {
      if (legion.scrollWheelDelta > 0) deck.buttonL4Grip = true;
      if (legion.scrollWheelDelta < 0) deck.buttonL5Grip = true;
    }
  }

  return deck;
}

/**
 * Encodes a 64-byte Valve Steam Deck Controller (VID 0x28DE, PID 0x1205 "Neptune")
 * HID Input Report matching Steam's CControllerDevice_SteamDeck struct layout.
 */
export function encodeSteamDeckNeptune64ByteReport(
  state: SteamDeckControllerState,
  frameCounter: number
): Uint8Array {
  const buffer = new ArrayBuffer(64);
  const view = new DataView(buffer);

  // Bytes 00..03: Report Header (0x01 = Input Report, 0x00, 0x09 = Neptune Controller State, 0x3C = 60 payload bytes)
  view.setUint8(0, 0x01);
  view.setUint8(1, 0x00);
  view.setUint8(2, 0x09);
  view.setUint8(3, 0x3c);

  // Bytes 04..07: uint32 Monotonic Frame Counter (250Hz)
  view.setUint32(4, frameCounter >>> 0, true);

  // Byte 08: Buttons Bank 0 (Triggers, Bumpers, ABXY)
  let buttons0 = 0;
  if (state.buttonR2Digital) buttons0 |= 0x01;
  if (state.buttonL2Digital) buttons0 |= 0x02;
  if (state.buttonR1) buttons0 |= 0x04;
  if (state.buttonL1) buttons0 |= 0x08;
  if (state.buttonY) buttons0 |= 0x10;
  if (state.buttonB) buttons0 |= 0x20;
  if (state.buttonX) buttons0 |= 0x40;
  if (state.buttonA) buttons0 |= 0x80;
  view.setUint8(8, buttons0);

  // Byte 09: Buttons Bank 1 (D-Pad, View, Steam, Menu, L5)
  let buttons1 = 0;
  if (state.dpadUp) buttons1 |= 0x01;
  if (state.dpadRight) buttons1 |= 0x02;
  if (state.dpadLeft) buttons1 |= 0x04;
  if (state.dpadDown) buttons1 |= 0x08;
  if (state.buttonView) buttons1 |= 0x10;
  if (state.buttonSteam) buttons1 |= 0x20;
  if (state.buttonMenu) buttons1 |= 0x40;
  if (state.buttonL5Grip) buttons1 |= 0x80;
  view.setUint8(9, buttons1);

  // Byte 10: Buttons Bank 2 (R5, Pad Clicks, Pad Touches, Stick Clicks)
  let buttons2 = 0;
  if (state.buttonR5Grip) buttons2 |= 0x01;
  if (state.leftTrackpadClick) buttons2 |= 0x02;
  if (state.rightTrackpadClick) buttons2 |= 0x04;
  if (state.leftTrackpadTouch) buttons2 |= 0x08;
  if (state.rightTrackpadTouch) buttons2 |= 0x10;
  if (state.buttonL3Click) buttons2 |= 0x40;
  if (state.buttonR3Click) buttons2 |= 0x80;
  view.setUint8(10, buttons2);

  // Byte 11: Reserved / Pad Haptic Flags
  view.setUint8(11, 0x00);

  // Byte 12: Buttons Bank 4 (L4, R4, Capacitive Stick Touches)
  let buttons4 = 0;
  if (state.buttonL4Grip) buttons4 |= 0x02;
  if (state.buttonR4Grip) buttons4 |= 0x04;
  if (state.leftStickCapacitiveTouch) buttons4 |= 0x40;
  if (state.rightStickCapacitiveTouch) buttons4 |= 0x80;
  view.setUint8(12, buttons4);

  // Byte 13: Buttons Bank 5 (Quick Access "..." Button)
  let buttons5 = 0;
  if (state.buttonQuickAccess) buttons5 |= 0x04;
  view.setUint8(13, buttons5);

  // Bytes 14..15: Reserved padding
  view.setUint16(14, 0, true);

  // Bytes 16..23: Left & Right Trackpad X/Y (int16 little-endian)
  view.setInt16(16, state.leftTrackpadX, true);
  view.setInt16(18, state.leftTrackpadY, true);
  view.setInt16(20, state.rightTrackpadX, true);
  view.setInt16(22, state.rightTrackpadY, true);

  // Bytes 24..35: 6-Axis IMU Accelerometer (X,Y,Z) & Gyroscope (Pitch,Yaw,Roll)
  view.setInt16(24, state.accelX, true);
  view.setInt16(26, state.accelY, true);
  view.setInt16(28, state.accelZ, true);
  view.setInt16(30, state.gyroPitch, true);
  view.setInt16(32, state.gyroYaw, true);
  view.setInt16(34, state.gyroRoll, true);

  // Bytes 36..43: Quaternion Orientation W, X, Y, Z (Identity Quaternion [16384, 0, 0, 0])
  view.setInt16(36, 16384, true);
  view.setInt16(38, 0, true);
  view.setInt16(40, 0, true);
  view.setInt16(42, 0, true);

  // Bytes 44..47: Left & Right Analog Triggers (uint16 0..32767)
  view.setUint16(44, state.leftTriggerAnalog, true);
  view.setUint16(46, state.rightTriggerAnalog, true);

  // Bytes 48..55: Left & Right Thumbsticks X/Y (int16 -32768..32767)
  view.setInt16(48, state.leftStickX, true);
  view.setInt16(50, state.leftStickY, true);
  view.setInt16(52, state.rightStickX, true);
  view.setInt16(54, state.rightStickY, true);

  // Bytes 56..59: Left & Right Trackpad Pressure (uint16 0..32767)
  view.setUint16(56, state.leftTrackpadPressure, true);
  view.setUint16(58, state.rightTrackpadPressure, true);

  // Bytes 60..63: Controller Timestamp / CRC Footer
  view.setUint32(60, (frameCounter * 4000) >>> 0, true);

  return new Uint8Array(buffer);
}

export const STEAM_DECK_BYTE_DESCRIPTORS: HidByteFieldDescriptor[] = [
  {
    byteStart: 0,
    byteEnd: 3,
    fieldName: 'Neptune Report Header',
    pythonStructFormat: 'BBBB (0x01, 0x00, 0x09, 0x3C)',
    category: 'header',
    description: 'Report ID 0x01, Type 0x09 (Deck Input State), Payload Length 60 bytes (0x3C).',
  },
  {
    byteStart: 4,
    byteEnd: 7,
    fieldName: 'Frame Counter (250Hz)',
    pythonStructFormat: '<I (uint32)',
    category: 'header',
    description: 'Monotonic 32-bit packet counter incremented every 4ms.',
  },
  {
    byteStart: 8,
    byteEnd: 15,
    fieldName: 'Buttons, Grips & Touch Bitmasks',
    pythonStructFormat: '8B (Bitfields 0..7)',
    category: 'buttons',
    description:
      'ABXY, D-Pad, L1/R1, L2/R2 Click, L3/R3 Click, L4/R4/L5/R5 Grips, Steam, QAM (...), Pad & Stick Capacitive Touch.',
  },
  {
    byteStart: 16,
    byteEnd: 23,
    fieldName: 'Left & Right Trackpad Coordinates',
    pythonStructFormat: '<hhhh (4x int16)',
    category: 'trackpads',
    description: 'Signed 16-bit X/Y coordinates (-32768..32767) for Left Pad (16..19) and Right Pad (20..23).',
  },
  {
    byteStart: 24,
    byteEnd: 35,
    fieldName: '6-Axis IMU (Accel + Gyro)',
    pythonStructFormat: '<hhhhhh (6x int16)',
    category: 'imu',
    description: 'Signed 16-bit Accel X/Y/Z (24..29) and Gyro Pitch/Yaw/Roll (30..35) for native Steam Gyro.',
  },
  {
    byteStart: 36,
    byteEnd: 43,
    fieldName: 'Sensor Quaternion (W, X, Y, Z)',
    pythonStructFormat: '<hhhh (4x int16)',
    category: 'imu',
    description: 'Sensor fusion quaternion orientation required by Steam Input Gyro calibration.',
  },
  {
    byteStart: 44,
    byteEnd: 47,
    fieldName: 'Analog Triggers (L2 / R2)',
    pythonStructFormat: '<HH (2x uint16)',
    category: 'triggers',
    description: '16-bit unsigned analog pull values (0..32767) for Left (44..45) and Right (46..47) triggers.',
  },
  {
    byteStart: 48,
    byteEnd: 55,
    fieldName: 'Left & Right Thumbsticks (X / Y)',
    pythonStructFormat: '<hhhh (4x int16)',
    category: 'sticks',
    description: 'Signed 16-bit Hall Effect thumbstick axes for Left Stick (48..51) and Right Stick (52..55).',
  },
  {
    byteStart: 56,
    byteEnd: 59,
    fieldName: 'Left & Right Trackpad Pressure',
    pythonStructFormat: '<HH (2x uint16)',
    category: 'trackpads',
    description: '16-bit unsigned force sensor pressure (0..32767) for Left (56..57) and Right (58..59) pads.',
  },
  {
    byteStart: 60,
    byteEnd: 63,
    fieldName: 'Hardware Microsecond Timer',
    pythonStructFormat: '<I (uint32)',
    category: 'header',
    description: '4ms tick hardware timestamp used by Steam Input for gyro integration.',
  },
];

export const VALVE_FEATURE_REPORT_HANDSHAKES = [
  {
    reportCommandHex: '0x81 (ID_CLEAR_DIGITAL_MAPPINGS)',
    direction: 'Steam -> Python USB/IP Server (SET_FEATURE)',
    purpose: 'Disables hardware "Lizard Mode" (desktop keyboard/mouse fallback) when Steam Input takes control.',
    pythonResponseHex: '00 81 00 00 00 ... (64-byte ACK)',
  },
  {
    reportCommandHex: '0x83 (ID_GET_ATTRIBUTES_VALUES)',
    direction: 'Steam <-> Python USB/IP Server (GET_FEATURE)',
    purpose: 'Queries controller product ID (0x1205), board revision, and IMU/Trackpad capabilities.',
    pythonResponseHex: '00 83 15 01 05 12 00 00 02 00 00 00 ...',
  },
  {
    reportCommandHex: '0x87 (ID_LOAD_DEFAULT_SETTINGS)',
    direction: 'Steam -> Python USB/IP Server (SET_FEATURE)',
    purpose: 'Initializes trackpad haptics, gyro active flags, and analog trigger thresholds.',
    pythonResponseHex: '00 87 00 00 00 ... (64-byte ACK)',
  },
  {
    reportCommandHex: '0xAE (ID_GET_STRING_ATTRIBUTE)',
    direction: 'Steam <-> Python USB/IP Server (GET_FEATURE)',
    purpose: 'Reads the controller Serial Number so Steam saves your per-game Steam Deck profiles.',
    pythonResponseHex: '00 AE 15 01 "SD-LEGION-GO-28DE" ...',
  },
];
