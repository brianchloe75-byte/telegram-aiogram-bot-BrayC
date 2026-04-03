import os
import time
import asyncio
import logging
from aiohttp import web
import yt_dlp

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

# ------------------------------
# CONFIG
# ------------------------------
TOKEN = os.getenv("TOKEN")
MAIN_BOT_USERNAME = "BrayC_bot"
YOUTUBE_BOT_USERNAME = "EarthsBestDownloader-bot"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# ------------------------------
# QUEUE & COOLDOWN
# ------------------------------
semaphore = asyncio.Semaphore(2)
cooldown = {}

# ------------------------------
# WEB SERVER (ASYNC - NO CRASH)
# ------------------------------
async def handle(request):
    return web.Response(text="Alive")

async def start_web():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ------------------------------
# PLATFORM DETECTION
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
        return "Twitter/X"
    elif "pinterest.com" in url:
        return "Pinterest"
    elif "reddit.com" in url:
        return "Reddit"
    elif "vimeo.com" in url:
        return "Vimeo"
    return "Unknown"

# ------------------------------
# DOWNLOAD FUNCTION (SAFE)
# ------------------------------
def download_video(url, user_id, choice):
    filename = f"downloads/{user_id}_{int(time.time())}.%(ext)s"

    formats = {
        "hd": ["bestvideo+bestaudio", "best"],
        "sd": ["best[height<=480]", "best"],
        "audio": ["bestaudio"]
    }

    for fmt in formats[choice]:
        try:
            with yt_dlp.YoutubeDL({
                "format": fmt,
                "outtmpl": filename,
                "quiet": True,
                "retries": 3,
                "fragment_retries": 3
            }) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
        except:
            continue

    raise Exception("Download failed")

# ------------------------------
# COMMANDS
# ------------------------------
@dp.message()
async def handle_all(message: types.Message):
    text = message.text

    if text == "/start":
        return await message.answer(
            f"🔥 Multi Downloader\n\n"
            f"Send a link to download\n"
            f"📢 @{BrayC_bot}"
        )

    url = text.strip()
    user_id = message.from_user.id

    # cooldown
    if time.time() - cooldown.get(user_id, 0) < 5:
        return await message.reply("⏳ Wait a few seconds.")
    cooldown[user_id] = time.time()

    platform = detect_platform(url)

    if platform == "YouTube":
        return await message.reply(f"Use @{EarthsBestDownloader_bot}")

    if platform == "Unknown":
        return await message.reply("❌ Unsupported link")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="HD", callback_data=f"hd|{url}"),
            InlineKeyboardButton(text="SD", callback_data=f"sd|{url}")
        ],
        [
            InlineKeyboardButton(text="Audio", callback_data=f"audio|{url}")
        ]
    ])

    await message.reply(f"{platform} detected. Choose:", reply_markup=kb)

# ------------------------------
# CALLBACK HANDLER
# ------------------------------
@dp.callback_query()
async def buttons(call: types.CallbackQuery):
    choice, url = call.data.split("|")
    asyncio.create_task(process_download(call.message, url, call.from_user.id, choice))
    await call.answer()

# ------------------------------
# PROCESS DOWNLOAD (RETRY SAFE)
# ------------------------------
async def process_download(message, url, user_id, choice):
    async with semaphore:
        msg = await message.answer("⏳ Processing...")

        loop = asyncio.get_event_loop()

        for attempt in range(3):
            try:
                await msg.edit_text(f"⬇️ Downloading ({attempt+1}/3)")

                file_path = await loop.run_in_executor(
                    None, lambda: download_video(url, user_id, choice)
                )

                size = os.path.getsize(file_path) / (1024 * 1024)
                if size > 50:
                    os.remove(file_path)
                    return await msg.edit_text("❌ File too large")

                await msg.edit_text("📤 Uploading...")

                file = FSInputFile(file_path)

                if choice == "audio":
                    await message.answer_audio(file)
                else:
                    await message.answer_video(file)

                os.remove(file_path)
                return await msg.edit_text("✅ Done")

            except Exception as e:
                print("Retry error:", e)
                await asyncio.sleep(1)

        await msg.edit_text("❌ Failed after retries")

# ------------------------------
# MAIN (AUTO-RESTART)
# ------------------------------
async def main():
    while True:
        try:
            print("🚀 Bot running...")

            await start_web()
            await dp.start_polling(bot)

        except Exception as e:
            print("💥 Crash:", e)
            await asyncio.sleep(5)

# ------------------------------
# START
# ------------------------------
if _name_ == "_main_":
    asyncio.run(main())
