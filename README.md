# Akane Piano Player (MVP)

Local MIDI → QWERTY key inject for the **Neverness To Everness** Akane **Piano** minigame (E3–D#6 / MIDI 52–87).

- **Windows native**, QWERTY layout  
- **Python 3.10+**  
- **Local `.mid` files only** (no web search/download)  
- **Countdown then Start** — you focus the game yourself (no auto window focus)  
- **Offline / private use**

## ToS / account warning

Sending synthetic keystrokes into an online game client may violate the game’s Terms of Service or risk account action. **Use only offline / private sessions if policy allows.** This tool does **not** implement anti-detect, obfuscation, or bypass. You are responsible for how you use it.

## Install (Windows)

```powershell
cd akane-piano-player
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
# On Windows this installs mido + pynput. Dry-run only needs mido.
```

## Run

**Dry-run** (print timed key timeline — safe anywhere):

```powershell
python play.py samples\scale_e3_ds6.mid --dry-run
# or
python -m akane_piano samples\scale_e3_ds6.mid --dry-run
```

**Inject** (focus the game first during the countdown):

1. Open NTE, enter Akane Piano mode.  
2. Alt-tab back to the terminal, run:

```powershell
python play.py path\to\song.mid
```

3. Immediately focus the **game** window (tool does **not** steal focus).  
4. Default **3s countdown**, then keys fire via Windows **scan-code** `SendInput` (DirectInput-friendly; not Unicode/VK_PACKET).  
5. **F8** = panic: stop playback and release all held keys.

### If keys appear in Notepad but not in-game

- Confirm the **game** window is focused when countdown hits 0 (not the terminal).  
- If the game was launched **as Administrator**, run the terminal **as Administrator** too (UIPI blocks lower→higher inject).  
- Prefer a **US QWERTY** physical layout mentally: map is by key *position* (scan code), not typed character / IME.  
- Some clients ignore synthetic input entirely; this tool does not bypass anti-cheat.

### Useful flags

| Flag | Meaning |
|------|---------|
| `--dry-run` | Timeline only, no inject |
| `--tempo 80` | Play at 80% speed |
| `--countdown 5` | Wait 5s before inject |
| `--out-of-range fold\|skip` | Notes outside MIDI 52–87 (default: `fold`) |
| `--track N` | Single MIDI track |
| `--list-tracks` | Show tracks and exit |
| `--panic-key f9` | Change panic hotkey |
| `--print-keymap` | Dump hard-coded Piano map |

## Key map (summary)

Three chromatic rows on the Piano UI:

| Row | Keys | Notes |
|-----|------|-------|
| High | `1`…`0` `-` `=` | E5–D#6 |
| Mid | `Q`…`P` `[` `]` | E4–D#5 |
| Low | `A`…`L` `;` `'` `Enter` | E3–D#4 |

Hold = sustain (keydown / keyup). Verify once in-game.

## Smoke test (in-game)

1. `--dry-run` on `samples/scale_e3_ds6.mid` — expect 36 chromatic notes + final chord.  
2. Inject gamut: each key E3→D#6 should sound once.  
3. Confirm polyphony on the closing C–E–G chord.  
4. Press **F8** mid-scale — all keys release, playback stops.  
5. Optional: `--tempo 50` for easier timing checks; `--out-of-range skip` on a MIDI with notes below E3 / above D#6.

## Launcher (GUI + .exe)

Desktop app (CustomTkinter, UI tiếng Việt): tìm **BitMidi** / **FreeMIDI**, import local, danh sách MIDI đã tải, lọc track piano theo range 52–87, rồi Phát.

```powershell
# Dev
.\.venv\Scripts\activate
pip install -r requirements.txt
python launcher.py

# Build .exe (bắt buộc UAC Admin)
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1
# → .\dist\AkanePianoLauncher\AkanePianoLauncher.exe
```

MIDI tải về `midi/cache/` (hiện ở cột **Đã tải** trong launcher).

## Layout

```
akane-piano-player/
  play.py                 # CLI entry
  launcher.py             # GUI entry
  requirements.txt
  README.md
  docs/launcher-design.md
  scripts/build_exe.ps1
  akane_piano/            # package (+ gui, sources, analyze)
  samples/                # sample MIDI
  midi/                   # local + cache
```

## Not in this MVP

Guitar Chord/Fret, MusicXML, OCR, auto window focus, anti-cheat evasion, MuseScore.
