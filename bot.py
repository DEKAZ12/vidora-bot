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
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# ==========================================
# ⚙️ تنظیمات اصلی و لاگ‌ها
# ==========================================
TOKEN = os.getenv("TOKEN")
CHANNEL_USERNAME = "@VidoraDownloadercl"
ADMIN_ID = 7738720967
BOT_USERNAME = "@Vidora22DLBot"

DATA_FILE = "bot_data.json"
DAILY_LIMIT = 5

# تنظیم سیستم لاگ برای دیباگ کردن در رندر
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ساخت پوشه دانلود در صورت نبودن
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# ==========================================
# 🗄️ توابع دیتابیس (ذخیره کاربران)
# ==========================================
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"users": {}, "total_downloads": 0, "banned_users": []}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def get_user_status(user_id):
    data = load_data()
    if str(user_id) in data.get("banned_users", []):
        return "banned"
    return "active"

def check_daily_limit(user_id):
    data = load_data()
    today = str(datetime.date.today())
    user_id_str = str(user_id)
    
    if user_id_str not in data["users"]:
        data["users"][user_id_str] = {"daily_downloads": 0, "last_date": today, "bonus": 0}
        save_data(data)
        return True, DAILY_LIMIT
    
    user = data["users"][user_id_str]
    if user.get("last_date") != today:
        user["daily_downloads"] = 0
        user["last_date"] = today
        save_data(data)
    
    max_allowed = DAILY_LIMIT + user.get("bonus", 0)
    if user["daily_downloads"] >= max_allowed:
        return False, 0
    
    return True, max_allowed - user["daily_downloads"]

def increment_download(user_id):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str in data["users"]:
        data["users"][user_id_str]["daily_downloads"] += 1
        data["total_downloads"] += 1
        save_data(data)

# ==========================================
# 🛠️ موتورهای دانلود
# ==========================================
def download_tiktok_no_watermark(url: str):
    """دانلود تیک‌تاک بدون واترمارک با استفاده از API قدرتمند"""
    try:
        api_url = f"https://tikwm.com/api/?url={url}"
        response = requests.get(api_url, timeout=15).json()
        
        if response.get("code") == 0:
            video_data = response["data"]
            video_url = video_data.get("play") # لینک بدون واترمارک
            title = video_data.get("title", "TikTok Video")
            video_id = video_data.get("id", "tiktok_vid")
            
            file_path = f"downloads/{video_id}.mp4"
            
            # دانلود فایل ویدیو
            vid_response = requests.get(video_url, timeout=20)
            with open(file_path, "wb") as f:
                f.write(vid_response.content)
                
            return file_path, title, "video"
        return None, None, None
    except Exception as e:
        logger.error(f"TikTok Download Error: {e}")
        return None, None, None

def download_ytdlp(url: str, media_type: str):
    """دانلود از یوتیوب، اینستاگرام و..."""
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'impersonate': 'chrome', # دور زدن فیلتر اینستاگرام
        'timeout': 30
    }
    
    if media_type == "audio":
        ydl_opts['format'] = 'bestaudio/best'
    else:
        ydl_opts['format'] = 'best[filesize<49M]/bestvideo[filesize<49M]+bestaudio/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            
            for ext in ['.mp4', '.mkv', '.webm', '.m4a', '.mp3']:
                if os.path.exists(base + ext):
                    return base + ext, info.get('title', 'Unknown'), media_type
        return None, None, None
    except Exception as e:
        logger.error(f"YTDLP Error: {e}")
        return None, None, None

# ==========================================
# 🎮 هندلرهای ربات (دستورات)
# ==========================================
async def is_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=update.effective_user.id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return True

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if get_user_status(user_id) == "banned":
        await update.message.reply_text("⛔️ شما از استفاده از ربات مسدود شده‌اید.")
        return

    data = load_data()
    today = str(datetime.date.today())

    # ثبت‌نام کاربر جدید
    if user_id not in data["users"]:
        data["users"][user_id] = {"daily_downloads": 0, "last_date": today, "bonus": 0}
        save_data(data)
    
    # منوی اصلی
    keyboard = [
        [
            InlineKeyboardButton("📢 کانال ما", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
            InlineKeyboardButton("🎁 دعوت دوستان", callback_data="invite")
        ],
        [
            InlineKeyboardButton("📖 راهنما", callback_data="help"),
            InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")
        ],
        [
            InlineKeyboardButton("📩 ارسال پیام به ادمین", callback_data="contact_admin")
        ]
    ]
    
    welcome_text = (
        f"سلام <b>{update.effective_user.first_name}</b> عزیز 👋\n\n"
        "به ربات <b>دانلودر حرفه‌ای Vidora</b> خوش آمدی! 🚀\n\n"
        "🎯 <b>امکانات ربات:</b>\n"
        "✅ دانلود از یوتیوب، اینستاگرام و...\n"
        "✅ دانلود تیک‌تاک <b>بدون واترمارک</b>\n\n"
        "👇 <i>همین الان یه لینک بفرست!</i>"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # چک کردن مسدودی
    if get_user_status(user_id) == "banned":
        await update.message.reply_text("⛔️ شما مسدود هستید.")
        return

    # چک کردن عضویت در کانال
    if not await is_member(update, context):
        keyboard = [
            [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")]
        ]
        await update.message.reply_text("⛔️ <b>دسترسی محدود!</b>\nبرای استفاده از ربات، اول باید توی کانال ما عضو بشی 👇", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # سیستم پیام ناشناس
    if context.user_data.get('state') == 'waiting_for_admin_msg':
        user_msg = update.message.text
        admin_text = f"📩 <b>پیام ناشناس جدید:</b>\n\n<i>{user_msg}</i>\n\n👤 برای پاسخ کلیک کنید:"
        reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ پاسخ به این کاربر", callback_data=f"reply_{user_id}")]])
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML, reply_markup=reply_kb)
            await update.message.reply_text("✅ پیام شما به صورت ناشناس برای مدیریت ارسال شد.")
        except:
            await update.message.reply_text("❌ خطا در ارسال پیام.")
        context.user_data['state'] = None
        return

    # سیستم پاسخ ادمین به کاربر
    if update.effective_user.id == ADMIN_ID and context.user_data.get('state', '').startswith('reply_'):
        target_user = context.user_data['state'].replace('reply_', '')
        try:
            await context.bot.send_message(chat_id=target_user, text=f"📬 <b>پاسخ مدیریت:</b>\n\n<i>{update.message.text}</i>", parse_mode=ParseMode.HTML)
            await update.message.reply_text("✅ پاسخ شما برای کاربر ارسال شد.")
        except:
            await update.message.reply_text("❌ کاربر ربات را بلاک کرده است.")
        context.user_data['state'] = None
        return

    # دریافت لینک
    url = update.message.text
    if not url.startswith("http"):
        await update.message.reply_text("❌ لطفاً یک لینک معتبر بفرست یا از دکمه‌های منو استفاده کن.")
        return

    # ذخیره لینک در حافظه
    context.user_data['url'] = url
    
    # تشخیص خودکار نوع لینک برای پیام بهتر
    site_name = "ویدیو"
    if "tiktok.com" in url: site_name = "تیک‌تاک (بدون واترمارک)"
    elif "instagram.com" in url: site_name = "اینستاگرام"
    elif "youtube.com" in url or "youtu.be" in url: site_name = "یوتیوب"

    keyboard = [
        [InlineKeyboardButton("🎬 دانلود ویدیو (MP4)", callback_data="dl_video")],
        [InlineKeyboardButton("🎵 دانلود صدا (MP3)", callback_data="dl_audio")]
    ]
    await update.message.reply_text(f"لینک {site_name} دریافت شد ✅\nچی می‌خوای؟ 👇", reply_markup=InlineKeyboardMarkup(keyboard))

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # چک کردن محدودیت دانلود
    can_download, remaining = check_daily_limit(user_id)
    if not can_download:
        keyboard = [[InlineKeyboardButton("🎁 دعوت دوستان برای دانلود بیشتر", callback_data="invite")]]
        await query.edit_message_text("⚠️ <b>محدودیت روزانه!</b>\nشما به سقف دانلود امروز رسیدی.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    url = context.user_data.get('url')
    if not url:
        await query.edit_message_text("❌ لینک منقضی شده! لطفاً لینک را دوباره بفرستید.")
        return

    media_type = "video" if query.data == "dl_video" else "audio"
    await query.edit_message_text("⏳ <b>در حال پردازش و دانلود...</b>\n<i>لطفاً صبر کنید، این ممکن است کمی طول بکشد.</i>", parse_mode=ParseMode.HTML)

    file_path, title, file_type = None, None, None

    # 1. اگر تیک‌تاک بود، از API بدون واترمارک استفاده کن
    if "tiktok.com" in url and media_type == "video":
        file_path, title, file_type = await asyncio.to_thread(download_tiktok_no_watermark, url)
    
    # 2. اگر تیک‌تاک نبود یا صدا می‌خواست، از yt-dlp استفاده کن
    if not file_path:
        file_path, title, file_type = await asyncio.to_thread(download_ytdlp, url, media_type)

    # 3. ارسال فایل
    if file_path:
        increment_download(user_id)
        
        caption = (
            f"🎉 <b>دانلود با موفقیت انجام شد!</b>\n\n"
            f"🎬 <b>عنوان:</b> <i>{str(title)[:50]}...</i>\n"
            f"📥 <b>دانلودهای باقی‌مانده امروز:</b> {remaining - 1}\n\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            "📢 <b>تبلیغات حامی:</b>\n"
            "🔗 <a href='https://t.me/VidoraDownloadercl'>کانال ما رو دنبال کنید!</a>\n"
            "➖➖➖➖➖➖➖➖➖➖\n\n"
            f"🤖 {BOT_USERNAME}"
        )

        try:
            if media_type == "video" or file_type == "video":
                await query.message.reply_video(video=open(file_path, 'rb'), caption=caption, parse_mode=ParseMode.HTML, supports_streaming=True)
            else:
                await query.message.reply_audio(audio=open(file_path, 'rb'), caption=caption, parse_mode=ParseMode.HTML)
            
            await query.message.delete()
            os.remove(file_path) # پاک کردن فایل از سرور برای آزادسازی فضا
        except Exception as e:
            logger.error(f"Send Error: {e}")
            await query.edit_message_text("❌ خطا در ارسال فایل به تلگرام. ممکن است حجم فایل بیش از ۵۰ مگابایت باشد.")
    else:
        await query.edit_message_text("❌ <b>دانلود ناموفق بود!</b>\n<i>ممکن است لینک خصوصی باشد، سایت پشتیبانی نشود، یا حجم فایل بیش از ۵۰ مگابایت باشد.</i>", parse_mode=ParseMode.HTML)

# ==========================================
# 🎮 هندلرهای دکمه‌ها (Callbacks)
# ==========================================
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        text = (
            "📖 <b>راهنمای استفاده از ربات</b>\n\n"
            "1️⃣ لینک ویدیو (یوتیوب، اینستاگرام، تیک‌تاک) را کپی کنید.\n"
            "2️⃣ آن را در چت ربات پیست (Paste) کرده و ارسال کنید.\n"
            "3️⃣ نوع خروجی (ویدیو یا صدا) را انتخاب کنید.\n"
            "4️⃣ منتظر بمانید تا دانلود شود.\n\n"
            "⚠️ <b>نکته:</b> ویدیوهای تیک‌تاک به صورت خودکار بدون واترمارک دانلود می‌شوند."
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]]))
    
    elif query.data == "invite":
        link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start=ref_{query.from_user.id}"
        text = (
            "🎁 <b>سیستم دعوت دوستان</b>\n\n"
            "با دعوت دوستانت به ربات، به ازای هر نفر <b>۲ دانلود هدیه</b> بگیر!\n\n"
            f"🔗 <b>لینک اختصاصی شما:</b>\n<code>{link}</code>\n\n"
            "این لینک را برای دوستان خود بفرستید."
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]]))

    elif query.data == "settings":
        text = "⚙️ <b>تنظیمات</b>\n\nاین بخش به زودی با امکانات جدید (تغییر زبان و کیفیت) آپدیت می‌شود."
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]]))

async def back_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await start_command(update, context)

async def contact_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = 'waiting_for_admin_msg'
    text = (
        "📩 <b>ارسال پیام ناشناس</b>\n\n"
        "لطفاً پیام، انتقاد یا درخواست تبلیغ خود را در یک پیام بنویسید و ارسال کنید.\n\n"
        "⚠️ پیام شما بدون نمایش اطلاعات شما، مستقیماً برای مدیریت ارسال می‌شود."
    )
    keyboard = [[InlineKeyboardButton("🔙 انصراف", callback_data="back_start")]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    target_user = query.data.replace('reply_', '')
    context.user_data['state'] = f"reply_{target_user}"
    await query.edit_message_text("✍️ لطفاً پاسخ خود را بنویسید و ارسال کنید:")

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await is_member(update, context):
        await query.edit_message_text("✅ عالی! عضویت شما تایید شد. حالا لینک خود را بفرستید.")
    else:
        await query.answer("❌ شما هنوز عضو نشده‌اید!", show_alert=True)

# ==========================================
# 👑 پنل مدیریت (دستورات ادمین)
# ==========================================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    data = load_data()
    text = (
        "👑 <b>پنل مدیریت ربات</b>\n\n"
        f"👥 <b>تعداد کل کاربران:</b> {len(data['users'])}\n"
        f"📥 <b>تعداد کل دانلودها:</b> {data['total_downloads']}\n"
        f"🚫 <b>کاربران مسدود:</b> {len(data.get('banned_users', []))}\n\n"
        "دستورات مدیریتی:\n"
        "/ban [آیدی] - مسدود کردن کاربر\n"
        "/unban [آیدی] - آزاد کردن کاربر"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("روش استفاده: /ban 123456789")
        return
    user_to_ban = str(context.args[0])
    data = load_data()
    if "banned_users" not in data: data["banned_users"] = []
    if user_to_ban not in data["banned_users"]:
        data["banned_users"].append(user_to_ban)
        save_data(data)
        await update.message.reply_text(f"✅ کاربر {user_to_ban} مسدود شد.")
    else:
        await update.message.reply_text("این کاربر از قبل مسدود است.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("روش استفاده: /unban 123456789")
        return
    user_to_unban = str(context.args[0])
    data = load_data()
    if user_to_unban in data.get("banned_users", []):
        data["banned_users"].remove(user_to_unban)
        save_data(data)
        await update.message.reply_text(f"✅ کاربر {user_to_unban} آزاد شد.")
    else:
        await update.message.reply_text("این کاربر در لیست مسدودها نیست.")

# ==========================================
# 🚀 راه‌اندازی نهایی ربات
# ==========================================
def main():
    print("⏳ در حال روشن کردن ربات Vidora...")
    
    # فعال‌سازی وب‌سرور برای جلوگیری از خواب رندر
    keep_alive()
    
    if not TOKEN:
        print("❌ خطا: متغیر TOKEN در تنظیمات رندر یافت نشد!")
        return

    # ساخت اپلیکیشن
    app = Application.builder().token(TOKEN).build()

    # 1. اضافه کردن دستورات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    
    # 2. اضافه کردن هندلر پیام‌ها (لینک‌ها و پیام‌های ناشناس)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 3. اضافه کردن دکمه‌های شیشه‌ای (Callbacks)
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(help|invite|settings)$"))
    app.add_handler(CallbackQueryHandler(back_start_callback, pattern="back_start"))
    app.add_handler(CallbackQueryHandler(contact_admin_callback, pattern="contact_admin"))
    app.add_handler(CallbackQueryHandler(reply_callback, pattern="^reply_"))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="dl_"))

    print("✅ ربات با موفقیت روشن شد و آماده دریافت پیام‌هاست!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
