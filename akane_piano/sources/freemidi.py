"""Search / download MIDI from freemidi.org."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import requests

from .local_cache import save_bytes

_BASE = "https://freemidi.org"
_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

_SONG_HREF_RE = re.compile(
    r"href=download3-(\d+)-([^\s>]+)\s*>(?:\s*)([^<]*)</a>",
    re.I,
)
_SONG_HREF_LOOSE_RE = re.compile(r"href=download3-(\d+)([^\s>]*)", re.I)
_ARTIST_HREF_RE = re.compile(
    r'href="?/artist-(\d+)-([^"\'>\s]+)"?[^>]*>([^<]+)</a>',
    re.I,
)
_TITLE_ATTR_RE = re.compile(
    r'href=download3-(\d+)[^\s>]*\s+title="([^"]+)"',
    re.I,
)


@dataclass(frozen=True)
class FreeMidiHit:
    id: int
    title: str
    artist: str

    @property
    def name(self) -> str:
        if self.artist:
            return f"{self.title} — {self.artist}"
        return self.title

    @property
    def page_url(self) -> str:
        return f"{_BASE}/download3-{self.id}"

    @property
    def getter_url(self) -> str:
        return f"{_BASE}/getter-{self.id}"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_UA)
    return s


def _slug_to_title(slug: str) -> str:
    s = slug.strip("-_")
    if not s:
        return ""
    return re.sub(r"[-_]+", " ", s).strip().title()


def _parse_songs(html: str, default_artist: str = "") -> list[FreeMidiHit]:
    by_id: dict[int, FreeMidiHit] = {}

    for m in _TITLE_ATTR_RE.finditer(html):
        sid = int(m.group(1))
        title = m.group(2).strip() or f"id-{sid}"
        by_id[sid] = FreeMidiHit(id=sid, title=title, artist=default_artist)

    for m in _SONG_HREF_RE.finditer(html):
        sid = int(m.group(1))
        slug = m.group(2)
        text = (m.group(3) or "").strip()
        if text.lower().startswith("error"):
            text = ""
        # Freemidi sometimes lists untitled stubs: download3-123--artist
        if not text and re.match(r"^-+", slug or ""):
            continue
        title = text or _slug_to_title(slug) or f"id-{sid}"
        prev = by_id.get(sid)
        artist = default_artist
        if prev and prev.artist:
            artist = prev.artist
        by_id[sid] = FreeMidiHit(id=sid, title=title, artist=artist)

    if not by_id:
        for m in _SONG_HREF_LOOSE_RE.finditer(html):
            sid = int(m.group(1))
            slug = (m.group(2) or "").lstrip("-")
            title = _slug_to_title(slug) or f"id-{sid}"
            by_id[sid] = FreeMidiHit(id=sid, title=title, artist=default_artist)

    return list(by_id.values())


def _parse_artists(html: str) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    seen: set[int] = set()
    for m in _ARTIST_HREF_RE.finditer(html):
        aid = int(m.group(1))
        if aid in seen:
            continue
        seen.add(aid)
        slug = m.group(2)
        name = (m.group(3) or "").strip() or _slug_to_title(slug)
        out.append((aid, slug, name))
    return out


def search_freemidi(query: str, *, max_songs: int = 40) -> list[FreeMidiHit]:
    q = query.strip()
    if not q:
        return []
    sess = _session()
    r = sess.get(f"{_BASE}/search", params={"q": q}, timeout=30)
    r.raise_for_status()
    html = r.text

    songs = _parse_songs(html)
    by_id = {s.id: s for s in songs}

    # Expand top artist pages for more tracks
    for aid, slug, name in _parse_artists(html)[:5]:
        if len(by_id) >= max_songs:
            break
        ar = sess.get(f"{_BASE}/artist-{aid}-{slug}", timeout=30)
        if ar.status_code != 200:
            continue
        for hit in _parse_songs(ar.text, default_artist=name):
            by_id.setdefault(hit.id, hit)
            if len(by_id) >= max_songs:
                break

    hits = [
        h
        for h in by_id.values()
        if h.title.strip().lower() != (h.artist or "").strip().lower()
    ]
    # Prefer titles that mention the query
    ql = q.lower()

    def rank(h: FreeMidiHit) -> tuple[int, str]:
        blob = f"{h.title} {h.artist}".lower()
        return (0 if ql in blob else 1, h.title.lower())

    hits.sort(key=rank)
    return hits[:max_songs]


def download_freemidi(hit: FreeMidiHit) -> Path:
    sess = _session()
    page = hit.page_url
    pr = sess.get(page, timeout=30)
    pr.raise_for_status()
    gr = sess.get(
        hit.getter_url,
        headers={**_UA, "Referer": page},
        timeout=60,
    )
    gr.raise_for_status()
    data = gr.content
    if not data or data[:4] != b"MThd":
        # retry without following odd redirects
        gr2 = sess.get(
            hit.getter_url,
            headers={**_UA, "Referer": page},
            allow_redirects=False,
            timeout=60,
        )
        data = gr2.content
    if not data or data[:4] != b"MThd":
        raise ValueError("FreeMIDI không trả về file MIDI hợp lệ")
    fname = f"{hit.title}"
    if hit.artist:
        fname = f"{hit.title} - {hit.artist}"
    return save_bytes(data, f"{fname}.mid")
