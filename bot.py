import os
import json
import logging
import asyncio
import datetime
import yt_dlp
from keep_alive import keep_alive
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# ==========================================
# ⚙️ تنظیمات اصلی
# ==========================================
TOKEN = os.getenv("TOKEN")  # توکن رو در Render تنظیم می‌کنیم
CHANNEL_USERNAME = "@VidoraDownloadercl"
ADMIN_ID = 7738720967
BOT_USERNAME = "@VidoraDownloadercl"

# ==========================================
# 🗄️ دیتابیس
# ==========================================
DATA_FILE = "bot_data.json"
DAILY_LIMIT = 5

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"users": {}, "total_downloads": 0}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# ==========================================
# 🛠️ توابع کمکی
# ==========================================
async def is_user_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=update.effective_user.id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return True

def download_media(url: str, media_type: str):
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    if media_type == "audio":
        ydl_opts['format'] = 'bestaudio/best'
    else:
        ydl_opts['format'] = 'best[filesize<49M]/bestvideo[filesize<49M]+bestaudio/best'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        base, _ = os.path.splitext(filename)
        for ext in ['.mp4', '.mkv', '.webm', '.m4a', '.mp3']:
            if os.path.exists(base + ext):
                return base + ext, info.get('title', 'Unknown')
        return filename, info.get('title', 'Unknown')

# ==========================================
# 🎮 هندلرها
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    today = str(datetime.date.today())

    if context.args and context.args[0].startswith("ref_"):
        inviter_id = context.args[0].replace("ref_", "")
        if inviter_id in data["users"] and inviter_id != user_id:
            data["users"][inviter_id]["bonus"] = data["users"].get(inviter_id, {}).get("bonus", 0) + 2
            save_data(data)
            try:
                await context.bot.send_message(inviter_id, "🎉 یکی از دوستانت با لینک تو وارد ربات شد! ۲ دانلود هدیه گرفتی.")
            except:
                pass

    if user_id not in data["users"]:
        data["users"][user_id] = {"daily_downloads": 0, "last_date": today, "bonus": 0}
        save_data(data)
    
    keyboard = [
        [InlineKeyboardButton("📢 کانال ما", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("🎁 دعوت دوستان (جایزه)", callback_data="invite")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help"), InlineKeyboardButton("ℹ️ درباره ما", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"سلام <b>{update.effective_user.first_name}</b> عزیز 👋\n\n"
        "به ربات <b>دانلودر حرفه‌ای Vidora</b> خوش آمدی! 🚀\n\n"
        "🎯 <b>چطور کار می‌کنم؟</b>\n"
        "کافیه لینک ویدیو رو برام بفرستی تا برات دانلودش کنم.\n\n"
        "👇 <i>همین الان یه لینک بفرست!</i>"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def invite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start=ref_{user_id}"
    text = (
        "🎁 <b>سیستم دعوت دوستان</b>\n\n"
        "با دعوت دوستانت به ربات، به ازای هر نفر <b>۲ دانلود هدیه</b> بگیر!\n\n"
        f"🔗 <b>لینک اختصاصی شما:</b>\n<code>{link}</code>\n\n"
        "این لینک رو برای دوستات بفرست."
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]]))

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "📖 <b>راهنما</b>\n\n"
        "1️⃣ لینک رو کپی کن.\n"
        "2️⃣ بفرستش.\n"
        "3️⃣ نوع خروجی (ویدیو یا صدا) رو انتخاب کن.\n"
        f"⚠️ <b>محدودیت روزانه:</b> {DAILY_LIMIT} دانلود رایگان.\n"
        "📦 <b>حجم مجاز:</b> زیر ۵۰ مگابایت."
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]]))

async def about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "ℹ️ <b>درباره ربات</b>\n\nساخته شده با yt-dlp\n👨‍💻 نسخه 3.0"
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]]))

async def back_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await start_command(update, context)

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await is_user_member(update, context):
        await query.edit_message_text("✅ عالی! حالا لینکت رو بفرست.")
    else:
        await query.answer("❌ هنوز عضو نشدی!", show_alert=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_member(update, context):
        keyboard = [
            [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")]
        ]
        await update.message.reply_text("⛔️ <b>اول توی کانال عضو شو!</b> 👇", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    url = update.message.text
    if not url.startswith("http"):
        await update.message.reply_text("❌ لطفاً یک لینک معتبر بفرست.")
        return

    context.user_data['url'] = url
    keyboard = [
        [InlineKeyboardButton("🎬 دانلود ویدیو (MP4)", callback_data="dl_video")],
        [InlineKeyboardButton("🎵 دانلود صدا (MP3)", callback_data="dl_audio")]
    ]
    await update.message.reply_text("لینک دریافت شد ✅\nچی می‌خوای؟ 👇", reply_markup=InlineKeyboardMarkup(keyboard))

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = load_data()
    today = str(datetime.date.today())

    if data["users"][user_id]["last_date"] != today:
        data["users"][user_id]["daily_downloads"] = 0
        data["users"][user_id]["last_date"] = today
        save_data(data)

    if data["users"][user_id]["daily_downloads"] >= (DAILY_LIMIT + data["users"][user_id].get("bonus", 0)):
        keyboard = [[InlineKeyboardButton("🎁 دعوت دوستان", callback_data="invite")]]
        await query.edit_message_text("⚠️ <b>محدودیت روزانه!</b>\nبرای دانلود بیشتر دوستانت رو دعوت کن.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    url = context.user_data.get('url')
    if not url:
        await query.edit_message_text("❌ خطا! لینک رو دوباره بفرست.")
        return

    media_type = "video" if query.data == "dl_video" else "audio"
    await query.edit_message_text("⏳ <b>در حال دانلود...</b>\n<i>صبر کن.</i>", parse_mode=ParseMode.HTML)

    try:
        file_path, title = await asyncio.to_thread(download_media, url, media_type)
        
        data["users"][user_id]["daily_downloads"] += 1
        data["total_downloads"] += 1
        save_data(data)

        caption = (
            f"🎉 <b>آماده شد!</b>\n\n"
            f"🎬 <b>عنوان:</b> <i>{title[:50]}...</i>\n\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            "📢 <b>تبلیغات حامی:</b>\n"
            "🔗 <a href='https://t.me/VidoraDownloadercl'>کانال ما رو دنبال کنید!</a>\n"
            "➖➖➖➖➖➖➖➖➖➖\n\n"
            f"🤖 {BOT_USERNAME}"
        )

        if media_type == "video":
            await query.message.reply_video(video=open(file_path, 'rb'), caption=caption, parse_mode=ParseMode.HTML, supports_streaming=True)
        else:
            await query.message.reply_audio(audio=open(file_path, 'rb'), caption=caption, parse_mode=ParseMode.HTML)

        await query.message.delete()
        os.remove(file_path)

    except Exception as e:
        error_msg = str(e)
        if "File is larger than" in error_msg or "filesize" in error_msg:
            await query.edit_message_text("❌ <b>حجم فایل زیاده!</b>\nتلگرام اجازه بالای ۵۰ مگ رو نمیده.", parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text(f"❌ <b>خطا در دانلود!</b>\n<i>لینک خصوصیه یا سایت پشتیبانی نمیشه.</i>", parse_mode=ParseMode.HTML)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    data = load_data()
    text = f"📊 <b>آمار:</b>\n\n👥 کاربران: {len(data['users'])}\n📥 دانلودها: {data['total_downloads']}"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❗️ روش: \n<code>/broadcast متن شما</code>", parse_mode=ParseMode.HTML)
        return
    msg = " ".join(context.args)
    data = load_data()
    success = 0
    await update.message.reply_text("⏳ در حال ارسال...")
    for user in data["users"]:
        try:
            await context.bot.send_message(chat_id=user, text=msg)
            success += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await update.message.reply_text(f"✅ به {success} نفر ارسال شد.")

# ==========================================
# 🚀 اجرا
# ==========================================
def main():
    print("⏳ در حال روشن کردن ربات...")
    
    # سرور آنلاین (برای Render)
    keep_alive()
    
    if not TOKEN:
        print("❌ خطا: توکن پیدا نشد! باید در تنظیمات Render متغیر TOKEN را تنظیم کنی.")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    
    app.add_handler(CallbackQueryHandler(help_callback, pattern="help"))
    app.add_handler(CallbackQueryHandler(about_callback, pattern="about"))
    app.add_handler(CallbackQueryHandler(invite_callback, pattern="invite"))
    app.add_handler(CallbackQueryHandler(back_start_callback, pattern="back_start"))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="dl_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ ربات روشن شد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()