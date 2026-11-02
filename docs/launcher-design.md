# Akane Piano Launcher — Design

## Understanding summary

- Windows **`.exe` launcher** (CustomTkinter + PyInstaller) để tìm/tải MIDI, chọn bài, chỉnh tùy chọn, rồi inject vào NTE Akane Piano.
- UI **tiếng Việt**.
- Nguồn: **BitMidi** + **FreeMIDI** search/tải; **import local**; panel **Đã tải** (`midi/cache`).
- Lọc: ưu tiên bài có **1 track piano** khớp range **MIDI 52–87** tốt nhất.
- App **bắt buộc chạy Administrator từ đầu** (manifest).
- Non-goals: không bypass paywall MuseScore; không anti-cheat evasion; không auto-focus cửa sổ game.

## Assumptions

- Single-user; MIDI tải về `midi/cache/` (hoặc tương đương) để chơi offline sau đó.
- Copyright / ToS game + nguồn MIDI do người dùng tự chịu.
- Tùy chọn Play giữ parity CLI: tempo, countdown, out-of-range fold/skip, chọn track, panic F8, dry-run (log trong UI).
- BitMidi dùng public API (`/api/midi/search`, `downloadUrl`); MuseScore chỉ HTTP download khi URL cho phép — không login/Pro automation.
- Đóng gói PyInstaller Windows x64; CLI `play.py` vẫn giữ.

## Decision log

| Quyết định | Lựa chọn | Phương án khác | Lý do |
|------------|----------|----------------|-------|
| Dạng app | `.exe` (PyInstaller) | Chỉ script Python | Double-click, kèm Admin |
| UI kit | CustomTkinter | tkinter thuần / WebView | Nhìn app hơn, vẫn Python |
| Ngôn ngữ UI | Tiếng Việt | Anh | Yêu cầu người dùng |
| Nguồn online | BitMidi + FreeMIDI | MuseScore link | FreeMIDI ổn định hơn Pro wall |
| Thư viện local | Cột Đã tải + xóa file | Chỉ sau khi search | Chơi lại nhanh |
| Log | Xóa khi chọn bài + nút Xóa log | Log dài vô hạn | Dễ đọc |
| Lọc range | Ưu tiên 1 track piano khớp 52–87 | Ngưỡng 80% cứng / chỉ sort % | Phù hợp minigame piano |
| Quyền | Require Admin từ đầu | Elevate lúc Play / chỉ cảnh báo | Game elevated → UIPI |

## Architecture

```
[Launcher UI - CustomTkinter]
   │  search / paste URL / import
   ▼
[midi_sources]  BitMidi | MuseScoreLink | LocalFile
   │  download → midi/cache/
   ▼
[midi_analyze]  list tracks, score % in 52–87, pick best piano track
   ▼
[play_session]  parse_midi + PianoInjector (scan-code) trên thread riêng
   │
   ▼
[build]  PyInstaller + requireAdministrator manifest
```

CLI tái sử dụng package hiện có (`parse_midi`, `list_tracks`, `PianoInjector` / scan-code).

## UI & modules

**Cửa sổ chính**

1. Tìm BitMidi + nút Tìm  
2. Dán link MuseScore + nút Tải  
3. Import file `.mid` local  
4. Danh sách kết quả: tên, nguồn, % range, track đề xuất (sort theo điểm)  
5. Tùy chọn: Tempo %, Countdown, Ngoài range, Track, Dry-run, Panic F8  
6. Phát / Dừng + log ngắn  
7. Banner nhắc Admin + focus game khi countdown  

**Module gợi ý**

- `launcher.py` — entry  
- `akane_piano/gui_app.py` — CustomTkinter  
- `akane_piano/sources/bitmidi.py`  
- `akane_piano/sources/musescore_link.py`  
- `akane_piano/analyze.py`  
- `scripts/build_exe.ps1` — PyInstaller + manifest Admin  

## Data flow & errors

- **BitMidi:** search API → chọn → tải `https://bitmidi.com` + `downloadUrl` → cache → analyze.  
- **MuseScore:** thử tải MIDI/zip; 401/403/paywall/HTML → thông báo cần Pro hoặc PD/free, hoặc Import tay.  
- **Analyze:** mỗi track → `%` nốt trong 52–87 + bonus tên/instrument piano + ưu tiên “một track rõ”; auto-track = điểm cao nhất.  
- **Play:** countdown UI → inject thread riêng → F8/Dừng = `release_all`.  
- **Cạnh:** MIDI trống/corrupt, 0 kết quả, mất mạng, đang Phát thì phải Dừng trước khi đổi file.

## Build, test, risks

- Deps thêm: `customtkinter`, `requests`.  
- Test: BitMidi search/tải; MuseScore PD vs Pro; import sample scale; `.exe` Admin → inject / F8.  
- Rủi ro: site đổi API/HTML (tách adapter); CustomTkinter + PyInstaller; anti-cheat có thể nuốt input (ngoài scope).
