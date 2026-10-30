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
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

# ==========================================
# ⚙️ تنظیمات اصلی (Configuration)
# ==========================================
TOKEN = os.getenv("TOKEN")
CHANNEL_USERNAME = "@VidoraDownloadercl"
ADMIN_ID = 7738720967
BOT_USERNAME = "@Vidora22DLBot"

DATA_FILE = "bot_data.json"

# تنظیم لاگ‌ها برای دیباگ در رندر
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# ==========================================
# 🗄️ دیتابیس (Database Management)
# ==========================================
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    return {"users": [], "total_downloads": 0, "banned_users": []}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def register_user(user_id):
    data = load_data()
    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)

def is_banned(user_id):
    data = load_data()
    return user_id in data.get("banned_users", [])

# ==========================================
# 🛠️ موتورهای دانلود (Download Engines)
# ==========================================
def download_tiktok_no_watermark(url: str):
    """دانلود تیک‌تاک بدون واترمارک با استفاده از API قوی"""
    try:
        api_url = f"https://tikwm.com/api/?url={url}"
        response = requests.get(api_url, timeout=15).json()
        if response.get("code") == 0:
            video_data = response["data"]
            file_path = f"downloads/{video_data.get('id', 'tiktok_vid')}.mp4"
            vid_response = requests.get(video_data.get("play"), timeout=20)
            with open(file_path, "wb") as f:
                f.write(vid_response.content)
            return file_path, video_data.get("title", "TikTok Video")
        return None, None
    except Exception as e:
        logger.error(f"TikTok API Error: {e}")
        return None, None

def download_ytdlp(url: str):
    """دانلود ویدیو از یوتیوب، اینستاگرام و... با بالاترین کیفیت"""
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'impersonate': 'chrome',
        'format': 'best[filesize<49M]/bestvideo[filesize<49M]+bestaudio/best',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            for ext in ['.mp4', '.mkv', '.webm']:
                if os.path.exists(base + ext):
                    return base + ext, info.get('title', 'Unknown')
        return None, None
    except Exception as e:
        logger.error(f"YT-DLP Error: {e}")
        return None, None

# ==========================================
# 🔐 سیستم عضویت اجباری (Force Join)
# ==========================================
async def is_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=update.effective_user.id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Force Join Error (Is Bot Admin?): {e}")
        return True # برای جلوگیری از کرش شدن اگر ربات ادمین نبود

# ==========================================
# 🎨 کیبوردها (Keyboards)
# ==========================================
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 کانال ما", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"), 
         InlineKeyboardButton("🎁 دعوت دوستان", callback_data="invite")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help"), 
         InlineKeyboardButton("📩 پیام به ادمین", callback_data="contact_admin")]
    ])

def get_join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats"), 
         InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🚫 مسدود کردن", callback_data="admin_ban"), 
         InlineKeyboardButton("✅ رفع مسدودی", callback_data="admin_unban")]
    ])

# ==========================================
# 🎮 هندلرهای کاربر (User Handlers)
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await update.message.reply_text("⛔️ شما از استفاده از ربات مسدود شده‌اید.")
        return

    # بررسی عضویت
    if not await is_member(update, context):
        await update.message.reply_text(
            "⛔️ <b>دسترسی محدود!</b>\n\nبرای استفاده از ربات، ابتدا باید در کانال ما عضو شوی 👇", 
            parse_mode=ParseMode.HTML, 
            reply_markup=get_join_keyboard()
        )
        return

    register_user(user_id)
    
    welcome_text = (
        f"سلام <b>{update.effective_user.first_name}</b> عزیز 👋\n\n"
        "به ربات <b>دانلودر فوق‌حرفه‌ای Vidora</b> خوش آمدی! 🚀\n\n"
        "🎯 <b>من اینجا هستم تا:</b>\n"
        "✅ ویدیوهای یوتیوب و اینستاگرام را با بالاترین کیفیت دانلود کنم.\n"
        "✅ ویدیوهای تیک‌تاک را <b>بدون واترمارک</b> تحویلت بدم.\n\n"
        "👇 <i>فقط کافیه لینکت رو بفرستی!</i>"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return

        user_id = update.effective_user.id
        
        if is_banned(user_id):
            return

        # سیستم پیام ناشناس
        if context.user_data.get('state') == 'waiting_for_admin_msg':
            user_msg = update.message.text
            admin_text = f"📩 <b>پیام ناشناس جدید:</b>\n\n<i>{user_msg}</i>\n\n👤 برای پاسخ کلیک کنید:"
            reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ پاسخ", callback_data=f"reply_{user_id}")]])
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML, reply_markup=reply_kb)
                await update.message.reply_text("✅ پیام شما به صورت ناشناس ارسال شد.")
            except:
                await update.message.reply_text("❌ خطا در ارسال.")
            context.user_data['state'] = None
            return

        # پاسخ ادمین
        if user_id == ADMIN_ID and context.user_data.get('state', '').startswith('reply_'):
            target = context.user_data['state'].replace('reply_', '')
            try:
                await context.bot.send_message(chat_id=target, text=f"📬 <b>پاسخ مدیریت:</b>\n\n<i>{update.message.text}</i>", parse_mode=ParseMode.HTML)
                await update.message.reply_text("✅ پاسخ ارسال شد.")
            except:
                await update.message.reply_text("❌ کاربر بلاک کرده.")
            context.user_data['state'] = None
            return

        url = update.message.text
        if not url.startswith("http"):
            await update.message.reply_text("❌ <b>لینک نامعتبر!</b>\nلطفاً یک لینک معتبر بفرست.", parse_mode=ParseMode.HTML)
            return

        # بررسی مجدد عضویت قبل از دانلود
        if not await is_member(update, context):
            await update.message.reply_text("⛔️ ابتدا در کانال عضو شوید.", reply_markup=get_join_keyboard())
            return

        context.user_data['url'] = url
        site = "تیک‌تاک (بدون واترمارک)" if "tiktok.com" in url else "اینستاگرام" if "instagram.com" in url else "یوتیوب" if "youtu" in url else "ویدیو"

        keyboard = [[InlineKeyboardButton("🎬 دانلود ویدیو (MP4)", callback_data="dl_video")]]
        await update.message.reply_text(f"✅ لینک <b>{site}</b> دریافت شد.\nبرای شروع دانلود کلیک کن 👇", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Message Handler Error: {e}")

# ==========================================
# 📥 پردازش دانلود (Download Callback)
# ==========================================
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    url = context.user_data.get('url')
    if not url:
        await query.edit_message_text("❌ لینک منقضی شده است! لطفاً دوباره بفرستید.")
        return

    await query.edit_message_text("⏳ <b>در حال پردازش و دانلود...</b>\n<i>لطفاً صبر کنید، ممکن است کمی طول بکشد.</i>", parse_mode=ParseMode.HTML)

    file_path, title = None, None

    if "tiktok.com" in url:
        file_path, title = await asyncio.to_thread(download_tiktok_no_watermark, url)
    
    if not file_path:
        file_path, title = await asyncio.to_thread(download_ytdlp, url)

    if file_path:
        # آپدیت آمار
        data = load_data()
        data["total_downloads"] += 1
        save_data(data)

        caption = (
            f"🎉 <b>دانلود با موفقیت انجام شد!</b>\n\n"
            f"🎬 <b>عنوان:</b> <i>{str(title)[:50]}...</i>\n\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            "📢 <b>تبلیغات حامی:</b>\n"
            "🔗 <a href='https://t.me/VidoraDownloadercl'>کانال ما رو دنبال کنید!</a>\n"
            "➖➖➖➖➖➖➖➖➖➖\n\n"
            f"🤖 {BOT_USERNAME}"
        )
        try:
            await query.message.reply_video(video=open(file_path, 'rb'), caption=caption, parse_mode=ParseMode.HTML, supports_streaming=True)
            await query.message.delete()
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Upload Error: {e}")
            await query.edit_message_text("❌ خطا در ارسال فایل. ممکن است حجم ویدیو بیش از ۵۰ مگابایت باشد.")
    else:
        await query.edit_message_text("❌ <b>دانلود ناموفق بود!</b>\n<i>ممکن است لینک خصوصی باشد یا سایت پشتیبانی نشود.</i>", parse_mode=ParseMode.HTML)

# ==========================================
# 🎛️ هندلرهای دکمه‌ها (Callbacks)
# ==========================================
async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await is_member(update, context):
        await query.message.delete()
        await start_command(update, context)
    else:
        await query.answer("❌ شما هنوز عضو کانال نشده‌اید!", show_alert=True)

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        text = "📖 <b>راهنما:</b>\n\n1️⃣ لینک ویدیو (یوتیوب، اینستاگرام، تیک‌تاک) را کپی کنید.\n2️⃣ آن را در چت ربات ارسال کنید.\n3️⃣ روی دکمه دانلود کلیک کنید."
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]]))
    elif query.data == "invite":
        link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start=ref_{query.from_user.id}"
        await query.edit_message_text(f"🎁 <b>لینک اختصاصی دعوت شما:</b>\n\n<code>{link}</code>\n\nاین لینک را برای دوستان خود بفرستید.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]]))

async def contact_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = 'waiting_for_admin_msg'
    keyboard = [[InlineKeyboardButton("🔙 انصراف", callback_data="back_start")]]
    await query.edit_message_text("📩 <b>ارسال پیام ناشناس</b>\n\nلطفاً پیام خود را بنویسید. اطلاعات شما محرمانه می‌ماند.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    target_user = query.data.replace('reply_', '')
    context.user_data['state'] = f"reply_{target_user}"
    await query.edit_message_text("✍️ لطفاً پاسخ خود را بنویسید و ارسال کنید:")

async def back_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await start_command(update, context)

# ==========================================
# 👑 پنل ادمین (Admin Panel)
# ==========================================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("👑 <b>به پنل مدیریت خوش آمدید.</b>\nیک گزینه را انتخاب کنید:", parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    
    data = load_data()
    
    if query.data == "admin_stats":
        text = f"📊 <b>آمار ربات:</b>\n\n👥 کاربران: {len(data['users'])}\n📥 دانلودها: {data['total_downloads']}\n🚫 مسدودها: {len(data.get('banned_users', []))}"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
    elif query.data == "admin_back":
        await query.edit_message_text("👑 <b>پنل مدیریت:</b>\nیک گزینه را انتخاب کنید:", parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())

# ==========================================
# 🚀 اجرای نهایی
# ==========================================
def main():
    print("⏳ ربات در حال روشن شدن...")
    keep_alive()
    
    app = Application.builder().token(TOKEN).build()

    # دستورات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    
    # پیام‌ها
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # دکمه‌ها
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="dl_video"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(help|invite)$"))
    app.add_handler(CallbackQueryHandler(back_start_callback, pattern="back_start"))
    app.add_handler(CallbackQueryHandler(contact_admin_callback, pattern="contact_admin"))
    app.add_handler(CallbackQueryHandler(reply_callback, pattern="^reply_"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))

    print("✅ ربات با موفقیت روشن شد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
