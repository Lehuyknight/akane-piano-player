"""Score MIDI tracks for Akane Piano range fit (MIDI 52–87)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import mido

from .keymap import MIDI_MAX, MIDI_MIN

_PIANO_RE = re.compile(
    r"piano|keys|keyboard|grand|upright|rhodes|epiano|electric.?piano|akit",
    re.I,
)


@dataclass(frozen=True)
class TrackScore:
    index: int
    name: str
    note_ons: int
    in_range: int
    out_range: int
    pct_in_range: float
    piano_hint: bool
    score: float


@dataclass(frozen=True)
class MidiAnalysis:
    path: Path
    tracks: list[TrackScore]
    best_track: int | None

    @property
    def best(self) -> TrackScore | None:
        if self.best_track is None:
            return None
        for t in self.tracks:
            if t.index == self.best_track:
                return t
        return None


def _track_note_pitches(track: mido.MidiTrack) -> list[int]:
    pitches: list[int] = []
    for msg in track:
        if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
            pitches.append(int(msg.note))
    return pitches


def _score_track(index: int, track: mido.MidiTrack) -> TrackScore | None:
    name = (track.name or f"track-{index}").strip() or f"track-{index}"
    pitches = _track_note_pitches(track)
    if not pitches:
        return None
    in_range = sum(1 for n in pitches if MIDI_MIN <= n <= MIDI_MAX)
    out_range = len(pitches) - in_range
    pct = 100.0 * in_range / len(pitches)
    piano_hint = bool(_PIANO_RE.search(name))
    # Prefer high in-range %, piano-named tracks, and denser melodic lines.
    score = pct
    if piano_hint:
        score += 12.0
    score += min(8.0, len(pitches) / 80.0)
    return TrackScore(
        index=index,
        name=name,
        note_ons=len(pitches),
        in_range=in_range,
        out_range=out_range,
        pct_in_range=pct,
        piano_hint=piano_hint,
        score=score,
    )


def analyze_midi(path: str | Path) -> MidiAnalysis:
    """Analyze each track; pick best single piano-range candidate."""
    p = Path(path)
    mid = mido.MidiFile(str(p))
    scored: list[TrackScore] = []
    for i, track in enumerate(mid.tracks):
        ts = _score_track(i, track)
        if ts is not None:
            scored.append(ts)

    best: int | None = None
    if scored:
        # Prefer a clear single strong track: highest score, break ties by pct then notes.
        ranked = sorted(
            scored,
            key=lambda t: (t.score, t.pct_in_range, t.note_ons),
            reverse=True,
        )
        best = ranked[0].index

    return MidiAnalysis(path=p, tracks=scored, best_track=best)
