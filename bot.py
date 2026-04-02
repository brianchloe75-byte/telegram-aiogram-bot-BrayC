import os
import time
import asyncio
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

# Queue control
semaphore = asyncio.Semaphore(2)

# Store user choices
user_data = {}

# 🌐 Render web fix
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

# 🎬 Detect platform
def detect_platform(url):
    if "youtube" in url:
        return "🎥 YouTube"
    elif "tiktok" in url:
        return "🎵 TikTok"
    elif "instagram" in url:
        return "📸 Instagram"
    elif "facebook" in url:
        return "📘 Facebook"
    return "🌐 Video"

# ⬇️ Download
def download_video(url, user_id, choice):
    filename = f"downloads/{user_id}_{int(time.time())}.%(ext)s"

    if choice == "hd":
        fmt = "best[ext=mp4]/best"
    elif choice == "sd":
        fmt = "worst[ext=mp4]/worst"
    else:
        fmt = "bestaudio/best"

    ydl_opts = {
        "format": fmt,
        "outtmpl": filename,
        "quiet": True,
        "noplaylist": True,
        "retries": 5,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        return file_path, info

# 🚀 START
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply(
        "🔥 ULTRA Downloader Bot\n\n"
        "📥 Send any video link\n"
        "🎯 Choose quality\n"
        "⚡ Fast downloads\n\n"
        "🚀 Invite friends & grow together",
        parse_mode="Markdown"
    )

# 📩 Handle link
@dp.message_handler()
async def handle_link(message: types.Message):
    url = message.text
    user_id = message.from_user.id

    if not url.startswith("http"):
        return await message.reply("❌ Send a valid link")

    platform = detect_platform(url)

    msg = await message.reply("🔍 Fetching info...")

    try:
        ydl = yt_dlp.YoutubeDL({"quiet": True})
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
            caption=f"{platform}\n\n🎬 {title}\n\nChoose quality:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except:
        await msg.edit_text("❌ Failed to fetch video")

# 🎛 Button handler
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
            await msg.edit_text("⬇️ Downloading...")

            loop = asyncio.get_event_loop()
            file_path, info = await loop.run_in_executor(
                None, lambda: download_video(url, user_id, choice)
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

            await msg.edit_text("✅ Done!\n📥 Saved to gallery")

            # 📈 Growth message
            await message.reply(
                "🚀 Enjoying the bot?\n"
                "Invite friends and grow together!\n"
                "@BrayC_bot",
                parse_mode="Markdown"
            )

        except:
            await msg.edit_text("❌ Failed, try again")

# 🌐 Start web server
threading.Thread(target=run_web).start()

# 🚀 Start bot
print("🔥 PREMIUM BOT RUNNING")
executor.start_polling(dp)
