"""
PC-DECK 7710 — Pioneer-style OEM head-unit display for PC audio.

Captures whatever the machine is playing (Spotify, browser, games) via WASAPI
loopback, runs a 13-band analysis + oscilloscope feed, reads now-playing
metadata/album art/playback position from Windows SMTC, looks up lyrics, and
streams it all to the faceplate UI over a WebSocket at http://127.0.0.1:7710
"""

import asyncio
import base64
import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import numpy as np
import pyaudiowpatch as pyaudio
from aiohttp import web, WSMsgType

PORT = 7710
WEB = Path(__file__).parent / "web"

# The two lookups are the only things on the deck that leave the machine, and
# both send just title/artist/album (plus duration for lyrics). Set either to
# False to keep the deck that much more offline.
#
# LYRICS: lrclib.net, an open no-key lyrics database, for the LRC.
# ART: SMTC hands us no thumbnail for a lot of players — most browsers, plenty
# of desktop apps — which leaves the album art screen empty. When that happens,
# fall back to the free iTunes Search API for the sleeve. Never used when the
# player gave us art of its own.
LYRICS_ENABLED = True
LYRICS_API = "https://lrclib.net/api"
ART_LOOKUP_ENABLED = True
ART_API = "https://itunes.apple.com/search"
ART_MAX_BYTES = 2_000_000
DECK_UA = "pc-deck-7710 (local head-unit display)"

# 13-band analyzer, 63 Hz .. 16 kHz (classic head-unit spacing)
BAND_CENTERS = [63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300, 10000, 16000]
FFT_N = 4096
BLOCK = 1024
DB_FLOOR = -58.0          # band level mapped to 0
DB_TILT = 1.6             # dB of lift per band index (music has less HF energy)
BROADCAST_FPS = 30

# ---------------------------------------------------------------- shared state
_lock = threading.Lock()
_audio = {
    "spec": [0.0] * 13,     # mono bands 0..1
    "specL": [0.0] * 13,
    "specR": [0.0] * 13,
    "rmsL": -70.0,          # dBFS
    "rmsR": -70.0,
    "wave": [0.0] * 96,     # mono scope trace -1..1
    "clip": False,
    "alive": False,         # capture stream healthy
}
_meta = {
    "type": "meta",
    "title": "",
    "artist": "",
    "album": "",
    "app": "",
    "status": "stopped",
    "art": None,            # data URL or None
}
_pos = {                    # playback head, pushed once a second
    "type": "pos",
    "position": 0.0,        # seconds into the track
    "duration": 0.0,        # 0 when unknown
    "status": "stopped",
}
_art_tried = ""             # track key the sleeve lookup has already run for
_lyrics = {                 # last lyrics lookup result
    "type": "lyrics",
    "key": "",              # title\x1fartist the lines belong to
    "state": "idle",        # idle | searching | ok | none
    "synced": False,
    "lines": [],            # [[seconds|null, "text"], ...]
    "source": "",
}
_clients: set = set()


# ---------------------------------------------------------------- audio capture
def _band_slices(rate: int):
    """Per-band rfft bin ranges using geometric-mean edges between centers."""
    freqs = np.fft.rfftfreq(FFT_N, 1.0 / rate)
    edges = [BAND_CENTERS[0] / 1.35]
    for a, b in zip(BAND_CENTERS, BAND_CENTERS[1:]):
        edges.append((a * b) ** 0.5)
    edges.append(min(BAND_CENTERS[-1] * 1.35, rate / 2 - 1))
    out = []
    for lo, hi in zip(edges, edges[1:]):
        idx = np.where((freqs >= lo) & (freqs < hi))[0]
        if len(idx) == 0:
            idx = np.array([int(np.argmin(np.abs(freqs - (lo + hi) / 2)))])
        out.append(idx)
    return out


def _norm_bands(power: np.ndarray, slices) -> list:
    vals = []
    for i, idx in enumerate(slices):
        p = float(np.mean(power[idx]) + 1e-12)
        db = 10.0 * np.log10(p) + i * DB_TILT
        v = (db - DB_FLOOR) / (0.0 - DB_FLOOR)
        vals.append(round(min(1.0, max(0.0, v)) ** 0.85, 3))
    return vals


def audio_thread():
    """Capture default-output loopback forever; reopen on any device change/error."""
    window = np.hanning(FFT_N).astype(np.float32)
    # power spectrum of a full-scale sine through this window ~= (N/4)^2 * 2/N;
    # fold the window+length gain into one reference so band dB ~ dBFS-ish
    ref = (np.sum(window) / 2.0) ** 2
    while True:
        p = stream = None
        try:
            p = pyaudio.PyAudio()
            lb = p.get_default_wasapi_loopback()
            rate, ch = int(lb["defaultSampleRate"]), max(1, lb["maxInputChannels"])
            slices = _band_slices(rate)
            bufL = np.zeros(FFT_N, dtype=np.float32)
            bufR = np.zeros(FFT_N, dtype=np.float32)
            stream = p.open(format=pyaudio.paInt16, channels=ch, rate=rate,
                            input=True, input_device_index=lb["index"],
                            frames_per_buffer=BLOCK)
            print(f"[audio] loopback: {lb['name']} @ {rate} Hz x{ch}")
            with _lock:
                _audio["alive"] = True
            while True:
                raw = stream.read(BLOCK, exception_on_overflow=False)
                x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                x = x.reshape(-1, ch)
                l = x[:, 0]
                r = x[:, 1] if ch > 1 else x[:, 0]
                mono = (l + r) * 0.5
                bufL = np.concatenate((bufL[len(l):], l))
                bufR = np.concatenate((bufR[len(r):], r))
                mid = (bufL + bufR) * 0.5

                sL = np.abs(np.fft.rfft(bufL * window)) ** 2 / ref
                sR = np.abs(np.fft.rfft(bufR * window)) ** 2 / ref
                sM = np.abs(np.fft.rfft(mid * window)) ** 2 / ref

                step = max(1, len(mono) // 96)
                wave = mono[::step][:96]
                with _lock:
                    _audio["spec"] = _norm_bands(sM, slices)
                    _audio["specL"] = _norm_bands(sL, slices)
                    _audio["specR"] = _norm_bands(sR, slices)
                    _audio["rmsL"] = round(20 * np.log10(float(np.sqrt(np.mean(l * l))) + 1e-9), 1)
                    _audio["rmsR"] = round(20 * np.log10(float(np.sqrt(np.mean(r * r))) + 1e-9), 1)
                    _audio["wave"] = [round(float(v), 3) for v in wave]
                    _audio["clip"] = bool(np.max(np.abs(x)) > 0.985)
        except Exception as e:
            print(f"[audio] stream lost ({e}); retrying in 2s")
            with _lock:
                _audio["alive"] = False
                _audio["spec"] = [0.0] * 13
                _audio["specL"] = [0.0] * 13
                _audio["specR"] = [0.0] * 13
                _audio["rmsL"] = _audio["rmsR"] = -70.0
            time.sleep(2)
        finally:
            try:
                if stream:
                    stream.stop_stream(); stream.close()
                if p:
                    p.terminate()
            except Exception:
                pass


# ---------------------------------------------------------------- lyrics
_LRC_TAG = re.compile(r"\[(\d{1,3}):(\d{1,2}(?:[.:]\d{1,3})?)\]")


def parse_lrc(text: str) -> list:
    """LRC -> [[seconds, line], ...]. Blank bodies are kept: they are the
    instrumental gaps, and the faceplate shows them as a rest."""
    out = []
    for raw in text.splitlines():
        tags = list(_LRC_TAG.finditer(raw))
        if not tags:
            continue
        body = raw[tags[-1].end():].strip()
        for m in tags:                       # one line can carry several stamps
            secs = int(m.group(1)) * 60 + float(m.group(2).replace(":", "."))
            out.append([round(secs, 2), body])
    out.sort(key=lambda r: r[0])
    return out


async def _lrclib(session, path: str, params: dict):
    async with session.get(f"{LYRICS_API}/{path}", params=params) as r:
        if r.status != 200:
            return None
        return await r.json()


async def fetch_lyrics(title, artist, album, duration):
    """Exact LRCLIB match first, then a looser search. -> (synced, lines)."""
    params = {"track_name": title, "artist_name": artist}
    if album:
        params["album_name"] = album
    if duration:
        params["duration"] = str(int(round(duration)))
    timeout = aiohttp.ClientTimeout(total=8)
    async with aiohttp.ClientSession(timeout=timeout,
                                     headers={"User-Agent": DECK_UA}) as s:
        rec = await _lrclib(s, "get", params)
        if not rec:
            hits = await _lrclib(s, "search", {"track_name": title,
                                               "artist_name": artist}) or []
            rec = next((h for h in hits if h.get("syncedLyrics")), None) or \
                (hits[0] if hits else None)
        if not rec:
            return False, []
        if rec.get("syncedLyrics"):
            lines = parse_lrc(rec["syncedLyrics"])
            if lines:
                return True, lines
        if rec.get("plainLyrics"):
            return False, [[None, l.strip()] for l in rec["plainLyrics"].splitlines()]
    return False, []


async def lyrics_task(key, title, artist, album, duration):
    """Look a track's lyrics up in the background; drop the result if the
    track has moved on by the time it lands."""
    global _lyrics
    try:
        synced, lines = await fetch_lyrics(title, artist, album, duration)
    except Exception as e:
        print(f"[lyrics] lookup failed ({e})")
        synced, lines = False, []
    if _lyrics.get("key") != key:
        return
    _lyrics = {"type": "lyrics", "key": key, "state": "ok" if lines else "none",
               "synced": synced, "lines": lines, "source": "LRCLIB"}
    kind = "synced" if synced else ("plain" if lines else "none")
    print(f"[lyrics] {title} — {kind} ({len(lines)} lines)")
    await broadcast(json.dumps(_lyrics))


# ---------------------------------------------------------------- art lookup
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _pick_release(hits, title, artist, album=""):
    """Best-scoring hit. iTunes ranks well, but a bare title pulls up covers
    compilations, so score title/artist/album agreement and take the winner."""
    nt, na, nb = _norm(title), _norm(artist), _norm(album)

    def score(h):
        ht, ha, hb = (_norm(h.get("trackName")), _norm(h.get("artistName")),
                      _norm(h.get("collectionName")))
        s = 0
        if nt and ht and (nt in ht or ht in nt):
            s += 4
        if na and ha and (na in ha or ha in na):
            s += 3
        if nb and hb and (nb in hb or hb in nb):
            s += 2                      # right album beats a greatest-hits sleeve
        return s

    ranked = [h for h in hits if h.get("artworkUrl100")]
    return max(ranked, key=score) if ranked else None


async def fetch_art(title, artist, album):
    """Sleeve from the iTunes Search API as a data URL, or None."""
    term = " ".join(x for x in (artist, title) if x)
    if not term:
        return None
    timeout = aiohttp.ClientTimeout(total=8)
    async with aiohttp.ClientSession(timeout=timeout,
                                     headers={"User-Agent": DECK_UA}) as s:
        params = {"term": term, "entity": "song", "limit": "5"}
        async with s.get(ART_API, params=params) as r:
            if r.status != 200:
                return None
            # iTunes replies as text/javascript; don't let aiohttp refuse it
            data = await r.json(content_type=None)
        hit = _pick_release(data.get("results", []), title, artist, album)
        if not hit:
            return None
        # the 100x100 thumbnail URL rewrites to any size the store holds
        url = hit["artworkUrl100"].replace("100x100", "600x600")
        async with s.get(url) as r:
            if r.status != 200:
                return None
            ctype = r.headers.get("Content-Type", "")
            if not ctype.startswith("image/"):
                return None
            # read to completion, capped: content.read(n) returns only what is
            # buffered so far and would hand back a truncated JPEG
            blob = bytearray()
            async for chunk in r.content.iter_chunked(65536):
                blob.extend(chunk)
                if len(blob) > ART_MAX_BYTES:
                    return None
        if not blob:
            return None
        return f"data:{ctype.split(';')[0]};base64,{base64.b64encode(bytes(blob)).decode()}"


async def art_task(key, title, artist, album):
    """Background sleeve lookup; discarded if the track moved on meanwhile."""
    try:
        art = await fetch_art(title, artist, album)
    except Exception as e:
        print(f"[art] lookup failed ({e})")
        return
    if not art or _track_key(_meta) != key or _meta["art"]:
        return
    _meta["art"] = art
    print(f"[art] {title} — sleeve found ({len(art) // 1024} KB)")
    await broadcast(json.dumps(_meta))


# ---------------------------------------------------------------- SMTC metadata
async def _read_art(thumb_ref) -> str | None:
    from winsdk.windows.storage.streams import Buffer, DataReader, InputStreamOptions
    try:
        stream = await thumb_ref.open_read_async()
        size = int(stream.size)
        if size == 0 or size > 2_000_000:
            return None
        buf = Buffer(size)
        await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
        reader = DataReader.from_buffer(buf)
        out = bytearray(size)
        reader.read_bytes(out)          # winsdk fills the passed bytearray
        data = bytes(out)
        mime = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return None


def _timeline(session, playing: bool):
    """(position, duration) in seconds, extrapolated from the last SMTC update."""
    try:
        tl = session.get_timeline_properties()
        start = tl.start_time.total_seconds()
        duration = max(0.0, tl.end_time.total_seconds() - start)
        pos = max(0.0, tl.position.total_seconds() - start)
        if playing and tl.last_updated_time is not None:
            age = (datetime.now(timezone.utc) - tl.last_updated_time).total_seconds()
            pos += min(max(age, 0.0), 5.0)     # apps report lazily; never trust a big gap
        if duration:
            pos = min(pos, duration)
        return round(pos, 2), round(duration, 2)
    except Exception:
        return 0.0, 0.0


async def smtc_task():
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as Manager,
    )
    STATUS = {0: "closed", 1: "opened", 2: "changing", 3: "stopped", 4: "playing", 5: "paused"}
    last_key = None
    while True:
        try:
            mgr = await Manager.request_async()
            session = mgr.get_current_session()
            pos = dur = 0.0
            if session is None:
                update = {"title": "", "artist": "", "album": "", "app": "",
                          "status": "stopped", "art": None}
                key = ("", "", "stopped")
            else:
                props = await session.try_get_media_properties_async()
                status = STATUS.get(session.get_playback_info().playback_status, "stopped")
                app = session.source_app_user_model_id or ""
                if "spotify" in app.lower():
                    app = "SPOTIFY"
                elif app:
                    app = app.split("!")[0].split("_")[0].split(".")[-1].upper()[:10]
                key = (props.title, props.artist, status)
                update = {"title": props.title or "", "artist": props.artist or "",
                          "album": props.album_title or "", "app": app, "status": status}
                if (props.title, props.artist) != (last_key or ("", "", ""))[:2]:
                    update["art"] = await _read_art(props.thumbnail) if props.thumbnail else None
                else:
                    update["art"] = _meta["art"]
                pos, dur = _timeline(session, status == "playing")
            if key != last_key:
                last_key = key
                _meta.update(update)
                await broadcast(json.dumps(_meta))
                await _sync_lyrics(update, dur)
                await _sync_art(_meta)
            _pos.update({"position": pos, "duration": dur,
                         "status": update["status"]})
            await broadcast(json.dumps(_pos))
        except Exception as e:
            print(f"[smtc] {e}")
        await asyncio.sleep(1.0)


def _track_key(meta: dict) -> str:
    return f"{meta['title']}\x1f{meta['artist']}"


async def _sync_art(meta: dict):
    """When the player gave us no thumbnail, go looking for the sleeve. Once per
    track: the play/pause key also changes, and a miss shouldn't re-query."""
    global _art_tried
    key = _track_key(meta)
    if not (ART_LOOKUP_ENABLED and meta["title"]) or meta["art"] or key == _art_tried:
        return
    _art_tried = key
    asyncio.create_task(art_task(key, meta["title"], meta["artist"], meta["album"]))


async def _sync_lyrics(meta: dict, duration: float):
    """Kick off a lookup when the track (not just the play state) changed."""
    global _lyrics
    title, artist = meta["title"], meta["artist"]
    key = _track_key(meta)
    if key == _lyrics.get("key"):
        return
    searching = bool(LYRICS_ENABLED and title)
    _lyrics = {"type": "lyrics", "key": key,
               "state": "searching" if searching else "none",
               "synced": False, "lines": [], "source": "LRCLIB" if searching else ""}
    await broadcast(json.dumps(_lyrics))
    if searching:
        asyncio.create_task(lyrics_task(key, title, artist, meta["album"], duration))


# ---------------------------------------------------------------- web + ws
async def broadcast(text: str):
    dead = []
    for ws in _clients:
        try:
            await ws.send_str(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


async def audio_broadcast_task():
    while True:
        if _clients:
            with _lock:
                msg = {"type": "audio", **_audio}
            await broadcast(json.dumps(msg))
        await asyncio.sleep(1.0 / BROADCAST_FPS)


async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    _clients.add(ws)
    await ws.send_str(json.dumps(_meta))
    await ws.send_str(json.dumps(_pos))
    await ws.send_str(json.dumps(_lyrics))
    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                break
    finally:
        _clients.discard(ws)
    return ws


async def index(_):
    return web.FileResponse(WEB / "index.html")


async def main():
    threading.Thread(target=audio_thread, daemon=True).start()
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_static("/web", WEB)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    print(f"[deck] PC-DECK 7710 online -> http://127.0.0.1:{PORT}")
    asyncio.create_task(smtc_task())
    await audio_broadcast_task()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
