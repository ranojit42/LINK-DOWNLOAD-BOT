# ================= CONFIG =================
from pyrogram import Client, filters
from pyrogram.types import *
import yt_dlp, os, re, asyncio, time, shutil

BOT_TOKEN = "8478599778:AAExe8JshyYtDkn1-4_Pm9ULJe2oMhOUn5w"
API_ID = 38063189
API_HASH = "1f5b2b7bd33615a2a3f34e406dd9ecab"

OWNER_ID = 8156670159
CHANNEL_LINK = "@SEXTYMODS"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

bot = Client(
    "vip_downloader",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================= GLOBAL =================
user_mode = {}
user_quality = {}
premium_users = set()
active_downloads = 0
tasks = {}
paused_tasks = {}
cancel_tasks = {}
bot_start_time = time.time()

# ================= UTIL =================
def is_url(u): return re.match(r"https?://", u)

def bar(p):
    p = int(p)
    done = int(p / 10)
    return "█" * done + "░" * (10 - done)

def hsize(b):
    for u in ["B","KB","MB","GB"]:
        if b < 1024:
            return f"{b:.2f}{u}"
        b /= 1024
    return "∞"

def uptime():
    s = int(time.time() - bot_start_time)
    return f"{s//3600}h {(s%3600)//60}m {s%60}s"

def storage():
    d = shutil.disk_usage("/")
    return hsize(d.used), hsize(d.free)

def is_image(url):
    return any(url.lower().endswith(x) for x in [".jpg",".jpeg",".png",".webp"])

def control_buttons(paused=False):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("▶ Resume" if paused else "⏸ Pause",
                             callback_data="resume_dl" if paused else "pause_dl"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_dl")
    ]])

# ================= START =================
@bot.on_message(filters.command("start"))
async def start(_, m: Message):
    await m.reply_text(
        f"🤖 **LINK DOWNLOADER BOT** 🧿\n\n"
        f"YT / Insta / FB / ALL\n\n"
        f"📢 Join channel:\n{CHANNEL_LINK}\n\n"
        f"👇 Select Mode",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎥 Video", callback_data="video"),
                InlineKeyboardButton("🎧 Audio", callback_data="audio")
            ],
            [
                InlineKeyboardButton("🖼 Photo", callback_data="photo"),
                InlineKeyboardButton("ℹ Admin", callback_data="admin")
            ]
        ])
    )

# ================= CALLBACK =================
@bot.on_callback_query()
async def cb(_, q: CallbackQuery):
    uid = q.from_user.id

    if q.data in ["video","audio","photo"]:
        user_mode[uid] = q.data

        if q.data == "video":
            await q.message.edit_text(
                "Select quality",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("360p","v360"),
                    InlineKeyboardButton("720p","v720"),
                    InlineKeyboardButton("1080p","v1080")
                ]])
            )
        elif q.data == "photo":
            await q.message.edit_text("Send image link")
        else:
            await q.message.edit_text("Send link")

    elif q.data.startswith("v"):
        user_quality[uid] = q.data
        await q.message.edit_text("✅ Quality set\nSend link")

    elif q.data == "admin" and uid == OWNER_ID:
        used, free = storage()
        await q.message.edit_text(
            f"👑 **ADMIN PANEL**\n\n"
            f"📊 Active downloads: {active_downloads}\n"
            f"🚀 Uptime: {uptime()}\n"
            f"💾 Used: {used}\n"
            f"💾 Free: {free}"
        )

    elif q.data == "pause_dl":
        paused_tasks[uid] = True
        await q.message.edit_reply_markup(control_buttons(paused=True))

    elif q.data == "resume_dl":
        paused_tasks[uid] = False
        await q.message.edit_reply_markup(control_buttons(paused=False))

    elif q.data == "cancel_dl":
        cancel_tasks[uid] = True
        await q.message.edit_text("❌ **Download Cancelled**")

# ================= MAIN =================
@bot.on_message(
    filters.private
    & filters.text
    & ~filters.command(["start", "help", "admin"])
)
async def downloader(_, m: Message):
    global active_downloads
    uid = m.from_user.id
    url = m.text.strip()

    if not is_url(url):
        return await m.reply_text("❌ Invalid link")

    mode = user_mode.get(uid)
    if not mode:
        return await m.reply_text("⚠ Select mode")

    interval = 0.5 if uid in premium_users else 1.5
    status = await m.reply_text("⏳ Starting...", reply_markup=control_buttons())
    active_downloads += 1
    start = time.time()
    last = 0
    cancel_tasks[uid] = False
    paused_tasks[uid] = False

    def hook(d):
        nonlocal last
        if cancel_tasks.get(uid):
            raise Exception("Cancelled")

        while paused_tasks.get(uid):
            time.sleep(1)

        if d["status"] == "downloading":
            now = time.time()
            if now - last < interval:
                return
            last = now

            done = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            percent = done * 100 / total if total else 0
            speed = done / max(now - start, 1)
            eta = (total - done) / speed if speed and total else 0

            asyncio.create_task(
                status.edit(
                    f"⬇ **Downloading**\n"
                    f"`{bar(percent)}` {percent:.1f}%\n"
                    f"📦 {hsize(done)} / {hsize(total)}\n"
                    f"⚡ {hsize(speed)}/s\n"
                    f"⏳ {int(eta)}s",
                    reply_markup=control_buttons(paused_tasks[uid])
                )
            )

    try:
        if mode == "photo" and is_image(url):
            file = f"{DOWNLOAD_DIR}/{int(time.time())}.jpg"
            os.system(f"curl -L '{url}' -o '{file}'")
            await m.reply_photo(file)
            os.remove(file)
            await status.delete()
            return

        ydl_opts = {
            "quiet": True,
            "progress_hooks": [hook],
            "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s"
        }

        if mode == "video":
            q = user_quality.get(uid, "v720")[1:]
            ydl_opts["format"] = f"bestvideo[height<={q}]+bestaudio/best"
            ydl_opts["merge_output_format"] = "mp4"
        else:
            ydl_opts["format"] = "bestaudio/best"

        with yt_dlp.YoutubeDL(ydl_opts) as y:
            info = y.extract_info(url, download=True)
            file = y.prepare_filename(info)

        await status.edit("📤 Uploading...", reply_markup=None)
        if mode == "video":
            await m.reply_video(file)
        else:
            await m.reply_audio(file)

        os.remove(file)
        await status.delete()

    except Exception as e:
        await status.edit(f"❌ {e}")

    finally:
        active_downloads -= 1
        paused_tasks.pop(uid, None)
        cancel_tasks.pop(uid, None)

# ================= RUN =================
print("🤖 BOT STARTED")
bot.run()
