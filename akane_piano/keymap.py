"""Hard-coded Piano QWERTY map (plan §2): MIDI 52–87 / E3–D#6."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OutOfRangeMode = Literal["fold", "skip"]

MIDI_MIN = 52  # E3
MIDI_MAX = 87  # D#6

# midi_note -> (label for display, logical key id used by injector)
# Logical keys: printable chars as themselves; Enter as "enter".
MIDI_TO_KEY: dict[int, tuple[str, str]] = {
    # High row (E5–D#6)
    76: ("E5", "1"),
    77: ("F5", "2"),
    78: ("F#5", "3"),
    79: ("G5", "4"),
    80: ("G#5", "5"),
    81: ("A5", "6"),
    82: ("A#5", "7"),
    83: ("B5", "8"),
    84: ("C6", "9"),
    85: ("C#6", "0"),
    86: ("D6", "-"),
    87: ("D#6", "="),
    # Mid row (E4–D#5)
    64: ("E4", "q"),
    65: ("F4", "w"),
    66: ("F#4", "e"),
    67: ("G4", "r"),
    68: ("G#4", "t"),
    69: ("A4", "y"),
    70: ("A#4", "u"),
    71: ("B4", "i"),
    72: ("C5", "o"),
    73: ("C#5", "p"),
    74: ("D5", "["),
    75: ("D#5", "]"),
    # Low row (E3–D#4)
    52: ("E3", "a"),
    53: ("F3", "s"),
    54: ("F#3", "d"),
    55: ("G3", "f"),
    56: ("G#3", "g"),
    57: ("A3", "h"),
    58: ("A#3", "j"),
    59: ("B3", "k"),
    60: ("C4", "l"),
    61: ("C#4", ";"),
    62: ("D4", "'"),
    63: ("D#4", "enter"),
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_name(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{(midi // 12) - 1}"


def fold_or_skip(midi: int, mode: OutOfRangeMode) -> int | None:
    """Map a MIDI note into 52–87, or return None if skipped."""
    if MIDI_MIN <= midi <= MIDI_MAX:
        return midi
    if mode == "skip":
        return None
    n = midi
    while n < MIDI_MIN:
        n += 12
    while n > MIDI_MAX:
        n -= 12
    if MIDI_MIN <= n <= MIDI_MAX:
        return n
    return None


@dataclass(frozen=True)
class MappedKey:
    midi_original: int
    midi_mapped: int
    note_name: str
    key_id: str  # injector id


def map_midi(midi: int, mode: OutOfRangeMode = "fold") -> MappedKey | None:
    mapped = fold_or_skip(midi, mode)
    if mapped is None:
        return None
    note_name, key_id = MIDI_TO_KEY[mapped]
    return MappedKey(
        midi_original=midi,
        midi_mapped=mapped,
        note_name=note_name,
        key_id=key_id,
    )
