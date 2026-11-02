"""Local MIDI cache helpers next to the project / frozen exe."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def cache_dir() -> Path:
    d = app_root() / "midi" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(name: str, suffix: str = ".mid") -> str:
    base = re.sub(r"[^\w\-_. ]+", "_", name, flags=re.UNICODE).strip(" ._")
    if not base:
        base = "song"
    if not base.lower().endswith((".mid", ".midi")):
        base = f"{base}{suffix}"
    return base[:120]


def save_bytes(data: bytes, preferred_name: str) -> Path:
    path = cache_dir() / _safe_name(preferred_name)
    # Avoid clobbering different content with same name
    if path.exists() and path.read_bytes() != data:
        stem = path.stem
        n = 2
        while True:
            cand = cache_dir() / f"{stem}_{n}{path.suffix}"
            if not cand.exists() or cand.read_bytes() == data:
                path = cand
                break
            n += 1
    path.write_bytes(data)
    return path


def import_local_midi(src: str | Path) -> Path:
    src_p = Path(src)
    if not src_p.is_file():
        raise FileNotFoundError(str(src_p))
    dest = cache_dir() / _safe_name(src_p.name)
    if dest.resolve() != src_p.resolve():
        shutil.copy2(src_p, dest)
    return dest


def list_cached_midis() -> list[Path]:
    """MIDI đã tải/import trong midi/cache, mới nhất trước."""
    files = [
        p
        for p in cache_dir().iterdir()
        if p.is_file() and p.suffix.lower() in {".mid", ".midi"}
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def delete_cached_midi(path: str | Path) -> None:
    p = Path(path)
    root = cache_dir().resolve()
    rp = p.resolve()
    if root not in rp.parents and rp != root:
        raise ValueError("Chỉ xóa được file trong midi/cache")
    if rp.is_file():
        rp.unlink()
