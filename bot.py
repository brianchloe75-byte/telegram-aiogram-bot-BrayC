import os
import time
import asyncio
import random
import yt_dlp
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# 🔥 Controlled workers (prevents overload)
semaphore = asyncio.Semaphore(2)
executor_pool = ThreadPoolExecutor(max_workers=2)

user_data = {}

# 🌐 Render keep-alive
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Alive")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

# 🔥 Proxy system (optional)
PROXIES = [
    None,
    # "http://user:pass@ip:port",
]

def get_random_proxy():
    return random.choice(PROXIES)

# ⚙️ yt-dlp options
def get_opts(filename, fmt):
    proxy = get_random_proxy()

    return {
        "format": fmt,
        "outtmpl": filename,
        "quiet": True,
        "noplaylist": True,

        "retries": 1,
        "fragment_retries": 1,
        "socket_timeout": 10,

        "nocheckcertificate": True,

        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        },

        "proxy": proxy
    }

# 🔥 SAFE DOWNLOAD (ANTI-HANG)
def download_video(url, user_id, choice):
    filename = f"downloads/{user_id}_{int(time.time())}.%(ext)s"

    if choice == "hd":
        formats = ["bestvideo+bestaudio", "best"]
    elif choice == "sd":
        formats = ["best[height<=480]", "best"]
    else:
        formats = ["bestaudio", "best"]

    last_error = None

    for attempt in range(2):
        for fmt in formats:
            try:
                ydl_opts = get_opts(filename, fmt)

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file_path = ydl.prepare_filename(info)

                    if os.path.exists(file_path):
                        return file_path, info

            except Exception as e:
                print(f"Attempt {attempt+1} failed:", str(e))
                last_error = e
                continue

        time.sleep(2)

    raise Exception(f"Download failed: {str(last_error)}")

# 🚀 START
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply(
        "🔥 ULTRA Downloader v2\n\n"
        "⚡ Fast & Reliable\n"
        "🎬 HD | 📱 SD | 🎧 Audio\n"
        "🚀 TikTok • Instagram • Facebook • YouTube\n\n"
        "📩 Send a video link to begin",
        parse_mode="Markdown"
    )

# 📩 HANDLE LINK
@dp.message_handler()
async def handle_link(message: types.Message):
    url = message.text
    user_id = message.from_user.id

    if not url.startswith("http"):
        return await message.reply("❌ Send a valid link")

    msg = await message.reply("🔍 Fetching info...")

    try:
        ydl = yt_dlp.YoutubeDL({
            "quiet": True,
            "nocheckcertificate": True,
            "http_headers": {"User-Agent": "Mozilla/5.0"}
        })

        info = ydl.extract_info(url, download=False)

        title = info.get("title", "Video")
        thumb = info.get("thumbnail")

        user_data[user_id] = {"url": url}

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🎥 HD", callback_data="hd"))
        keyboard.add(InlineKeyboardButton("📱 SD", callback_data="sd"))
        keyboard.add(InlineKeyboardButton("🎧 Audio", callback_data="audio"))

        await msg.delete()

        await message.reply_photo(
            photo=thumb,
            caption=f"🎬 {title}\n\nChoose quality:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except Exception as e:
        print("INFO ERROR:", str(e))
        await msg.edit_text("❌ Couldn't fetch video info")

# 🎛 BUTTON HANDLER
@dp.callback_query_handler(lambda c: True)
async def handle_buttons(call: types.CallbackQuery):
    user_id = call.from_user.id
    choice = call.data

    data = user_data.get(user_id)
    if not data:
        return await call.message.reply("❌ Send link again")

    asyncio.create_task(process(call.message, data["url"], user_id, choice))
    await call.answer()

# ⚙️ PROCESS (FIXED CORE)
async def process(message, url, user_id, choice):
    async with semaphore:
        msg = await message.reply(
            "⏳ In Queue...\n⚡ Preparing download",
            parse_mode="Markdown"
        )

        try:
            await msg.edit_text("⚡ Processing...", parse_mode="Markdown")
            await msg.edit_text("⬇️ Downloading...", parse_mode="Markdown")

            loop = asyncio.get_event_loop()

            try:
                file_path, info = await asyncio.wait_for(
                    loop.run_in_executor(
                        executor_pool,
                        lambda: download_video(url, user_id, choice)
                    ),
                    timeout=60
                )
            except asyncio.TimeoutError:
                return await msg.edit_text(
                    "⚠️ Took too long (server busy or blocked)\nTry again later"
                )

            if not os.path.exists(file_path):
                return await msg.edit_text("❌ File missing after download")

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

            await msg.edit_text("✅ Done! Save to gallery 📥")
            await message.reply(f"🚀 Share this bot:@{BOT_USERNAME}")

        except Exception as e:
            print("PROCESS ERROR:", str(e))
            await msg.edit_text("❌ Failed. Try another link")

# 🌐 START WEB
threading.Thread(target=run_web).start()

# 🚀 START BOT
print("🔥 BULLETPROOF BOT RUNNING")
executor.start_polling(dp)
