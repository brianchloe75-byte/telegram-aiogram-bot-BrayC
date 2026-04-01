import os
import time
import yt_dlp
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InputFile

# 🔑 TOKEN (from Render env)
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# 📁 Create downloads folder
if not os.path.exists("downloads"):
    os.makedirs("downloads")


# 🌐 Fake web server (for Render free plan)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")


def run_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


# ▶️ Start command
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.reply(
        "🔥 Premium Video Downloader Bot\n\n"
        "📥 Send any link:\n"
        "• YouTube\n• TikTok\n• Instagram\n• Facebook\n\n"
        "⚡ Fast downloads | HD quality",
        parse_mode="Markdown"
    )


# 📥 Detect platform
def detect_platform(url):
    if "youtube.com" in url or "youtu.be" in url:
        return "YouTube"
    elif "tiktok.com" in url:
        return "TikTok"
    elif "instagram.com" in url:
        return "Instagram"
    elif "facebook.com" in url:
        return "Facebook"
    return "Video"


# ⬇️ Download function
def download_video(url, user_id):
    filename = f"downloads/{user_id}_{int(time.time())}.%(ext)s"

    ydl_opts = {
        "format": "best",
        "outtmpl": filename,
        "quiet": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        return file_path, info


# 📩 Handle messages
@dp.message_handler()
async def handle_message(message: types.Message):
    url = message.text
    user_id = message.from_user.id

    if not url.startswith("http"):
        await message.reply("❌ Send a valid video link.")
        return

    platform = detect_platform(url)
    msg = await message.reply(f"⏳ Downloading from {platform}...")

    try:
        file_path, info = download_video(url, user_id)

        title = info.get("title", "Video")
        duration = info.get("duration", 0)
        views = info.get("view_count", "N/A")

        caption = f"🎬 {title}\n⏱ Duration: {duration}s\n👀 Views: {views}"

        # 📸 Thumbnail
        thumb_url = info.get("thumbnail")
        thumb_path = None

        if thumb_url:
            import requests
            thumb_path = f"downloads/{user_id}_thumb.jpg"
            with open(thumb_path, "wb") as f:
                f.write(requests.get(thumb_url).content)

        # 🎥 Send video
        await message.reply_video(
            video=InputFile(file_path),
            caption=caption,
            parse_mode="Markdown",
            thumb=InputFile(thumb_path) if thumb_path else None
        )

        await msg.edit_text("✅ Download complete!")

        # 🧹 Cleanup
        os.remove(file_path)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

    except Exception as e:
        await msg.edit_text("❌ Failed to download. Try another link.")


# 🌐 Start web server (Render fix)
threading.Thread(target=run_web).start()

# 🚀 Start bot
print("🔥 Bot is running...")
executor.start_polling(dp)
