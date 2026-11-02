"""CustomTkinter launcher UI (tiếng Việt)."""

from __future__ import annotations

import ctypes
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog
from typing import Any

import customtkinter as ctk

from . import __version__
from .analyze import MidiAnalysis, analyze_midi
from .injector import PianoInjector
from .midi_parse import parse_midi
from .sources.bitmidi import BitMidiHit, download_bitmidi, search_bitmidi
from .sources.freemidi import FreeMidiHit, download_freemidi, search_freemidi
from .sources.local_cache import (
    delete_cached_midi,
    import_local_midi,
    list_cached_midis,
)


def is_admin() -> bool:
    if sys_platform() != "win32":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def sys_platform() -> str:
    import sys

    return sys.platform


@dataclass
class ResultRow:
    title: str
    source: str
    path: Path | None = None
    bitmidi: BitMidiHit | None = None
    freemidi: FreeMidiHit | None = None
    analysis: MidiAnalysis | None = None
    status: str = ""


class AkaneLauncherApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Akane Piano Launcher v{__version__}")
        self.geometry("1100x740")
        self.minsize(960, 660)

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self._ui_q: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._results: list[ResultRow] = []
        self._selected: int | None = None
        self._row_widgets: list[ctk.CTkFrame] = []
        self._lib_widgets: list[ctk.CTkFrame] = []
        self._library_paths: list[Path] = []
        self._play_thread: threading.Thread | None = None
        self._injector: PianoInjector | None = None
        self._stop_play = threading.Event()
        self._current: ResultRow | None = None

        self._build()
        self.after(100, self._drain_ui_queue)
        self._refresh_admin_banner()
        self._refresh_library()

    def _build(self) -> None:
        pad = {"padx": 12, "pady": 6}

        self.admin_banner = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.admin_banner.pack(fill="x", **pad)

        src = ctk.CTkFrame(self)
        src.pack(fill="x", **pad)

        ctk.CTkLabel(src, text="Nguồn").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.source_var = ctk.StringVar(value="Cả hai")
        ctk.CTkOptionMenu(
            src,
            variable=self.source_var,
            values=["Cả hai", "BitMidi", "FreeMIDI"],
            width=120,
        ).grid(row=1, column=0, padx=8, pady=4)

        ctk.CTkLabel(src, text="Tìm MIDI").grid(row=0, column=1, sticky="w", padx=8, pady=4)
        self.search_entry = ctk.CTkEntry(src, placeholder_text="Tên bài / nghệ sĩ…")
        self.search_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        self.search_btn = ctk.CTkButton(src, text="Tìm", width=100, command=self._on_search)
        self.search_btn.grid(row=1, column=2, padx=8, pady=4)

        self.import_btn = ctk.CTkButton(src, text="Import local…", width=120, command=self._on_import)
        self.import_btn.grid(row=1, column=3, padx=8, pady=4)
        src.grid_columnconfigure(1, weight=1)

        lists = ctk.CTkFrame(self)
        lists.pack(fill="both", expand=True, **pad)
        lists.grid_columnconfigure(0, weight=3)
        lists.grid_columnconfigure(1, weight=2)
        lists.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            lists,
            text="Kết quả tìm kiếm (track piano · MIDI 52–87)",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        ctk.CTkLabel(lists, text="Đã tải (midi/cache)", anchor="w").grid(
            row=0, column=1, sticky="ew", padx=8, pady=(8, 4)
        )

        self.list_frame = ctk.CTkScrollableFrame(lists)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=4)

        lib_wrap = ctk.CTkFrame(lists, fg_color="transparent")
        lib_wrap.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=4)
        lib_wrap.grid_rowconfigure(0, weight=1)
        lib_wrap.grid_columnconfigure(0, weight=1)
        self.lib_frame = ctk.CTkScrollableFrame(lib_wrap)
        self.lib_frame.grid(row=0, column=0, sticky="nsew")
        lib_btns = ctk.CTkFrame(lib_wrap, fg_color="transparent")
        lib_btns.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ctk.CTkButton(lib_btns, text="Làm mới", width=90, command=self._refresh_library).pack(
            side="left", padx=2
        )
        ctk.CTkButton(
            lib_btns,
            text="Xóa file",
            width=90,
            fg_color="#8B2942",
            command=self._on_delete_library,
        ).pack(side="left", padx=2)

        opts = ctk.CTkFrame(self)
        opts.pack(fill="x", **pad)
        ctk.CTkLabel(opts, text="Tùy chọn phát").grid(
            row=0, column=0, columnspan=6, sticky="w", padx=8, pady=4
        )

        ctk.CTkLabel(opts, text="Tempo %").grid(row=1, column=0, padx=8, sticky="e")
        self.tempo_var = ctk.StringVar(value="100")
        ctk.CTkEntry(opts, textvariable=self.tempo_var, width=70).grid(row=1, column=1, padx=4)

        ctk.CTkLabel(opts, text="Countdown (s)").grid(row=1, column=2, padx=8, sticky="e")
        self.countdown_var = ctk.StringVar(value="5")
        ctk.CTkEntry(opts, textvariable=self.countdown_var, width=70).grid(row=1, column=3, padx=4)

        ctk.CTkLabel(opts, text="Ngoài range").grid(row=1, column=4, padx=8, sticky="e")
        self.oor_var = ctk.StringVar(value="fold")
        ctk.CTkOptionMenu(opts, variable=self.oor_var, values=["fold", "skip"], width=90).grid(
            row=1, column=5, padx=4
        )

        ctk.CTkLabel(opts, text="Track").grid(row=2, column=0, padx=8, sticky="e")
        self.track_var = ctk.StringVar(value="auto")
        self.track_menu = ctk.CTkOptionMenu(opts, variable=self.track_var, values=["auto"], width=220)
        self.track_menu.grid(row=2, column=1, columnspan=3, sticky="w", padx=4, pady=6)

        self.dry_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opts, text="Dry-run (chỉ log, không bấm phím)", variable=self.dry_var).grid(
            row=2, column=4, columnspan=2, sticky="w", padx=8
        )

        actions = ctk.CTkFrame(self)
        actions.pack(fill="x", **pad)
        self.play_btn = ctk.CTkButton(actions, text="Phát", width=120, command=self._on_play)
        self.play_btn.pack(side="left", padx=8, pady=8)
        self.stop_btn = ctk.CTkButton(
            actions, text="Dừng (F8)", width=120, fg_color="#8B2942", command=self._on_stop
        )
        self.stop_btn.pack(side="left", padx=8, pady=8)
        ctk.CTkButton(actions, text="Xóa log", width=90, command=self._clear_log).pack(
            side="left", padx=8, pady=8
        )
        ctk.CTkLabel(
            actions,
            text="Khi countdown: chuyển focus sang cửa sổ game Piano.",
            anchor="w",
        ).pack(side="left", padx=12)

        self.log = ctk.CTkTextbox(self, height=130)
        self.log.pack(fill="x", padx=12, pady=(0, 12))
        self._log(
            "Sẵn sàng. Tìm BitMidi / FreeMIDI, hoặc Import local.\n"
            "Chọn bài sẽ xóa log cũ. Khuyến nghị chạy Administrator."
        )

        self.search_entry.bind("<Return>", lambda _e: self._on_search())

    def _refresh_admin_banner(self) -> None:
        if is_admin():
            self.admin_banner.configure(
                text="✓ Đang chạy với quyền Administrator",
                text_color=("#1A7F37", "#3DD68C"),
            )
        else:
            self.admin_banner.configure(
                text="⚠ Chưa Admin — nếu game chạy elevated, inject có thể bị chặn. "
                "Hãy mở lại launcher bằng Run as administrator.",
                text_color=("#9A3412", "#FDBA74"),
            )

    def _clear_log(self) -> None:
        self.log.delete("1.0", "end")

    def _log(self, msg: str) -> None:
        self.log.insert("end", msg.rstrip() + "\n")
        self.log.see("end")

    def _post(self, kind: str, payload: Any = None) -> None:
        self._ui_q.put((kind, payload))

    def _drain_ui_queue(self) -> None:
        try:
            while True:
                kind, payload = self._ui_q.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "results":
                    self._results = list(payload)
                    self._selected = 0 if self._results else None
                    self._render_results()
                    if self._selected is not None:
                        self._apply_selection(self._selected, clear_log=False)
                elif kind == "busy":
                    self._set_busy(bool(payload))
                elif kind == "playing":
                    self.play_btn.configure(state="disabled" if payload else "normal")
                elif kind == "library":
                    self._refresh_library()
                elif kind == "select_path":
                    self._select_library_path(Path(payload), clear_log=False)
        except queue.Empty:
            pass
        self.after(100, self._drain_ui_queue)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for w in (self.search_btn, self.import_btn):
            w.configure(state=state)

    def _fmt_analysis(self, a: MidiAnalysis) -> str:
        best = a.best
        if best is None:
            return "Không có nốt"
        piano = " · piano?" if best.piano_hint else ""
        return f"track {best.index} “{best.name}” · {best.pct_in_range:.0f}% in-range{piano}"

    def _render_results(self) -> None:
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()
        for i, row in enumerate(self._results):
            fr = ctk.CTkFrame(self.list_frame, fg_color=("gray85", "gray25"))
            fr.pack(fill="x", pady=3, padx=2)
            detail = row.status or ("Chưa tải" if row.path is None else "…")
            label = ctk.CTkLabel(
                fr,
                text=f"[{row.source}] {row.title}\n{detail}",
                anchor="w",
                justify="left",
            )
            label.pack(side="left", fill="x", expand=True, padx=8, pady=6)
            btn = ctk.CTkButton(
                fr,
                text="Chọn",
                width=70,
                command=lambda idx=i: self._apply_selection(idx, clear_log=True),
            )
            btn.pack(side="right", padx=8, pady=6)
            if row.path is None and (row.bitmidi is not None or row.freemidi is not None):
                dl = ctk.CTkButton(
                    fr,
                    text="Tải",
                    width=70,
                    command=lambda idx=i: self._download_result(idx),
                )
                dl.pack(side="right", padx=4, pady=6)
            self._row_widgets.append(fr)
            if self._selected == i:
                fr.configure(fg_color=("gray75", "gray35"))

    def _refresh_library(self) -> None:
        for w in self._lib_widgets:
            w.destroy()
        self._lib_widgets.clear()
        self._library_paths = list_cached_midis()
        if not self._library_paths:
            empty = ctk.CTkLabel(self.lib_frame, text="(chưa có file)", anchor="w")
            empty.pack(fill="x", padx=8, pady=8)
            self._lib_widgets.append(empty)
            return
        current_path = self._current.path.resolve() if self._current and self._current.path else None
        for p in self._library_paths:
            fr = ctk.CTkFrame(self.lib_frame, fg_color=("gray85", "gray25"))
            fr.pack(fill="x", pady=2, padx=2)
            ctk.CTkLabel(fr, text=p.name, anchor="w").pack(
                side="left", fill="x", expand=True, padx=8, pady=4
            )
            ctk.CTkButton(
                fr,
                text="Chọn",
                width=60,
                command=lambda path=p: self._select_library_path(path, clear_log=True),
            ).pack(side="right", padx=6, pady=4)
            if current_path and p.resolve() == current_path:
                fr.configure(fg_color=("gray75", "gray35"))
            self._lib_widgets.append(fr)

    def _apply_track_menu(self, analysis: MidiAnalysis | None) -> None:
        values = ["auto"]
        if analysis:
            for t in sorted(analysis.tracks, key=lambda x: x.score, reverse=True):
                values.append(f"{t.index}: {t.name} ({t.pct_in_range:.0f}%)")
        self.track_menu.configure(values=values)
        self.track_var.set("auto")

    def _apply_selection(self, idx: int, *, clear_log: bool) -> None:
        if idx < 0 or idx >= len(self._results):
            return
        if clear_log:
            self._clear_log()
        self._selected = idx
        self._render_results()
        row = self._results[idx]
        self._current = row
        self._apply_track_menu(row.analysis)
        self._refresh_library()
        self._log(f"Đã chọn: {row.title}" + (f" → {row.path}" if row.path else " (chưa tải)"))

    def _select_library_path(self, path: Path, *, clear_log: bool) -> None:
        if clear_log:
            self._clear_log()

        def work() -> None:
            self._post("busy", True)
            try:
                analysis = analyze_midi(path)
                row = ResultRow(
                    title=path.name,
                    source="Đã tải",
                    path=path,
                    analysis=analysis,
                    status=self._fmt_analysis(analysis),
                )
                self._post("log", f"Đã chọn từ cache: {path.name}")
                self._post("log", self._fmt_analysis(analysis))

                def apply() -> None:
                    self._current = row
                    self._selected = None
                    self._render_results()
                    self._apply_track_menu(analysis)
                    self._refresh_library()

                self.after(0, apply)
            except Exception as exc:
                self._post("log", f"Lỗi đọc cache: {exc}")
            finally:
                self._post("busy", False)

        threading.Thread(target=work, daemon=True).start()

    def _on_delete_library(self) -> None:
        if not self._current or not self._current.path:
            self._log("Chọn một file trong Đã tải trước khi xóa.")
            return
        path = self._current.path
        try:
            delete_cached_midi(path)
            self._current = None
            self._refresh_library()
            self._log(f"Đã xóa {path.name}")
        except Exception as exc:
            self._log(f"Không xóa được: {exc}")

    def _resolve_track(self) -> int | None:
        raw = self.track_var.get().strip()
        if raw == "auto":
            if self._current and self._current.analysis:
                return self._current.analysis.best_track
            return None
        if ":" in raw:
            return int(raw.split(":", 1)[0])
        return int(raw)

    def _on_search(self) -> None:
        q = self.search_entry.get().strip()
        if not q:
            self._log("Nhập từ khóa trước.")
            return
        src = self.source_var.get()

        def work() -> None:
            self._post("busy", True)
            self._post("log", f"Đang tìm ({src}): {q!r}…")
            rows: list[ResultRow] = []
            try:
                if src in ("Cả hai", "BitMidi"):
                    try:
                        for h in search_bitmidi(q):
                            rows.append(
                                ResultRow(
                                    title=h.name,
                                    source="BitMidi",
                                    bitmidi=h,
                                    status="Chưa tải",
                                )
                            )
                    except Exception as exc:
                        self._post("log", f"BitMidi lỗi: {exc}")
                if src in ("Cả hai", "FreeMIDI"):
                    try:
                        for h in search_freemidi(q):
                            rows.append(
                                ResultRow(
                                    title=h.name,
                                    source="FreeMIDI",
                                    freemidi=h,
                                    status="Chưa tải",
                                )
                            )
                    except Exception as exc:
                        self._post("log", f"FreeMIDI lỗi: {exc}")
                self._post("results", rows)
                self._post("log", f"Tìm thấy {len(rows)} kết quả.")
            finally:
                self._post("busy", False)

        threading.Thread(target=work, daemon=True).start()

    def _download_result(self, idx: int) -> None:
        row = self._results[idx]
        bit = row.bitmidi
        free = row.freemidi
        if bit is None and free is None:
            return

        def work() -> None:
            self._post("busy", True)
            title = bit.name if bit else free.name  # type: ignore[union-attr]
            self._post("log", f"Đang tải {title}…")
            try:
                if bit is not None:
                    path = download_bitmidi(bit)
                    match_id = ("bit", bit.id)
                else:
                    assert free is not None
                    path = download_freemidi(free)
                    match_id = ("free", free.id)
                analysis = analyze_midi(path)
                status = self._fmt_analysis(analysis)
                updated: list[ResultRow] = []
                for r in self._results:
                    hit_bit = r.bitmidi and match_id == ("bit", r.bitmidi.id)
                    hit_free = r.freemidi and match_id == ("free", r.freemidi.id)
                    if hit_bit or hit_free:
                        updated.append(
                            ResultRow(
                                title=r.title,
                                source=r.source,
                                path=path,
                                bitmidi=r.bitmidi,
                                freemidi=r.freemidi,
                                analysis=analysis,
                                status=status,
                            )
                        )
                    else:
                        updated.append(r)
                ranked = sorted(
                    updated,
                    key=lambda r: (
                        r.analysis.best.score if r.analysis and r.analysis.best else -1
                    ),
                    reverse=True,
                )
                self._post("results", ranked)
                self._post("library", None)
                self._post("log", f"Đã tải → {path}")
            except Exception as exc:
                self._post("log", f"Lỗi tải: {exc}")
            finally:
                self._post("busy", False)

        threading.Thread(target=work, daemon=True).start()

    def _on_import(self) -> None:
        path = filedialog.askopenfilename(
            title="Chọn file MIDI",
            filetypes=[("MIDI", "*.mid *.midi"), ("All", "*.*")],
        )
        if not path:
            return

        def work() -> None:
            self._post("busy", True)
            try:
                dest = import_local_midi(path)
                analysis = analyze_midi(dest)
                row = ResultRow(
                    title=dest.name,
                    source="Local",
                    path=dest,
                    analysis=analysis,
                    status=self._fmt_analysis(analysis),
                )
                self._post("results", [row])
                self._post("library", None)
                self._post("log", f"Đã import → {dest}")
            except Exception as exc:
                self._post("log", f"Lỗi import: {exc}")
            finally:
                self._post("busy", False)

        threading.Thread(target=work, daemon=True).start()

    def _on_stop(self) -> None:
        self._stop_play.set()
        if self._injector is not None:
            self._injector.request_stop()
            self._injector.release_all()
        self._log("Đã gửi lệnh dừng.")

    def _on_play(self) -> None:
        if self._play_thread and self._play_thread.is_alive():
            self._log("Đang phát — bấm Dừng trước.")
            return
        row = self._current
        if row is None:
            self._log("Chọn một bài (kết quả hoặc Đã tải) trước.")
            return
        if row.path is None:
            self._log("Bài này chưa tải — bấm Tải trước.")
            return
        try:
            tempo = float(self.tempo_var.get())
            countdown = float(self.countdown_var.get())
        except ValueError:
            self._log("Tempo / countdown phải là số.")
            return
        oor = self.oor_var.get()
        if oor not in ("fold", "skip"):
            oor = "fold"
        track = self._resolve_track()
        dry = bool(self.dry_var.get())
        path = row.path
        self._stop_play.clear()

        def work() -> None:
            self._post("playing", True)
            try:
                events = parse_midi(
                    path,
                    out_of_range=oor,  # type: ignore[arg-type]
                    track=track,
                    tempo_percent=tempo,
                )
                self._post(
                    "log",
                    f"Parse OK: {len(events)} sự kiện · track={track!r} · dry={dry}",
                )
                if dry:
                    for ev in events[:40]:
                        self._post(
                            "log",
                            f"  {ev.time_s:7.3f}s {ev.action:4} {ev.mapped.key_id!r} {ev.mapped.note_name}",
                        )
                    if len(events) > 40:
                        self._post("log", f"  … (+{len(events) - 40} sự kiện)")
                    self._post("log", "Dry-run xong.")
                    return
                inj = PianoInjector(
                    countdown_s=countdown,
                    panic_key="f8",
                    on_log=lambda m: self._post("log", m),
                )
                self._injector = inj
                code = inj.play(events)
                self._post("log", f"Kết thúc phát (code={code}).")
            except Exception as exc:
                self._post("log", f"Lỗi phát: {exc}")
            finally:
                self._injector = None
                self._post("playing", False)

        self._play_thread = threading.Thread(target=work, daemon=True)
        self._play_thread.start()


def run_app() -> None:
    app = AkaneLauncherApp()
    app.mainloop()
