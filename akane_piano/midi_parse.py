"""Parse local .mid files into timed note on/off events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import mido

from .keymap import MappedKey, OutOfRangeMode, map_midi


@dataclass(frozen=True)
class TimedKeyEvent:
    """One scheduled key action after mapping."""

    time_s: float
    action: str  # "down" | "up"
    mapped: MappedKey


def list_tracks(path: str | Path) -> list[tuple[int, str, int]]:
    """Return (index, name, note_event_count) for each track."""
    mid = mido.MidiFile(str(path))
    out: list[tuple[int, str, int]] = []
    for i, track in enumerate(mid.tracks):
        name = track.name or f"track-{i}"
        notes = sum(1 for m in track if m.type in ("note_on", "note_off"))
        out.append((i, name, notes))
    return out


def _build_tick_to_seconds(
    mid: mido.MidiFile, tempo_percent: float
) -> Callable[[int], float]:
    """Integrate set_tempo meta across all tracks → absolute seconds."""
    ticks_per_beat = mid.ticks_per_beat
    scale = 100.0 / tempo_percent
    tempo_by_tick: list[tuple[int, int]] = [(0, 500_000)]
    abs_tick = 0
    for msg in mido.merge_tracks(mid.tracks):
        abs_tick += msg.time
        if msg.type == "set_tempo":
            tempo_by_tick.append((abs_tick, msg.tempo))

    def tick_to_seconds(tick: int) -> float:
        t = 0.0
        prev_tick = 0
        prev_tempo = tempo_by_tick[0][1]
        for seg_tick, seg_tempo in tempo_by_tick[1:]:
            if tick <= prev_tick:
                break
            end = min(tick, seg_tick)
            if end > prev_tick:
                t += mido.tick2second(end - prev_tick, ticks_per_beat, prev_tempo)
            if tick <= seg_tick:
                return t * scale
            prev_tick = seg_tick
            prev_tempo = seg_tempo
        if tick > prev_tick:
            t += mido.tick2second(tick - prev_tick, ticks_per_beat, prev_tempo)
        return t * scale

    return tick_to_seconds


def parse_midi(
    path: str | Path,
    *,
    out_of_range: OutOfRangeMode = "fold",
    track: int | None = None,
    tempo_percent: float = 100.0,
) -> list[TimedKeyEvent]:
    """
    Parse a MIDI file into mapped key down/up events.

    - ``track=None`` merges all tracks.
    - ``tempo_percent`` scales wall-clock timing (100 = original).
    """
    if tempo_percent <= 0:
        raise ValueError("tempo_percent must be > 0")

    mid = mido.MidiFile(str(path))
    if track is not None and (track < 0 or track >= len(mid.tracks)):
        raise IndexError(f"track {track} out of range (0..{len(mid.tracks) - 1})")

    tick_to_seconds = _build_tick_to_seconds(mid, tempo_percent)
    events: list[TimedKeyEvent] = []
    active: dict[int, int] = {}

    if track is None:
        stream = mido.merge_tracks(mid.tracks)
    else:
        stream = mid.tracks[track]

    abs_tick = 0
    for msg in stream:
        abs_tick += msg.time
        _consume_msg(msg, abs_tick, tick_to_seconds, out_of_range, active, events)

    # Release any dangling notes at end of stream
    if active:
        end_t = tick_to_seconds(abs_tick)
        for mid_n in sorted(active):
            mapped = map_midi(mid_n, "fold")
            if mapped is not None:
                events.append(TimedKeyEvent(time_s=end_t, action="up", mapped=mapped))
        active.clear()

    # Same timestamp: ups before downs (helps re-strikes)
    events.sort(key=lambda e: (e.time_s, 0 if e.action == "up" else 1))
    return events


def _consume_msg(
    msg: mido.Message,
    abs_tick: int,
    tick_to_seconds: Callable[[int], float],
    out_of_range: OutOfRangeMode,
    active: dict[int, int],
    events: list[TimedKeyEvent],
) -> None:
    if msg.type == "note_on" and msg.velocity > 0:
        mapped = map_midi(msg.note, out_of_range)
        if mapped is None:
            return
        mid_n = mapped.midi_mapped
        count = active.get(mid_n, 0)
        active[mid_n] = count + 1
        if count == 0:
            events.append(
                TimedKeyEvent(
                    time_s=tick_to_seconds(abs_tick), action="down", mapped=mapped
                )
            )
    elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
        mapped = map_midi(msg.note, out_of_range)
        if mapped is None:
            return
        mid_n = mapped.midi_mapped
        count = active.get(mid_n, 0)
        if count <= 0:
            return
        active[mid_n] = count - 1
        if active[mid_n] == 0:
            del active[mid_n]
            events.append(
                TimedKeyEvent(
                    time_s=tick_to_seconds(abs_tick), action="up", mapped=mapped
                )
            )
