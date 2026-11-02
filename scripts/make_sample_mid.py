#!/usr/bin/env python3
"""Generate samples/scale_e3_ds6.mid — chromatic gamut for smoke tests."""

from __future__ import annotations

from pathlib import Path

import mido

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "samples" / "scale_e3_ds6.mid"


def main() -> None:
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="Akane gamut E3-D#6", time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=500_000, time=0))  # 120 BPM

    # Quarter notes MIDI 52..87
    for i, note in enumerate(range(52, 88)):
        on_delay = 0 if i == 0 else 0
        track.append(mido.Message("note_on", note=note, velocity=80, time=on_delay))
        track.append(mido.Message("note_off", note=note, velocity=0, time=480))

    # Short C-major arpeggio chord burst at end (polyphony)
    chord = [60, 64, 67]  # C4 E4 G4 — maps to l, q, r
    for j, note in enumerate(chord):
        track.append(mido.Message("note_on", note=note, velocity=90, time=0 if j else 480))
    for j, note in enumerate(chord):
        track.append(mido.Message("note_off", note=note, velocity=0, time=960 if j == 0 else 0))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    mid.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
