 import os
import random
import sqlite3
import time
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================
# تنظیمات
# =========================

TOKEN=("8610448625:AAFUbF1bEl-o-DPvmJGyQOR9VwwbBEpXyMA")

DB = "labubu.db"

OPEN_COOLDOWN = 120  # دو دقیقه

RARITIES = {
    "common": ("Common", 21),
    "uncommon": ("Uncommon", 15),
    "rare": ("Rare", 12),
    "epic": ("Epic", 10),
    "legendary": ("Legendary", 8),
    "ultra_rare": ("Ultra-Rare", 4),
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# =========================
# دیتابیس
# =========================

def db():
    return sqlite3.connect(DB)


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            money INTEGER DEFAULT 1000000
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS collection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            labubu_name TEXT,
            rarity TEXT,
            image_path TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_cooldown (
            chat_id INTEGER PRIMARY KEY,
            last_open INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def add_user(user):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO users
        (user_id, username, money)
        VALUES (?, ?, 1000000)
        """,
        (user.id, user.username or "")
    )

    conn.commit()
    conn.close()


# =========================
# پیدا کردن عکس‌ها
# =========================

def get_images():
    result = {}

    for folder in RARITIES:
        path = Path("images") / folder

        if not path.exists():
            result[folder] = []
            continue

        files = [
            str(x)
            for x in path.iterdir()
            if x.is_file() and x.suffix.lower() in IMAGE_EXTENSIONS
        ]

        result[folder] = files

    return result


def choose_rarity():
    # تعدادهای تعیین‌شده برای هر رده
    choices = []

    for rarity, (_, count) in RARITIES.items():
        choices.extend([rarity] * count)

    return random.choice(choices)


# =========================
# منو
# =========================

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "🐰 باز کردن لبوبو",
                callback_data="open"
            ),
            InlineKeyboardButton(
                "📖 راهنما",
                callback_data="guide"
            )
        ],
        [
            InlineKeyboardButton(
                "🎒 مجموعه من",
                callback_data="collection"
            )
        ],
        [
            InlineKeyboardButton(
                "🏆 برترین‌ها",
                callback_data="top"
            )
        ],
        [
            InlineKeyboardButton(
                "🛒 فروشگاه",
                callback_data="shop"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# /start
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user)

    await update.message.reply_text(
        "🐰 به دنیای Labubu خوش اومدی!\n\n"
        "💰 موجودی شروع: $1,000,000\n\n"
        "از منوی زیر شروع کن 👇",
        reply_markup=main_menu()
    )


# =========================
# باز کردن لبوبو
# =========================

async def open_labubu(query):
    chat_id = query.message.chat_id
    now = int(time.time())

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT last_open FROM chat_cooldown WHERE chat_id = ?",
        (chat_id,)
    )

    row = cur.fetchone()
    last_open = row[0] if row else 0

    remaining = OPEN_COOLDOWN - (now - last_open)

    if remaining > 0:
        minutes = remaining // 60
        seconds = remaining % 60

        await query.message.reply_text(
            f"⏳ هنوز زوده!\n\n"
            f"تا باز کردن لبوبوی بعدی:\n"
            f"**{minutes} دقیقه و {seconds} ثانیه**",
            parse_mode="Markdown"
        )

        conn.close()
        return

    images = get_images()

    available = [
        rarity
        for rarity, files in images.items()
        if files
    ]

    if not available:
        await query.message.reply_text(
            "❌ هنوز هیچ عکس لبوبویی داخل پوشه‌های images پیدا نکردم."
        )
        conn.close()
        return

    rarity = choose_rarity()

    # اگر آن رده هنوز عکس نداشت، از رده‌های موجود استفاده کن
    if not images.get(rarity):
        rarity = random.choice(available)

    image_path = random.choice(images[rarity])

    rarity_name = RARITIES[rarity][0]

    # نام لبوبو از اسم فایل
    labubu_name = Path(image_path).stem

    user = query.from_user
    add_user(user)

    cur.execute(
        """
        INSERT INTO collection
        (user_id, labubu_name, rarity, image_path)
        VALUES (?, ?, ?, ?)
        """,
        (
            user.id,
            labubu_name,
            rarity_name,
            image_path
        )
    )

    cur.execute(
        """
        INSERT OR REPLACE INTO chat_cooldown
        (chat_id, last_open)
        VALUES (?, ?)
        """,
        (chat_id, now)
    )

    conn.commit()
    conn.close()

    caption = (
        "🎉 لبوبو جدید پیدا کردی!\n\n"
        f"🧸 {labubu_name}\n"
        f"✨ Rarity: {rarity_name}\n\n"
        "🎒 به مجموعه‌ات اضافه شد!"
    )

    try:
        with open(image_path, "rb") as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=caption
            )
    except Exception:
        await query.message.reply_text(caption)


# =========================
# مجموعه
# =========================

async def show_collection(query):
    user_id = query.from_user.id

    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT labubu_name, rarity
        FROM collection
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    )

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await query.message.reply_text(
            "🎒 مجموعه‌ات هنوز خالیه!\n"
            "🐰 اولین لبوبوت رو باز کن."
        )
        return

    text = "🎒 **مجموعه من**\n\n"

    for i, (name, rarity) in enumerate(rows, 1):
        text += f"{i}. 🧸 {name} — {rarity}\n"

    await query.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================
# برترین‌ها
# =========================

async def show_top(query):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            users.username,
            COUNT(collection.id) AS total
        FROM users
        LEFT JOIN collection
        ON users.user_id = collection.user_id
        GROUP BY users.user_id
        ORDER BY total DESC
        LIMIT 10
    """)

    rows = cur.fetchall()
    conn.close()

    text = "🏆 **برترین مجموعه‌ها**\n\n"

    for i, (username, total) in enumerate(rows, 1):
        name = f"@{username}" if username else "بدون نام کاربری"
        text += f"{i}. {name} — {total} لبوبو\n"

    await query.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================
# راهنما
# =========================

async def show_guide(query):
    await query.message.reply_text(
        "📖 **راهنمای Labubu World**\n\n"
        "🐰 با دکمه باز کردن لبوبو، یک لبوبو دریافت می‌کنی.\n\n"
        "⏳ زمان باز کردن: هر ۲ دقیقه\n\n"
        "🎒 مجموعه من: لبوبوهای خودت\n\n"
        "🏆 برترین‌ها: بازیکنان با بیشترین لبوبو\n\n"
        "🧸 رده‌ها:\n"
        "Common\n"
        "Uncommon\n"
        "Rare\n"
        "Epic\n"
        "Legendary\n"
        "Ultra-Rare",
        parse_mode="Markdown"
    )


# =========================
# فروشگاه
# =========================

async def show_shop(query):
    await query.message.reply_text(
        "🛒 **فروشگاه Labubu**\n\n"
        "سیستم خرید و فروش لبوبو در مرحله بعد به فروشگاه اضافه می‌شود. 🔥",
        parse_mode="Markdown"
    )


# =========================
# دکمه‌ها
# =========================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    add_user(user)

    if query.data == "open":
        await open_labubu(query)

    elif query.data == "guide":
        await show_guide(query)

    elif query.data == "collection":
        await show_collection(query)

    elif query.data == "top":
        await show_top(query)

    elif query.data == "shop":
        await show_shop(query)


# =========================
# اجرای بات
# =========================

def run():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN تنظیم نشده است."
        )

    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CallbackQueryHandler(button)
    )

    print("Labubu Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    run()
