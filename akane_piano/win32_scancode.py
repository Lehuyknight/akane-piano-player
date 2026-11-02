"""Windows SendInput with KEYEVENTF_SCANCODE (DirectInput-friendly).

pynput's KeyCode.from_char() uses virtual-key SendInput. That reaches text
editors (WM_CHAR path) but many games / DirectInput listeners only see
hardware-style scan-code events. OSK key highlight also tends to follow
scan-code traffic more closely than Unicode/VK_PACKET.
"""

from __future__ import annotations

import ctypes
import sys

# US QWERTY set-1 scan codes matching the Piano physical key positions.
# Independent of active keyboard layout / IME.
KEY_ID_TO_SCAN: dict[str, int] = {
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "7": 0x08,
    "8": 0x09,
    "9": 0x0A,
    "0": 0x0B,
    "-": 0x0C,
    "=": 0x0D,
    "q": 0x10,
    "w": 0x11,
    "e": 0x12,
    "r": 0x13,
    "t": 0x14,
    "y": 0x15,
    "u": 0x16,
    "i": 0x17,
    "o": 0x18,
    "p": 0x19,
    "[": 0x1A,
    "]": 0x1B,
    "a": 0x1E,
    "s": 0x1F,
    "d": 0x20,
    "f": 0x21,
    "g": 0x22,
    "h": 0x23,
    "j": 0x24,
    "k": 0x25,
    "l": 0x26,
    ";": 0x27,
    "'": 0x28,
    "enter": 0x1C,
}


def _ensure_win32() -> None:
    if sys.platform != "win32":
        raise RuntimeError("scan-code inject is Windows-only")


def send_scancode(key_id: str, *, press: bool) -> None:
    """Press or release a logical Piano key via hardware scan code."""
    _ensure_win32()
    scan = KEY_ID_TO_SCAN.get(key_id)
    if scan is None:
        raise ValueError(f"no scan code for key_id: {key_id!r}")

    from pynput._util.win32 import INPUT, INPUT_union, KEYBDINPUT, SendInput

    flags = KEYBDINPUT.SCANCODE
    if not press:
        flags |= KEYBDINPUT.KEYUP

    inp = INPUT(
        type=INPUT.KEYBOARD,
        value=INPUT_union(
            ki=KEYBDINPUT(
                wVk=0,
                wScan=scan,
                dwFlags=flags,
                time=0,
                dwExtraInfo=None,
            )
        ),
    )
    sent = SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if sent != 1:
        err = ctypes.get_last_error()
        raise OSError(f"SendInput failed for {key_id!r} (sent={sent}, err={err})")
