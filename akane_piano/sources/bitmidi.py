"""BitMidi public search + download."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

from .local_cache import save_bytes

_BASE = "https://bitmidi.com"
_UA = {"User-Agent": "akane-piano-player/0.2 (+local launcher)"}


@dataclass(frozen=True)
class BitMidiHit:
    id: int
    name: str
    download_url: str  # absolute URL
    page_url: str


def search_bitmidi(query: str, *, page: int = 0, page_size: int = 15) -> list[BitMidiHit]:
    q = query.strip()
    if not q:
        return []
    r = requests.get(
        f"{_BASE}/api/midi/search",
        params={"q": q, "page": page, "pageSize": page_size},
        headers=_UA,
        timeout=30,
    )
    r.raise_for_status()
    payload = r.json()
    results = (payload.get("result") or {}).get("results") or []
    hits: list[BitMidiHit] = []
    for item in results:
        rel = item.get("downloadUrl") or ""
        if not rel:
            continue
        dl = rel if rel.startswith("http") else f"{_BASE}{rel}"
        page_rel = item.get("url") or ""
        page_url = page_rel if str(page_rel).startswith("http") else f"{_BASE}{page_rel}"
        hits.append(
            BitMidiHit(
                id=int(item["id"]),
                name=str(item.get("name") or f"id-{item['id']}"),
                download_url=dl,
                page_url=page_url,
            )
        )
    return hits


def download_bitmidi(hit: BitMidiHit) -> Path:
    r = requests.get(hit.download_url, headers=_UA, timeout=60)
    r.raise_for_status()
    ctype = (r.headers.get("Content-Type") or "").lower()
    data = r.content
    if not data:
        raise ValueError("BitMidi trả về file rỗng")
    if "html" in ctype or data[:1] == b"<":
        raise ValueError("BitMidi không trả về MIDI (có thể bị chặn)")
    if data[:4] not in (b"MThd",) and b"MThd" not in data[:64]:
        # Some servers omit strict type; still try save if looks binary
        if data[:4] == b"PK\x03\x04":
            raise ValueError("BitMidi trả về ZIP — chưa hỗ trợ giải nén nguồn này")
    return save_bytes(data, hit.name)
