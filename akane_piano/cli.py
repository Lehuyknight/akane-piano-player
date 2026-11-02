"""CLI for Akane Piano player."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .injector import PianoInjector
from .keymap import MIDI_MAX, MIDI_MIN, MIDI_TO_KEY
from .midi_parse import TimedKeyEvent, list_tracks, parse_midi


def _format_event(ev: TimedKeyEvent) -> str:
    m = ev.mapped
    fold = ""
    if m.midi_original != m.midi_mapped:
        fold = f" (folded from MIDI {m.midi_original})"
    return (
        f"{ev.time_s:8.3f}s  {ev.action.upper():4}  "
        f"key={m.key_id!r:8}  {m.note_name:4}  MIDI {m.midi_mapped}{fold}"
    )


def dry_run(events: list[TimedKeyEvent]) -> None:
    print(f"# Dry-run: {len(events)} key events (no inject)")
    print(f"# Range playable: MIDI {MIDI_MIN}–{MIDI_MAX} ({len(MIDI_TO_KEY)} keys)")
    if not events:
        print("(empty)")
        return
    print(f"# Duration ≈ {events[-1].time_s:.3f}s")
    for ev in events:
        print(_format_event(ev))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="akane-piano",
        description=(
            "Play a local MIDI file as NTE Akane Piano QWERTY keystrokes. "
            "Offline / private use only — see README ToS warning."
        ),
    )
    p.add_argument("midi", nargs="?", help="Path to .mid / .midi file")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print timed key timeline to console; do not inject keys",
    )
    p.add_argument(
        "--tempo",
        type=float,
        default=100.0,
        metavar="PCT",
        help="Playback tempo percent (default: 100)",
    )
    p.add_argument(
        "--countdown",
        type=float,
        default=3.0,
        metavar="SEC",
        help="Seconds to wait before inject so you can focus the game (default: 3)",
    )
    p.add_argument(
        "--out-of-range",
        choices=("fold", "skip"),
        default="fold",
        help="Notes outside MIDI 52–87: octave-fold (default) or skip",
    )
    p.add_argument(
        "--track",
        type=int,
        default=None,
        metavar="N",
        help="Use only MIDI track index N (default: merge all)",
    )
    p.add_argument(
        "--list-tracks",
        action="store_true",
        help="List tracks in the MIDI file and exit",
    )
    p.add_argument(
        "--panic-key",
        default="f8",
        help="Hotkey to stop and release all keys (default: f8)",
    )
    p.add_argument(
        "--print-keymap",
        action="store_true",
        help="Print the hard-coded Piano key map and exit",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.print_keymap:
        print(f"Piano map MIDI {MIDI_MIN}–{MIDI_MAX} (QWERTY)")
        for midi in sorted(MIDI_TO_KEY):
            name, key = MIDI_TO_KEY[midi]
            print(f"  MIDI {midi:3d}  {name:4}  →  {key}")
        return 0

    if not args.midi:
        build_parser().print_help()
        print("\nError: midi path required (unless --print-keymap).", file=sys.stderr)
        return 2

    path = Path(args.midi)
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 2

    if args.list_tracks:
        for i, name, notes in list_tracks(path):
            print(f"  [{i}] {name!r}  note_events={notes}")
        return 0

    try:
        events = parse_midi(
            path,
            out_of_range=args.out_of_range,
            track=args.track,
            tempo_percent=args.tempo,
        )
    except Exception as exc:
        print(f"Failed to parse MIDI: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        dry_run(events)
        return 0

    injector = PianoInjector(
        countdown_s=args.countdown,
        panic_key=args.panic_key,
    )
    return injector.play(events)


if __name__ == "__main__":
    raise SystemExit(main())
