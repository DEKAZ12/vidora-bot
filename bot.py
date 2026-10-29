import os
import json
import logging
import asyncio
import datetime
import yt_dlp
import requests
from keep_alive import keep_alive
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
from telegram.constants import ParseMode

# ==========================================
# ⚙️ تنظیمات اصلی
# ==========================================
TOKEN = os.getenv("TOKEN")
CHANNEL_USERNAME = "@VidoraDownloadercl"
ADMIN_ID = 7738720967
BOT_USERNAME = "@Vidora22DLBot"

DATA_FILE = "bot_data.json"
DAILY_LIMIT = 5

# ==========================================
# 🗄️ دیتابیس
# ==========================================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"users": {}, "total_downloads": 0, "banned_users": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_user_status(user_id):
    data = load_data()
    if str(user_id) in data.get("banned_users", []):
        return "banned"
    return "active"

# ==========================================
# 🛠️ توابع دانلود
# ==========================================
def download_tiktok_api(url: str):
    try:
        api_url = f"https://tikwm.com/api/?url={url}"
        response = requests.get(api_url, timeout=15).json()
        if response.get("code") == 0:
            video_url = response["data"]["play"]
            title = response["data"]["title"]
            file_path = f"downloads/{response['data']['id']}.mp4"
            video_data = requests.get(video_url, timeout=20).content
            with open(file_path, "wb") as f:
                f.write(video_data)
            return file_path, title
        return None, None
    except:
        return None, None

def download_ytdlp(url: str, media_type: str):
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'impersonate': 'chrome'
    }
    if media_type == "audio":
        ydl_opts['format'] = 'ba/b'
    else:
        ydl_opts['format'] = 'b[filesize<49M]/b'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            for ext in ['.mp4', '.mkv', '.webm', '.m4a', '.mp3']:
                if os.path.exists(base + ext):
                    return base + ext, info.get('title', 'Unknown')
    except Exception as e:
        print(f"YTDLP Error: {e}")
        return None, None

# ==========================================
# 🎮 هندلرها (دستورات و دکمه‌ها)
# ==========================================
async def is_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=update.effective_user.id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return True

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if get_user_status(user_id) == "banned":
        await update.message.reply_text("⛔️ شما از استفاده از ربات مسدود شده‌اید.")
        return

    data = load_data()
    today = str(datetime.date.today())

    if user_id not in data["users"]:
        data["users"][user_id] = {"daily_downloads": 0, "last_date": today, "bonus": 0}
        save_data(data)
    
    # اضافه شدن دکمه پیام ناشناس به منوی اصلی
    keyboard = [
        [InlineKeyboardButton("📢 کانال ما", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"), InlineKeyboardButton("🎁 دعوت دوستان", callback_data="invite")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help"), InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
        [InlineKeyboardButton("📩 ارسال پیام به ادمین (ناشناس)", callback_data="contact_admin")]
    ]
    
    welcome_text = (
        f"سلام <b>{update.effective_user.first_name}</b> عزیز 👋\n\n"
        "به ربات <b>دانلودر فوق‌حرفه‌ای Vidora</b> خوش آمدی! 🚀\n\n"
        "کافیه لینک ویدیو (یوتیوب، اینستا، تیک‌تاک) رو بفرستی تا برات دانلودش کنم.\n\n"
        "👇 <i>همین الان یه لینک بفرست!</i>"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def contact_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = 'waiting_for_admin_msg'
    text = (
        "📩 <b>ارسال پیام ناشناس</b>\n\n"
        "لطفاً پیام، ایده، انتقاد یا درخواست تبلیغ خود را در یک پیام بنویسید و ارسال کنید.\n\n"
        "⚠️ پیام شما بدون اینکه اطلاعات شما نمایش داده شود، مستقیماً برای مدیریت ارسال می‌شود."
    )
    keyboard = [[InlineKeyboardButton("🔙 انصراف", callback_data="cancel_admin_msg")]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def cancel_admin_msg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    await query.message.delete()
    await start_command(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if get_user_status(user_id) == "banned":
        await update.message.reply_text("⛔️ شما مسدود هستید.")
        return

    if not await is_member(update, context):
        keyboard = [
            [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")]
        ]
        await update.message.reply_text("⛔️ <b>اول توی کانال عضو شو!</b> 👇", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # چک کردن اینکه کاربر توی حالت ارسال پیام ناشناس هست یا نه
    if context.user_data.get('state') == 'waiting_for_admin_msg':
        user_msg = update.message.text
        try:
            admin_text = (
                "📩 <b>پیام ناشناس جدید از کاربر:</b>\n\n"
                f"<i>{user_msg}</i>"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML)
            await update.message.reply_text("✅ پیام شما با موفقیت و به صورت ناشناس برای ادمین ارسال شد.")
        except Exception:
            await update.message.reply_text("❌ خطا در ارسال پیام.")
        
        context.user_data['state'] = None
        return

    # اگر در حالت ارسال پیام نبود، یعنی داره لینک می‌فرسته
    url = update.message.text
    if not url.startswith("http"):
        await update.message.reply_text("❌ لطفاً یک لینک معتبر بفرست یا از دکمه‌های منو استفاده کن.")
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
        await query.edit_message_text("⚠️ <b>محدودیت روزانه!</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    url = context.user_data.get('url')
    if not url:
        await query.edit_message_text("❌ لینک منقضی شده! دوباره بفرست.")
        return

    media_type = "video" if query.data == "dl_video" else "audio"
    await query.edit_message_text("⏳ <b>در حال پردازش...</b>", parse_mode=ParseMode.HTML)

    file_path, title = None, None
    if "tiktok.com" in url:
        file_path, title = await asyncio.to_thread(download_tiktok_api, url)
    
    if not file_path:
        file_path, title = await asyncio.to_thread(download_ytdlp, url, media_type)

    if file_path:
        data["users"][user_id]["daily_downloads"] += 1
        data["total_downloads"] += 1
        save_data(data)

        caption = (
            f"🎉 <b>آماده شد!</b>\n\n"
            f"🎬 <b>عنوان:</b> <i>{str(title)[:50]}...</i>\n\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            "📢 <b>تبلیغات حامی:</b>\n"
            "🔗 <a href='https://t.me/VidoraDownloadercl'>کانال ما رو دنبال کنید!</a>\n"
            "➖➖➖➖➖➖➖➖➖➖\n\n"
            f"🤖 {BOT_USERNAME}"
        )

        try:
            if media_type == "video" or "tiktok.com" in url:
                await query.message.reply_video(video=open(file_path, 'rb'), caption=caption, parse_mode=ParseMode.HTML)
            else:
                await query.message.reply_audio(audio=open(file_path, 'rb'), caption=caption, parse_mode=ParseMode.HTML)
            
            await query.message.delete()
            os.remove(file_path)
        except:
            await query.edit_message_text("❌ خطا در ارسال فایل.")
    else:
        await query.edit_message_text("❌ <b>دانلود ناموفق بود!</b>", parse_mode=ParseMode.HTML)

# ==========================================
# 👑 دستورات ادمین
# ==========================================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    data = load_data()
    text = (
        "👑 <b>پنل مدیریت</b>\n\n"
        f"👥 کاربران: {len(data['users'])}\n"
        f"📥 دانلودها: {data['total_downloads']}\n"
        f"🚫 مسدودها: {len(data.get('banned_users', []))}\n\n"
        "/ban [آیدی] - مسدود کردن\n"
        "/unban [آیدی] - آزاد کردن"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return
    user_to_ban = str(context.args[0])
    data = load_data()
    if "banned_users" not in data: data["banned_users"] = []
    if user_to_ban not in data["banned_users"]:
        data["banned_users"].append(user_to_ban)
        save_data(data)
        await update.message.reply_text(f"✅ کاربر {user_to_ban} مسدود شد.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return
    user_to_unban = str(context.args[0])
    data = load_data()
    if user_to_unban in data.get("banned_users", []):
        data["banned_users"].remove(user_to_unban)
        save_data(data)
        await update.message.reply_text(f"✅ کاربر {user_to_unban} آزاد شد.")

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await is_member(update, context):
        await query.edit_message_text("✅ عالی! حالا لینکت رو بفرست.")
    else:
        await query.answer("❌ هنوز عضو نشدی!", show_alert=True)

# ==========================================
# 🚀 اجرای برنامه
# ==========================================
def main():
    print("⏳ در حال روشن کردن ربات...")
    keep_alive()
    
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.add_handler(CallbackQueryHandler(contact_admin_callback, pattern="contact_admin"))
    app.add_handler(CallbackQueryHandler(cancel_admin_msg_callback, pattern="cancel_admin_msg"))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="dl_"))
    
    # هندلرهای منو (help, about, invite, settings)
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.edit_message_text("📖 راهنما..."), pattern="help"))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.edit_message_text("⚙️ تنظیمات..."), pattern="settings"))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.edit_message_text("🎁 سیستم دعوت..."), pattern="invite"))

    print("✅ ربات با موفقیت روشن شد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()