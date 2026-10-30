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

# ==============================================================================
# ⚙️ بخش ۱: تنظیمات اصلی، لاگ‌ها و متغیرهای محیطی (Configuration)
# ==============================================================================
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 7738720967
BOT_USERNAME = "@Vidora22DLBot"
DATA_FILE = "bot_data.json"

# کانال اصلی و پیش‌فرض شما
MAIN_CHANNEL = "@VidoraDownloadercl"
DAILY_LIMIT = 5

# تنظیم سیستم لاگ برای مشاهده خطاها در Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# اطمینان از وجود پوشه دانلود برای ذخیره موقت فایل‌ها
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# ==============================================================================
# 🗄️ بخش ۲: مدیریت دیتابیس (Database Management)
# ==============================================================================
def load_data():
    """
    بارگذاری اطلاعات کاربران، کانال‌ها، پیام‌ها و آمار از فایل JSON
    اگر فایل وجود نداشته باشد، مقادیر پیش‌فرض را برمی‌گرداند.
    """
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading database: {e}")
    
    # دیتابیس پیش‌فرض (فقط کانال خود شما در ابتدا)
    return {
        "users": {},
        "total_downloads": 0,
        "banned_users": [],
        "channels": [MAIN_CHANNEL], # لیست کانال‌های جوین اجباری
        "admin_messages": []
    }

def save_data(data):
    """
    ذخیره اطلاعات در فایل JSON
    """
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Error saving database: {e}")

def register_user(user_id):
    """
    ثبت کاربر جدید در دیتابیس همراه با تاریخ عضویت و تنظیمات اولیه
    """
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str not in data["users"]:
        data["users"][user_id_str] = {
            "joined_date": str(datetime.date.today()),
            "daily_downloads": 0,
            "last_download_date": str(datetime.date.today())
        }
        save_data(data)

def check_daily_limit(user_id):
    """
    بررسی محدودیت دانلود روزانه (DAILY_LIMIT)
    اگر روز عوض شده باشد، شمارنده را صفر می‌کند.
    """
    data = load_data()
    user_id_str = str(user_id)
    today = str(datetime.date.today())
    
    if user_id_str not in data["users"]:
        register_user(user_id)
        data = load_data()
    
    user = data["users"][user_id_str]
    
    # ریست کردن شمارنده دانلود در صورت تغییر روز
    if user.get("last_download_date") != today:
        user["daily_downloads"] = 0
        user["last_download_date"] = today
        save_data(data)
        
    if user["daily_downloads"] >= DAILY_LIMIT:
        return False
    return True

def increment_download(user_id):
    """
    افزایش تعداد دانلود کاربر و کل سیستم
    """
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str in data["users"]:
        data["users"][user_id_str]["daily_downloads"] += 1
        data["total_downloads"] += 1
        save_data(data)

# ==============================================================================
# 🔐 بخش ۳: سیستم عضویت اجباری (Force Join System)
# ==============================================================================
async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    بررسی می‌کند که آیا کاربر در تمام کانال‌های لیست شده عضو است یا خیر.
    لیست کانال‌ها از دیتابیس خوانده می‌شود تا ادمین بتواند کانال اضافه کند.
    """
    data = load_data()
    channels = data.get("channels", [])
    
    if not channels:
        return True # اگر هیچ کانالی تنظیم نشده بود، اجازه عبور بده

    user_id = update.effective_user.id
    
    for channel in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            # بررسی وضعیت کاربر در کانال
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            # اگر ربات در کانال ادمین نباشد، برای جلوگیری از کرش کردن، اجازه عبور می‌دهیم
            logger.warning(f"Bot is not admin in {channel} or channel invalid: {e}")
            continue
            
    return True

def get_join_keyboard():
    """
    ساخت دکمه‌های شیشه‌ای برای کانال‌های جوین اجباری
    این دکمه‌ها به صورت داینامیک از دیتابیس خوانده می‌شوند.
    """
    data = load_data()
    channels = data.get("channels", [])
    
    keyboard = []
    for channel in channels:
        channel_url = f"https://t.me/{channel.replace('@', '')}"
        keyboard.append([InlineKeyboardButton(f"📢 عضویت در {channel}", url=channel_url)])
    
    # دکمه تایید در پایین
    keyboard.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")])
    return InlineKeyboardMarkup(keyboard)

# ==============================================================================
# 🛠️ بخش ۴: موتورهای دانلود (Download Engines)
# ==============================================================================
def download_tiktok(url: str):
    """
    دانلود ویدیو از تیک‌تاک به صورت بدون واترمارک (با استفاده از API)
    """
    try:
        api_url = f"https://tikwm.com/api/?url={url}"
        response = requests.get(api_url, timeout=15).json()
        if response.get("code") == 0:
            video_data = response["data"]
            file_path = f"downloads/{video_data.get('id', 'tk')}.mp4"
            vid_res = requests.get(video_data.get("play"), timeout=20)
            with open(file_path, "wb") as f:
                f.write(vid_res.content)
            return file_path, video_data.get("title", "ویدیو تیک‌تاک")
        return None, None
    except Exception as e:
        logger.error(f"TikTok Error: {e}")
        return None, None

def download_ytdlp(url: str):
    """
    دانلود ویدیو از یوتیوب، اینستاگرام و... با استفاده از yt-dlp
    کیفیت بالا و حجم زیر ۵۰ مگابایت برای ارسال در تلگرام
    """
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'impersonate': 'chrome', # دور زدن محدودیت اینستاگرام
        'format': 'best[filesize<49M]/bestvideo[filesize<49M]+bestaudio/best',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            for ext in ['.mp4', '.mkv', '.webm']:
                if os.path.exists(base + ext):
                    return base + ext, info.get('title', 'ویدیو')
        return None, None
    except Exception as e:
        logger.error(f"YTDLP Error: {e}")
        return None, None

# ==============================================================================
# 🎨 بخش ۵: کیبوردها و ظاهر ربات (Keyboards & UI)
# ==============================================================================
def get_main_keyboard():
    """
    منوی اصلی کاربر
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 کانال ما", url=f"https://t.me/VidoraDownloadercl"), 
         InlineKeyboardButton("🎁 دعوت دوستان", callback_data="invite")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help"), 
         InlineKeyboardButton("📩 پیام به ادمین", callback_data="contact_admin")]
    ])

def get_admin_keyboard():
    """
    منوی مدیریت مخصوص ادمین
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats")],
        [InlineKeyboardButton("📥 صندوق پیام‌ها", callback_data="admin_inbox")],
        [InlineKeyboardButton("⚙️ مدیریت کانال‌ها", callback_data="admin_channels")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")]
    ])

# ==============================================================================
# 🎮 بخش ۶: هندلرهای کاربر (User Handlers)
# ==============================================================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دستور /start : بررسی مسدودی، بررسی عضویت و نمایش منو
    """
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # چک کردن مسدودی
    data = load_data()
    if str(user_id) in data.get("banned_users", []):
        await update.message.reply_text("⛔️ شما از استفاده از ربات محروم شده‌اید.")
        return

    # ۱. بررسی عضویت اجباری
    if not await check_membership(update, context):
        join_text = (
            f"سلام {user_name} عزیز 👋\n\n"
            "برای استفاده از ربات، ابتدا باید در کانال‌های ما عضو شوید.\n"
            "پس از عضویت، روی دکمه «✅ عضو شدم» کلیک کنید 👇"
        )
        await update.message.reply_text(
            join_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_join_keyboard()
        )
        return

    register_user(user_id)
    
    # ۲. نمایش منوی اصلی
    welcome_text = (
        f"سلام <b>{user_name}</b> عزیز 👋\n\n"
        "به ربات <b>دانلودر Vidora</b> خوش آمدی! 🚀\n\n"
        "🎯 <b>من می‌توانم:</b>\n"
        "✅ ویدیوهای یوتیوب و اینستاگرام را با کیفیت بالا دانلود کنم.\n"
        "✅ ویدیوهای تیک‌تاک را <b>بدون واترمارک</b> برایت بیاورم.\n\n"
        f"⚠️ <b>محدودیت روزانه:</b> شما می‌توانید روزانه {DAILY_LIMIT} ویدیو دانلود کنید.\n\n"
        "👇 <i>همین الان لینک خود را بفرستید!</i>"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    وقتی کاربر روی دکمه «عضو شدم» کلیک می‌کند، اینجا چک می‌شود.
    """
    query = update.callback_query
    await query.answer()
    
    if await check_membership(update, context):
        await query.message.delete()
        await start_command(update, context)
    else:
        await query.answer("❌ شما هنوز در تمام کانال‌ها عضو نشده‌اید!", show_alert=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    مدیریت تمام پیام‌های متنی دریافتی (لینک‌ها، پیام‌های ناشناس، و تنظیمات ادمین)
    """
    try:
        # جلوگیری از باگ‌های غیرمتنی (مثل استیکر یا عکس)
        if not update.message or not update.message.text:
            return

        user_id = update.effective_user.id
        state = context.user_data.get('state', '')
        
        # ==========================================
        # پردازش‌های مخصوص ادمین
        # ==========================================
        if user_id == ADMIN_ID:
            if state == 'waiting_for_broadcast':
                context.user_data['state'] = None
                data = load_data()
                success = 0
                await update.message.reply_text("⏳ در حال ارسال پیام همگانی...")
                for uid in data["users"].keys():
                    try:
                        await context.bot.send_message(chat_id=uid, text=update.message.text)
                        success += 1
                        await asyncio.sleep(0.05) # جلوگیری از بلاک شدن توسط تلگرام
                    except:
                        pass
                await update.message.reply_text(f"✅ پیام برای {success} کاربر ارسال شد.")
                return
                
            elif state == 'waiting_for_channel_add':
                context.user_data['state'] = None
                new_channel = update.message.text
                if not new_channel.startswith('@'):
                    new_channel = '@' + new_channel
                data = load_data()
                if new_channel not in data["channels"]:
                    data["channels"].append(new_channel)
                    save_data(data)
                    await update.message.reply_text(f"✅ کانال {new_channel} با موفقیت به لیست جوین اجباری اضافه شد.")
                else:
                    await update.message.reply_text("این کانال از قبل در لیست وجود دارد.")
                return

            elif state.startswith('reply_to_'):
                target_user = state.replace('reply_to_', '')
                context.user_data['state'] = None
                try:
                    await context.bot.send_message(chat_id=target_user, text=f"📬 <b>پاسخ ادمین:</b>\n\n{update.message.text}", parse_mode=ParseMode.HTML)
                    await update.message.reply_text("✅ پاسخ شما با موفقیت ارسال شد.")
                except:
                    await update.message.reply_text("❌ کاربر ربات را بلاک کرده است.")
                return

        # ==========================================
        # پردازش‌های کاربر عادی
        # ==========================================
        if state == 'waiting_for_admin_msg':
            context.user_data['state'] = None
            data = load_data()
            msg_id = len(data["admin_messages"]) + 1
            
            # ذخیره پیام در دیتابیس
            data["admin_messages"].append({
                "id": msg_id,
                "user_id": str(user_id),
                "text": update.message.text,
                "date": str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
            })
            save_data(data)
            
            # ارسال به ادمین
            admin_text = f"📩 <b>پیام ناشناس #{msg_id}</b>\n\n{update.message.text}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ پاسخ", callback_data=f"reply_{user_id}")]])
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=kb)
                await update.message.reply_text("✅ پیام شما با موفقیت به ادمین ارسال شد.")
            except:
                await update.message.reply_text("❌ خطا در ارسال پیام به ادمین.")
            return

        # اگر هیچ استیتی نداشت، یعنی دارد لینک می‌فرستد
        url = update.message.text
        if not url.startswith("http"):
            await update.message.reply_text("❌ لطفاً یک لینک معتبر بفرستید.")
            return

        # بررسی عضویت مجدد برای اطمینان
        if not await check_membership(update, context):
            await update.message.reply_text("⛔️ ابتدا باید در کانال‌ها عضو شوید.", reply_markup=get_join_keyboard())
            return
            
        # بررسی محدودیت روزانه
        if not check_daily_limit(user_id):
            await update.message.reply_text(f"⚠️ <b>محدودیت روزانه!</b>\nشما امروز {DAILY_LIMIT} ویدیو دانلود کرده‌اید. فردا دوباره تلاش کنید.", parse_mode=ParseMode.HTML)
            return

        # ذخیره لینک و نمایش دکمه دانلود
        context.user_data['url'] = url
        site = "تیک‌تاک (بدون واترمارک)" if "tiktok" in url else "اینستاگرام" if "instagram" in url else "یوتیوب" if "youtu" in url else "ویدیو"

        keyboard = [[InlineKeyboardButton("🎬 دانلود ویدیو (MP4)", callback_data="dl_video")]]
        await update.message.reply_text(f"✅ لینک <b>{site}</b> دریافت شد.\nبرای شروع پردازش کلیک کنید 👇", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Handler Error: {e}")

# ==============================================================================
# 📥 بخش ۷: پردازش دانلود (Download Logic)
# ==============================================================================
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    این تابع فایل را دانلود کرده و به کاربر ارسال می‌کند.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    url = context.user_data.get('url')
    
    if not url:
        await query.edit_message_text("❌ لینک منقضی شده است! لطفاً دوباره بفرستید.")
        return

    await query.edit_message_text("⏳ <b>در حال دانلود و پردازش...</b>\n<i>لطفاً شکیبا باشید.</i>", parse_mode=ParseMode.HTML)

    file_path, title = None, None

    # انتخاب روش دانلود
    if "tiktok.com" in url:
        file_path, title = await asyncio.to_thread(download_tiktok, url)
    
    if not file_path:
        file_path, title = await asyncio.to_thread(download_ytdlp, url)

    # اگر فایل دانلود شد
    if file_path:
        increment_download(user_id)
        
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
        await query.edit_message_text("❌ <b>دانلود ناموفق بود!</b>\n<i>لینک خصوصی است یا سایت پشتیبانی نمی‌شود.</i>", parse_mode=ParseMode.HTML)

# ==============================================================================
# 🎛️ بخش ۸: هندلرهای دکمه‌های منو (Menu Callbacks)
# ==============================================================================
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    مدیریت دکمه‌های راهنما و دعوت دوستان
    """
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        text = "📖 <b>راهنما:</b>\n\n1️⃣ لینک ویدیو را کپی کنید.\n2️⃣ آن را در چت ربات ارسال کنید.\n3️⃣ روی دکمه دانلود کلیک کنید.\n\n⚠️ روزانه ۵ دانلود مجاز است."
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]]))
    
    elif query.data == "invite":
        link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start=ref_{query.from_user.id}"
        await query.edit_message_text(f"🎁 <b>لینک اختصاصی شما:</b>\n\n<code>{link}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]]))

async def contact_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    فعال کردن حالت ارسال پیام ناشناس به ادمین
    """
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = 'waiting_for_admin_msg'
    keyboard = [[InlineKeyboardButton("🔙 انصراف", callback_data="back_start")]]
    await query.edit_message_text("📩 <b>ارسال پیام ناشناس</b>\n\nلطفاً پیام خود را بنویسید:", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def back_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    بازگشت به منوی اصلی
    """
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    await query.message.delete()
    await start_command(update, context)

# ==============================================================================
# 👑 بخش ۹: پنل مدیریت (Admin Panel)
# ==============================================================================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دستور /admin : فقط برای شما کار می‌کند.
    """
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("👑 <b>پنل مدیریت Vidora</b>\n\nیک گزینه را انتخاب کنید:", parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())

async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    مدیریت تمام دکمه‌های داخل پنل ادمین
    """
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    
    data = load_data()
    
    if query.data == "admin_stats":
        text = f"📊 <b>آمار ربات:</b>\n\n👥 کاربران: {len(data['users'])}\n📥 کل دانلودها: {data['total_downloads']}\n📢 تعداد کانال‌ها: {len(data['channels'])}"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
        
    elif query.data == "admin_inbox":
        msgs = data.get("admin_messages", [])
        if not msgs:
            await query.edit_message_text("📥 صندوق پیام خالی است.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
            return
        
        text = "📥 <b>آخرین پیام‌ها:</b>\n\n"
        for m in msgs[-5:]: # نمایش ۵ پیام آخر
            text += f"#{m['id']} | {m['date']}\n{m['text']}\n➖➖➖\n"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
        
    elif query.data == "admin_channels":
        text = "⚙️ <b>مدیریت کانال‌ها:</b>\n\n"
        for ch in data['channels']:
            text += f"- {ch}\n"
        text += "\nبرای اضافه کردن کانال جدید، روی دکمه زیر بزنید و آیدی (با @) را بفرستید."
        kb = [
            [InlineKeyboardButton("➕ افزودن کانال جدید", callback_data="admin_add_channel")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        
    elif query.data == "admin_add_channel":
        context.user_data['state'] = 'waiting_for_channel_add'
        await query.edit_message_text("لطفاً آیدی کانال جدید را با @ بفرستید (مثلاً @my_new_channel):")
        
    elif query.data == "admin_broadcast":
        context.user_data['state'] = 'waiting_for_broadcast'
        await query.edit_message_text("📢 لطفاً متن پیام همگانی را بفرستید:")
        
    elif query.data == "admin_back":
        await query.edit_message_text("👑 <b>پنل مدیریت Vidora</b>\n\nیک گزینه را انتخاب کنید:", parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())

async def reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    پاسخ دادن به پیام‌های ناشناس توسط ادمین
    """
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    target_user = query.data.replace('reply_', '')
    context.user_data['state'] = f'reply_to_{target_user}'
    await query.edit_message_text("✍️ لطفاً پاسخ خود را بنویسید:")

# ==============================================================================
# 🚀 بخش ۱۰: راه‌اندازی برنامه (Main App)
# ==============================================================================
def main():
    """
    تابع اصلی برای راه‌اندازی ربات و اضافه کردن هندلرها
    """
    print("⏳ در حال روشن کردن ربات...")
    keep_alive()
    
    app = Application.builder().token(TOKEN).build()

    # هندلرهای دستورات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    
    # هندلر پیام‌ها
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # هندلرهای دکمه‌ها
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="dl_video"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(help|invite)$"))
    app.add_handler(CallbackQueryHandler(back_start_callback, pattern="back_start"))
    app.add_handler(CallbackQueryHandler(contact_admin_callback, pattern="contact_admin"))
    app.add_handler(CallbackQueryHandler(reply_callback, pattern="^reply_"))
    
    # هندلرهای پنل ادمین
    app.add_handler(CallbackQueryHandler(admin_callbacks, pattern="^admin_"))

    print("✅ ربات نسخه Enterprise با موفقیت روشن شد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
