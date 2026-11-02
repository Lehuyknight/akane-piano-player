"""Keyboard inject via Windows scan-code SendInput + countdown + panic release."""

from __future__ import annotations

import sys
import threading
import time
from typing import Callable

from .midi_parse import TimedKeyEvent

# Lazy import so dry-run works without pynput display/backend quirks on CI/Linux headless.


def _resolve_panic_key(name: str):
    from pynput.keyboard import Key

    n = name.strip().lower()
    mapping = {
        "f8": Key.f8,
        "f9": Key.f9,
        "f10": Key.f10,
        "esc": Key.esc,
        "escape": Key.esc,
    }
    if n not in mapping:
        raise ValueError(f"unsupported panic key: {name!r} (try f8, f9, f10, esc)")
    return mapping[n]


def _require_pynput() -> None:
    try:
        import pynput  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "pynput is required for inject mode. On Windows:\n"
            "  pip install pynput\n"
            "Or use --dry-run to print the timeline without injecting."
        ) from exc


class PianoInjector:
    """Schedule key down/up with optional countdown and panic hotkey."""

    def __init__(
        self,
        *,
        countdown_s: float = 3.0,
        panic_key: str = "f8",
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self.countdown_s = max(0.0, countdown_s)
        self.panic_key_name = panic_key
        self._log = on_log or (lambda m: print(m, flush=True))
        self._held: set[str] = set()
        self._stop = threading.Event()
        self._listener = None
        self._backend_ready = False

    def _ensure_backend(self) -> None:
        if self._backend_ready:
            return
        _require_pynput()
        if sys.platform != "win32":
            raise SystemExit(
                "Inject mode needs Windows scan-code SendInput "
                f"(this OS is {sys.platform!r}). Use --dry-run elsewhere."
            )
        # Import once so missing symbols fail before countdown.
        from .win32_scancode import send_scancode  # noqa: F401

        self._backend_ready = True

    def press(self, key_id: str) -> None:
        self._ensure_backend()
        from .win32_scancode import send_scancode

        if key_id not in self._held:
            send_scancode(key_id, press=True)
            self._held.add(key_id)

    def release(self, key_id: str) -> None:
        self._ensure_backend()
        from .win32_scancode import send_scancode

        if key_id in self._held:
            try:
                send_scancode(key_id, press=False)
            except Exception:
                pass
            self._held.discard(key_id)

    def release_all(self) -> None:
        for key_id in list(self._held):
            self.release(key_id)

    def request_stop(self) -> None:
        self._stop.set()

    def _start_panic_listener(self) -> None:
        from pynput.keyboard import Listener

        panic = _resolve_panic_key(self.panic_key_name)

        def on_press(key):
            if key == panic:
                self._log(f"[panic] {self.panic_key_name.upper()} — releasing all keys")
                self.request_stop()
                self.release_all()
                return False  # stop listener
            return None

        self._listener = Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def _stop_panic_listener(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def play(self, events: list[TimedKeyEvent]) -> int:
        """
        Countdown, then inject events. Returns 0 on success, 1 if panicked/stopped,
        2 if no events.
        """
        if not events:
            self._log("No events to play.")
            return 2

        self._ensure_backend()
        self._stop.clear()
        self._start_panic_listener()
        try:
            if self.countdown_s > 0:
                self._log(
                    f"Focus the game window now. Starting in {self.countdown_s:.1f}s… "
                    f"(scan-code inject; panic: {self.panic_key_name.upper()})"
                )
                deadline = time.perf_counter() + self.countdown_s
                while not self._stop.is_set():
                    remaining = deadline - time.perf_counter()
                    if remaining <= 0:
                        break
                    self._log(f"  {remaining:.1f}…")
                    time.sleep(min(1.0, remaining))
                if self._stop.is_set():
                    self.release_all()
                    return 1
            else:
                self._log(f"Starting now (panic: {self.panic_key_name.upper()})")

            self._log("Playing…")
            t0 = time.perf_counter()
            for ev in events:
                if self._stop.is_set():
                    break
                target = t0 + ev.time_s
                while True:
                    if self._stop.is_set():
                        break
                    now = time.perf_counter()
                    delay = target - now
                    if delay <= 0:
                        break
                    # Sleep most of the wait; spin the last ~2ms for tighter timing
                    if delay > 0.003:
                        time.sleep(delay - 0.002)
                    else:
                        while time.perf_counter() < target and not self._stop.is_set():
                            pass
                        break
                if self._stop.is_set():
                    break
                if ev.action == "down":
                    self.press(ev.mapped.key_id)
                else:
                    self.release(ev.mapped.key_id)

            self.release_all()
            if self._stop.is_set():
                self._log("Stopped.")
                return 1
            self._log("Done.")
            return 0
        finally:
            self.release_all()
            self._stop_panic_listener()
