import os
import time
import asyncio
import random
import yt_dlp
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# 🔥 Queue system (limit active downloads)
semaphore = asyncio.Semaphore(2)

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

# 🔥 Proxy list (add more later)
PROXIES = [
    None,  # fallback (no proxy)
    # "http://user:pass@ip:port",
    # "http://ip:port",
]

def get_random_proxy():
    return random.choice(PROXIES)

# ⚙️ yt-dlp options (optimized)
def get_opts(filename, fmt):
    proxy = get_random_proxy()

    return {
        "format": fmt,
        "outtmpl": filename,
        "quiet": True,
        "noplaylist": True,

        # 🔥 FAST + SAFE
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 10,

        "nocheckcertificate": True,

        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        },

        "proxy": proxy
    }

# 🔥 Smart download with retry logic
def download_video(url, user_id, choice):
    filename = f"downloads/{user_id}_{int(time.time())}.%(ext)s"

    if choice == "hd":
        formats = ["bestvideo+bestaudio", "best"]
    elif choice == "sd":
        formats = ["best[height<=480]", "best"]
    else:
        formats = ["bestaudio", "best"]

    last_error = None

    for attempt in range(3):  # 🔁 smart retry
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

        time.sleep(2)  # small delay before retry

    raise Exception(f"Download failed: {str(last_error)}")

# 🚀 START
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply(
        "🔥 ULTRA Downloader\n\n"
        "⚡ Fast | Reliable | Multi-platform\n"
        "🎯 Send link → choose quality",
        parse_mode="Markdown"
    )

# 📩 Handle link
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

# 🎛 Buttons
@dp.callback_query_handler(lambda c: True)
async def handle_buttons(call: types.CallbackQuery):
    user_id = call.from_user.id
    choice = call.data

    data = user_data.get(user_id)
    if not data:
        return await call.message.reply("❌ Send link again")

    asyncio.create_task(process(call.message, data["url"], user_id, choice))
    await call.answer()

# ⚙️ Process queue
async def process(message, url, user_id, choice):
    async with semaphore:
        msg = await message.reply("⏳ Queued...")

        try:
            await msg.edit_text("⚡ Processing...")
            await msg.edit_text("⬇️ Downloading...")

            loop = asyncio.get_event_loop()

            # 🔥 HARD TIMEOUT
            file_path, info = await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: download_video(url, user_id, choice)
                ),
                timeout=30
            )

            size = os.path.getsize(file_path) / (1024 * 1024)

            if size > 49:
                os.remove(file_path)
                return await msg.edit_text("❌ File too large")

            await msg.edit_text("📤 Uploading...")

            if choice == "audio":
                await message.reply_audio(audio=InputFile(file_path))
            else:
                await message.reply_video(video=InputFile(file_path))

            os.remove(file_path)

            await msg.edit_text("✅ Done!\n📥 Save to gallery")
            await message.reply("🚀 Share this bot: @BrayC_bot")

        except asyncio.TimeoutError:
            await msg.edit_text("❌ Took too long. Try again.")

        except Exception as e:
            print("PROCESS ERROR:", str(e))
            await msg.edit_text("❌ Failed, try another link")

# 🌐 Start web server
threading.Thread(target=run_web).start()

# 🚀 Start bot
print("🔥 BULLETPROOF BOT RUNNING")
executor.start_polling(dp)
