"""
PC-DECK 7710 — Pioneer-style OEM head-unit display for PC audio.

Captures whatever the machine is playing (Spotify, browser, games) via WASAPI
loopback, runs a 13-band analysis + oscilloscope feed, reads now-playing
metadata/album art from Windows SMTC, and streams it all to the faceplate UI
over a WebSocket at http://127.0.0.1:7710
"""

import asyncio
import base64
import json
import threading
import time
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio
from aiohttp import web, WSMsgType

PORT = 7710
WEB = Path(__file__).parent / "web"

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
            if key != last_key:
                last_key = key
                _meta.update(update)
                await broadcast(json.dumps(_meta))
        except Exception as e:
            print(f"[smtc] {e}")
        await asyncio.sleep(1.0)


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
