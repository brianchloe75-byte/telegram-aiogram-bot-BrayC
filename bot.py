import os
import time
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
import yt_dlp

# ------------------------------
# ✅ Bot usernames
# ------------------------------
MAIN_BOT_USERNAME = "BrayC_bot"   # BrayC_bot
YOUTUBE_BOT_USERNAME = "YT_BOT_USERNAME"   # your EarthsBestDownloader_bot

# ------------------------------
# Bot setup
# ------------------------------
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# ------------------------------
# Queue & cooldown
# ------------------------------
semaphore = asyncio.Semaphore(4)  # concurrent downloads
cooldown = {}

# ------------------------------
# Mini web server to keep alive (Render)
# ------------------------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Alive")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# ------------------------------
# Platform detection
# ------------------------------
def detect_platform(url: str) -> str:
    url = url.lower()
    if "youtube" in url:
        return "YouTube"
    elif "tiktok" in url:
        return "TikTok"
    elif "instagram" in url:
        return "Instagram"
    elif "facebook" in url or "fb.watch" in url:
        return "Facebook"
    elif "twitter.com" in url or "x.com" in url:
        return "Twitter / X"
    elif "pinterest.com" in url:
        return "Pinterest"
    elif "reddit.com" in url:
        return "Reddit"
    elif "vimeo.com" in url:
        return "Vimeo"
    else:
        return "Unknown"

# ------------------------------
# yt-dlp options
# ------------------------------
def get_opts(filename, fmt):
    return {
        "format": fmt,
        "outtmpl": filename,
        "quiet": True,
        "nocheckcertificate": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 10
    }

# ------------------------------
# Download function
# ------------------------------
def download_video(url, user_id, choice):
    filename = f"downloads/{user_id}_{int(time.time())}.%(ext)s"
    formats = {
        "hd": ["bestvideo+bestaudio", "best"],
        "sd": ["best[height<=480]", "best"],
        "audio": ["bestaudio"]
    }

    last_error = None
    for fmt in formats[choice]:
        try:
            with yt_dlp.YoutubeDL(get_opts(filename, fmt)) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                return file_path, info
        except Exception as e:
            last_error = e
            continue

    raise Exception(f"All download attempts failed: {last_error}")

# ------------------------------
# /start command
# ------------------------------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply(
        f"🔥 Multi-platform Downloader\n\n"
        f"⚡ TikTok | Instagram | Facebook | Twitter/X | Pinterest | Reddit | Vimeo\n"
        f"🎯 Send a link → choose quality\n"
        f"🚀 Share this bot with friends: @{MAIN_BOT_USERNAME}",
        parse_mode="Markdown"
    )

# ------------------------------
# Handle incoming links
# ------------------------------
@dp.message_handler()
async def handle_link(message: types.Message):
    url = message.text.strip()
    user_id = message.from_user.id

    # cooldown
    now = time.time()
    if now - cooldown.get(user_id, 0) < 5:
        return await message.reply("⏳ Wait a few seconds before sending another link.")
    cooldown[user_id] = now

    platform = detect_platform(url)

    # Redirect YouTube links to YouTube bot
    if platform == "YouTube":
        return await message.reply(
            f"⚠️ YouTube videos are handled by another bot.\n"
            f"Please use: @{EarthsBestDownloader_bot}"
        )

    if platform == "Unknown":
        return await message.reply("❌ Unsupported platform or invalid link.")

    msg = await message.reply(f"🔍 Preparing {platform} video info...")

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("🎥 HD", callback_data=f"hd|{url}"),
        InlineKeyboardButton("📱 SD", callback_data=f"sd|{url}"),
        InlineKeyboardButton("🎧 Audio", callback_data=f"audio|{url}")
    )

    await msg.delete()
    await message.reply(
        f"🎬 {platform} video detected!\nChoose download quality:",
        reply_markup=keyboard
    )

# ------------------------------
# Handle button presses
# ------------------------------
@dp.callback_query_handler(lambda c: True)
async def handle_buttons(call: types.CallbackQuery):
    choice, url = call.data.split("|")
    user_id = call.from_user.id
    asyncio.create_task(process_download(call.message, url, user_id, choice))
    await call.answer()

# ------------------------------
# Download queue
# ------------------------------
async def process_download(message, url, user_id, choice):
    async with semaphore:
        msg = await message.reply("⏳ Queued for download...")

        try:
            await msg.edit_text("⬇️ Downloading...")
            loop = asyncio.get_event_loop()

            file_path, info = await loop.run_in_executor(
                None, lambda: download_video(url, user_id, choice)
            )

            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if size_mb > 50:
                os.remove(file_path)
                return await msg.edit_text("❌ File too large to send.")

            await msg.edit_text("📤 Uploading to Telegram...")
            if choice == "audio":
                await message.reply_audio(audio=InputFile(file_path))
            else:
                await message.reply_video(video=InputFile(file_path))

            os.remove(file_path)
            await msg.edit_text(f"✅ Done! 🎉 Share: @{BrayC_bot}")

        except Exception as e:
            print("Download error:", e)
            await msg.edit_text("❌ Something went wrong, try another link.")

# ------------------------------
# Start bot
# ------------------------------
async def main():
    print(f"🚀 {MAIN_BOT_USERNAME} running...")
    #start_polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
# keep main thread alive so render knows the process is running 
import time 
while true:
    time.sleep(60)
