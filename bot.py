import os
import re
import json
import time
import uuid
import asyncio
import logging
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote_plus

import requests
import imageio_ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)
from shazamio import Shazam

TOKEN = os.environ["BOT_TOKEN"]
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ytmusicbot")

WELCOME = (
    "Namaste! 🎵\n\n"
    "Main gaane dhoondh kar MP3 bhejta hoon. Mujhe bhejo:\n\n"
    "📝 Gaane ka naam, singer, ya lyrics ki line\n"
    "🎤 Voice note jisme gaana baj raha ho\n"
    "🎬 Audio ya video jisme gaana ho\n"
    "🔗 YouTube, Instagram ya TikTok link\n\n"
    "Phir list se gaana chuno aur MP3 pao. Enjoy!"
)

NO_RESULT = "Is naam se kuch nahi mila. Naam thoda badal kar bhejo (singer ka naam jodo)."

INVIDIOUS = ["https://yt.chocolatemoo53.com"]
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
MAX_SECONDS = 15 * 60  # refuse downloads longer than 15 min

SESSIONS = {}  # token -> {"query": str, "ts": float}
shazam = Shazam()


# ---------- search ----------

def _walk(o, out):
    if isinstance(o, dict):
        v = o.get("videoRenderer")
        if v and v.get("videoId"):
            out.append({
                "vid": v["videoId"],
                "title": "".join(r.get("text", "") for r in v.get("title", {}).get("runs", [])) or "Unknown",
                "channel": "".join(r.get("text", "") for r in v.get("ownerText", {}).get("runs", [])) or "",
                "seconds": None,
                "dur": v.get("lengthText", {}).get("simpleText"),
            })
        for x in o.values():
            _walk(x, out)
    elif isinstance(o, list):
        for x in o:
            _walk(x, out)


def yt_search(query, page=1):
    """Return list of {vid,title,channel,seconds,dur}."""
    for host in INVIDIOUS:
        try:
            r = requests.get(f"{host}/api/v1/search",
                             params={"q": query, "type": "video", "page": page}, timeout=15)
            if r.status_code == 200:
                out = []
                for it in r.json():
                    if it.get("type") == "video" and it.get("videoId"):
                        sec = it.get("lengthSeconds")
                        out.append({
                            "vid": it["videoId"],
                            "title": it.get("title") or "Unknown",
                            "channel": it.get("author") or "",
                            "seconds": int(sec) if sec else None,
                            "dur": f"{int(sec)//60}:{int(sec)%60:02d}" if sec else None,
                        })
                        if len(out) >= 10:
                            return out
                if out:
                    return out
        except Exception as exc:
            log.info("invidious search failed: %s", exc)
    # fallback: scrape youtube (page param unsupported)
    try:
        r = requests.get("https://www.youtube.com/results",
                         params={"search_query": query}, headers=UA, timeout=15)
        m = re.search(r"var ytInitialData = (\{.*?\});</script>", r.text, re.S)
        if m:
            out = []
            _walk(json.loads(m.group(1)), out)
            return out[:10]
    except Exception as exc:
        log.info("scrape search failed: %s", exc)
    return []


def video_meta(vid):
    for host in INVIDIOUS:
        try:
            r = requests.get(f"{host}/api/v1/videos/{vid}", timeout=15)
            if r.status_code == 200:
                d = r.json()
                return {"title": d.get("title") or "Unknown",
                        "channel": d.get("author") or "",
                        "seconds": d.get("lengthSeconds")}
        except Exception:
            pass
    return None


# ---------- audio download / convert ----------

def download_mp3(vid, workdir):
    """Download audio via invidious proxy, convert to mp3. Returns path or None."""
    m4a = os.path.join(workdir, f"{vid}.m4a")
    mp3 = os.path.join(workdir, f"{vid}.mp3")
    for itag in ("140", "139", "251", "250", "249"):
        for host in INVIDIOUS:
            try:
                url = f"{host}/latest_version?id={vid}&itag={itag}&local=true"
                with requests.get(url, stream=True, timeout=(15, 300)) as r:
                    if r.status_code != 200:
                        continue
                    with open(m4a, "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
                if os.path.getsize(m4a) > 10000:
                    break
            except Exception as exc:
                log.info("download itag=%s host=%s failed: %s", itag, host, exc)
        else:
            continue
        break
    else:
        return None
    try:
        subprocess.run([FFMPEG, "-y", "-i", m4a, "-c:a", "libmp3lame", "-q:a", "4", mp3],
                       check=True, capture_output=True, timeout=300)
        return mp3
    except Exception as exc:
        log.info("ffmpeg failed: %s", exc)
        return None


def bytes_to_mp3(data, workdir, name="in", max_seconds=90):
    src = os.path.join(workdir, name)
    with open(src, "wb") as f:
        f.write(data)
    mp3 = os.path.join(workdir, name + ".mp3")
    subprocess.run([FFMPEG, "-y", "-i", src, "-t", str(max_seconds),
                    "-c:a", "libmp3lame", "-q:a", "4", mp3],
                   check=True, capture_output=True, timeout=120)
    return mp3


# ---------- recognition / lyrics ----------

async def recognize_file(path):
    with open(path, "rb") as f:
        data = f.read()
    r = await shazam.recognize(data=data)
    t = (r or {}).get("track") or {}
    if not t.get("title"):
        return None
    return {"title": t["title"], "artist": t.get("subtitle") or ""}


def get_lyrics(artist, title):
    try:
        r = requests.get("https://lrclib.net/api/get",
                         params={"artist_name": artist, "track_name": title}, timeout=15)
        if r.status_code == 200:
            return r.json().get("plainLyrics")
    except Exception:
        pass
    return None


def search_lyrics(q):
    try:
        r = requests.get("https://lrclib.net/api/search", params={"q": q}, timeout=15)
        if r.status_code == 200:
            for item in r.json():
                if item.get("plainLyrics"):
                    return item["plainLyrics"]
    except Exception:
        pass
    return None


# ---------- telegram helpers ----------

def fmt_line(t):
    dur = f"• {t['dur']} • " if t.get("dur") else ""
    ch = f" — {t['channel']}" if t.get("channel") else ""
    return f"{dur}{t['title']}{ch}"


def search_keyboard(query, page, results):
    token = uuid.uuid4().hex[:8]
    SESSIONS[token] = {"query": query, "ts": time.time()}
    rows = [[InlineKeyboardButton(fmt_line(t)[:64], callback_data=f"d:{t['vid']}")]
            for t in results[:10]]
    nav = [InlineKeyboardButton("➕ More tracks", callback_data=f"p:{token}:{page + 1}"),
           InlineKeyboardButton("❌ Cancel", callback_data="x")]
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def card_keyboard(title, artist):
    q = quote_plus(f"{title} {artist}".strip())
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Google", url=f"https://www.google.com/search?q={q}"),
        InlineKeyboardButton("YouTube Music", url=f"https://music.youtube.com/search?q={q}"),
        InlineKeyboardButton("Spotify", url=f"https://open.spotify.com/search/{q}"),
    ]])


async def send_song(message, vid, context):
    """Download vid as mp3 and send with a Lyrics button."""
    meta = video_meta(vid)
    if meta and meta.get("seconds") and meta["seconds"] > MAX_SECONDS:
        await message.reply_text("Ye track bahut lamba hai (15 min se zyada), isey bhej nahi sakta. Chhota version chuno.")
        return
    status = await message.reply_text("⬇️ Download ho raha hai, thoda intezaar karo (1-2 min lag sakte hain)...")
    workdir = f"/tmp/dl_{uuid.uuid4().hex[:8]}"
    os.makedirs(workdir, exist_ok=True)
    mp3 = await asyncio.to_thread(download_mp3, vid, workdir)
    if not mp3:
        await status.edit_text("Maaf karna, abhi ye gaana download nahi ho paya. Thodi der baad ya koi aur version try karo.")
        return
    title = meta["title"] if meta else "Song"
    artist = meta["channel"] if meta else ""
    fname = (f"{artist} - {title}".strip(" -") or "song")[:60] + ".mp3"
    try:
        with open(mp3, "rb") as f:
            await message.reply_audio(
                audio=f,
                filename=fname,
                title=title[:64], performer=artist[:64],
                duration=meta.get("seconds") if meta else None,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔤 Lyrics", callback_data=f"l:{vid}")]]),
                write_timeout=300, read_timeout=300,
            )
        await status.delete()
    except Exception as exc:
        log.warning("send audio failed: %s", exc)
        await status.edit_text("File bhejne mein dikkat aayi. Dobara try karo.")


# ---------- handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return
    m = re.search(r"(?:youtube\.com/(?:watch\?[^ ]*v=|shorts/)|youtu\.be/)([\w-]{11})", text)
    if m:
        await handle_youtube_link(update, m.group(1))
        return
    if re.search(r"https?://", text):
        await handle_other_link(update, text)
        return
    wait = await update.message.reply_text("🔍 Dhoondh raha hoon...")
    results = await asyncio.to_thread(yt_search, text)
    if not results:
        await wait.edit_text(NO_RESULT)
        return
    await wait.edit_text("Gaana chuno:",
                         reply_markup=search_keyboard(text, 1, results))


async def handle_youtube_link(update: Update, vid):
    status = await update.message.reply_text("🎧 Link mila, audio nikal kar pehchan raha hoon (1-2 min)...")
    workdir = f"/tmp/yt_{uuid.uuid4().hex[:8]}"
    os.makedirs(workdir, exist_ok=True)
    mp3 = await asyncio.to_thread(download_mp3, vid, workdir)
    if not mp3:
        await status.edit_text("Is link ka audio nahi nikal paya. Dobara ya kisi aur link se try karo.")
        return
    await finish_recognition(update, status, mp3)


async def handle_other_link(update: Update, text):
    status = await update.message.reply_text("🎧 Link se audio nikal raha hoon...")
    workdir = f"/tmp/ln_{uuid.uuid4().hex[:8]}"
    os.makedirs(workdir, exist_ok=True)
    out = os.path.join(workdir, "a.%(ext)s")
    def _dl():
        import yt_dlp
        opts = {"quiet": True, "format": "bestaudio/best", "outtmpl": out,
                "ffmpeg_location": FFMPEG,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]}
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([text])
        p = os.path.join(workdir, "a.mp3")
        return p if os.path.exists(p) else None
    try:
        mp3 = await asyncio.to_thread(_dl)
    except Exception as exc:
        log.info("link download failed: %s", exc)
        mp3 = None
    if not mp3:
        await status.edit_text("Is link se audio nahi nikal paya. YouTube link ya voice note try karo.")
        return
    await finish_recognition(update, status, mp3)


async def finish_recognition(update: Update, status, mp3_path):
    try:
        rec = await recognize_file(mp3_path)
    except Exception as exc:
        log.info("recognize failed: %s", exc)
        rec = None
    if not rec:
        await status.edit_text("Gaana pehchan nahi paya. Saaf audio ya gaane ka naam likh kar bhejo.")
        return
    title, artist = rec["title"], rec["artist"]
    await status.edit_text(f"🎵 {title} — {artist}",
                           reply_markup=card_keyboard(title, artist))
    q = f"{title} {artist}".strip()
    results = await asyncio.to_thread(yt_search, q)
    if results:
        await send_song(update.message, results[0]["vid"], None)


async def on_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    fileobj = msg.voice or msg.audio or msg.video or msg.video_note or msg.document
    if not fileobj:
        return
    status = await msg.reply_text("🎧 Sun raha hoon, gaana pehchan raha hoon...")
    try:
        tgfile = await context.bot.get_file(fileobj.file_id)
        data = await tgfile.download_as_bytearray()
    except Exception as exc:
        log.info("tg download failed: %s", exc)
        await status.edit_text("Ye file download nahi ho payi. 20 MB se chhoti file bhejo.")
        return
    workdir = f"/tmp/md_{uuid.uuid4().hex[:8]}"
    os.makedirs(workdir, exist_ok=True)
    try:
        mp3 = await asyncio.to_thread(bytes_to_mp3, bytes(data), workdir)
    except Exception as exc:
        log.info("convert failed: %s", exc)
        await status.edit_text("Is audio ko samajh nahi paya. Dusri file try karo.")
        return
    await finish_recognition(update, status, mp3)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""
    try:
        await q.answer()
    except Exception:
        pass
    try:
        if data == "x":
            await q.message.delete()
        elif data.startswith("p:"):
            _, token, page = data.split(":")
            sess = SESSIONS.get(token)
            if not sess:
                await q.answer("Purani search hai, dobara naam bhejo.", show_alert=True)
                return
            results = await asyncio.to_thread(yt_search, sess["query"], int(page))
            if not results:
                await q.answer("Aur results nahi mile.", show_alert=True)
                return
            await q.message.edit_reply_markup(
                reply_markup=search_keyboard(sess["query"], int(page), results))
        elif data.startswith("d:"):
            await send_song(q.message, data[2:], context)
        elif data.startswith("l:"):
            await q.message.reply_text("🔤 Lyrics dhoondh raha hoon...")
            meta = await asyncio.to_thread(video_meta, data[2:])
            if not meta:
                await q.message.reply_text("Lyrics nahi mili.")
                return
            lyrics = await asyncio.to_thread(get_lyrics, meta["channel"], meta["title"])
            if not lyrics:
                lyrics = await asyncio.to_thread(search_lyrics, f"{meta['title']} {meta['channel']}")
            if not lyrics:
                await q.message.reply_text(f"Is track ki lyrics uplabdh nahi hai: {meta['title']}")
                return
            for i in range(0, len(lyrics), 4000):
                await q.message.reply_text(lyrics[i:i + 4000])
    except Exception as exc:
        log.warning("callback %s failed: %s", data, exc)


# ---------- health server / main ----------

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def run_http():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


def main():
    threading.Thread(target=run_http, daemon=True).start()
    app = (ApplicationBuilder().token(TOKEN)
           .read_timeout(300).write_timeout(300).connect_timeout(60)
           .media_write_timeout(300).build())
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO | filters.VIDEO | filters.VIDEO_NOTE | filters.ATTACHMENT,
        on_media))
    log.info("bot starting (long polling)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
