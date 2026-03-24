import os
import time
import datetime
import asyncio
import yt_dlp
import matplotlib.pyplot as plt
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor

# Get token from environment for cloud deployment
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Create downloads folder
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# User session & analytics
user_data = {}
users = set()
analytics = {}
global_stats = {"total_downloads": 0, "total_mb": 0, "daily": {}}

# Limit concurrent downloads
MAX_CONCURRENT_DOWNLOADS = 3
semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)


# ------------------------
# UTILITIES
# ------------------------
def detect_platform(url):
    if "youtube.com" in url or "youtu.be" in url:
        return "▶️ YouTube"
    elif "tiktok.com" in url:
        return "🎵 TikTok"
    elif "instagram.com" in url:
        return "📸 Instagram"
    elif "facebook.com" in url:
        return "📘 Facebook"
    else:
        return "🌐 Video"


def generate_growth_chart():
    dates = sorted(global_stats["daily"].keys())
    downloads = [global_stats["daily"][d]["downloads"] for d in dates]
    sizes = [global_stats["daily"][d]["mb"] for d in dates]

    plt.figure(figsize=(10,5))
    plt.plot(dates, downloads, marker='o', label="Downloads")
    plt.plot(dates, sizes, marker='x', label="Total MB")
    plt.title("Bot Growth Analytics")
    plt.xlabel("Date")
    plt.ylabel("Count / MB")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    chart_path = "downloads/growth_chart.png"
    plt.savefig(chart_path)
    plt.close()
    return chart_path


# ------------------------
# COMMAND HANDLERS
# ------------------------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply("🔥 Bot is running! Send a video link to download.")


@dp.message_handler(commands=["stats"])
async def stats(message: types.Message):
    await message.reply(f"👥 Total users: {len(users)}")


@dp.message_handler(commands=["analytics"])
async def show_analytics(message: types.Message):
    chat_id = message.chat.id
    user_stats = analytics.get(chat_id, {"downloads": 0, "total_mb": 0})
    await message.reply(
        f"📊 Your Analytics:\n"
        f"Videos downloaded: {user_stats['downloads']}\n"
        f"Total size: {user_stats['total_mb']:.2f} MB"
    )


@dp.message_handler(commands=["growth"])
async def growth(message: types.Message):
    chart_path = generate_growth_chart()
    await message.reply_photo(photo=open(chart_path, "rb"))


# ------------------------
# VIDEO LINK HANDLER
# ------------------------
@dp.message_handler()
async def handle_message(message: types.Message):
    url = message.text
    chat_id = message.chat.id

    users.add(message.from_user.id)
    platform = detect_platform(url)

    info_msg = await message.reply("🔍 Fetching video info...")

    try:
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "Video")
        duration = info.get("duration", 0)
        thumbnail = info.get("thumbnail")
        minutes = duration // 60
        seconds = duration % 60

        user_data[chat_id] = {"url": url, "title": title, "platform": platform}

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton("🎥 HD", callback_data="hd")],
                [InlineKeyboardButton("📱 SD", callback_data="sd")],
                [InlineKeyboardButton("🎧 Audio", callback_data="audio")]
            ]
        )

        caption = (
            f"{platform}\n\n"
            f"🎬 {title}\n"
            f"⏱️ {minutes}:{seconds:02d}\n\n"
            f"⚡ Choose format:"
        )

        await info_msg.delete()

        await message.reply_photo(
            photo=thumbnail,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except Exception as e:
        await info_msg.edit_text("❌ Couldn't fetch video info.")


# ------------------------
# BUTTON HANDLER
# ------------------------
@dp.callback_query_handler(lambda c: True)
async def handle_choice(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = user_data.get(chat_id)
    if not data:
        await callback_query.message.reply("❌ Session expired. Send link again.")
        return

    asyncio.create_task(process_download(chat_id, callback_query.message, callback_query.data))
    await callback_query.answer()


# ------------------------
# DOWNLOAD FUNCTION
# ------------------------
async def process_download(chat_id, message, choice):
    async with semaphore:
        data = user_data.get(chat_id)
        if not data:
            return

        url = data["url"]
        title = data["title"]
        platform = data["platform"]

        msg = await message.reply("⏳ Downloading now...")

        try:
            filename = f"downloads/{chat_id}_{int(time.time())}.%(ext)s"

            if platform == "🎵 TikTok":
                fmt = "bestvideo+bestaudio/best"
                ydl_opts = {
                    "format": fmt,
                    "outtmpl": filename,
                    "quiet": True,
                    "noplaylist": True,
                    "merge_output_format": "mp4",
                    "concurrent_fragment_downloads": 5,
                    "retries": 5,
                    "postprocessors": [{"key": "FFmpegMetadata"}],
                }
            else:
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
                    "merge_output_format": "mp4",
                    "http_headers": {"User-Agent": "Mozilla/5.0"},
                    "concurrent_fragment_downloads": 5,
                    "retries": 5,
                }

            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=True))
            file_path = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info)

            if choice != "audio" and not file_path.endswith(".mp4"):
                file_path = file_path.rsplit(".", 1)[0] + ".mp4"

            size = os.path.getsize(file_path) / (1024 * 1024)
            if size > 49:
                os.remove(file_path)
                await msg.edit_text("❌ File too large (>50MB). Try SD.")
                return

            await msg.edit_text("📤 Uploading...")

            if choice == "audio":
                await message.reply_audio(audio=open(file_path, "rb"), title=title)
            else:
                await message.reply_video(video=open(file_path, "rb"), caption=f"🎬 {title}")

            os.remove(file_path)
            await msg.edit_text("✅ Done!\n📥 Tap → Save to gallery")
            await message.reply("🚀 Share this bot with friends:\n@YourBotUsername")

            # Update user analytics
            user_stats = analytics.get(chat_id, {"downloads": 0, "total_mb": 0})
            user_stats["downloads"] += 1
            user_stats["total_mb"] += size
            analytics[chat_id] = user_stats

            # Update global stats
            today = datetime.date.today().isoformat()
            if today not in global_stats["daily"]:
                global_stats["daily"][today] = {"downloads": 0, "mb": 0}
            global_stats["total_downloads"] += 1
            global_stats["total_mb"] += size
            global_stats["daily"][today]["downloads"] += 1
            global_stats["daily"][today]["mb"] += size

        except Exception as e:
            await msg.edit_text("❌ Failed. Try another link.")


# ------------------------
# START BOT
# ------------------------
if __name__ == "__main__":
    print("🔥 ULTRA PRO AIORAM BOT RUNNING")
    executor.start_polling(dp, skip_updates=True)