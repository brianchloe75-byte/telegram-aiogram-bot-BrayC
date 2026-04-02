import os
import time
import json
import asyncio
import yt_dlp
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile

TOKEN = os.getenv("TOKEN")
YT_BOT = "EarthsBestDownloader_bot"  # set your YouTube bot username (without @)
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# 📁 folders
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# ⚡ queue control
semaphore = asyncio.Semaphore(2)
cooldown = {}

# 🌐 render keep-alive
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Alive")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

# ⚙️ yt-dlp options
def get_opts(filename, fmt):
    return {
        "format": fmt,
        "outtmpl": filename,
        "quiet": True,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 15,
        "nocheckcertificate": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"}
    }

# ⬇️ download video
def download_video(url, user_id, choice):
    filename = f"downloads/{user_id}_{int(time.time())}.%(ext)s"
    formats = {
        "hd": ["bestvideo+bestaudio", "best"],
        "sd": ["best[height<=480]", "best"],
        "audio": ["bestaudio"]
    }
    last_error = None
    for attempt in range(3):
        for fmt in formats[choice]:
            try:
                with yt_dlp.YoutubeDL(get_opts(filename, fmt)) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file_path = ydl.prepare_filename(info)
                    if os.path.exists(file_path):
                        return file_path, info
            except Exception as e:
                last_error = e
                continue
        time.sleep(1)
    raise Exception(f"Download failed: {last_error}")

# 🚀 start command
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply(
        "🔥 Ultimate Downloader\n\n"
        "⚡ Fast | TikTok | Instagram | Facebook\n"
        "🎯 Send link → choose quality\n\n"
        "🚀 Invite friends to grow!",
        parse_mode="Markdown"
    )

# 📩 link handler
@dp.message_handler()
async def handle(message: types.Message):
    url = message.text
    user_id = message.from_user.id

    # cooldown
    now = time.time()
    if now - cooldown.get(user_id, 0) < 10:
        return await message.reply("⏳ Wait a bit...")
    cooldown[user_id] = now

    # redirect YouTube links
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "🚀 Open YouTube Downloader",
                url=f"https://t.me/{YT_BOT}"
            )
        )
        return await message.reply(
            "🎥 YouTube detected\n\n"
            "⚡ For fast & stable downloads, use our YouTube bot:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    msg = await message.reply("🔍 Fetching info...")
    try:
        ydl = yt_dlp.YoutubeDL({"quiet": True})
        info = ydl.extract_info(url, download=False)
        title = info.get("title", "Video")
        thumb = info.get("thumbnail")

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🎥 HD", callback_data=f"hd|{url}"))
        keyboard.add(InlineKeyboardButton("📱 SD", callback_data=f"sd|{url}"))
        keyboard.add(InlineKeyboardButton("🎧 Audio", callback_data=f"audio|{url}"))

        await msg.delete()
        await message.reply_photo(
            photo=thumb,
            caption=f"🎬 {title}\nChoose quality:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        print("INFO ERROR:", e)
        await msg.edit_text("❌ Failed to fetch info")

# 🎛 handle buttons
@dp.callback_query_handler(lambda c: True)
async def handle_buttons(call: types.CallbackQuery):
    choice, url = call.data.split("|")
    user_id = call.from_user.id
    asyncio.create_task(process(call.message, url, user_id, choice))
    await call.answer()

# ⚙️ process download + upload
async def process(message, url, user_id, choice):
    async with semaphore:
        msg = await message.reply("⏳ Queued...")
        try:
            await msg.edit_text("⬇️ Downloading...")
            loop = asyncio.get_event_loop()
            file_path, info = await loop.run_in_executor(
                None, lambda: download_video(url, user_id, choice)
            )
            size = os.path.getsize(file_path) / (1024 * 1024)
            if size > 49:
                os.remove(file_path)
                return await msg.edit_text("❌ File too large (>50MB)")
            await msg.edit_text("📤 Uploading...")
            if choice == "audio":
                await message.reply_audio(audio=InputFile(file_path))
            else:
                await message.reply_video(video=InputFile(file_path))
            os.remove(file_path)
            await msg.edit_text("✅ Done!\n📥 Save to gallery")
        except Exception as e:
            print("PROCESS ERROR:", e)
            await msg.edit_text("❌ Failed, try again later.")

# 🌐 start web server
threading.Thread(target=run_web).start()
print("🔥 Main Bot Running")
executor.start_polling(dp)
